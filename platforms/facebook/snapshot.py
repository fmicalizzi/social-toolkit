"""Orquestador de snapshot completo de una pagina de Facebook.

Pipeline: discover -> metadata -> CSV -> download -> convert

Si discovered.json ya existe, salta el discovery (scroll del feed)
y va directo a visitar cada post individualmente.
"""

from pathlib import Path

from shared.browser import BrowserContext, ensure_logged_in, is_login_redirect
from shared.converter import convert_all
from shared.output import save_json, load_all_metadata, write_csv, STANDARD_FIELDS
from shared.rate_limiter import rate_limit, rate_limit_batch
from shared.utils import today

from platforms.facebook.page_scraper import scrape_page, load_discovered
from platforms.facebook.post_scraper import scrape_post


def run_snapshot(page_name: str, config: dict,
                 no_download: bool = False,
                 no_convert: bool = False,
                 max_posts: int = 0):
    """Pipeline completo de snapshot para una pagina de Facebook."""
    page_name = page_name.strip().lstrip("@").strip()

    output_dir = Path(config["output"]["base_dir"]) / "facebook" / page_name
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "discovered.json"

    print("=" * 60)
    print(f"  SNAPSHOT FACEBOOK: {page_name}")
    print("=" * 60)

    # === FASE 1: Discovery (skip si ya existe discovered.json) ===
    existing_posts = load_discovered(progress_file)
    if existing_posts:
        posts = existing_posts
        print(f"\nUsando discovery existente: {len(posts)} posts en {progress_file}")
        print("  (Para re-descubrir, elimina discovered.json y corre de nuevo)")
    else:
        print("\nFase 1: Discovery (scroll del feed)...")

    with BrowserContext(config) as (ctx, page):
        if not existing_posts:
            page_info, posts = scrape_page(
                page, page_name, config,
                max_posts=max_posts,
                save_progress=progress_file,
            )
            save_json(output_dir / "page.json", page_info.to_dict())
            print(f"\nPagina guardada: {output_dir / 'page.json'}")

        if not posts:
            print("No hay posts para scrapear.")
            return

        # === FASE 2: Metadata (visita post por post) ===
        print(f"\n{'=' * 60}")
        print(f"  SCRAPING METADATA: {len(posts)} posts")
        print(f"{'=' * 60}\n")

        already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
        pending = [p for p in posts if p.post_id not in already_scraped]
        print(f"Ya scrapeados: {len(already_scraped)} | Pendientes: {len(pending)}\n")

        ok, failed = 0, []
        for i, post in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] {post.post_id[:20]}", end=" ", flush=True)

            if is_login_redirect(page):
                ensure_logged_in(page)

            meta = scrape_post(page, post.post_id, post.url, config)

            if meta:
                save_json(metadata_dir / f"{post.post_id}.json", meta)
                likes_str = f"L:{meta.get('likes', '?')}" if meta.get("likes") else ""
                print(f"-> {meta.get('date', '?')} {likes_str}")
                ok += 1
            else:
                print("-> sin metadata")
                failed.append(post.post_id)

            rate_limit(config, "facebook", "scrape_delay")
            rate_limit_batch(config, "facebook", i)

        print(f"\nScrapeados: {ok} | Fallidos: {len(failed)}")

    # === FASE 3: CSV ===
    print(f"\n{'=' * 60}")
    print(f"  GENERANDO SNAPSHOT CSV")
    print(f"{'=' * 60}\n")

    all_metadata = load_all_metadata(metadata_dir)
    all_metadata.sort(key=lambda r: (r.get("date", ""), r.get("shortcode", "")))

    csv_path = output_dir / f"snapshot_{today()}.csv"
    write_csv(csv_path, all_metadata, STANDARD_FIELDS)

    total_likes = sum(r.get("likes") or 0 for r in all_metadata)
    total_comments = sum(r.get("comments") or 0 for r in all_metadata)
    total_views = sum(r.get("views") or 0 for r in all_metadata)

    print(f"\nResumen {page_name}:")
    print(f"  Posts: {len(all_metadata)}")
    print(f"  Likes totales: {total_likes:,}")
    print(f"  Comments totales: {total_comments:,}")
    print(f"  Views totales: {total_views:,}")

    # === FASE 4: Download videos ===
    if not no_download:
        print(f"\n{'=' * 60}")
        print(f"  DESCARGANDO VIDEOS")
        print(f"{'=' * 60}\n")

        _download_fb_videos(all_metadata, videos_dir, config)

    if not no_convert and not no_download:
        print(f"\n{'=' * 60}")
        print(f"  CONVIRTIENDO VIDEOS")
        print(f"{'=' * 60}\n")

        convert_all(videos_dir, config)

    print(f"\n{'=' * 60}")
    print(f"  SNAPSHOT COMPLETADO: {page_name}")
    print(f"  Output: {output_dir}")
    print(f"{'=' * 60}")


