# Social Media Toolkit — Agent Instructions

## Repository documentation map

| File | Audience | Contents |
|------|----------|----------|
| [`README.md`](./README.md) | Human users | Installation, first use, commands, troubleshooting |
| [`AI_CONTEXT.md`](./AI_CONTEXT.md) | AI agents | Full architecture, pipeline, design rules, extension guide |

**Before any technical task**: read `AI_CONTEXT.md` in full.
**If asked about how to use the toolkit**: refer to `README.md`.

---

## Summary

Python CLI toolkit for scraping and downloading content from social media. Five platforms: Instagram, Facebook, TikTok, YouTube, Twitter.

**Entry point**: `cli.py` → `platforms/{platform}/snapshot.py`

**Key invariant**: every operation is idempotent. Every phase has a checkpoint. Never break this.

**Media download order**: cache extraction first → browser-based image fetch → yt-dlp for videos. Never skip or reorder layers.

## Task guidelines

When asked to **add a platform**: follow the template in `AI_CONTEXT.md` exactly.

When asked to **fix a scraper**: selectors are isolated in a single function in `post_scraper.py` — change only there.

When asked to **change output format**: modify `STANDARD_FIELDS` in `shared/output.py` and all `to_csv_row()` methods that need the field.

When asked to **improve media download**: work inside `shared/media_downloader.py`. Preserve the three-layer strategy and `_post_mapping.json` generation.

When asked to **update docs**: usage content goes in `README.md`, architecture content goes in `AI_CONTEXT.md`. Never duplicate between them.

## Do not

- Break idempotency (checkpoints, skip-if-exists logic)
- Open multiple Playwright browser contexts against the same `browser_profile/`
- Hardcode rate limit values — read from `config["rate_limits"][platform][key]`
- Add platform-specific CSV columns without updating `STANDARD_FIELDS`
- Duplicate content between `README.md` and `AI_CONTEXT.md`
