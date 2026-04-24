"""Scraper de perfiles de TikTok: usa yt-dlp para discovery de videos."""

import json
import subprocess
import re
import time
import random
from pathlib import Path
from playwright.sync_api import Page

from platforms.tiktok.models import TikTokProfile, DiscoveredVideo
from shared.output import save_json


def scrape_profile(page: Page, username: str, config: dict,
                   max_videos: int = 0,
                   save_progress: Path = None) -> tuple[TikTokProfile, list[DiscoveredVideo]]:
    """Navega al perfil de TikTok, extrae info y descubre videos.

    Usa Playwright para el header del perfil y yt-dlp para listar videos.
    """
    url = f"https://www.tiktok.com/@{username}"
    print(f"Navegando a {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(3, 5))

    # Extraer info del perfil desde el DOM
    profile = _extract_profile_header(page, username)
    print(f"Perfil: @{username} | {profile.full_name}")
    print(f"  Videos: {profile.video_count} | Followers: {profile.followers:,} | Likes: {profile.likes:,}")

    # Usar yt-dlp para listar videos (mas confiable que scroll)
    print(f"\nDescubriendo videos con yt-dlp...")
    videos = _discover_with_ytdlp(username, config, max_videos)

    if not videos:
        # Fallback: scroll del perfil
        print("  yt-dlp no encontro videos, intentando scroll...")
        videos = _scroll_and_collect(page, username, max_videos, config)

    if save_progress and videos:
        _save_discovered(save_progress, videos)

    print(f"\nDescubiertos: {len(videos)} videos")
    return profile, videos


def _extract_profile_header(page: Page, username: str) -> TikTokProfile:
    """Extrae datos del header del perfil de TikTok desde el DOM."""
    info = page.evaluate("""() => {
        const getText = (sel) => {
            const el = document.querySelector(sel);
            return el ? el.textContent.trim() : '';
        };

        // TikTok usa data-e2e attributes para sus elementos
        return {
            name: getText('[data-e2e="user-subtitle"]') || getText('h1') || '',
            bio: getText('[data-e2e="user-bio"]') || '',
            followers: getText('[data-e2e="followers-count"]') || '0',
            following: getText('[data-e2e="following-count"]') || '0',
            likes: getText('[data-e2e="likes-count"]') || '0',
            videoCount: getText('[data-e2e="video-count"]') || '0',
        };
    }""")

    return TikTokProfile(
        username=username,
        full_name=info.get("name", ""),
        bio=info.get("bio", "")[:500],
        followers=_parse_tiktok_count(info.get("followers", "0")),
        following=_parse_tiktok_count(info.get("following", "0")),
        likes=_parse_tiktok_count(info.get("likes", "0")),
        video_count=_parse_tiktok_count(info.get("videoCount", "0")),
        url=f"https://www.tiktok.com/@{username}",
    )


def _parse_tiktok_count(text: str) -> int:
    """Parsea contadores de TikTok: '1.2M', '45.6K', '1234'."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    multiplier = 1
    if text.upper().endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.upper().endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def _discover_with_ytdlp(username: str, config: dict,
                         max_videos: int = 0) -> list[DiscoveredVideo]:
    """Usa yt-dlp --flat-playlist para listar videos de un perfil TikTok."""
    ytdlp = config["downloads"]["ytdlp_binary"]
    url = f"https://www.tiktok.com/@{username}"

    cmd = [
        ytdlp,
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--quiet",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("  Timeout al listar videos (120s)")
        return []

    if result.returncode != 0:
        return []

    videos = []
    seen = set()
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        video_id = str(entry.get("id", ""))
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)

        videos.append(DiscoveredVideo(
            video_id=video_id,
            url=entry.get("url", f"https://www.tiktok.com/@{username}/video/{video_id}"),
            title=entry.get("title", ""),
        ))

    if max_videos > 0 and len(videos) > max_videos:
        videos = videos[:max_videos]

    return videos


def _scroll_and_collect(page: Page, username: str,
                        max_videos: int, config: dict) -> list[DiscoveredVideo]:
    """Fallback: scroll del perfil para descubrir videos."""
    collected = {}
    no_new_count = 0
    scroll_delay = config.get("rate_limits", {}).get("tiktok", {}).get("scroll_delay", [1.5, 3.0])

    for scroll_num in range(1, 200):
        links = page.evaluate("""() => {
            const results = [];
            const seen = new Set();
            const links = document.querySelectorAll('a[href*="/video/"]');
            for (const a of links) {
                const href = a.getAttribute('href');
                const match = href.match(/video\\/(\\d+)/);
                if (!match) continue;
                const id = match[1];
                if (seen.has(id)) continue;
                seen.add(id);
                results.push({ video_id: id, url: href });
            }
            return results;
        }""")

        prev_count = len(collected)
        for link in links:
            vid = link["video_id"]
            if vid not in collected:
                url = link["url"]
                if not url.startswith("http"):
                    url = f"https://www.tiktok.com{url}"
                collected[vid] = DiscoveredVideo(video_id=vid, url=url)

        new_found = len(collected) - prev_count
        target_str = str(max_videos) if max_videos > 0 else "?"
        print(f"  Scroll #{scroll_num}: {len(collected)}/{target_str} videos (+{new_found})", end="\r", flush=True)

        if max_videos > 0 and len(collected) >= max_videos:
            print(f"\n  Target alcanzado ({max_videos} videos)")
            break

        if new_found == 0:
            no_new_count += 1
            if no_new_count >= 8:
                print(f"\n  Sin videos nuevos en 8 scrolls. Fin.")
                break
        else:
            no_new_count = 0

        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(random.uniform(scroll_delay[0], scroll_delay[1]))

    videos = list(collected.values())
    if max_videos > 0:
        videos = videos[:max_videos]
    return videos


def _save_discovered(path: Path, videos: list[DiscoveredVideo]):
    data = [{"video_id": v.video_id, "url": v.url, "title": v.title} for v in videos]
    save_json(path, data)


def load_discovered(path: Path) -> list[DiscoveredVideo]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [DiscoveredVideo(**d) for d in data]
