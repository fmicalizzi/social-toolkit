"""Scraper de metadata de videos individuales de YouTube usando yt-dlp."""

import json
import subprocess
import re
from typing import Optional

from platforms.youtube.models import YouTubeVideo
from shared.utils import timestamp_iso


def scrape_video(video_id: str, config: dict) -> Optional[dict]:
    """Extrae metadata completa de un video de YouTube con yt-dlp --dump-json.

    Returns:
        dict con campos de YouTubeVideo, o None si falla.
    """
    ytdlp = config["downloads"]["ytdlp_binary"]
    url = f"https://www.youtube.com/watch?v={video_id}"

    cmd = [
        ytdlp,
        "--dump-json",
        "--no-download",
        "--no-warnings",
        "--quiet",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  [err] {video_id}: timeout")
        return None

    if result.returncode != 0:
        err = (result.stderr or "").strip()[:100]
        print(f"  [err] {video_id}: {err}")
        return None

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  [err] {video_id}: JSON invalido")
        return None

    # Parsear fecha: yt-dlp da upload_date como "20230315"
    upload_date = info.get("upload_date", "")
    if len(upload_date) == 8:
        date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        date = upload_date

    # Extraer hashtags del titulo y descripcion
    description = info.get("description", "") or ""
    title = info.get("title", "") or ""
    hashtags = re.findall(r'#(\w+)', f"{title} {description}")

    # Content type
    duration = info.get("duration")
    content_type = "short" if duration and duration < 62 else "video"

    video = YouTubeVideo(
        video_id=video_id,
        url=info.get("webpage_url", url),
        username=info.get("channel", info.get("uploader", "")),
        full_name=info.get("channel", ""),
        date=date,
        content_type=content_type,
        is_video=True,
        likes=info.get("like_count"),
        comments=info.get("comment_count"),
        views=info.get("view_count"),
        duration_sec=duration,
        hashtags=", ".join(hashtags[:15]),
        caption=f"{title}. {description}"[:500].replace("\n", " "),
        scraped_at=timestamp_iso(),
    )

    return video.to_csv_row()
