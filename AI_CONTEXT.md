# Social Media Toolkit — Contexto para Agentes de IA

## Mapa de documentación del repositorio

| Archivo | Para quién | Contenido |
|---------|-----------|-----------|
| [`README.md`](./README.md) | Usuarios humanos | Instalación, primer uso, comandos, tiempos, troubleshooting |
| **`AI_CONTEXT.md`** (este archivo) | Agentes de IA | Arquitectura, pipeline, reglas de diseño, cómo extender |
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code | Apunta a este archivo + reglas específicas de Claude |
| [`AGENTS.md`](./AGENTS.md) | Codex / agentes generales | Apunta a este archivo + reglas para agentes |
| [`qwen.md`](./qwen.md) | Qwen y otros modelos | Apunta a este archivo + resumen ejecutivo |

**Regla**: contenido de uso va en `README.md`. Contenido de arquitectura va aquí. Sin duplicar entre los dos.

---

## Qué hace este toolkit

Extrae datos y media de perfiles en redes sociales mediante un pipeline de 5 fases:

```
Discovery → Metadata → CSV → Descarga de media → Conversión H.264
```

Plataformas: **Instagram · Facebook · TikTok · YouTube · X/Twitter**

Diseñado para ser portable, reanudable (idempotente) y extensible a nuevas plataformas.

---

## Mapa de archivos

### Raíz

| Archivo | Rol |
|---------|-----|
| `cli.py` | Entry point único. Argparse con subcomandos por plataforma. Delega a `platforms/*/snapshot.py` |
| `config.yaml` | Toda la configuración: browser, rate limits por plataforma, paths de binarios, output dir |
| `requirements.txt` | `playwright`, `yt-dlp`, `pyyaml` |
| `setup.sh` | Bootstrap idempotente. Acepta argumento opcional: path a browser_profile existente |

### `shared/` — Infraestructura reutilizable

| Archivo | Rol |
|---------|-----|
| `browser.py` | `BrowserContext`: context manager Playwright con perfil persistente. `ensure_logged_in()`: detecta redirección a login y pausa para login manual. `is_login_redirect()`: check inline |
| `config.py` | `load_config(path, root)`: carga config.yaml, resuelve `profile_dir` y `base_dir` relativos al root del toolkit |
| `media_downloader.py` | **Módulo central de descarga.** Ver sección "Pipeline de descarga" más abajo |
| `downloader.py` | `download_all()`: yt-dlp wrapper legacy, usado por Instagram para videos. La lógica nueva vive en `media_downloader.py` |
| `converter.py` | `convert_all(dir, config)`: detecta codec con ffprobe, convierte VP9/AV1/VP8 → H.264 con ffmpeg. Salta H.264 existentes |
| `cookies.py` | `export_cookies(config)`: extrae cookies del perfil de Chromium a formato Netscape (para yt-dlp) |
| `rate_limiter.py` | `rate_limit(config, platform, key)`: sleep aleatorio entre [min,max] del config. `rate_limit_batch(config, platform, i)`: pausa larga cada `batch_size` posts |
| `output.py` | `save_json()`, `load_all_metadata(dir)`, `write_csv(path, rows, fields)`. `STANDARD_FIELDS`: lista de columnas del CSV normalizado |
| `utils.py` | `today()`: fecha YYYY-MM-DD. `timestamp_iso()`: datetime ISO. `normalize_username()`: quita `@`. `sanitize()`: limpia caracteres para nombres de archivo |

### `platforms/{platform}/`

Cada plataforma tiene 4 archivos con el mismo patrón:

| Archivo | Rol |
|---------|-----|
| `models.py` | Dataclasses: `ProfileInfo`, `{Platform}Post`. Cada post tiene `.to_dict()` y `.to_csv_row()` |
| `profile_scraper.py` | Navega el perfil/canal, hace scroll, extrae IDs de posts. Exporta `scrape_profile(page, username, config, max_posts, save_progress)` y `load_discovered(path)` |
| `post_scraper.py` / `video_scraper.py` | Visita un post individual, extrae metadata: fecha, caption, hashtags, engagement. Exporta `scrape_{post|video|tweet}(page_or_id, ...)` |
| `snapshot.py` | Orquestador. Exporta `run_snapshot()`, `run_discover()`, `run_download()`. Opcionalmente `run_extract_cache()` (Facebook, Instagram) |

