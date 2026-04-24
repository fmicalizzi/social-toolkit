"""Orquestador de snapshot completo de un perfil de Instagram.

Pipeline: discover -> scrape metadata -> CSV -> download videos -> convert
"""

import re
from pathlib import Path

from shared.browser import BrowserContext, ensure_logged_in, is_login_redirect
from shared.cookies import export_cookies
from shared.downloader import download_all
from shared.converter import convert_all
from shared.output import save_json, load_all_metadata, write_csv, STANDARD_FIELDS
from shared.rate_limiter import rate_limit, rate_limit_batch
from shared.utils import today, normalize_username

from platforms.instagram.profile_scraper import scrape_profile, load_discovered
from platforms.instagram.post_scraper import scrape_post


def run_snapshot(username: str, config: dict,
                 no_download: bool = False,
                 no_convert: bool = False,
                 max_posts: int = 0):
    """Pipeline completo de snapshot para un perfil de Instagram."""
    username = normalize_username(username)

    # Directorios de output
    output_dir = Path(config["output"]["base_dir"]) / "instagram" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "discovered.json"

    print("=" * 60)
    print(f"  SNAPSHOT: @{username}")
    print("=" * 60)

    # ═══ FASE 1: Discovery (skip si ya existe discovered.json) ═══
    existing_posts = load_discovered(progress_file)

    with BrowserContext(config) as (ctx, page):
        ensure_logged_in(page)

        if existing_posts:
            posts = existing_posts
            print(f"\nUsando discovery existente: {len(posts)} posts en {progress_file}")
            print("  (Para re-descubrir, elimina discovered.json y corre de nuevo)")
        else:
            print("\nFase 1: Discovery (scroll del perfil)...")
            profile, posts = scrape_profile(
                page, username, config,
                max_posts=max_posts,
                save_progress=progress_file,
            )
            save_json(output_dir / "profile.json", profile.to_dict())
            print(f"\nPerfil guardado: {output_dir / 'profile.json'}")

        if not posts:
            print("No hay posts para scrapear.")
            return

        # ═══ FASE 2: Metadata ═══
        print(f"\n{'=' * 60}")
        print(f"  SCRAPING METADATA: {len(posts)} posts")
        print(f"{'=' * 60}\n")

        already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
        pending = [p for p in posts if p.shortcode not in already_scraped]
        print(f"Ya scrapeados: {len(already_scraped)} | Pendientes: {len(pending)}\n")

        ok, failed = 0, []
        for i, post in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] {post.shortcode}", end=" ", flush=True)

            # Verificar que no perdimos la sesion
            if is_login_redirect(page):
                print("\n*** Sesion expirada durante el scraping ***")
                ensure_logged_in(page)

            meta = scrape_post(page, post.shortcode, config)

            if meta:
                save_json(metadata_dir / f"{post.shortcode}.json", meta)
                likes_str = f"L:{meta.get('likes', '?')}" if meta.get("likes") else ""
                print(f"-> @{meta.get('username', '?')[:20]} | {meta.get('date', '?')} {likes_str}")
                ok += 1
            else:
                print("-> sin metadata")
                failed.append(post.shortcode)

            rate_limit(config, "instagram", "scrape_delay")
            rate_limit_batch(config, "instagram", i)

        print(f"\nScrapeados: {ok} | Fallidos: {len(failed)}")
        if failed:
            print(f"Fallidos: {failed[:20]}{'...' if len(failed) > 20 else ''}")

    # ═══ FASE 3: CSV ═══
    print(f"\n{'=' * 60}")
    print(f"  GENERANDO SNAPSHOT CSV")
    print(f"{'=' * 60}\n")

    all_metadata = load_all_metadata(metadata_dir)
    all_metadata.sort(key=lambda r: (r.get("date", ""), r.get("shortcode", "")))

    csv_path = output_dir / f"snapshot_{today()}.csv"
    write_csv(csv_path, all_metadata, STANDARD_FIELDS)

    # Stats resumen
    total_likes = sum(r.get("likes") or 0 for r in all_metadata)
    total_comments = sum(r.get("comments") or 0 for r in all_metadata)
    total_views = sum(r.get("views") or 0 for r in all_metadata)
    video_count = sum(1 for r in all_metadata if r.get("is_video"))

    print(f"\nResumen @{username}:")
    print(f"  Posts: {len(all_metadata)} ({video_count} videos)")
    print(f"  Likes totales: {total_likes:,}")
    print(f"  Comments totales: {total_comments:,}")
    print(f"  Views totales: {total_views:,}")

    # ═══ FASE 4: Download videos ═══
    if not no_download:
        print(f"\n{'=' * 60}")
        print(f"  DESCARGANDO VIDEOS")
        print(f"{'=' * 60}\n")

        export_cookies(config)

        video_posts = [m for m in all_metadata if m.get("is_video")]
        if video_posts:
            download_all(video_posts, videos_dir, config)
        else:
            print("No hay videos para descargar.")

    # ═══ FASE 5: Convert ═══
    if not no_convert and not no_download:
        print(f"\n{'=' * 60}")
        print(f"  CONVIRTIENDO VIDEOS")
        print(f"{'=' * 60}\n")

        convert_all(videos_dir, config)

    print(f"\n{'=' * 60}")
    print(f"  SNAPSHOT COMPLETADO: @{username}")
    print(f"  Output: {output_dir}")
    print(f"{'=' * 60}")


