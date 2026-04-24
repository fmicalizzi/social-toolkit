# Social Media Toolkit

Toolkit portable para extraccion de datos y descarga de contenido desde redes sociales.

Pipeline completo por perfil: **discovery → metadata → CSV → descarga de media (imagenes + videos) → conversion H.264**

Plataformas implementadas: **Instagram · Facebook · TikTok · YouTube · X (Twitter)**

---

## Requisitos del sistema

| Requisito | Version minima | Instalacion |
|-----------|---------------|-------------|
| Python | >= 3.10 | `brew install python` o python.org |
| ffmpeg | cualquiera | `brew install ffmpeg` (macOS) / `apt install ffmpeg` (Linux) |
| macOS / Linux | macOS 14+ recomendado | — |

---

## Instalacion

```bash
# 1. Clonar o descargar el repositorio
cd social-toolkit

# 2. Ejecutar setup (crea venv, instala deps Python, descarga Chromium)
bash setup.sh

# 3. Verificar
venv/bin/python3 cli.py --help
```

El setup es idempotente: se puede ejecutar multiples veces sin riesgo.

### Reutilizar sesion de un proyecto anterior

Si ya tienes un `browser_profile/` con sesiones activas:

```bash
bash setup.sh /ruta/a/browser_profile_existente
```

---

## Uso rapido

```bash
# Instagram
venv/bin/python3 cli.py instagram snapshot @username

# Facebook
venv/bin/python3 cli.py facebook snapshot nombre_de_pagina

# TikTok
venv/bin/python3 cli.py tiktok snapshot @username

# YouTube
venv/bin/python3 cli.py youtube snapshot https://youtube.com/@handle

# X (Twitter)
venv/bin/python3 cli.py twitter snapshot @username
```

**La primera vez** que uses Instagram o Facebook se abre un browser para login manual. La sesion se guarda en `browser_profile/` y dura ~30-90 dias. TikTok, YouTube y Twitter no requieren login.

---

## Referencia de comandos

### Instagram

| Comando | Descripcion |
|---------|-------------|
| `instagram snapshot @user` | Pipeline completo: discover + metadata + CSV + media |
| `instagram snapshot @user --no-download` | Solo metadata y CSV |
| `instagram snapshot @user --max-posts 50` | Limitar a 50 posts |
| `instagram discover @user` | Solo scrollear perfil y extraer IDs |
| `instagram scrape --from-file urls.txt` | Scrape desde archivo de URLs o chat exportado |
| `instagram download @user` | Descargar media (fotos + videos) de un perfil ya scrapeado |
| `instagram extract-cache @user` | Extraer imagenes del cache del browser sin navegar |

### Facebook

| Comando | Descripcion |
|---------|-------------|
| `facebook snapshot pagename` | Pipeline completo |
| `facebook snapshot pagename --no-download` | Solo metadata y CSV |
| `facebook snapshot pagename --max-posts 100` | Limitar posts |
| `facebook discover pagename` | Solo scroll del feed para descubrir posts |
| `facebook download pagename` | Descargar media (fotos + videos) |
| `facebook extract-cache pagename` | Extraer del cache del browser |

### TikTok

| Comando | Descripcion |
|---------|-------------|
| `tiktok snapshot @user` | Pipeline completo |
| `tiktok snapshot @user --no-download` | Solo metadata y CSV |
| `tiktok discover @user` | Solo descubrir videos |
| `tiktok download @user` | Descargar videos |

### YouTube

| Comando | Descripcion |
|---------|-------------|
| `youtube snapshot https://youtube.com/@handle` | Pipeline completo |
| `youtube snapshot URL --no-download` | Solo metadata y CSV |
| `youtube discover URL` | Solo descubrir videos |
| `youtube download URL` | Descargar videos |

### X (Twitter)

| Comando | Descripcion |
|---------|-------------|
| `twitter snapshot @user` | Pipeline completo |
| `twitter snapshot @user --no-download` | Solo metadata y CSV |
| `twitter discover @user` | Solo descubrir tweets |
| `twitter download @user` | Descargar videos de tweets |

