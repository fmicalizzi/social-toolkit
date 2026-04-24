"""Scraper de canales de YouTube usando yt-dlp para discovery."""

import json
import subprocess
from pathlib import Path

from platforms.youtube.models import ChannelInfo, DiscoveredVideo
from shared.output import save_json


def scrape_channel(channel_url: str, config: dict,
                   max_videos: int = 0,
                   save_progress: Path = None) -> tuple[ChannelInfo, list[DiscoveredVideo]]:
    """Descubre todos los videos de un canal usando yt-dlp --flat-playlist.

    Args:
        channel_url: URL del canal (https://www.youtube.com/@handle/videos)
        config: Config dict global
        max_videos: Limitar a N videos (0 = todos)
        save_progress: Path para guardar video IDs incrementalmente

    Returns:
        (ChannelInfo, lista de DiscoveredVideo)
    """
    ytdlp = config["downloads"]["ytdlp_binary"]

    # Asegurar que la URL apunta a /videos
    if not channel_url.rstrip("/").endswith("/videos"):
        channel_url = channel_url.rstrip("/") + "/videos"

    print(f"Descubriendo videos de {channel_url}")

    cmd = [
        ytdlp,
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--quiet",
        channel_url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("  Timeout al listar videos del canal (120s)")
        return ChannelInfo(channel_id=""), []

    if result.returncode != 0:
        err = (result.stderr or "").strip()[:200]
        print(f"  Error listando canal: {err}")
        return ChannelInfo(channel_id=""), []

    # Parsear cada linea como JSON (una por video)
    videos = []
    channel_info = None
    seen = set()

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        video_id = entry.get("id", "")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)

        # Extraer info del canal del primer video
        if channel_info is None:
            channel_info = ChannelInfo(
                channel_id=entry.get("channel_id", ""),
                handle=entry.get("channel", entry.get("uploader", "")),
                title=entry.get("channel", entry.get("uploader", "")),
                url=entry.get("channel_url", channel_url),
            )

        videos.append(DiscoveredVideo(
            video_id=video_id,
            url=entry.get("url", f"https://www.youtube.com/watch?v={video_id}"),
            title=entry.get("title", ""),
        ))

    if channel_info is None:
        channel_info = ChannelInfo(channel_id="unknown")

    print(f"  Canal: {channel_info.title}")
    print(f"  Videos encontrados: {len(videos)}")

    # Limitar al target
    if max_videos > 0 and len(videos) > max_videos:
        videos = videos[:max_videos]
        print(f"  Limitado a: {max_videos} videos")

    # Guardar progreso
    if save_progress:
        _save_discovered(save_progress, videos)

    return channel_info, videos


def _save_discovered(path: Path, videos: list[DiscoveredVideo]):
    data = [{"video_id": v.video_id, "url": v.url, "title": v.title} for v in videos]
    save_json(path, data)


def load_discovered(path: Path) -> list[DiscoveredVideo]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [DiscoveredVideo(**d) for d in data]