def run_discover(username: str, config: dict, max_posts: int = 0):
    """Solo fase de discovery: navegar perfil y extraer shortcodes."""
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "instagram" / f"@{username}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with BrowserContext(config) as (ctx, page):
        ensure_logged_in(page)
        profile, posts = scrape_profile(
            page, username, config,
            max_posts=max_posts,
            save_progress=output_dir / "discovered.json",
        )
        save_json(output_dir / "profile.json", profile.to_dict())

    print(f"\nDescubiertos {len(posts)} posts. Guardados en {output_dir / 'discovered.json'}")
    print(f"Para scrapear metadata: python cli.py instagram snapshot @{username}")


def run_scrape_from_file(file_path: str, config: dict):
    """Scrape metadata desde un archivo de URLs/shortcodes (compat con _chat.txt)."""
    pattern = r'instagram\.com/(?:reel|p)/([A-Za-z0-9_\-]+)'
    shortcodes = []
    seen = set()

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            for sc in re.findall(pattern, line):
                if sc not in seen:
                    seen.add(sc)
                    shortcodes.append(sc)

    if not shortcodes:
        print(f"No se encontraron shortcodes en {file_path}")
        return

    print(f"Encontrados {len(shortcodes)} shortcodes en {file_path}")

    output_dir = Path(config["output"]["base_dir"]) / "instagram" / "_from_file"
    metadata_dir = output_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
    pending = [sc for sc in shortcodes if sc not in already_scraped]
    print(f"Ya scrapeados: {len(already_scraped)} | Pendientes: {len(pending)}\n")

    with BrowserContext(config) as (ctx, page):
        ensure_logged_in(page)

        ok = 0
        for i, sc in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] {sc}", end=" ", flush=True)

            if is_login_redirect(page):
                ensure_logged_in(page)

            meta = scrape_post(page, sc, config)
            if meta:
                save_json(metadata_dir / f"{sc}.json", meta)
                print(f"-> @{meta.get('username', '?')[:20]} | {meta.get('date', '?')}")
                ok += 1
            else:
                print("-> sin metadata")

            rate_limit(config, "instagram", "scrape_delay")
            rate_limit_batch(config, "instagram", i)

    all_metadata = load_all_metadata(metadata_dir)
    csv_path = output_dir / f"snapshot_{today()}.csv"
    write_csv(csv_path, all_metadata, STANDARD_FIELDS)


def run_download(username: str, config: dict):
    """Descarga TODO el media (imagenes + videos) de un perfil ya scrapeado.

    Estrategia:
    1. Extrae imagenes del cache del browser (sin red)
    2. Descarga con browser lo que falte (fotos via og:image)
    3. Descarga videos con yt-dlp + cookies
    """
    from shared.media_downloader import extract_from_cache, download_missing_media

    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "instagram" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    media_dir = output_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    all_metadata = load_all_metadata(metadata_dir)
    if not all_metadata:
        print(f"No hay metadata para @{username}")
        return

    videos_dir = output_dir / "videos"  # legacy dir de descargas anteriores
    photos = [m for m in all_metadata if not m.get("is_video")]
    videos = [m for m in all_metadata if m.get("is_video")]
    print(f"Total: {len(all_metadata)} posts ({len(photos)} fotos, {len(videos)} videos)")

    # PASO 1: Extraer del cache
    print(f"\n--- Paso 1: Extrayendo del cache del browser ---")
    extract_from_cache(
        config["browser"]["profile_dir"], media_dir,
        platform_filter="instagram"
    )

    # PASO 2: Descargar lo que falte
    # Pasa TODOS los posts — download_missing_media revisa media/ + videos/
    print(f"\n--- Paso 2: Completando media faltante ---")
    export_cookies(config)
    with BrowserContext(config) as (ctx, page):
        ensure_logged_in(page)
        download_missing_media(
            all_metadata, media_dir, config, page=page,
            platform="instagram",
            rate_delay=tuple(config["rate_limits"]["instagram"]["download_delay"]),
            also_check_dirs=[videos_dir],
        )

    # PASO 3: Convertir videos
    video_files = [f for f in media_dir.iterdir() if f.suffix in (".mp4", ".mkv", ".webm")]
    if video_files:
        convert_all(media_dir, config)


def run_extract_cache(username: str, config: dict):
    """Extrae media del cache del browser sin navegar."""
    from shared.media_downloader import extract_from_cache

    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "instagram" / f"@{username}"
    media_dir = output_dir / "media"

    extract_from_cache(
        config["browser"]["profile_dir"], media_dir,
        platform_filter="instagram"
    )
