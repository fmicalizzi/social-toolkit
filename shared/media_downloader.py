"""Descarga de media (imagenes + videos) para todas las plataformas.

Estrategia inteligente:
1. extract_from_cache() — saca imagenes del cache del browser (sin red)
2. download_missing_media() — solo baja lo que REALMENTE falta:
   - Revisa media/, videos/, y cualquier otro directorio legacy
   - Para fotos: visita post → extrae og:image → si el CDN filename ya
     existe en media/ (del cache), NO re-descarga, solo registra el mapping
   - Para videos: revisa videos/ y media/ antes de llamar yt-dlp
"""

import os
import re
import json
import time
import random
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional


# ── Cache extraction ──

def extract_from_cache(browser_profile_dir: str, media_dir: Path,
                       platform_filter: str = "") -> dict:
    """Extrae imagenes del cache de Chromium.

    Returns:
        dict con {extracted: int, total_mb: float, filenames: set}
    """
    cache_dir = Path(browser_profile_dir) / "Default" / "Cache" / "Cache_Data"
    if not cache_dir.exists():
        print(f"Cache no encontrado: {cache_dir}")
        return {"extracted": 0, "total_mb": 0, "filenames": set()}

    media_dir.mkdir(parents=True, exist_ok=True)

    # Skip si ya tenemos archivos del cache (idempotente)
    existing_cache = set(f.name for f in media_dir.iterdir()
                         if f.is_file() and not f.name.startswith("_"))
    if existing_cache:
        print(f"Ya hay {len(existing_cache)} archivos en {media_dir.name}/")
        print(f"  (Para re-extraer, vacia la carpeta primero)")
        return {"extracted": 0, "total_mb": 0, "filenames": existing_cache}

    files = os.listdir(cache_dir)
    print(f"Escaneando {len(files)} archivos de cache...")

    PLATFORM_FILTERS = {
        "facebook": {
            "url_patterns": ["/t39.30808-6/", "/t39.30808-1/"],
            "url_must_contain": "scontent",
            "min_size": 5000,
        },
        "instagram": {
            "url_patterns": ["cdninstagram"],
            "url_must_contain": "",
            "min_size": 50000,
        },
        "tiktok": {
            "url_patterns": ["tiktok"],
            "url_must_contain": "",
            "min_size": 5000,
        },
        "twitter": {
            "url_patterns": ["twimg"],
            "url_must_contain": "",
            "min_size": 5000,
        },
    }

    pf = PLATFORM_FILTERS.get(platform_filter, {})
    url_patterns = pf.get("url_patterns", [])
    url_must_contain = pf.get("url_must_contain", "")
    min_file_size = pf.get("min_size", 5000)

    extracted = []
    seen_filenames = set()

    for f in files:
        path = cache_dir / f
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < min_file_size:
            continue

        with open(path, "rb") as fh:
            data = fh.read()

        jpeg_pos = data.find(b"\xff\xd8\xff")
        if jpeg_pos < 0:
            jpeg_pos = data.find(b"\x89PNG")
            if jpeg_pos < 0:
                continue

        header = data[:jpeg_pos].decode("latin-1", errors="replace")

        if url_patterns:
            if not any(p in header for p in url_patterns):
                continue
        if url_must_contain and url_must_contain not in header:
            continue

        urls = re.findall(
            r"(https?://[^\x00-\x1f\s\"<>]+\.(?:jpg|jpeg|png|webp))",
            header,
        )
        url = urls[0] if urls else ""

        name_match = re.search(r"/([^/]+\.(?:jpg|jpeg|png|webp))", url) if url else None
        if name_match:
            filename = name_match.group(1)
        else:
            filename = f"{f}.jpg"

        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)

        image_data = data[jpeg_pos:]
        if len(image_data) < min_file_size:
            continue

        out_path = media_dir / filename
        with open(out_path, "wb") as fh:
            fh.write(image_data)

        extracted.append({"filename": filename, "size": len(image_data), "url": url[:200]})

    total_mb = sum(e["size"] for e in extracted) / 1024 / 1024

    manifest_path = media_dir / "_cache_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(extracted, f, indent=2)

    print(f"Extraidos: {len(extracted)} archivos ({total_mb:.1f} MB)")
    return {
        "extracted": len(extracted),
        "total_mb": total_mb,
        "filenames": seen_filenames,
    }


# ── Inventory: what do we already have? ──

