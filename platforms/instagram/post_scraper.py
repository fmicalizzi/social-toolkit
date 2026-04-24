"""Scraper de posts individuales de Instagram: metadata + engagement metrics."""

import re
import time
import random
from typing import Optional
from playwright.sync_api import Page

from platforms.instagram.models import InstagramPost
from shared.utils import timestamp_iso

# ── Selectores DOM para engagement (actualizar cuando Instagram cambie) ──
# Estos selectores se usan para extraer likes/views/comments del DOM renderizado.
# Instagram cambia su HTML frecuentemente — si dejan de funcionar, actualizar aqui.
SELECTORS = {
    "likes_section": 'section span, a[href*="liked_by"] span, button[type="button"] span',
    "views_text": '[role="button"] span, span',
    "comments_link": 'a[href*="/comments/"] span, a span',
}


def scrape_post(page: Page, shortcode: str, config: dict) -> Optional[dict]:
    """Navega a un post individual y extrae metadata completa.

    Extrae de:
    1. OG meta tags (og:title, og:description, article:published_time)
    2. JSON-LD structured data
    3. DOM elements para engagement metrics (likes, comments, views)

    Returns:
        dict con campos de InstagramPost, o None si falla.
    """
    url = f"https://www.instagram.com/p/{shortcode}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2, 4))

        # Si redirige a login, abortar
        if "login" in page.url:
            return None

        # Extraer metadata base desde OG tags + JSON-LD
        meta = _extract_meta_tags(page)
        if not meta:
            return None

        title = meta.get("title", "")
        description = meta.get("description", "")
        published = (meta.get("published") or "")[:10]
        og_url = meta.get("url", "")
        jsonld = meta.get("jsonld") or {}

        # Username
        username = _extract_username(title, jsonld)

        # Date: from meta tag, JSON-LD, or og:description
        if not published:
            published = (jsonld.get("uploadDate") or jsonld.get("datePublished") or "")[:10]
        if not published:
            published = _extract_date_from_description(description)

        # Caption y hashtags — extract from inside quotes in og:description
        caption = _extract_caption_from_description(description) \
                  or jsonld.get("description", "") or description or title
        hashtags = re.findall(r'#(\w+)', caption)

        # Content type
        content_type = "reel" if "/reel/" in (og_url or page.url) else "post"

        # Engagement metrics (del DOM)
        engagement = _extract_engagement(page, description)

        if not username and not caption:
            return None

        post = InstagramPost(
            shortcode=shortcode,
            url=og_url or f"https://www.instagram.com/p/{shortcode}/",
            username=username,
            date=published,
            content_type=content_type,
            is_video=content_type in ("reel", "video") or bool(jsonld.get("video")),
            likes=engagement.get("likes"),
            comments=engagement.get("comments"),
            views=engagement.get("views"),
            location=_extract_location(jsonld),
            hashtags=", ".join(hashtags[:15]),
            caption=caption[:500].replace("\n", " "),
            scraped_at=timestamp_iso(),
        )

        return post.to_csv_row()

    except Exception as e:
        print(f"  [err] {shortcode}: {e}")
        return None


def _extract_meta_tags(page: Page) -> Optional[dict]:
    """Extrae OG meta tags y JSON-LD de la pagina."""
    try:
        return page.evaluate("""() => {
            const get = (name) => {
                const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                return el ? el.getAttribute('content') : '';
            };
            let jsonld = null;
            for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                try { jsonld = JSON.parse(s.textContent); break; } catch(e) {}
            }
            return {
                title:       get('og:title'),
                description: get('og:description'),
                published:   get('article:published_time'),
                url:         get('og:url'),
                type:        get('og:type'),
                jsonld:      jsonld,
            };
        }""")
    except Exception:
        return None


def _extract_username(title: str, jsonld: dict) -> str:
    """Extrae username desde og:title o JSON-LD."""
    username = ""
    if " on Instagram" in title:
        username = title.split(" on Instagram")[0].strip()
    elif " en Instagram" in title:
        username = title.split(" en Instagram")[0].strip()
    else:
        author = jsonld.get("author", {})
        if isinstance(author, dict):
            u = author.get("url", "")
            username = u.strip("/").split("/")[-1] if u else author.get("name", "")
    return username


