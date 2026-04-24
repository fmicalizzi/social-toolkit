"""Scraper de perfiles de Instagram: navega al perfil, scrollea, extrae todos los shortcodes."""

import re
import json
import time
import random
from pathlib import Path
from playwright.sync_api import Page

from platforms.instagram.models import ProfileInfo, DiscoveredPost
from shared.rate_limiter import rate_limit_batch
from shared.output import save_json


def scrape_profile(page: Page, username: str, config: dict,
                   max_posts: int = 0,
                   save_progress: Path = None) -> tuple[ProfileInfo, list[DiscoveredPost]]:
    """Navega al perfil, extrae header y scrollea para descubrir todos los posts.

    Args:
        page: Pagina Playwright con sesion activa
        username: Username de Instagram (sin @)
        config: Config dict global
        max_posts: Limitar a N posts (0 = todos)
        save_progress: Path para guardar shortcodes incrementalmente

    Returns:
        (ProfileInfo, lista de DiscoveredPost)
    """
    url = f"https://www.instagram.com/{username}/"
    print(f"Navegando a {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(3, 5))

    # Esperar a que el grid de posts se renderice (hasta 15s)
    try:
        page.wait_for_selector('a[href*="/p/"], a[href*="/reel/"]', timeout=15000)
    except Exception:
        pass  # Puede no haber posts o ser privado — se maneja abajo

    # Verificar que no redirigió a login
    if "login" in page.url:
        raise RuntimeError("Redirigido a login. Sesion expirada.")

    # Verificar que el perfil existe
    if page.locator("text=Sorry, this page isn't available").count() > 0:
        raise RuntimeError(f"Perfil @{username} no encontrado o no disponible.")

    # Extraer info del perfil
    profile = _extract_profile_header(page, username)
    print(f"Perfil: @{username} | {profile.full_name}")
    print(f"  Posts: {profile.post_count} | Followers: {profile.followers:,} | Following: {profile.following:,}")

    if profile.is_private:
        print("  PERFIL PRIVADO — no se pueden scrapear posts.")
        return profile, []

    # Calcular target
    target = profile.post_count if profile.post_count > 0 else 0
    if max_posts > 0:
        target = min(target, max_posts) if target > 0 else max_posts
    print(f"  Target: {target if target > 0 else 'todos (scroll hasta el final)'} posts\n")

    # Scroll para descubrir posts
    posts = _scroll_and_collect(page, target, config, save_progress)

    # Guardar progreso final
    if save_progress:
        _save_discovered(save_progress, posts)

    print(f"\nDescubiertos: {len(posts)} posts")
    return profile, posts


def _extract_profile_header(page: Page, username: str) -> ProfileInfo:
    """Extrae datos del header del perfil."""
    info = page.evaluate("""() => {
        const getMeta = (name) => {
            const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
            return el ? el.getAttribute('content') : '';
        };

        // Contadores de followers/following/posts
        // Instagram los pone en <meta content="N Followers, N Following, N Posts ...">
        const desc = getMeta('og:description') || '';

        // JSON-LD para datos adicionales
        let jsonld = null;
        for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try { jsonld = JSON.parse(s.textContent); break; } catch(e) {}
        }

        return {
            title: getMeta('og:title'),
            description: desc,
            jsonld: jsonld,
        };
    }""")

    title = info.get("title", "")
    desc = info.get("description", "")

    # Parse nombre desde og:title
    # EN: "Name (@user) • Instagram photos and videos"
    # ES: "Nombre (@user) • Fotos y videos de Instagram"
    full_name = ""
    if "(" in title:
        full_name = title.split("(")[0].strip()
    elif " on Instagram" in title:
        full_name = title.split(" on Instagram")[0].strip()
    elif " en Instagram" in title:
        full_name = title.split(" en Instagram")[0].strip()
    # Limpiar sufijos comunes
    for suffix in [" •", " |", " -"]:
        if suffix in full_name:
            full_name = full_name.split(suffix)[0].strip()

    # Parse contadores desde og:description
    # EN: "N Followers, N Following, N Posts - ..."
    # ES: "N seguidores, N seguidos, N publicaciones - ..."
    # PT: "N seguidores, N seguindo, N publicações - ..."
    followers = _parse_count(desc, r'([\d,.KkMm]+)\s*(?:Followers|seguidores|Seguidores)')
    following = _parse_count(desc, r'([\d,.KkMm]+)\s*(?:Following|seguidos|Seguidos|seguindo)')
    post_count = _parse_count(desc, r'([\d,.KkMm]+)\s*(?:Posts|publicaciones|Publicaciones|publicações)')

    # Detectar si es privado
    is_private = page.locator("text=This account is private").count() > 0 or \
                 page.locator("text=Esta cuenta es privada").count() > 0

    # Detectar verificado (badge azul)
    is_verified = page.locator('[title="Verified"]').count() > 0 or \
                  page.locator('svg[aria-label="Verified"]').count() > 0

    # Bio: desde JSON-LD o desde el DOM
    bio = ""
    jsonld = info.get("jsonld") or {}
    if isinstance(jsonld, dict):
        bio = jsonld.get("description", "")
    if not bio:
        # Intentar extraer bio del og:description (despues del separador " - ")
        parts = desc.split(" - ", 1)
        if len(parts) > 1:
            remainder = parts[1].strip()
            # Quitar el prefijo "Ver fotos y videos..."
            for prefix in ["Ver fotos y videos de Instagram de",
                           "See Instagram photos and videos from"]:
                if remainder.startswith(prefix):
                    remainder = ""
                    break
            if remainder:
                bio = remainder

    return ProfileInfo(
        username=username,
        full_name=full_name,
        bio=bio[:500],
        followers=followers,
        following=following,
        post_count=post_count,
        is_private=is_private,
        is_verified=is_verified,
    )


def _parse_count(text: str, pattern: str) -> int:
    """Parsea contadores como '1,234', '12.5K', '1.2M'."""
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return 0
    raw = match.group(1).replace(",", "").strip()
    multiplier = 1
    if raw.upper().endswith("K"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.upper().endswith("M"):
        multiplier = 1_000_000
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return 0


def _extract_post_links(page: Page) -> list[dict]:
    """Extrae todos los links de posts visibles en el DOM actual.

    Busca <a href="/p/SHORTCODE/"> y <a href="/reel/SHORTCODE/">.
    Retorna lista de dicts con shortcode, url, y tipo.
    """
    return page.evaluate("""() => {
        const results = [];
        const seen = new Set();
        const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
        for (const a of links) {
            const href = a.getAttribute('href');
            const match = href.match(/\\/(p|reel)\\/([A-Za-z0-9_-]+)/);
            if (!match) continue;
            const type = match[1];
            const shortcode = match[2];
            if (seen.has(shortcode)) continue;
            seen.add(shortcode);
            // Detectar si contiene video (icono de play o elemento video)
            const hasVideo = a.querySelector('svg[aria-label*="video"], svg[aria-label*="Video"], svg[aria-label*="Reel"]') !== null
                          || a.querySelector('video') !== null;
            results.push({
                shortcode: shortcode,
                url: 'https://www.instagram.com/' + type + '/' + shortcode + '/',
                type: type,
                hasVideo: hasVideo || type === 'reel',
            });
        }
        return results;
    }""")


def _scroll_and_collect(page: Page, target: int, config: dict,
                        save_progress: Path = None) -> list[DiscoveredPost]:
    """Scrollea el grid del perfil, colectando shortcodes de los links.

    Instagram usa un virtual scroller que solo renderiza las filas visibles.
    scrollTo(0, body.scrollHeight) rompe la virtualizacion — hay que scrollear
    incrementalmente con scrollBy para que cargue nuevas filas.
    """
    collected = {}  # shortcode -> DiscoveredPost
    no_new_count = 0
    scroll_num = 0
    scroll_delay = config.get("rate_limits", {}).get("instagram", {}).get("scroll_delay", [1.5, 3.0])
    max_stale_scrolls = 8  # Mas tolerancia — IG puede tardar en cargar filas

    while True:
        # Extraer todos los links de posts visibles en el DOM
        links = _extract_post_links(page)

        prev_count = len(collected)
        for link in links:
            sc = link["shortcode"]
            if sc not in collected:
                collected[sc] = DiscoveredPost(
                    shortcode=sc,
                    url=link["url"],
                    is_video=link.get("hasVideo", False) or link.get("type") == "reel",
                )

        new_found = len(collected) - prev_count
        scroll_num += 1

        target_str = str(target) if target > 0 else "?"
        print(f"  Scroll #{scroll_num}: {len(collected)}/{target_str} posts"
              f" (+{new_found} nuevos)", end="\r", flush=True)

        # Verificar si llegamos al target
        if target > 0 and len(collected) >= target:
            print(f"\n  Target alcanzado ({target} posts)")
            break

        # Verificar si no hay nuevos
        if new_found == 0:
            no_new_count += 1
            if no_new_count >= max_stale_scrolls:
                print(f"\n  Sin posts nuevos en {max_stale_scrolls} scrolls consecutivos. Fin.")
                break
        else:
            no_new_count = 0

        # Guardar progreso incremental cada 50 posts
        if save_progress and len(collected) // 50 > prev_count // 50:
            _save_discovered(save_progress, list(collected.values()))

        # Batch pause
        rate_limit_batch(config, "instagram", len(collected))

        # Scroll INCREMENTAL — critico para el virtual scroller de Instagram
        scroll_px = random.randint(600, 1000)
        page.evaluate(f"window.scrollBy(0, {scroll_px})")

        # Esperar mas si no hubo nuevos (IG puede estar cargando)
        if new_found == 0:
            time.sleep(random.uniform(scroll_delay[1], scroll_delay[1] + 1.5))
        else:
            time.sleep(random.uniform(scroll_delay[0], scroll_delay[1]))

    posts = list(collected.values())

    # Limitar al target si se excedió
    if target > 0 and len(posts) > target:
        posts = posts[:target]

    return posts


def _save_discovered(path: Path, posts: list[DiscoveredPost]):
    """Guarda la lista de posts descubiertos para recuperacion."""
    data = [{"shortcode": p.shortcode, "url": p.url, "is_video": p.is_video} for p in posts]
    save_json(path, data)


def load_discovered(path: Path) -> list[DiscoveredPost]:
    """Carga posts descubiertos previamente."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [DiscoveredPost(**d) for d in data]
