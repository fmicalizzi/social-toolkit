"""yt-dlp wrapper con cookies, rate limiting e idempotencia."""

import subprocess
import time
import random
from pathlib import Path

from shared.rate_limiter import rate_limit
from shared.utils import sanitize


def already_downloaded(output_dir: Path, shortcode: str) -> bool:
    """Verifica si ya hay un video descargado para este shortcode."""
    for f in output_dir.rglob(f"*{shortcode}*"):
        if f.suffix in (".mp4", ".mkv", ".webm"):
            return True
    return False


def download_video(url: str, shortcode: str, output_dir: Path,
                   config: dict, username: str = "unknown") -> tuple[bool, str]:
    """Descarga un video con yt-dlp. Retorna (success, error_msg)."""
    account_dir = output_dir / f"@{sanitize(username)}"
    account_dir.mkdir(parents=True, exist_ok=True)

    out_template = str(account_dir / f"%(upload_date)s_{shortcode}.%(ext)s")

    ytdlp = config["downloads"]["ytdlp_binary"]
    cookies = config["downloads"]["cookies_file"]

    cmd = [
        ytdlp,
        "--cookies", cookies,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--output", out_template,
        "--quiet",
        "--no-warnings",
        "--write-info-json",
        "--no-embed-metadata",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, ""
        else:
            err = (result.stderr or result.stdout or "").strip()[-200:]
            return False, err
    except subprocess.TimeoutExpired:
        return False, "timeout (120s)"


def download_all(posts: list[dict], output_dir: Path, config: dict) -> dict:
    """Descarga todos los videos con rate limiting.

    posts: lista de dicts con al menos 'shortcode', 'url', 'username'.
    Retorna stats: {ok, skipped, failed, errors}.
    """
    ok, skipped, failed, errors = 0, 0, 0, []

    for i, post in enumerate(posts, 1):
        sc = post["shortcode"]
        url = post.get("url", f"https://www.instagram.com/p/{sc}/")
        username = post.get("username", "unknown")

        print(f"[{i}/{len(posts)}] @{username[:30]} | {sc}", end=" ", flush=True)

        if already_downloaded(output_dir, sc):
            print("-> ya existe")
            skipped += 1
            continue

        success, err = download_video(url, sc, output_dir, config, username)

        if success:
            print("-> ok")
            ok += 1
        else:
            print(f"-> error: {err[:80]}")
            failed += 1
            errors.append({"shortcode": sc, "url": url, "error": err})

        rate_limit(config, "instagram", "download_delay")

    print(f"\nDescargados: {ok} | Ya existian: {skipped} | Fallidos: {failed}")
    return {"ok": ok, "skipped": skipped, "failed": failed, "errors": errors}