### `tests/`

Tests unitarios con `unittest`. No requieren browser ni red. Cubren: config loading, models, output CSV/JSON, rate limiter, utils, scrapers (con mocks).

---

## El pipeline en detalle

### Fase 1: Discovery

`profile_scraper.py` abre el browser, navega al perfil, hace scroll del feed/grid y extrae IDs de posts. Guarda progreso en `discovered.json` cada `batch_size` items. Si el archivo ya existe al iniciar, se salta esta fase.

```python
# discovered.json guarda objetos con al menos:
{"post_id": "ABC123", "url": "https://...", "is_video": False}
```

### Fase 2: Metadata

`post_scraper.py` visita cada post individualmente. Extrae:
- **OG meta tags**: `og:title`, `og:description`, `article:published_time`, `og:image`
- **JSON-LD**: `datePublished`, `author`, `description`
- **DOM**: likes, comments, views, shares vía aria-labels y selectores CSS
- **Caption expandida**: click en "Ver más"/"See more" antes de extraer

Guarda `metadata/{post_id}.json`. Si el archivo existe, lo salta.

### Fase 3: CSV

`load_all_metadata()` lee todos los JSONs de `metadata/`. `write_csv()` los consolida en `snapshot_YYYY-MM-DD.csv` con `STANDARD_FIELDS`.

### Fase 4: Descarga de media

Ver sección "Pipeline de descarga" más abajo. Guarda en `media/`.

### Fase 5: Conversión

`convert_all()` detecta codec con ffprobe. Convierte solo lo que no es H.264. En sitio (sobreescribe) o en directorio, según config.

---

## Pipeline de descarga — `shared/media_downloader.py`

Este es el módulo más sofisticado. Tres capas, en orden de eficiencia:

### Capa 1: `extract_from_cache(browser_profile_dir, media_dir, platform_filter)`

Escanea `browser_profile/Default/Cache/Cache_Data/`. Cada archivo del cache de Chromium contiene los headers HTTP del response seguidos del body (la imagen). Se detecta el JPEG por magic bytes `\xff\xd8\xff`.

Filtros por plataforma (definidos en `PLATFORM_FILTERS` dentro de la función):
- **facebook**: URLs con `/t39.30808-6/` (fotos de posts de alta resolución)
- **instagram**: URLs con `cdninstagram`, tamaño mínimo 50KB (filtra thumbnails)

**Si `media/` ya tiene archivos, no re-extrae** (idempotente). Genera `_cache_manifest.json`.

Resultado típico: Facebook recupera 90%+ de fotos sin ninguna request HTTP.

### Capa 2: `download_image_via_browser(page, post_url, post_id, media_dir, date, platform, existing_filenames)`

Para cada post pendiente:
1. Navega a la URL del post
2. Extrae `og:image` (la URL CDN de la imagen)
3. Extrae el CDN filename de la URL (ej: `482264750_1040926_...jpg`)
4. Si ese CDN filename ya existe en `media/` → **no descarga**, guarda el mapping en `_post_mapping.json` y retorna True
5. Si no existe → descarga con `urllib.request`

**Esto resuelve el problema de que las fotos del cache tienen nombres CDN, no post_ids.** El browser visita el post para resolver la identidad, pero solo descarga cuando es estrictamente necesario.

### Capa 3: `download_video_via_ytdlp(url, post_id, media_dir, config, date, cookies)`

yt-dlp con `--merge-output-format mp4`. Cookies opcionales según plataforma (Facebook e Instagram las requieren, YouTube y TikTok no).

### Orquestador: `download_missing_media(posts, media_dir, config, page, platform, rate_delay, also_check_dirs)`

- Construye inventario de todo lo que ya existe con `_build_inventory([media_dir] + also_check_dirs)`
- `also_check_dirs` permite incluir `videos/` (directorio legacy) para no re-descargar lo que ya existe en otra carpeta
- Para cada post: check rápido por `post_id` en nombre de archivo → si no, usar capa 2 o 3
- Genera reporte: ok, skipped, failed, actually_downloaded