def _extract_engagement(page: Page, og_description: str) -> dict:
    """Extrae likes, comments y views del DOM renderizado y de og:description.

    og:description suele contener cosas como:
    - "41K likes, 724 comments"
    - "1.2M views"
    """
    result = {"likes": None, "comments": None, "views": None}

    # Primero intentar parsear desde og:description (mas confiable)
    if og_description:
        likes_match = re.search(r'([\d,.]+[KkMm]?)\s*likes?', og_description)
        if likes_match:
            result["likes"] = _parse_metric(likes_match.group(1))

        comments_match = re.search(r'([\d,.]+[KkMm]?)\s*comments?', og_description)
        if comments_match:
            result["comments"] = _parse_metric(comments_match.group(1))

        views_match = re.search(r'([\d,.]+[KkMm]?)\s*views?', og_description)
        if views_match:
            result["views"] = _parse_metric(views_match.group(1))

    # Si no se encontraron en og:description, intentar del DOM
    if result["likes"] is None:
        try:
            likes_text = page.evaluate("""() => {
                // Buscar en el area de likes
                const btns = document.querySelectorAll('section button, section a[href*="liked_by"]');
                for (const btn of btns) {
                    const text = btn.textContent || '';
                    const match = text.match(/(\\d[\\d,.]*[KkMm]?)\\s*(likes?|me gusta)/i);
                    if (match) return match[1];
                }
                return null;
            }""")
            if likes_text:
                result["likes"] = _parse_metric(likes_text)
        except Exception:
            pass

    if result["views"] is None:
        try:
            views_text = page.evaluate("""() => {
                const spans = document.querySelectorAll('span');
                for (const s of spans) {
                    const text = s.textContent || '';
                    const match = text.match(/(\\d[\\d,.]*[KkMm]?)\\s*(views?|reproducciones|visualizaciones)/i);
                    if (match) return match[1];
                }
                return null;
            }""")
            if views_text:
                result["views"] = _parse_metric(views_text)
        except Exception:
            pass

    return result


def _parse_metric(raw: str) -> Optional[int]:
    """Parsea metricas como '41K', '1.2M', '1,234'."""
    if not raw:
        return None
    raw = raw.replace(",", "").strip()
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
        return None


def _extract_date_from_description(description: str) -> str:
    """Extrae fecha de og:description.

    Formatos comunes:
    - "... on January 15, 2023: ..."
    - "... el March 15, 2023: ..."
    - "... el 15 de marzo de 2023: ..."
    """
    if not description:
        return ""

    # English: "on January 15, 2023:" or "January 15, 2023:"
    match = re.search(
        r'(?:on\s+)?'
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d{1,2},\s*\d{4})',
        description
    )
    if match:
        from datetime import datetime
        try:
            dt = datetime.strptime(match.group(1), "%B %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Spanish: "el 15 de marzo de 2023"
    months_es = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }
    match = re.search(r'el\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', description, re.IGNORECASE)
    if match:
        day, month_name, year = match.group(1), match.group(2).lower(), match.group(3)
        month_num = months_es.get(month_name)
        if month_num:
            return f"{year}-{month_num:02d}-{int(day):02d}"

    return ""


def _extract_caption_from_description(description: str) -> str:
    """Extrae el caption real del og:description de Instagram.

    og:description tiene formato:
    "N likes, N comments - username on/el DATE: \"CAPTION\". "
    o sin quotes:
    "N likes, N comments - username on/el DATE: CAPTION"
    """
    if not description:
        return ""

    # Buscar el patron: despues de la fecha y ":"
    # El caption viene entre comillas despues de la fecha
    match = re.search(r'\d{4}:\s*"(.+)"', description, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Sin comillas: despues de "YYYY: "
    match = re.search(r'\d{4}:\s*(.+)', description, re.DOTALL)
    if match:
        text = match.group(1).strip().rstrip('"').strip()
        if text:
            return text

    return ""


def _extract_location(jsonld: dict) -> str:
    """Extrae ubicacion desde JSON-LD."""
    loc = jsonld.get("contentLocation", {})
    if isinstance(loc, dict):
        return loc.get("name", "")
    return ""
