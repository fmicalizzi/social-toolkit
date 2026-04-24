"""Scraper de paginas de Facebook: navega al perfil, scrollea, extrae posts."""

import re
import json
import time
import random
from pathlib import Path
from playwright.sync_api import Page

from platforms.facebook.models import PageInfo, DiscoveredPost
from shared.rate_limiter import rate_limit_batch
from shared.output import save_json


def scrape_page(page: Page, page_name: str, config: dict,
                max_posts: int = 0,
                save_progress: Path = None) -> tuple[PageInfo, list[DiscoveredPost]]:
    """Navega a la pagina de Facebook, extrae info y descubre posts.

    Args:
        page: Pagina Playwright con sesion activa
        page_name: Nombre/slug de la pagina (ej: vivaldi.ve)
        config: Config dict global
        max_posts: Limitar a N posts (0 = todos)
        save_progress: Path para guardar posts incrementalmente
    """
    url = f"https://www.facebook.com/{page_name}"
    print(f"Navegando a {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(4, 6))

    # Verificar login
    if "login" in page.url and "checkpoint" not in page.url:
        raise RuntimeError("Redirigido a login. Sesion expirada.")

    # Extraer info de la pagina
    page_info = _extract_page_header(page, page_name)
    print(f"Pagina: {page_info.name}")
    print(f"  Followers: {page_info.followers:,} | Likes: {page_info.likes:,}")

    # Scroll para descubrir posts
    posts = _scroll_and_collect(page, page_name, max_posts, config, save_progress)

    if save_progress and posts:
        _save_discovered(save_progress, posts)

    print(f"\nDescubiertos: {len(posts)} posts")
    return page_info, posts


def _extract_page_header(page: Page, page_name: str) -> PageInfo:
    """Extrae datos del header de la pagina de Facebook."""
    info = page.evaluate("""() => {
        const getMeta = (name) => {
            const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
            return el ? el.getAttribute('content') : '';
        };

        // JSON-LD
        let jsonld = null;
        for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
            try { jsonld = JSON.parse(s.textContent); break; } catch(e) {}
        }

        return {
            title: getMeta('og:title') || document.title,
            description: getMeta('og:description') || '',
            url: getMeta('og:url') || '',
            jsonld: jsonld,
        };
    }""")

    title = info.get("title", page_name)
    desc = info.get("description", "")

    # Parsear followers/likes desde la pagina
    followers = _parse_fb_count(page, "followers") or _parse_fb_count(page, "seguidores")
    likes = _parse_fb_count(page, "likes") or _parse_fb_count(page, "me gusta")

    return PageInfo(
        page_id=page_name,
        name=title.split(" | ")[0].split(" - ")[0].strip(),
        description=desc[:500],
        followers=followers,
        likes=likes,
        url=info.get("url", f"https://www.facebook.com/{page_name}"),
    )


def _parse_fb_count(page: Page, keyword: str) -> int:
    """Busca un contador en la pagina de Facebook."""
    try:
        text = page.evaluate(f"""() => {{
            const spans = document.querySelectorAll('a span, div span');
            for (const s of spans) {{
                const t = s.textContent || '';
                if (t.toLowerCase().includes('{keyword}')) return t;
            }}
            return '';
        }}""")
        if not text:
            return 0
        match = re.search(r'([\d,.]+[KkMm]?)', text)
        if match:
            raw = match.group(1).replace(",", "").replace(".", "")
            if raw.upper().endswith("K"):
                return int(float(raw[:-1]) * 1000)
            elif raw.upper().endswith("M"):
                return int(float(raw[:-1]) * 1000000)
            return int(raw)
    except Exception:
        pass
    return 0


def _scroll_and_collect(page: Page, page_name: str, max_posts: int,
                        config: dict, save_progress: Path = None) -> list[DiscoveredPost]:
    """Scrollea la pagina de Facebook para descubrir posts."""
    collected = {}
    no_new_count = 0
    scroll_delay = config.get("rate_limits", {}).get("facebook", {}).get("scroll_delay", [2.0, 4.0])
    # Facebook carga posts muy lento (~3 posts cada 10 scrolls)
    # Necesita pre-scroll rapido para pasar la seccion de info/fotos
    max_stale_scrolls = 30

    # Pre-scroll: pasar rapido la seccion de info/fotos del sidebar
    print("  Pre-scroll: pasando seccion de info...")
    for _ in range(15):
        page.evaluate("window.scrollBy(0, 600)")
        time.sleep(0.8)

    for scroll_num in range(1, 500):
        links = page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            // Facebook usa multiples formatos de URL para posts:
            // 1. /stories/PAGE_ID/ENCODED_ID (posts del feed - timestamp links)
            // 2. /photo/?fbid=ID (fotos individuales)
            // 3. /posts/pfbid... (links compartidos)
            // 4. /videos/ID, /reel/ID, /watch/
            const anchors = document.querySelectorAll(
                'a[href*="/stories/"], a[href*="/posts/"], a[href*="/videos/"], ' +
                'a[href*="/photo/"], a[href*="/photo?"], a[href*="fbid="], ' +
                'a[href*="/reel/"], a[href*="story_fbid="], a[href*="/watch/"]'
            );

            for (const a of anchors) {
                const href = a.getAttribute('href') || '';

                // Filtrar links genericos
                if (href.endsWith('/photos') || href.endsWith('/photos/')) continue;
                if (href.includes('/photos_by') || href.includes('/photos_of')) continue;
                if (href.includes('reel/?s=tab')) continue;

                let postId = '';
                let isVideo = false;

                // /stories/PAGE_ID/ENCODED_POST_ID (main feed posts)
                let match = href.match(/\\/stories\\/[^/]+\\/([^/?]+)/);
                if (match) postId = match[1];

                // /photo/?fbid=ID  o  fbid=ID
                if (!postId) {
                    match = href.match(/fbid=([0-9]+)/);
                    if (match) postId = match[1];
                }

                // /posts/pfbid...
                if (!postId) {
                    match = href.match(/\\/posts\\/([a-zA-Z0-9]+)/);
                    if (match) postId = match[1];
                }

                // /videos/ID/
                if (!postId) {
                    match = href.match(/\\/videos\\/([0-9]+)/);
                    if (match) { postId = match[1]; isVideo = true; }
                }

                // /reel/ID/
                if (!postId) {
                    match = href.match(/\\/reel\\/([0-9]+)/);
                    if (match) { postId = match[1]; isVideo = true; }
                }

                // story_fbid=ID
                if (!postId) {
                    match = href.match(/story_fbid=([0-9]+)/);
                    if (match) postId = match[1];
                }

                // /watch/ (videos)
                if (!postId && href.includes('/watch/')) {
                    isVideo = true;
                    postId = 'watch_' + href.replace(/[^a-zA-Z0-9]/g, '').substring(0, 30);
                }

                if (!postId || seen.has(postId)) continue;
                seen.add(postId);

                let fullUrl = href;
                if (!fullUrl.startsWith('http')) {
                    fullUrl = 'https://www.facebook.com' + fullUrl;
                }
                // Limpiar tracking params
                try { fullUrl = fullUrl.split('&__cft__')[0]; } catch(e) {}

                results.push({
                    post_id: postId,
                    url: fullUrl,
                    is_video: isVideo,
                });
            }
            return results;
        }""")

        prev_count = len(collected)
        for link in links:
            pid = link["post_id"]
            if pid not in collected:
                collected[pid] = DiscoveredPost(
                    post_id=pid,
                    url=link["url"],
                    is_video=link.get("is_video", False),
                )

        new_found = len(collected) - prev_count
        target_str = str(max_posts) if max_posts > 0 else "?"
        print(f"  Scroll #{scroll_num}: {len(collected)}/{target_str} posts (+{new_found})", end="\r", flush=True)

        if max_posts > 0 and len(collected) >= max_posts:
            print(f"\n  Target alcanzado ({max_posts} posts)")
            break

        if new_found == 0:
            no_new_count += 1
            if no_new_count >= max_stale_scrolls:
                print(f"\n  Sin posts nuevos en {max_stale_scrolls} scrolls. Fin.")
                break
        else:
            no_new_count = 0

        if save_progress and len(collected) // 50 > prev_count // 50:
            _save_discovered(save_progress, list(collected.values()))

        rate_limit_batch(config, "facebook", len(collected))

        # Facebook carga posts uno por uno — scroll pequeno y constante
        page.evaluate(f"window.scrollBy(0, {random.randint(400, 700)})")
        if new_found == 0:
            time.sleep(random.uniform(1.5, 3.0))
        else:
            time.sleep(random.uniform(scroll_delay[0], scroll_delay[1]))

    posts = list(collected.values())
    if max_posts > 0:
        posts = posts[:max_posts]
    return posts


def _save_discovered(path: Path, posts: list[DiscoveredPost]):
    data = [{"post_id": p.post_id, "url": p.url, "is_video": p.is_video} for p in posts]
    save_json(path, data)


def load_discovered(path: Path) -> list[DiscoveredPost]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [DiscoveredPost(**d) for d in data]
