"""Scraper de posts individuales de Facebook: metadata + engagement.

Facebook obfusca engagement en el feed, pero los posts individuales
exponen mas datos via OG meta + aria-labels + DOM text nodes.
"""

import re
import time
import random
from typing import Optional
from playwright.sync_api import Page

from platforms.facebook.models import FacebookPost
from shared.utils import timestamp_iso


def scrape_post(page: Page, post_id: str, post_url: str,
                config: dict) -> Optional[dict]:
    """Navega a un post individual y extrae metadata.

    Returns:
        dict con campos de FacebookPost, o None si falla.
    """
    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(random.uniform(3, 6))

        if "login" in page.url and "checkpoint" not in page.url:
            return None

        # Intentar hacer click en "Ver mas" / "See more" para expandir caption
        try:
            see_more = page.query_selector(
                '[role="button"]:has-text("Ver más"), '
                '[role="button"]:has-text("See more"), '
                'div[dir="auto"] span:has-text("Ver más"), '
                'div[dir="auto"] span:has-text("See more")'
            )
            if see_more:
                see_more.click()
                time.sleep(1)
        except Exception:
            pass

        meta = page.evaluate("""() => {
            const get = (name) => {
                const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                return el ? el.getAttribute('content') : '';
            };
            let jsonld = null;
            for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                try { jsonld = JSON.parse(s.textContent); break; } catch(e) {}
            }
            return {
                title: get('og:title'),
                description: get('og:description'),
                published: get('article:published_time'),
                url: get('og:url'),
                type: get('og:type'),
                jsonld: jsonld,
            };
        }""")

        if not meta:
            return None

        title = meta.get("title", "")
        description = meta.get("description", "")
        published = (meta.get("published") or "")[:10]
        og_url = meta.get("url", post_url)
        jsonld = meta.get("jsonld") or {}

        # Username desde title
        username = ""
        if " - " in title:
            username = title.split(" - ")[0].strip()
        elif " | " in title:
            username = title.split(" | ")[0].strip()

        # Date: try multiple sources
        if not published and isinstance(jsonld, dict):
            published = (jsonld.get("datePublished") or jsonld.get("dateCreated") or "")[:10]
        if not published:
            published = _extract_date_from_dom(page)

        # Caption: try DOM first (expanded), fallback to og:description
        caption = _extract_caption_from_dom(page) or description or title

        # Hashtags
        hashtags = re.findall(r'#(\w+)', caption)

        # Content type
        is_video = _detect_video(page, post_url)
        content_type = "video" if is_video else "post"

        # Engagement desde el DOM (multiple strategies)
        engagement = _extract_engagement(page)

        post = FacebookPost(
            post_id=post_id,
            url=og_url or post_url,
            username=username,
            date=published,
            content_type=content_type,
            is_video=is_video,
            likes=engagement.get("likes"),
            comments=engagement.get("comments"),
            views=engagement.get("views"),
            shares=engagement.get("shares"),
            hashtags=", ".join(hashtags[:15]),
            caption=caption[:500].replace("\n", " "),
            scraped_at=timestamp_iso(),
        )

        return post.to_csv_row()

    except Exception as e:
        print(f"  [err] {post_id}: {e}")
        return None


def _extract_caption_from_dom(page: Page) -> str:
    """Extrae el texto completo del post desde el DOM."""
    try:
        text = page.evaluate("""() => {
            // Facebook pone el caption en divs con dir="auto" y data-ad-preview="message"
            // o en el primer div largo dentro del article/post container

            // Strategy 1: data-ad-preview="message"
            const adPreview = document.querySelector('[data-ad-preview="message"]');
            if (adPreview && adPreview.textContent.length > 10) {
                return adPreview.textContent.trim();
            }

            // Strategy 2: Find the post text container
            // It's usually a div[dir="auto"] with substantial text inside an article
            const articles = document.querySelectorAll('[role="article"], [data-pagelet*="FeedUnit"]');
            for (const art of articles) {
                const divs = art.querySelectorAll('div[dir="auto"]');
                let longest = '';
                for (const d of divs) {
                    const t = d.textContent || '';
                    if (t.length > longest.length && t.length > 20) {
                        // Skip if it's just a link or button text
                        if (!t.startsWith('http') && !t.includes('Me gusta') && !t.includes('Comentar')) {
                            longest = t;
                        }
                    }
                }
                if (longest.length > 20) return longest.trim();
            }

            // Strategy 3: Just find the longest text in any div[dir="auto"]
            const allDivs = document.querySelectorAll('div[dir="auto"]');
            let best = '';
            for (const d of allDivs) {
                const t = d.textContent || '';
                if (t.length > best.length && t.length > 20 && t.length < 5000) {
                    if (!t.includes('Iniciar sesión') && !t.includes('Crear cuenta')) {
                        best = t;
                    }
                }
            }
            return best.trim();
        }""")
        return text or ""
    except Exception:
        return ""