---

## Reglas de diseño (no romper)

1. **Idempotencia antes que velocidad**: Cada fase debe poder interrumpirse y reanudarse sin perder trabajo ni duplicar requests.

2. **Cache primero**: Antes de cualquier request HTTP, revisar si el contenido ya está en `browser_profile/Cache/`. Es gratis.

3. **Nunca asumir que `post_id` aparece en el nombre del archivo de cache**: Los CDN filenames no contienen post_ids. La resolución se hace via og:image en el browser. Guardar el mapping en `_post_mapping.json`.

4. **Rate limiting siempre**: Todo loop de requests usa `rate_limit()` y `rate_limit_batch()`. Los valores están en `config.yaml`, no hardcodeados.

5. **`also_check_dirs` en download**: Siempre pasar los directorios legacy (`videos/`) para no re-descargar. La lista de directorios a revisar puede crecer con el tiempo.

6. **Un solo `BrowserContext` por proceso**: Playwright tiene estado compartido. No abrir múltiples contextos en paralelo con el mismo `browser_profile/`.

7. **Separar discovery de metadata**: Discovery es scroll rápido (extrae IDs), metadata es visita post por post (más lenta, más datos). Nunca mezclarlos en el mismo loop.

8. **CSV con `STANDARD_FIELDS`**: Los campos del CSV son fijos y compartidos entre plataformas. Si un campo no aplica a una plataforma, va como `None`. No agregar columnas plataforma-específicas al CSV sin actualizar `STANDARD_FIELDS`.

---

## Cómo agregar una nueva plataforma

### Paso 1: Estructura de archivos

```bash
mkdir platforms/linkedin
touch platforms/linkedin/__init__.py
# Crear: models.py, profile_scraper.py, post_scraper.py, snapshot.py
```

### Paso 2: `models.py`

```python
from dataclasses import dataclass, field
from typing import Optional
from shared.utils import today, timestamp_iso

@dataclass
class LinkedInPost:
    post_id: str
    url: str
    username: str = ""
    date: str = ""
    content_type: str = "post"  # post, article, video
    is_video: bool = False
    likes: Optional[int] = None
    comments: Optional[int] = None
    views: Optional[int] = None
    shares: Optional[int] = None
    hashtags: str = ""
    caption: str = ""
    scraped_at: str = field(default_factory=timestamp_iso)

    def to_dict(self):
        return {**self.__dict__}

    def to_csv_row(self):
        return {
            "platform": "linkedin",
            "shortcode": self.post_id,
            "url": self.url,
            "username": self.username,
            "date": self.date,
            "content_type": self.content_type,
            "is_video": self.is_video,
            "likes": self.likes,
            "comments": self.comments,
            "views": self.views,
            "shares": self.shares,
            "hashtags": self.hashtags,
            "caption": self.caption,
            "scraped_at": self.scraped_at,
        }
```

### Paso 3: `snapshot.py` — patrón mínimo

