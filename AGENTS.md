# Social Media Toolkit — Agent Instructions

**Read first:**
→ [`AI_CONTEXT.md`](./AI_CONTEXT.md) — full architecture, pipeline, design rules, extension guide

---

## Summary for agents

This is a Python CLI toolkit for scraping and downloading content from social media profiles. Five platforms implemented: Instagram, Facebook, TikTok, YouTube, Twitter.

**Entry point**: `cli.py` dispatches to `platforms/{platform}/snapshot.py`

**Key invariant**: every operation is idempotent. Checkpoints exist at every phase. Agents must not break this.

**Media download order**: always cache extraction first (`extract_from_cache`) → browser-based image fetch → yt-dlp for videos. Never reverse or skip layers.

## Task guidelines

When asked to **add a platform**: follow the template in `AI_CONTEXT.md` exactly.

When asked to **fix a scraper**: selectors live in `post_scraper.py` isolated in a single function — change only there.

When asked to **change output format**: modify `STANDARD_FIELDS` in `shared/output.py` and all `to_csv_row()` methods that need the new field.

When asked to **improve media download**: work inside `shared/media_downloader.py`. The three-layer strategy and `_post_mapping.json` generation must be preserved.

## Do not

- Break idempotency (checkpoints, skip-if-exists logic)
- Open multiple Playwright browser contexts simultaneously against the same `browser_profile/`
- Hardcode rate limit values — read from `config["rate_limits"][platform][key]`
- Add platform-specific CSV columns without updating `STANDARD_FIELDS`
