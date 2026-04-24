"""Scraper de tweets individuales de X: metadata + engagement."""

import re
import time
import random
from typing import Optional
from playwright.sync_api import Page

from platforms.twitter.models import Tweet
from shared.utils import timestamp_iso


def scrape_tweet(page: Page, tweet_id: str, tweet_url: str,
                 config: dict) -> Optional[dict]:
    """Navega a un tweet individual y extrae metadata.

    Returns:
        dict con campos de Tweet, o None si falla.
    """
    try:
        page.goto(tweet_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(3, 5))

        if "/login" in page.url or "/i/flow/login" in page.url:
            return None

        # Extraer OG meta + DOM
        meta = page.evaluate("""() => {
            const get = (name) => {
                const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                return el ? el.getAttribute('content') : '';
            };
            return {
                title: get('og:title'),
                description: get('og:description'),
                url: get('og:url'),
            };
        }""")

        if not meta:
            return None

        title = meta.get("title", "")
        description = meta.get("description", "")
        og_url = meta.get("url", tweet_url)

        # Username: "Full Name on X: ..." o "Full Name (@handle) on X"
        username = ""
        full_name = ""
        name_match = re.match(r'(.+?)\s+(?:on X|on Twitter)', title)
        if name_match:
            full_name = name_match.group(1).strip()
            # Si tiene (@handle), extraer
            handle_match = re.search(r'\(@(\w+)\)', full_name)
            if handle_match:
                username = handle_match.group(1)
                full_name = full_name.split("(")[0].strip()

        # Caption: el texto del tweet viene en og:description
        caption = description.strip('"').strip()

        # Hashtags
        hashtags = re.findall(r'#(\w+)', caption)

        # Engagement desde el DOM
        engagement = _extract_engagement(page)

        # Date desde el DOM (X muestra la fecha en un <time> element)
        date = _extract_date(page)

        # Detectar video
        is_video = page.evaluate("""() => {
            return document.querySelector('video') !== null ||
                   document.querySelector('[data-testid="videoPlayer"]') !== null;
        }""")

        content_type = "video" if is_video else "tweet"

        tweet = Tweet(
            tweet_id=tweet_id,
            url=og_url or tweet_url,
            username=username,
            full_name=full_name,
            date=date,
            content_type=content_type,
            is_video=is_video,
            likes=engagement.get("likes"),
            comments=engagement.get("comments"),
            views=engagement.get("views"),
            shares=engagement.get("retweets"),
            hashtags=", ".join(hashtags[:15]),
            caption=caption[:500].replace("\n", " "),
            scraped_at=timestamp_iso(),
        )

        return tweet.to_csv_row()

    except Exception as e:
        print(f"  [err] {tweet_id}: {e}")
        return None


def _extract_engagement(page: Page) -> dict:
    """Extrae likes, replies, retweets, views del DOM de X."""
    result = {"likes": None, "comments": None, "views": None, "retweets": None}

    try:
        data = page.evaluate("""() => {
            const result = {};

            // X usa aria-label en los botones de engagement
            // "N Likes", "N replies", "N reposts", "N views"
            const groups = document.querySelectorAll('[role="group"]');
            for (const g of groups) {
                const buttons = g.querySelectorAll('button, a');
                for (const btn of buttons) {
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();

                    const numMatch = label.match(/(\\d[\\d,.]*[KkMm]?)/);
                    if (!numMatch) continue;
                    const num = numMatch[1];

                    if (label.includes('like')) result.likes = num;
                    else if (label.includes('repl')) result.comments = num;
                    else if (label.includes('repost') || label.includes('retweet')) result.retweets = num;
                    else if (label.includes('view')) result.views = num;
                    else if (label.includes('bookmark')) {} // ignore
                }
            }

            return result;
        }""")

        for key in ("likes", "comments", "views", "retweets"):
            if data.get(key):
                result[key] = _parse_metric(data[key])

    except Exception:
        pass

    return result


def _extract_date(page: Page) -> str:
    """Extrae la fecha del tweet desde el elemento <time>."""
    try:
        date = page.evaluate("""() => {
            // X pone <time datetime="2023-03-15T..."> en tweets
            const timeEl = document.querySelector('article time, [data-testid="tweet"] time');
            if (timeEl) {
                const dt = timeEl.getAttribute('datetime');
                if (dt) return dt.substring(0, 10);
            }
            return '';
        }""")
        return date or ""
    except Exception:
        return ""


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
