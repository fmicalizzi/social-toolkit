#!/usr/bin/env python3
"""Social Media Toolkit — CLI entry point.

Uso:
    python cli.py instagram snapshot @username
    python cli.py instagram discover @username
    python cli.py instagram scrape --from-file /path/to/urls.txt
    python cli.py instagram download @username
    python cli.py youtube snapshot https://www.youtube.com/@handle/videos
    python cli.py youtube discover https://www.youtube.com/@handle/videos
    python cli.py youtube download https://www.youtube.com/@handle/videos
    python cli.py tiktok snapshot @username
    python cli.py tiktok discover @username
    python cli.py tiktok download @username
    python cli.py facebook snapshot page_name
    python cli.py facebook discover page_name
    python cli.py facebook download page_name
    python cli.py twitter snapshot @username
    python cli.py twitter discover @username
    python cli.py twitter download @username
    python cli.py cookies export
    python cli.py convert /path/to/videos/
"""

import sys
import argparse
from pathlib import Path

# Asegurar que el root del toolkit está en sys.path
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from shared.config import load_config


def main():
    parser = argparse.ArgumentParser(
        prog="social-toolkit",
        description="Toolkit portable para extraccion de datos de redes sociales",
    )
    parser.add_argument("--config", default=str(ROOT / "config.yaml"),
                        help="Path al archivo de configuracion")

    sub = parser.add_subparsers(dest="command", help="Plataforma o utilidad")

    # ── Instagram ──
    ig = sub.add_parser("instagram", aliases=["ig"],
                        help="Operaciones de Instagram")
    ig_sub = ig.add_subparsers(dest="action")

    # instagram snapshot
    snap = ig_sub.add_parser("snapshot",
                             help="Snapshot completo de un perfil")
    snap.add_argument("username", help="Username de Instagram (con o sin @)")
    snap.add_argument("--no-download", action="store_true",
                      help="Solo metadata, sin descargar videos")
    snap.add_argument("--no-convert", action="store_true",
                      help="Sin conversion de codec")
    snap.add_argument("--max-posts", type=int, default=0,
                      help="Limitar a N posts (0 = todos)")

    # instagram discover
    disc = ig_sub.add_parser("discover",
                             help="Solo descubrir posts (sin metadata)")
    disc.add_argument("username", help="Username de Instagram")
    disc.add_argument("--max-posts", type=int, default=0)

    # instagram scrape
    scrape = ig_sub.add_parser("scrape",
                               help="Scrape desde archivo de URLs")
    scrape.add_argument("--from-file", required=True,
                        help="Archivo con URLs de Instagram")

    # instagram download (ahora baja imagenes + videos)
    dl = ig_sub.add_parser("download",
                           help="Descargar media (imagenes + videos) de un perfil ya scrapeado")
    dl.add_argument("username", help="Username de Instagram")

    # instagram extract-cache
    ec = ig_sub.add_parser("extract-cache",
                           help="Extraer imagenes del cache del browser (sin navegar)")
    ec.add_argument("username", help="Username de Instagram")

    # ── YouTube ──
    yt = sub.add_parser("youtube", aliases=["yt"],
                        help="Operaciones de YouTube")
    yt_sub = yt.add_subparsers(dest="action")

    yt_snap = yt_sub.add_parser("snapshot",
                                help="Snapshot completo de un canal")
    yt_snap.add_argument("url", help="URL del canal (https://youtube.com/@handle)")
    yt_snap.add_argument("--no-download", action="store_true")
    yt_snap.add_argument("--no-convert", action="store_true")
    yt_snap.add_argument("--max-videos", type=int, default=0)

    yt_disc = yt_sub.add_parser("discover",
                                help="Solo descubrir videos")
    yt_disc.add_argument("url", help="URL del canal")
    yt_disc.add_argument("--max-videos", type=int, default=0)

    yt_dl = yt_sub.add_parser("download",
                              help="Descargar videos de un canal ya scrapeado")
    yt_dl.add_argument("url", help="URL del canal")

    # ── TikTok ──
    tt = sub.add_parser("tiktok", aliases=["tt"],
                        help="Operaciones de TikTok")
    tt_sub = tt.add_subparsers(dest="action")

    tt_snap = tt_sub.add_parser("snapshot",
                                help="Snapshot completo de un perfil")
    tt_snap.add_argument("username", help="Username de TikTok")
    tt_snap.add_argument("--no-download", action="store_true")
    tt_snap.add_argument("--no-convert", action="store_true")
    tt_snap.add_argument("--max-videos", type=int, default=0)

    tt_disc = tt_sub.add_parser("discover",
                                help="Solo descubrir videos")
    tt_disc.add_argument("username", help="Username de TikTok")
    tt_disc.add_argument("--max-videos", type=int, default=0)

    tt_dl = tt_sub.add_parser("download",
                              help="Descargar videos de un perfil ya scrapeado")
    tt_dl.add_argument("username", help="Username de TikTok")

    # ── Facebook ──
    fb = sub.add_parser("facebook", aliases=["fb"],
                        help="Operaciones de Facebook")
    fb_sub = fb.add_subparsers(dest="action")

    fb_snap = fb_sub.add_parser("snapshot",
                                help="Snapshot completo de una pagina")
    fb_snap.add_argument("page", help="Nombre/slug de la pagina de Facebook")
    fb_snap.add_argument("--no-download", action="store_true")
    fb_snap.add_argument("--no-convert", action="store_true")
    fb_snap.add_argument("--max-posts", type=int, default=0)

    fb_disc = fb_sub.add_parser("discover",
                                help="Solo descubrir posts")
    fb_disc.add_argument("page", help="Nombre de la pagina")
    fb_disc.add_argument("--max-posts", type=int, default=0)

    fb_dl = fb_sub.add_parser("download",
                              help="Descargar media (imagenes + videos) de una pagina ya scrapeada")
    fb_dl.add_argument("page", help="Nombre de la pagina")

    fb_ec = fb_sub.add_parser("extract-cache",
                              help="Extraer imagenes del cache del browser (sin navegar)")
    fb_ec.add_argument("page", help="Nombre de la pagina")

    # ── Twitter/X ──
    tw = sub.add_parser("twitter", aliases=["x"],
                        help="Operaciones de X (Twitter)")
    tw_sub = tw.add_subparsers(dest="action")

    tw_snap = tw_sub.add_parser("snapshot",
                                help="Snapshot completo de un perfil")
    tw_snap.add_argument("username", help="Username de X")
    tw_snap.add_argument("--no-download", action="store_true")
    tw_snap.add_argument("--no-convert", action="store_true")
    tw_snap.add_argument("--max-posts", type=int, default=0)

    tw_disc = tw_sub.add_parser("discover",
                                help="Solo descubrir tweets")
    tw_disc.add_argument("username", help="Username de X")
    tw_disc.add_argument("--max-posts", type=int, default=0)

    tw_dl = tw_sub.add_parser("download",
                              help="Descargar videos de un perfil ya scrapeado")
    tw_dl.add_argument("username", help="Username de X")

    # ── Cookies ──
    cookies_parser = sub.add_parser("cookies",
                                    help="Gestion de cookies del browser")
    cookies_parser.add_argument("action", choices=["export"],
                                help="Accion a realizar")

    # ── Convert ──
    conv = sub.add_parser("convert",
                          help="Convertir videos a H.264")
    conv.add_argument("path", help="Directorio con videos")

    # ── Parse & dispatch ──
    args = parser.parse_args()
    config = load_config(Path(args.config), ROOT)

    if args.command in ("instagram", "ig"):
        _dispatch_instagram(args, config)
    elif args.command in ("youtube", "yt"):
        _dispatch_youtube(args, config)
    elif args.command in ("tiktok", "tt"):
        _dispatch_tiktok(args, config)
    elif args.command in ("facebook", "fb"):
        _dispatch_facebook(args, config)
    elif args.command in ("twitter", "x"):
        _dispatch_twitter(args, config)
    elif args.command == "cookies":
        _dispatch_cookies(args, config)
    elif args.command == "convert":
        _dispatch_convert(args, config)
    else:
        parser.print_help()


