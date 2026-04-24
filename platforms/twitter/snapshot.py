"""Orquestador de snapshot completo de un perfil de X (Twitter).

Pipeline: discover -> metadata -> CSV -> download videos
"""

from pathlib import Path

from shared.browser import BrowserContext, is_login_redirect
from shared.converter import convert_all
from shared.output import save_json, load_all_metadata, write_csv, STANDARD_FIELDS
from shared.rate_limiter import rate_limit, rate_limit_batch
from shared.utils import today, normalize_username

from platforms.twitter.profile_scraper import scrape_profile, load_discovered
from platforms.twitter.post_scraper import scrape_tweet


def run_snapshot(username: str, config: dict,
                 no_download: bool = False,
                 no_convert: bool = False,
                 max_posts: int = 0):
    """Pipeline completo de snapshot para un perfil de X."""
    username = normalize_username(username)

    output_dir = Path(config["output"]["base_dir"]) / "twitter" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "discovered.json"

    print("=" * 60)
    print(f"  SNAPSHOT X/TWITTER: @{username}")
    print("=" * 60)

    # === FASE 1: Discovery (skip si ya existe) ===
    existing = load_discovered(progress_file)

    with BrowserContext(config) as (ctx, page):
        if existing:
            tweets = existing
            print(f"\nUsando discovery existente: {len(tweets)} tweets en {progress_file}")
        else:
            profile, tweets = scrape_profile(
                page, username, config,
                max_posts=max_posts,
                save_progress=progress_file,
            )
            save_json(output_dir / "profile.json", profile.to_dict())
            print(f"\nPerfil guardado: {output_dir / 'profile.json'}")

        if not tweets:
            print("No hay tweets para scrapear.")
            return

        # === FASE 2: Metadata ===
        print(f"\n{'=' * 60}")
        print(f"  SCRAPING METADATA: {len(tweets)} tweets")
        print(f"{'=' * 60}\n")

        already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
        pending = [t for t in tweets if t.tweet_id not in already_scraped]
        print(f"Ya scrapeados: {len(already_scraped)} | Pendientes: {len(pending)}\n")

        ok, failed = 0, []
        for i, tweet in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] {tweet.tweet_id}", end=" ", flush=True)

            meta = scrape_tweet(page, tweet.tweet_id, tweet.url, config)

            if meta:
                save_json(metadata_dir / f"{tweet.tweet_id}.json", meta)
                likes_str = f"L:{meta.get('likes', '?')}" if meta.get("likes") else ""
                print(f"-> {meta.get('date', '?')} {likes_str}")
                ok += 1
            else:
                print("-> sin metadata")
                failed.append(tweet.tweet_id)

            rate_limit(config, "twitter", "scrape_delay")
            rate_limit_batch(config, "twitter", i)

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
    total_retweets = sum(r.get("shares") or 0 for r in all_metadata)

    print(f"\nResumen @{username}:")
    print(f"  Tweets: {len(all_metadata)}")
    print(f"  Likes totales: {total_likes:,}")
    print(f"  Replies totales: {total_comments:,}")
    print(f"  Retweets totales: {total_retweets:,}")
    print(f"  Views totales: {total_views:,}")

    # === FASE 4: Download videos ===
    if not no_download:
        video_tweets = [m for m in all_metadata if m.get("is_video")]
        if video_tweets:
            print(f"\n{'=' * 60}")
            print(f"  DESCARGANDO VIDEOS")
            print(f"{'=' * 60}\n")

            _download_x_videos(video_tweets, videos_dir, config)

            if not no_convert:
                convert_all(videos_dir, config)
        else:
            print("\nNo hay videos para descargar.")

    print(f"\n{'=' * 60}")
    print(f"  SNAPSHOT COMPLETADO: @{username}")
    print(f"  Output: {output_dir}")
    print(f"{'=' * 60}")


def run_discover(username: str, config: dict, max_posts: int = 0):
    """Solo fase de discovery."""
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "twitter" / f"@{username}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with BrowserContext(config) as (ctx, page):
        profile, tweets = scrape_profile(
            page, username, config,
            max_posts=max_posts,
            save_progress=output_dir / "discovered.json",
        )
    save_json(output_dir / "profile.json", profile.to_dict())
    print(f"\nDescubiertos {len(tweets)} tweets en {output_dir / 'discovered.json'}")


def run_download(username: str, config: dict):
    """Descarga videos de un perfil ya scrapeado."""
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "twitter" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    videos_dir = output_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    all_metadata = load_all_metadata(metadata_dir)
    video_tweets = [m for m in all_metadata if m.get("is_video")]

    if not video_tweets:
        print(f"No hay videos para @{username}")
        return

    print(f"Videos a descargar: {len(video_tweets)}")
    _download_x_videos(video_tweets, videos_dir, config)
    convert_all(videos_dir, config)


def _download_x_videos(metadata: list[dict], videos_dir: Path, config: dict):
    """Descarga videos de X con yt-dlp."""
    import subprocess

    ytdlp = config["downloads"]["ytdlp_binary"]
    ok, skipped, failed = 0, 0, 0

    for i, meta in enumerate(metadata, 1):
        tweet_id = meta.get("shortcode", meta.get("tweet_id", ""))
        url = meta.get("url", f"https://x.com/i/status/{tweet_id}")
        date = meta.get("date", "unknown")

        print(f"[{i}/{len(metadata)}] {tweet_id}", end=" ", flush=True)

        existing = list(videos_dir.glob(f"*{tweet_id}*"))
        if any(f.suffix in (".mp4", ".mkv", ".webm") for f in existing):
            print("-> ya existe")
            skipped += 1
            continue

        out_template = str(videos_dir / f"{date}_{tweet_id}.%(ext)s")

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

        rate_limit(config, "twitter", "download_delay")

    print(f"\nDescargados: {ok} | Ya existian: {skipped} | Fallidos: {failed}")
