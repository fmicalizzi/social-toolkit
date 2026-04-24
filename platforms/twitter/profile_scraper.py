"""Scraper de perfiles de X (Twitter): navega al perfil, scrollea, extrae tweets."""

import re
import json
import time
import random
from pathlib import Path
from playwright.sync_api import Page

from platforms.twitter.models import TwitterProfile, DiscoveredTweet
from shared.rate_limiter import rate_limit_batch
from shared.output import save_json


def scrape_profile(page: Page, username: str, config: dict,
                   max_posts: int = 0,
                   save_progress: Path = None) -> tuple[TwitterProfile, list[DiscoveredTweet]]:
    """Navega al perfil de X, extrae info y descubre tweets.

    Args:
        page: Pagina Playwright
        username: Username sin @
        config: Config dict global
        max_posts: Limitar a N tweets (0 = todos)
        save_progress: Path para guardar tweets incrementalmente
    """
    url = f"https://x.com/{username}"
    print(f"Navegando a {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(4, 6))

    # X puede redirigir a login o mostrar wall
    if "/login" in page.url or "/i/flow/login" in page.url:
        raise RuntimeError("Redirigido a login. X requiere sesion para scraping.")

    # Extraer info del perfil
    profile = _extract_profile_header(page, username)
    print(f"Perfil: @{username} | {profile.full_name}")
    print(f"  Tweets: {profile.tweet_count:,} | Followers: {profile.followers:,} | Following: {profile.following:,}")

    # Scroll para descubrir tweets
    tweets = _scroll_and_collect(page, username, max_posts, config, save_progress)

    if save_progress and tweets:
        _save_discovered(save_progress, tweets)

    print(f"\nDescubiertos: {len(tweets)} tweets")
    return profile, tweets


def _extract_profile_header(page: Page, username: str) -> TwitterProfile:
    """Extrae datos del header del perfil de X."""
    info = page.evaluate("""() => {
        const getText = (sel) => {
            const el = document.querySelector(sel);
            return el ? el.textContent.trim() : '';
        };

        const getMeta = (name) => {
            const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
            return el ? el.getAttribute('content') : '';
        };

        // Nombre y bio
        const nameEl = document.querySelector('[data-testid="UserName"]');
        let name = '', handle = '';
        if (nameEl) {
            const spans = nameEl.querySelectorAll('span');
            if (spans.length > 0) name = spans[0].textContent || '';
        }

        const bioEl = document.querySelector('[data-testid="UserDescription"]');
        const bio = bioEl ? bioEl.textContent.trim() : '';

        // Contadores
        const counters = {};
        const links = document.querySelectorAll('a[href*="/followers"], a[href*="/following"], a[href*="/verified_followers"]');
        for (const a of links) {
            const t = a.textContent || '';
            if (a.href.includes('/following')) {
                const m = t.match(/([\\d,.]+[KkMm]?)/);
                if (m) counters.following = m[1];
            } else if (a.href.includes('/followers')) {
                const m = t.match(/([\\d,.]+[KkMm]?)/);
                if (m) counters.followers = m[1];
            }
        }

        return {
            name: name,
            bio: bio,
            description: getMeta('og:description') || '',
            followers: counters.followers || '0',
            following: counters.following || '0',
        };
    }""")

    # Parsear tweet count desde og:description
    desc = info.get("description", "")
    tweet_count = 0
    tc_match = re.search(r'([\d,.]+[KkMm]?)\s*(?:posts?|tweets?)', desc, re.IGNORECASE)
    if tc_match:
        tweet_count = _parse_x_count(tc_match.group(1))

    return TwitterProfile(
        username=username,
        full_name=info.get("name", ""),
        bio=info.get("bio", "")[:500],
        followers=_parse_x_count(info.get("followers", "0")),
        following=_parse_x_count(info.get("following", "0")),
        tweet_count=tweet_count,
        url=f"https://x.com/{username}",
    )


def _parse_x_count(text: str) -> int:
    """Parsea contadores de X: '1.2M', '45.6K', '1,234'."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    multiplier = 1
    if text.upper().endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.upper().endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def _scroll_and_collect(page: Page, username: str, max_posts: int,
                        config: dict, save_progress: Path = None) -> list[DiscoveredTweet]:
    """Scrollea el timeline del perfil para descubrir tweets."""
    collected = {}
    no_new_count = 0
    scroll_delay = config.get("rate_limits", {}).get("twitter", {}).get("scroll_delay", [1.5, 3.0])

    for scroll_num in range(1, 500):
        links = page.evaluate("""(username) => {
            const results = [];
            const seen = new Set();

            // Tweets aparecen como <a href="/username/status/ID">
            const anchors = document.querySelectorAll('a[href*="/status/"]');
            for (const a of anchors) {
                const href = a.getAttribute('href') || '';
                const match = href.match(/\\/status\\/(\\d+)/);
                if (!match) continue;

                const tweetId = match[1];
                if (seen.has(tweetId)) continue;
                seen.add(tweetId);

                // Verificar que es del usuario correcto (no retweets en timeline)
                const isOwn = href.toLowerCase().includes('/' + username.toLowerCase() + '/status/');

                // Detectar video
                const article = a.closest('article');
                const hasVideo = article ? (
                    article.querySelector('video') !== null ||
                    article.querySelector('[data-testid="videoPlayer"]') !== null
                ) : false;

                if (isOwn) {
                    results.push({
                        tweet_id: tweetId,
                        url: 'https://x.com' + href,
                        is_video: hasVideo,
                    });
                }
            }
            return results;
        }""", username)

        prev_count = len(collected)
        for link in links:
            tid = link["tweet_id"]
            if tid not in collected:
                collected[tid] = DiscoveredTweet(
                    tweet_id=tid,
                    url=link["url"],
                    is_video=link.get("is_video", False),
                )

        new_found = len(collected) - prev_count
        target_str = str(max_posts) if max_posts > 0 else "?"
        print(f"  Scroll #{scroll_num}: {len(collected)}/{target_str} tweets (+{new_found})", end="\r", flush=True)

        if max_posts > 0 and len(collected) >= max_posts:
            print(f"\n  Target alcanzado ({max_posts} tweets)")
            break

        if new_found == 0:
            no_new_count += 1
            if no_new_count >= 10:
                print(f"\n  Sin tweets nuevos en 10 scrolls. Fin.")
                break
        else:
            no_new_count = 0

        if save_progress and len(collected) // 50 > prev_count // 50:
            _save_discovered(save_progress, list(collected.values()))

        rate_limit_batch(config, "twitter", len(collected))

        page.evaluate("window.scrollBy(0, window.innerHeight)")
        if new_found == 0:
            time.sleep(random.uniform(scroll_delay[1], scroll_delay[1] + 1.5))
        else:
            time.sleep(random.uniform(scroll_delay[0], scroll_delay[1]))

    tweets = list(collected.values())
    if max_posts > 0:
        tweets = tweets[:max_posts]
    return tweets


def _save_discovered(path: Path, tweets: list[DiscoveredTweet]):
    data = [{"tweet_id": t.tweet_id, "url": t.url, "is_video": t.is_video} for t in tweets]
    save_json(path, data)


def load_discovered(path: Path) -> list[DiscoveredTweet]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [DiscoveredTweet(**d) for d in data]