def _dispatch_instagram(args, config):
    if args.action == "snapshot":
        from platforms.instagram.snapshot import run_snapshot
        run_snapshot(args.username, config,
                     no_download=args.no_download,
                     no_convert=args.no_convert,
                     max_posts=args.max_posts)

    elif args.action == "discover":
        from platforms.instagram.snapshot import run_discover
        run_discover(args.username, config, max_posts=args.max_posts)

    elif args.action == "scrape":
        from platforms.instagram.snapshot import run_scrape_from_file
        run_scrape_from_file(args.from_file, config)

    elif args.action == "download":
        from platforms.instagram.snapshot import run_download
        run_download(args.username, config)

    elif args.action == "extract-cache":
        from platforms.instagram.snapshot import run_extract_cache
        run_extract_cache(args.username, config)

    else:
        print("Uso: python cli.py instagram {snapshot|discover|scrape|download|extract-cache}")
        print("     python cli.py instagram snapshot @username")


def _dispatch_youtube(args, config):
    if args.action == "snapshot":
        from platforms.youtube.snapshot import run_snapshot
        run_snapshot(args.url, config,
                     no_download=args.no_download,
                     no_convert=args.no_convert,
                     max_videos=args.max_videos)
    elif args.action == "discover":
        from platforms.youtube.snapshot import run_discover
        run_discover(args.url, config, max_videos=args.max_videos)
    elif args.action == "download":
        from platforms.youtube.snapshot import run_download
        run_download(args.url, config)
    else:
        print("Uso: python cli.py youtube {snapshot|discover|download} URL")