### Utilidades

| Comando | Descripcion |
|---------|-------------|
| `cookies export` | Exportar cookies del browser a formato Netscape para yt-dlp |
| `convert /path/to/videos/` | Convertir todos los videos no-H.264 en un directorio |

---

## Estructura de output

```
output/
└── {platform}/
    └── @username/
        ├── profile.json              # Bio, followers, etc.
        ├── discovered.json           # Checkpoint de progreso (IDs descubiertos)
        ├── snapshot_YYYY-MM-DD.csv   # Snapshot completo con metricas
        ├── metadata/                 # Un JSON por post
        │   ├── ABC123.json
        │   └── ...
        └── media/                    # Imagenes y videos descargados
            ├── 2025-01-15_ABC123.jpg
            ├── 2025-02-20_DEF456.mp4
            └── _post_mapping.json    # Mapa post_id → archivo (generado automaticamente)
```

### Columnas del CSV (estandarizadas en todas las plataformas)

| Campo | Descripcion |
|-------|-------------|
| `platform` | instagram, facebook, tiktok, youtube, twitter |
| `shortcode` | ID unico del post/video |
| `url` | URL completa |
| `username` | Nombre de la cuenta |
| `date` | Fecha YYYY-MM-DD |
| `content_type` | post, reel, video, tweet, etc. |
| `is_video` | True / False |
| `likes` | Likes (int) |
| `comments` | Comentarios (int) |
| `views` | Reproducciones (int) |
| `shares` | Compartidos (int) |
| `hashtags` | Hashtags separados por coma |
| `caption` | Texto del post (max 500 chars) |
| `scraped_at` | Timestamp del scraping |

---

## Descarga de media: estrategia inteligente

El comando `download` (y el paso 4 del `snapshot`) usa una estrategia en capas para evitar re-descargar contenido:

### 1. Cache del browser (gratis, sin red)

Antes de navegar, escanea `browser_profile/Default/Cache/`. Las imagenes que cargo el browser durante el scraping de metadata ya estan guardadas ahi. Se extraen en segundos sin ninguna request HTTP.

- **Facebook**: recupera tipicamente 90%+ de las fotos del perfil
- **Instagram**: recupera thumbnails (no full-size)

### 2. Browser solo para lo que falta

Para cada post pendiente:
1. Visita la URL del post con el browser
2. Extrae `og:image` (CDN URL de la imagen)
3. Compara el CDN filename con lo que ya esta en `media/`
4. Si ya existe (del cache) → registra el mapping, NO descarga
5. Si no existe → descarga con urllib

Solo se hacen descargas reales para los posts genuinamente ausentes.

### 3. Videos con yt-dlp

Revisa `media/` y `videos/` (legacy) antes de descargar. Usa cookies del browser para autenticacion.

### Idempotencia completa

Cada fase detecta lo que ya se proceso y lo salta:

| Fase | Checkpoint |
|------|-----------|
| Discovery | `discovered.json` (guarda cada 50 items) |
| Metadata | archivos en `metadata/` |
| Media (cache) | si `media/` tiene archivos, no re-extrae |
| Media (browser) | CDN filename ya en `media/` |
| Media (videos) | post_id en nombre de archivo en `media/` o `videos/` |
| Conversion | codec detectado con ffprobe, salta H.264 existentes |

---

## Configuracion (`config.yaml`)

```yaml
browser:
  headless: false             # true = sin ventana visible
  locale: "es-MX"             # Idioma del navegador

rate_limits:
  instagram:
    scrape_delay: [6, 14]     # Seg. entre posts (rango aleatorio)
    download_delay: [8, 18]
    scroll_delay: [1.5, 3.0]
    batch_size: 50             # Posts antes de pausa larga
    batch_pause: [120, 180]    # Seg. de pausa por batch

conversion:
  ffmpeg: "/opt/homebrew/bin/ffmpeg"
  crf: 20                     # Calidad (18-23 recomendado)
  preset: "fast"

output:
  base_dir: "output"          # Puede ser ruta absoluta
```

