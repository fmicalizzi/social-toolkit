"""Scraper de metadata de videos individuales de TikTok usando yt-dlp."""

import json
import subprocess
import re
from typing import Optional

from platforms.tiktok.models import TikTokVideo
from shared.utils import timestamp_iso


def scrape_video(video_id: str, username: str, config: dict) -> Optional[dict]:
    """Extrae metadata completa de un video de TikTok con yt-dlp.

    Returns:
        dict con campos de TikTokVideo, o None si falla.
    """
    ytdlp = config["downloads"]["ytdlp_binary"]
    url = f"https://www.tiktok.com/@{username}/video/{video_id}"

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

    # Fecha
    upload_date = info.get("upload_date", "") or ""
    if len(upload_date) == 8:
        date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        date = upload_date

    # Caption y hashtags
    description = info.get("description", "") or info.get("title", "") or ""
    hashtags = re.findall(r'#(\w+)', description)

    video = TikTokVideo(
        video_id=video_id,
        url=info.get("webpage_url", url),
        username=info.get("uploader", info.get("creator", username)),
        full_name=info.get("uploader", ""),
        date=date,
        content_type="video",
        is_video=True,
        likes=info.get("like_count"),
        comments=info.get("comment_count"),
        views=info.get("view_count"),
        shares=info.get("repost_count") or info.get("share_count"),
        duration_sec=info.get("duration"),
        hashtags=", ".join(hashtags[:15]),
        caption=description[:500].replace("\n", " "),
        scraped_at=timestamp_iso(),
    )

    return video.to_csv_row()