def _dispatch_tiktok(args, config):
    if args.action == "snapshot":
        from platforms.tiktok.snapshot import run_snapshot
        run_snapshot(args.username, config,
                     no_download=args.no_download,
                     no_convert=args.no_convert,
                     max_videos=args.max_videos)
    elif args.action == "discover":
        from platforms.tiktok.snapshot import run_discover
        run_discover(args.username, config, max_videos=args.max_videos)
    elif args.action == "download":
        from platforms.tiktok.snapshot import run_download
        run_download(args.username, config)
    else:
        print("Uso: python cli.py tiktok {snapshot|discover|download} @username")


def _dispatch_facebook(args, config):
    if args.action == "snapshot":
        from platforms.facebook.snapshot import run_snapshot
        run_snapshot(args.page, config,
                     no_download=args.no_download,
                     no_convert=args.no_convert,
                     max_posts=args.max_posts)
    elif args.action == "discover":
        from platforms.facebook.snapshot import run_discover
        run_discover(args.page, config, max_posts=args.max_posts)
    elif args.action == "download":
        from platforms.facebook.snapshot import run_download
        run_download(args.page, config)
    elif args.action == "extract-cache":
        from platforms.facebook.snapshot import run_extract_cache
        run_extract_cache(args.page, config)
    else:
        print("Uso: python cli.py facebook {snapshot|discover|download|extract-cache} page_name")


def _dispatch_twitter(args, config):
    if args.action == "snapshot":
        from platforms.twitter.snapshot import run_snapshot
        run_snapshot(args.username, config,
                     no_download=args.no_download,
                     no_convert=args.no_convert,
                     max_posts=args.max_posts)
    elif args.action == "discover":
        from platforms.twitter.snapshot import run_discover
        run_discover(args.username, config, max_posts=args.max_posts)
    elif args.action == "download":
        from platforms.twitter.snapshot import run_download
        run_download(args.username, config)
    else:
        print("Uso: python cli.py twitter {snapshot|discover|download} @username")


def _dispatch_cookies(args, config):
    if args.action == "export":
        from shared.cookies import export_cookies
        export_cookies(config)


def _dispatch_convert(args, config):
    from shared.converter import convert_all
    convert_all(Path(args.path), config)


if __name__ == "__main__":
    main()
