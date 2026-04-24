"""Orquestador de snapshot completo de un perfil de TikTok.

Pipeline: discover -> metadata -> CSV -> download -> convert
"""

from pathlib import Path

from shared.browser import BrowserContext, ensure_logged_in
from shared.converter import convert_all
from shared.output import save_json, load_all_metadata, write_csv, STANDARD_FIELDS
from shared.rate_limiter import rate_limit, rate_limit_batch
from shared.utils import today, normalize_username

from platforms.tiktok.profile_scraper import scrape_profile, load_discovered
from platforms.tiktok.video_scraper import scrape_video


def run_snapshot(username: str, config: dict,
                 no_download: bool = False,
                 no_convert: bool = False,
                 max_videos: int = 0):
    """Pipeline completo de snapshot para un perfil de TikTok."""
    username = normalize_username(username)

    output_dir = Path(config["output"]["base_dir"]) / "tiktok" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "discovered.json"

    print("=" * 60)
    print(f"  SNAPSHOT TIKTOK: @{username}")
    print("=" * 60)

    # === FASE 1: Discovery (skip si ya existe) ===
    existing = load_discovered(progress_file)
    if existing:
        videos = existing
        print(f"\nUsando discovery existente: {len(videos)} videos en {progress_file}")
    else:
        with BrowserContext(config) as (ctx, page):
            profile, videos = scrape_profile(
                page, username, config,
                max_videos=max_videos,
                save_progress=progress_file,
            )
        save_json(output_dir / "profile.json", profile.to_dict())
        print(f"\nPerfil guardado: {output_dir / 'profile.json'}")

    if not videos:
        print("No hay videos para scrapear.")
        return

    # === FASE 2: Metadata (via yt-dlp, no necesita browser) ===
    print(f"\n{'=' * 60}")
    print(f"  SCRAPING METADATA: {len(videos)} videos")
    print(f"{'=' * 60}\n")

    already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
    pending = [v for v in videos if v.video_id not in already_scraped]
    print(f"Ya scrapeados: {len(already_scraped)} | Pendientes: {len(pending)}\n")

    ok, failed = 0, []
    for i, video in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {video.video_id}", end=" ", flush=True)

        meta = scrape_video(video.video_id, username, config)

        if meta:
            save_json(metadata_dir / f"{video.video_id}.json", meta)
            views_str = f"V:{meta.get('views', '?'):,}" if meta.get("views") else ""
            print(f"-> {meta.get('date', '?')} {views_str}")
            ok += 1
        else:
            print("-> sin metadata")
            failed.append(video.video_id)

        rate_limit(config, "tiktok", "scrape_delay")
        rate_limit_batch(config, "tiktok", i)

    print(f"\nScrapeados: {ok} | Fallidos: {len(failed)}")

    # === FASE 3: CSV ===
    print(f"\n{'=' * 60}")
    print(f"  GENERANDO SNAPSHOT CSV")
    print(f"{'=' * 60}\n")

    all_metadata = load_all_metadata(metadata_dir)
    all_metadata.sort(key=lambda r: (r.get("date", ""), r.get("shortcode", "")))

    csv_path = output_dir / f"snapshot_{today()}.csv"
    write_csv(csv_path, all_metadata, STANDARD_FIELDS)

    total_views = sum(r.get("views") or 0 for r in all_metadata)
    total_likes = sum(r.get("likes") or 0 for r in all_metadata)
    total_shares = sum(r.get("shares") or 0 for r in all_metadata)

    print(f"\nResumen @{username}:")
    print(f"  Videos: {len(all_metadata)}")
    print(f"  Views totales: {total_views:,}")
    print(f"  Likes totales: {total_likes:,}")
    print(f"  Shares totales: {total_shares:,}")

    # === FASE 4: Download ===
    if not no_download:
        print(f"\n{'=' * 60}")
        print(f"  DESCARGANDO VIDEOS")
        print(f"{'=' * 60}\n")

        _download_tiktok_videos(all_metadata, videos_dir, config)

    # === FASE 5: Convert ===
    if not no_convert and not no_download:
        print(f"\n{'=' * 60}")
        print(f"  CONVIRTIENDO VIDEOS")
        print(f"{'=' * 60}\n")

        convert_all(videos_dir, config)

    print(f"\n{'=' * 60}")
    print(f"  SNAPSHOT COMPLETADO: @{username}")
    print(f"  Output: {output_dir}")
    print(f"{'=' * 60}")


def run_discover(username: str, config: dict, max_videos: int = 0):
    """Solo fase de discovery."""
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "tiktok" / f"@{username}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with BrowserContext(config) as (ctx, page):
        profile, videos = scrape_profile(
            page, username, config,
            max_videos=max_videos,
            save_progress=output_dir / "discovered.json",
        )
    save_json(output_dir / "profile.json", profile.to_dict())
    print(f"\nDescubiertos {len(videos)} videos en {output_dir / 'discovered.json'}")


def run_download(username: str, config: dict):
    """Descarga videos de un perfil ya scrapeado."""
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "tiktok" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    all_metadata = load_all_metadata(metadata_dir)
    if not all_metadata:
        print(f"No hay metadata para @{username}")
        return

    print(f"Videos a descargar: {len(all_metadata)}")
    _download_tiktok_videos(all_metadata, videos_dir, config)
    convert_all(videos_dir, config)


def _download_tiktok_videos(metadata: list[dict], videos_dir: Path, config: dict):
    """Descarga videos de TikTok con yt-dlp."""
    import subprocess

    ytdlp = config["downloads"]["ytdlp_binary"]
    ok, skipped, failed = 0, 0, 0

    for i, meta in enumerate(metadata, 1):
        video_id = meta.get("shortcode", meta.get("video_id", ""))
        url = meta.get("url", "")
        date = meta.get("date", "unknown")

        print(f"[{i}/{len(metadata)}] {video_id}", end=" ", flush=True)

        existing = list(videos_dir.glob(f"*{video_id}*"))
        if any(f.suffix in (".mp4", ".mkv", ".webm") for f in existing):
            print("-> ya existe")
            skipped += 1
            continue

        out_template = str(videos_dir / f"{date}_{video_id}.%(ext)s")

        cmd = [
            ytdlp,
            "--merge-output-format", "mp4",
            "--output", out_template,
            "--quiet", "--no-warnings",
            "--no-playlist",
            url,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                print("-> ok")
                ok += 1
            else:
                err = (result.stderr or "").strip()[-80:]
                print(f"-> error: {err}")
                failed += 1
        except subprocess.TimeoutExpired:
            print("-> timeout")
            failed += 1

        rate_limit(config, "tiktok", "download_delay")

    print(f"\nDescargados: {ok} | Ya existian: {skipped} | Fallidos: {failed}")