Si hay bloqueos o rate limiting, aumentar delays y reducir batch_size.

---

## Estructura del proyecto

```
social-toolkit/
├── cli.py                        # Entry point unico
├── config.yaml                   # Configuracion global
├── requirements.txt
├── setup.sh
│
├── shared/
│   ├── browser.py                # Playwright persistent context
│   ├── cookies.py                # Export cookies Netscape format
│   ├── media_downloader.py       # Cache → browser → yt-dlp (imagenes + videos)
│   ├── downloader.py             # yt-dlp wrapper (legacy)
│   ├── converter.py              # ffmpeg VP9→H.264
│   ├── rate_limiter.py           # Delays aleatorios + batch pauses
│   ├── output.py                 # CSV/JSON estandarizados
│   ├── config.py                 # Carga config.yaml
│   └── utils.py                  # Helpers: sanitize, timestamps, etc.
│
├── platforms/
│   ├── instagram/
│   │   ├── profile_scraper.py    # Scroll del grid de posts
│   │   ├── post_scraper.py       # OG tags + DOM → engagement
│   │   ├── snapshot.py           # Orquestador del pipeline
│   │   └── models.py
│   ├── facebook/
│   │   ├── page_scraper.py       # Scroll del feed
│   │   ├── post_scraper.py       # DOM: caption, fecha, engagement
│   │   ├── snapshot.py
│   │   └── models.py
│   ├── tiktok/
│   │   ├── profile_scraper.py    # Playwright scroll
│   │   ├── video_scraper.py      # Metadata via yt-dlp
│   │   ├── snapshot.py
│   │   └── models.py
│   ├── youtube/
│   │   ├── channel_scraper.py    # Descubre videos via yt-dlp
│   │   ├── video_scraper.py      # Metadata via yt-dlp
│   │   ├── snapshot.py
│   │   └── models.py
│   └── twitter/
│       ├── profile_scraper.py
│       ├── post_scraper.py
│       ├── snapshot.py
│       └── models.py
│
└── tests/
```

---

## Agregar una nueva plataforma

1. Crear `platforms/nueva/` con `__init__.py`, `models.py`, scraper(s), `snapshot.py`
2. Agregar `nueva:` en `config.yaml` bajo `rate_limits:`
3. Registrar subcomandos en `cli.py` (copiar patron de cualquier plataforma)
4. Reutilizar de `shared/` sin modificar: `browser.py`, `media_downloader.py`, `converter.py`, `output.py`, `rate_limiter.py`

---

## Usar en un nuevo proyecto

```bash
# Desde copia local
cp -R social-toolkit /nuevo/proyecto/
cd /nuevo/proyecto/social-toolkit
bash setup.sh

# Importar sesion existente para no re-hacer login
bash setup.sh /proyecto-anterior/social-toolkit/browser_profile

# Guardar output en otro lugar
# En config.yaml:
# output:
#   base_dir: "/ruta/absoluta/a/datos"
```

---

## Solucionar problemas

**Sesion expirada / redirige a login**
```bash
venv/bin/python3 cli.py instagram discover @cualquier_cuenta
# Se abre browser → login manual → Enter
```

**yt-dlp falla con videos**
```bash
venv/bin/pip install -q --upgrade yt-dlp
venv/bin/python3 cli.py cookies export   # re-exportar cookies
```

**Videos no se reproducen en QuickTime (macOS)**
```bash
venv/bin/python3 cli.py convert output/instagram/@username/media/
```

**Scraping interrumpido a mitad**
Volver a ejecutar el mismo comando. El pipeline detecta lo procesado y continua desde donde quedo.

---

## Dependencias

| Libreria | Uso |
|----------|-----|
| `playwright >= 1.40` | Browser automation con JS renderizado |
| `yt-dlp >= 2024.1` | Descarga de videos (YouTube, TikTok, Instagram, Facebook, etc.) |
| `pyyaml >= 6.0` | Lectura de config.yaml |
| `ffmpeg` (sistema) | Conversion de codecs |