def run_discover(page_name: str, config: dict, max_posts: int = 0):
    """Solo fase de discovery."""
    page_name = page_name.strip().lstrip("@").strip()
    output_dir = Path(config["output"]["base_dir"]) / "facebook" / page_name
    output_dir.mkdir(parents=True, exist_ok=True)

    with BrowserContext(config) as (ctx, page):
        page_info, posts = scrape_page(
            page, page_name, config,
            max_posts=max_posts,
            save_progress=output_dir / "discovered.json",
        )
    save_json(output_dir / "page.json", page_info.to_dict())
    print(f"\nDescubiertos {len(posts)} posts en {output_dir / 'discovered.json'}")


def run_download(page_name: str, config: dict):
    """Descarga TODO el media (imagenes + videos) de una pagina ya scrapeada.

    Estrategia:
    1. Extrae imagenes del cache del browser (sin red, instantaneo)
    2. Descarga con browser lo que falte (fotos via og:image)
    3. Descarga videos con yt-dlp
    """
    from shared.media_downloader import extract_from_cache, download_missing_media

    page_name = page_name.strip().lstrip("@").strip()
    output_dir = Path(config["output"]["base_dir"]) / "facebook" / page_name
    metadata_dir = output_dir / "metadata"
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Cargar posts: primero metadata, si no hay usar discovered.json
    all_metadata = load_all_metadata(metadata_dir)
    if not all_metadata:
        discovered = load_discovered(output_dir / "discovered.json")
        if discovered:
            all_metadata = [{"post_id": p.post_id, "url": p.url,
                            "is_video": p.is_video, "shortcode": p.post_id}
                           for p in discovered]

    if not all_metadata:
        print(f"No hay posts para {page_name}")
        return

    videos_dir = output_dir / "videos"  # legacy dir de descargas anteriores
    photos = [m for m in all_metadata if not m.get("is_video")]
    videos = [m for m in all_metadata if m.get("is_video")]
    print(f"Total: {len(all_metadata)} posts ({len(photos)} fotos, {len(videos)} videos)")

    # PASO 1: Extraer del cache (gratis, sin red)
    print(f"\n--- Paso 1: Extrayendo del cache del browser ---")
    extract_from_cache(
        config["browser"]["profile_dir"], media_dir,
        platform_filter="facebook"
    )

    # PASO 2: Descargar lo que falte
    # Pasa TODOS los posts — download_missing_media es inteligente:
    # - Revisa media/ y videos/ para no re-descargar
    # - Para fotos del cache, compara CDN filename antes de bajar
    print(f"\n--- Paso 2: Completando media faltante ---")
    with BrowserContext(config) as (ctx, page):
        download_missing_media(
            all_metadata, media_dir, config, page=page,
            platform="facebook",
            rate_delay=tuple(config["rate_limits"]["facebook"]["scrape_delay"]),
            also_check_dirs=[videos_dir],
        )

    # PASO 3: Convertir videos si los hay
    video_files = [f for f in media_dir.iterdir() if f.suffix in (".mp4", ".mkv", ".webm")]
    if video_files:
        convert_all(media_dir, config)


def run_extract_cache(page_name: str, config: dict):
    """Extrae media del cache del browser sin navegar."""
    from shared.media_downloader import extract_from_cache

    page_name = page_name.strip().lstrip("@").strip()
    output_dir = Path(config["output"]["base_dir"]) / "facebook" / page_name
    media_dir = output_dir / "media"

    extract_from_cache(
        config["browser"]["profile_dir"], media_dir,
        platform_filter="facebook"
    )


def _download_fb_videos(metadata: list[dict], videos_dir: Path, config: dict):
    """Descarga videos de Facebook con yt-dlp."""
    import subprocess

    ytdlp = config["downloads"]["ytdlp_binary"]
    cookies = config["downloads"]["cookies_file"]
    ok, skipped, failed = 0, 0, 0

    for i, meta in enumerate(metadata, 1):
        post_id = meta.get("shortcode", meta.get("post_id", ""))
        url = meta.get("url", "")
        date = meta.get("date", "unknown")

        print(f"[{i}/{len(metadata)}] {post_id[:20]}", end=" ", flush=True)

        existing = list(videos_dir.glob(f"*{post_id}*"))
        if any(f.suffix in (".mp4", ".mkv", ".webm") for f in existing):
            print("-> ya existe")
            skipped += 1
            continue

        out_template = str(videos_dir / f"{date}_{post_id}.%(ext)s")

        cmd = [
            ytdlp,
            "--cookies", cookies,
            "--merge-output-format", "mp4",
            "--output", out_template,
            "--quiet", "--no-warnings",
            "--no-playlist",
            url,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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

        rate_limit(config, "facebook", "download_delay")

    print(f"\nDescargados: {ok} | Ya existian: {skipped} | Fallidos: {failed}")