def _build_inventory(dirs: list[Path]) -> tuple[set, set]:
    """Construye inventario de media ya descargado.

    Revisa multiples directorios (media/, videos/, etc).

    Returns:
        (all_filenames, all_post_ids_found)
        - all_filenames: set de todos los nombres de archivo
        - all_post_ids_found: set de post_ids detectados en nombres
    """
    all_filenames = set()
    all_post_ids = set()

    for d in dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            if not f.is_file() or f.name.startswith("_"):
                continue
            all_filenames.add(f.name)
            # Intentar extraer post_id del nombre
            # Formatos: date_POSTID.ext, POSTID.ext, CDN_hash.jpg
            # Solo registrar como post_id si parece un ID valido
            stem = f.stem
            # "2024-01-15_ABC123def" → "ABC123def"
            parts = stem.split("_", 1)
            if len(parts) == 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
                all_post_ids.add(parts[1])
            all_post_ids.add(stem)

    return all_filenames, all_post_ids


def _post_already_downloaded(post_id: str, all_filenames: set,
                             all_post_ids: set) -> bool:
    """Chequea si un post ya tiene su media descargado."""
    # Match directo por post_id
    if post_id in all_post_ids:
        return True
    # Match parcial: post_id aparece en algun nombre de archivo
    for name in all_filenames:
        if post_id in name:
            return True
    return False


# ── Browser-based image download (smart) ──

def download_image_via_browser(page, post_url: str, post_id: str,
                               media_dir: Path, date: str = "unknown",
                               platform: str = "facebook",
                               existing_filenames: set = None) -> bool:
    """Visita un post y descarga la imagen — SOLO si no esta en cache.

    Flujo inteligente:
    1. Visita la URL del post
    2. Extrae og:image (URL del CDN)
    3. Extrae el filename del CDN (ej: 482264750_1040926_...jpg)
    4. Si ese filename ya existe en media/ (del cache) → NO descarga, solo
       guarda el mapping post_id → cdn_filename
    5. Si no existe → descarga con urllib
    """
    if existing_filenames is None:
        existing_filenames = set(f.name for f in media_dir.iterdir()
                                 if f.is_file() and not f.name.startswith("_"))

    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2, 4))

        # Extraer og:image
        image_url = page.evaluate("""() => {
            const el = document.querySelector('meta[property="og:image"]');
            return el ? el.getAttribute('content') : '';
        }""")

        if not image_url:
            image_url = _extract_image_from_dom(page)

        if not image_url:
            return False

        # Extraer CDN filename de la URL
        cdn_match = re.search(r"/([^/?]+\.(?:jpg|jpeg|png|webp))", image_url)
        cdn_filename = cdn_match.group(1) if cdn_match else ""

        # CHECK INTELIGENTE: ¿ya lo tenemos del cache?
        if cdn_filename and cdn_filename in existing_filenames:
            # Ya lo tenemos! Registrar el mapping pero no re-descargar
            _save_mapping(media_dir, post_id, cdn_filename)
            return True

        # No lo tenemos → descargar
        ext = ".jpg"
        if ".png" in image_url:
            ext = ".png"
        elif ".webp" in image_url:
            ext = ".webp"

        out_path = media_dir / f"{date}_{post_id}{ext}"
        if out_path.exists():
            return True

        req = urllib.request.Request(image_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
            "Referer": post_url,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(out_path, "wb") as f:
                f.write(resp.read())

        return True
    except Exception as e:
        print(f"  [img-err] {post_id}: {e}")
        return False


def _extract_image_from_dom(page) -> str:
    """Fallback: extraer URL de imagen principal del DOM."""
    try:
        return page.evaluate("""() => {
            // Facebook
            const fbImg = document.querySelector(
                'img[data-visualcompletion="media-vc-image"],' +
                '[role="article"] img[src*="scontent"],' +
                'img[src*="fbcdn"]'
            );
            if (fbImg) return fbImg.src || fbImg.getAttribute('data-src') || '';

            // Instagram
            const igImg = document.querySelector(
                'article img[srcset],' +
                'article img[src*="cdninstagram"],' +
                'img[src*="cdninstagram"]'
            );
            if (igImg) {
                const srcset = igImg.getAttribute('srcset');
                if (srcset) {
                    const parts = srcset.split(',').map(s => s.trim());
                    const last = parts[parts.length - 1];
                    return last.split(' ')[0];
                }
                return igImg.src;
            }
            return '';
        }""")
    except Exception:
        return ""


def _save_mapping(media_dir: Path, post_id: str, cdn_filename: str):
    """Guarda mapping post_id → cdn_filename en un archivo JSON incremental."""
    mapping_path = media_dir / "_post_mapping.json"
    mapping = {}
    if mapping_path.exists():
        try:
            with open(mapping_path) as f:
                mapping = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    mapping[post_id] = cdn_filename
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=2)