```python
from pathlib import Path
from shared.browser import BrowserContext
from shared.media_downloader import extract_from_cache, download_missing_media
from shared.converter import convert_all
from shared.output import save_json, load_all_metadata, write_csv, STANDARD_FIELDS
from shared.rate_limiter import rate_limit, rate_limit_batch
from shared.utils import today, normalize_username
from platforms.linkedin.profile_scraper import scrape_profile, load_discovered
from platforms.linkedin.post_scraper import scrape_post

def run_snapshot(username: str, config: dict, no_download=False, no_convert=False, max_posts=0):
    username = normalize_username(username)
    output_dir = Path(config["output"]["base_dir"]) / "linkedin" / f"@{username}"
    metadata_dir = output_dir / "metadata"
    media_dir = output_dir / "media"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / "discovered.json"

    # Fase 1: Discovery
    existing = load_discovered(progress_file)
    with BrowserContext(config) as (ctx, page):
        if existing:
            posts = existing
        else:
            profile, posts = scrape_profile(page, username, config,
                                            max_posts=max_posts,
                                            save_progress=progress_file)
            save_json(output_dir / "profile.json", profile.to_dict())

        if not posts:
            return

        # Fase 2: Metadata
        already_scraped = {f.stem for f in metadata_dir.glob("*.json")}
        pending = [p for p in posts if p.post_id not in already_scraped]

        for i, post in enumerate(pending, 1):
            meta = scrape_post(page, post.post_id, post.url, config)
            if meta:
                save_json(metadata_dir / f"{post.post_id}.json", meta)
            rate_limit(config, "linkedin", "scrape_delay")
            rate_limit_batch(config, "linkedin", i)

    # Fase 3: CSV
    all_metadata = load_all_metadata(metadata_dir)
    all_metadata.sort(key=lambda r: r.get("date", ""))
    write_csv(output_dir / f"snapshot_{today()}.csv", all_metadata, STANDARD_FIELDS)

    # Fase 4: Media
    if not no_download:
        extract_from_cache(config["browser"]["profile_dir"], media_dir, "linkedin")
        with BrowserContext(config) as (ctx, page):
            download_missing_media(all_metadata, media_dir, config, page=page,
                                   platform="linkedin",
                                   rate_delay=tuple(config["rate_limits"]["linkedin"]["download_delay"]))

    # Fase 5: Conversión
    if not no_convert and not no_download:
        convert_all(media_dir, config)

def run_discover(username, config, max_posts=0):
    # ... mismo patrón
    pass

def run_download(username, config):
    # ... mismo patrón
    pass
```

### Paso 4: `config.yaml` — agregar rate limits

```yaml
rate_limits:
  linkedin:
    scrape_delay: [8, 18]
    download_delay: [10, 20]
    scroll_delay: [2.0, 4.0]
    batch_size: 30
    batch_pause: [150, 240]
```

### Paso 5: `cli.py` — registrar subcomandos

Buscar el bloque de Facebook en `cli.py` y copiar el patrón. Agregar el parser de `linkedin` y la función `_dispatch_linkedin(args, config)` siguiendo exactamente el mismo patrón de las plataformas existentes.

---

## Cómo agregar un comando nuevo a una plataforma existente

Ejemplo: agregar `instagram stats @username` que muestre estadísticas resumidas.

1. En `platforms/instagram/snapshot.py`, agregar `run_stats(username, config)`.
2. En `cli.py`, dentro del bloque `ig_sub`, agregar:
   ```python
   st = ig_sub.add_parser("stats", help="Mostrar estadisticas del perfil")
   st.add_argument("username")
   ```
3. En `_dispatch_instagram(args, config)`, agregar el `elif args.action == "stats":` con el import y llamada.

---

## Convenciones de código

- **Sin comentarios obvios**: Solo comentar el "por qué", nunca el "qué".
- **Sin manejo de errores para casos imposibles**: `try/except` solo en operaciones reales (browser, red, filesystem). No validar inputs que ya vienen de CLI parseado.
- **Imports locales en funciones grandes**: `import subprocess` y similares van dentro de la función que los usa, no al top-level. Así el módulo se importa rápido.
- **Naming**: `run_snapshot`, `run_discover`, `run_download`, `run_extract_cache` son los nombres estándar en todos los `snapshot.py`. No inventar nombres distintos.
- **`shortcode` es el ID universal**: En el CSV y en `load_all_metadata()`, el campo de ID siempre se llama `shortcode`. Los modelos mapean su `post_id`/`video_id`/`tweet_id` a `shortcode` en `to_csv_row()`.

---

## Errores comunes a evitar

| Error | Por qué es malo | Corrección |
|-------|-----------------|------------|
| Reemplazar `discovered.json` en cada scroll | Pierde progreso si se interrumpe | Usar `save_progress` cada batch, append incremental |
| Abrir dos `BrowserContext` simultáneos | Playwright rompe el perfil compartido | Un solo contexto por proceso |
| Usar `is_video` del discovered.json para filtrar qué descargar | Se pierden las fotos | `download_missing_media` baja todo, diferencia en la capa (browser vs yt-dlp) |
| Hardcodear delays en el código | Inflexible entre proyectos | Siempre leer de `config["rate_limits"][platform][key]` |
| Guardar media en `videos/` directamente | Rompe la detección de media existente | Guardar en `media/`, pasar `videos/` como `also_check_dirs` |
| Asumir que og:image siempre existe | Facebook y TikTok a veces no lo tienen | Fallback a `_extract_image_from_dom()` |