def _extract_date_from_dom(page: Page) -> str:
    """Extrae fecha del DOM de Facebook."""
    try:
        date = page.evaluate("""() => {
            // Strategy 1: abbr or time elements with timestamp
            const timeEls = document.querySelectorAll('abbr[data-utime], time[datetime]');
            for (const el of timeEls) {
                const utime = el.getAttribute('data-utime');
                if (utime) {
                    const d = new Date(parseInt(utime) * 1000);
                    return d.toISOString().substring(0, 10);
                }
                const dt = el.getAttribute('datetime');
                if (dt) return dt.substring(0, 10);
            }

            // Strategy 2: aria-label on timestamp links
            const links = document.querySelectorAll('a[href*="/posts/"], a[href*="/photos/"], a[href*="/videos/"]');
            for (const a of links) {
                const label = a.getAttribute('aria-label') || '';
                // Match date patterns in aria-label
                const dateMatch = label.match(/(\\d{4})-(\\d{2})-(\\d{2})/);
                if (dateMatch) return dateMatch[0];
            }

            // Strategy 3: Look for "N de MONTH de YEAR" text near the post header
            const allText = document.body.innerText;
            const match = allText.match(/(\\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) de (\\d{4})/i);
            if (match) return match[0];

            return '';
        }""")
        if date and re.match(r'\d{4}-\d{2}-\d{2}', date):
            return date
        return _parse_spanish_date(date) if date else ""
    except Exception:
        return ""


def _parse_spanish_date(text: str) -> str:
    """Parsea '15 de marzo de 2025' a '2025-03-15'."""
    months = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    m = re.match(r'(\d{1,2}) de (\w+) de (\d{4})', text)
    if m:
        day, month, year = int(m.group(1)), months.get(m.group(2).lower(), 0), int(m.group(3))
        if month:
            return f"{year}-{month:02d}-{day:02d}"
    return ""


def _detect_video(page: Page, url: str) -> bool:
    """Detecta si el post es un video."""
    if any(x in url for x in ["/videos/", "/reel/", "/watch/"]):
        return True
    try:
        return page.evaluate("""() => {
            return document.querySelector('video') !== null ||
                   document.querySelector('[data-pagelet*="video"]') !== null;
        }""")
    except Exception:
        return False


def _extract_engagement(page: Page) -> dict:
    """Extrae likes, comments, shares, views del DOM de Facebook.

    Usa multiples estrategias porque Facebook varia la estructura.
    """
    result = {"likes": None, "comments": None, "views": None, "shares": None}

    try:
        data = page.evaluate("""() => {
            const result = {};

            // === Strategy 1: aria-labels (most reliable) ===
            // "Me gusta: N personas" on the reactions button
            const allElements = document.querySelectorAll('[aria-label]');
            for (const el of allElements) {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();

                // Likes/reactions: "me gusta: N personas"
                let match = label.match(/me gusta:\\s*(\\d[\\d.,]*\\s*(?:mil|k|m)?)/i);
                if (match && !result.likes) {
                    result.likes = match[1].trim();
                    continue;
                }
                // English: "N people reacted"
                match = label.match(/(\\d[\\d.,]*\\s*(?:k|m)?)\\s*(?:people|person)/i);
                if (match && !result.likes) {
                    result.likes = match[1].trim();
                    continue;
                }
            }

            // === Strategy 2: Visible text patterns ===
            const spans = document.querySelectorAll('span');
            for (const s of spans) {
                const t = (s.textContent || '').trim();
                if (t.length > 80) continue;

                // Comments: "N comentarios" or "N comments"
                let cm = t.match(/(\\d[\\d.,]*\\s*(?:mil|k|m)?)\\s*(?:comentarios?|comments?)/i);
                if (cm && !result.comments) {
                    result.comments = cm[1].trim();
                }

                // Shares: "N veces compartido" or "N shares"
                let sh = t.match(/(\\d[\\d.,]*\\s*(?:mil|k|m)?)\\s*(?:veces? compartido|shares?)/i);
                if (sh && !result.shares) {
                    result.shares = sh[1].trim();
                }

                // Views: "N visualizaciones" or "N reproducciones" or "N views"
                let vw = t.match(/(\\d[\\d.,]*\\s*(?:mil|k|m)?)\\s*(?:visualizaciones?|reproducciones?|views?)/i);
                if (vw && !result.views) {
                    result.views = vw[1].trim();
                }

                // Standalone number near reaction emoji (fallback for likes)
                if (!result.likes && /^\\d[\\d.,]*$/.test(t)) {
                    // Check if parent/sibling has reaction images
                    const parent = s.parentElement;
                    if (parent) {
                        const hasEmoji = parent.querySelector('img[src*="emoji"], img[alt*="like"], img[alt*="gusta"]');
                        if (hasEmoji) result.likes = t;
                    }
                }
            }

            // === Strategy 3: Specific Facebook engagement bar selectors ===
            // The engagement bar usually has a specific structure
            const engagementBar = document.querySelector('[aria-label*="reacciones"], [aria-label*="reactions"]');
            if (engagementBar && !result.likes) {
                const text = engagementBar.textContent.trim();
                const numMatch = text.match(/(\\d[\\d.,]*)/);
                if (numMatch) result.likes = numMatch[1];
            }

            return result;
        }""")

        for key in ("likes", "comments", "views", "shares"):
            if data.get(key):
                result[key] = _parse_metric(data[key])

    except Exception:
        pass

    return result


def _parse_metric(raw: str) -> Optional[int]:
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