# ── yt-dlp video download ──

def download_video_via_ytdlp(url: str, post_id: str, media_dir: Path,
                              config: dict, date: str = "unknown",
                              cookies: bool = True) -> bool:
    """Descarga un video con yt-dlp."""
    ytdlp = config["downloads"]["ytdlp_binary"]
    out_template = str(media_dir / f"{date}_{post_id}.%(ext)s")

    cmd = [
        ytdlp,
        "--merge-output-format", "mp4",
        "--output", out_template,
        "--quiet", "--no-warnings",
        "--no-playlist",
    ]

    if cookies and config["downloads"].get("cookies_file"):
        cookies_path = config["downloads"]["cookies_file"]
        if Path(cookies_path).exists():
            cmd.extend(["--cookies", cookies_path])

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# ── Orchestrator principal ──

def download_missing_media(posts: list[dict], media_dir: Path,
                           config: dict, page=None,
                           platform: str = "facebook",
                           rate_delay: tuple = (6, 14),
                           also_check_dirs: list[Path] = None) -> dict:
    """Descarga SOLO el media que realmente falta.

    Inteligencia:
    - Revisa media/ + videos/ + cualquier directorio extra
    - Para fotos: visita post → si og:image ya esta en cache → skip descarga
    - Para videos: revisa todos los directorios antes de yt-dlp
    - Genera _post_mapping.json para trackear que archivo corresponde a que post

    Args:
        posts: lista de dicts con post_id/shortcode, url, is_video, date
        media_dir: directorio destino principal
        config: config.yaml cargado
        page: Playwright Page (necesario para imagenes)
        platform: nombre de plataforma
        rate_delay: (min, max) segundos entre requests
        also_check_dirs: directorios adicionales donde buscar media existente
            (ej: videos/ de descargas anteriores)
    """
    media_dir.mkdir(parents=True, exist_ok=True)

    # Construir inventario de todo lo que ya tenemos
    check_dirs = [media_dir]
    if also_check_dirs:
        check_dirs.extend(also_check_dirs)

    all_filenames, all_post_ids = _build_inventory(check_dirs)
    # Tambien tener a mano los filenames de media/ para el check de cache
    media_filenames = set(f.name for f in media_dir.iterdir()
                          if f.is_file() and not f.name.startswith("_"))

    print(f"Inventario: {len(all_filenames)} archivos en {len(check_dirs)} directorios")

    ok, skipped, failed = 0, 0, 0
    actually_downloaded = 0

    for i, post in enumerate(posts, 1):
        post_id = (post.get("shortcode") or post.get("post_id")
                   or post.get("video_id") or post.get("tweet_id", ""))
        url = post.get("url", "")
        date = post.get("date", "unknown")
        is_video = post.get("is_video", False)

        print(f"[{i}/{len(posts)}] {post_id[:30]}", end=" ", flush=True)

        # Check rapido: ¿ya lo tenemos por post_id?
        if _post_already_downloaded(post_id, all_filenames, all_post_ids):
            print("-> ya existe")
            skipped += 1
            continue

        if is_video:
            use_cookies = platform in ("facebook", "instagram")
            success = download_video_via_ytdlp(
                url, post_id, media_dir, config, date, cookies=use_cookies
            )
            if success:
                actually_downloaded += 1
        else:
            if page is None:
                print("-> skip (no browser)")
                failed += 1
                continue
            success = download_image_via_browser(
                page, url, post_id, media_dir, date, platform,
                existing_filenames=media_filenames,
            )
            # Si fue exitoso via cache (no descarga real), indicarlo
            if success:
                # Re-check: si no se creo un archivo nuevo, fue match de cache
                new_files = set(f.name for f in media_dir.iterdir()
                                if f.is_file() and not f.name.startswith("_"))
                if len(new_files) > len(media_filenames):
                    actually_downloaded += 1
                    media_filenames = new_files

        if success:
            print("-> ok" if is_video or actually_downloaded else "-> ok (cache)")
            ok += 1
            # Actualizar inventario
            all_filenames = set(f.name for f in media_dir.iterdir()
                                if f.is_file() and not f.name.startswith("_"))
            all_post_ids.add(post_id)
        else:
            print("-> error")
            failed += 1

        time.sleep(random.uniform(*rate_delay))

    print(f"\nResultado: {ok} ok | {skipped} ya existian | {failed} fallidos")
    print(f"Descargas reales: {actually_downloaded} (el resto era cache o existente)")
    return {"ok": ok, "skipped": skipped, "failed": failed,
            "actually_downloaded": actually_downloaded}