---

## Estado actual del repositorio

### Completamente funcional
- Instagram: discovery, metadata (OG + JSON-LD + DOM engagement), CSV, download videos, convert
- Facebook: discovery, metadata (DOM extraction: caption expandida, fecha, engagement), CSV, extract-cache, download media
- TikTok: discovery (Playwright), metadata (yt-dlp), CSV, download
- YouTube: discovery (yt-dlp), metadata (yt-dlp), CSV, download
- Twitter: discovery (Playwright), metadata (DOM), CSV, download

### Parcial / mejorable
- **Instagram fotos full-size**: `extract-cache` recupera thumbnails (< 50KB). Las fotos full-size requieren `instagram download` que visita cada post.
- **Facebook videos de hashtags**: URLs tipo `/watch/hashtag/...` no son contenido propio de la página, yt-dlp no las descarga.
- **Twitter imágenes**: El downloader de imágenes no está implementado para Twitter, solo videos.

### No implementado aún
- Consolidación multi-perfil: un CSV con múltiples perfiles de la misma plataforma
- Detección de contenido nuevo (diff entre dos snapshots)
- Soporte para cuentas privadas (requiere follow previo manual)

---

## Cómo evolucionar el repositorio

### Agregar soporte para imágenes de Twitter

1. En `platforms/twitter/snapshot.py`, modificar `run_download` para pasar `page` a `download_missing_media` con `platform="twitter"`.
2. En `media_downloader.py`, agregar `"twitter"` a `PLATFORM_FILTERS` con el patrón de URL de `pbs.twimg.com`.
3. En `_extract_image_from_dom`, agregar selector para Twitter: `article img[src*="pbs.twimg.com"]`.

### Agregar un nuevo campo al CSV (ej: `location`)

1. Agregar `location` a `STANDARD_FIELDS` en `shared/output.py`.
2. Agregar el campo a los modelos de las plataformas que lo soporten (`.to_csv_row()`).
3. Los que no lo soporten simplemente no lo incluyen en `to_csv_row()` — `write_csv` usa `.get(field, "")`.

### Mejorar la extracción de captions de Facebook

Los selectores DOM de Facebook cambian frecuentemente. Si dejan de funcionar, actualizar `_extract_caption_from_dom()` en `platforms/facebook/post_scraper.py`. Los selectores están aislados en esa función — un solo punto de cambio.

### Cambiar el directorio de output

Modificar `config.yaml`:
```yaml
output:
  base_dir: "/ruta/absoluta/a/datos"
```

No requiere cambios de código. `shared/config.py` resuelve rutas relativas al root del toolkit, pero acepta absolutas directamente.

---

## Referencia rápida: config.yaml

```yaml
browser:
  profile_dir: "browser_profile"     # Relativo al root del toolkit
  headless: false                    # true = sin ventana (requiere sesión activa)
  user_agent: "..."                  # UA del browser
  locale: "es-MX"                   # Idioma del browser
  viewport: {width: 1280, height: 800}

rate_limits:
  {platform}:
    scrape_delay: [min, max]         # Seg. entre posts en metadata loop
    download_delay: [min, max]       # Seg. entre descargas
    scroll_delay: [min, max]         # Seg. entre scrolls del perfil
    batch_size: N                    # Posts antes de pausa larga
    batch_pause: [min, max]          # Seg. de pausa por batch

downloads:
  ytdlp_binary: "venv/bin/yt-dlp"   # Relativo al root
  cookies_file: "browser_profile/cookies.txt"

conversion:
  ffmpeg: "/opt/homebrew/bin/ffmpeg" # Absoluta al binario del sistema
  ffprobe: "/opt/homebrew/bin/ffprobe"
  codec: "libx264"
  crf: 20                            # 18-23 recomendado
  preset: "fast"
  audio_codec: "aac"
  audio_bitrate: "128k"

output:
  base_dir: "output"                 # Relativo al root, o absoluta
```
