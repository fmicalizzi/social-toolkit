# Social Media Toolkit

Toolkit portable para extraccion de datos y descarga de contenido desde redes sociales.

Pipeline: **discovery → metadata → CSV → imagenes + videos → conversion H.264**

Plataformas: **Instagram · Facebook · TikTok · YouTube · X (Twitter)**

> Para agentes de IA y contribuidores: ver [`AI_CONTEXT.md`](./AI_CONTEXT.md) — arquitectura, reglas de diseño, cómo extender el toolkit.

---

## Requisitos

| Requisito | Version | Instalacion |
|-----------|---------|-------------|
| Python | >= 3.10 | `brew install python` (macOS) |
| ffmpeg | cualquiera | `brew install ffmpeg` (macOS) / `apt install ffmpeg` (Linux) |

---

## Instalacion

```bash
cd social-toolkit
bash setup.sh
```

El setup instala las dependencias Python, descarga Chromium (Playwright), y crea las carpetas necesarias. Es idempotente: se puede correr multiples veces sin riesgo.

**Verificar que funciona:**
```bash
venv/bin/python3 cli.py --help
```

### Verificar ffmpeg antes de usar

El setup avisa si ffmpeg no esta en la ruta esperada. Si la ruta es distinta a `/opt/homebrew/bin/ffmpeg`, actualizar `config.yaml`:

```yaml
conversion:
  ffmpeg:  "/ruta/que/reporto/el/setup"
  ffprobe: "/ruta/que/reporto/el/setup/ffprobe"
```

Si no se actualiza, la descarga y el scraping funcionan, pero la conversion de video a H.264 falla silenciosamente.

---

## Primer uso: paso a paso

> Hacer esto antes de un snapshot completo. Confirma que el login funciona y el toolkit opera correctamente.

```bash
# 1. Primer snapshot de prueba — limita a 5 posts para probar rapido
venv/bin/python3 cli.py instagram snapshot @alguna_cuenta_publica --max-posts 5
```

**Lo que va a pasar:**

1. Se abre una ventana de Chromium
2. Si nunca iniciaste sesion, te lleva a `instagram.com/login`
3. **Logueate manualmente** en esa ventana (usuario y contraseña de Instagram)
4. Cuando estes dentro de Instagram, **vuelve a la terminal** y presiona `Enter`
5. El toolkit empieza a scrollear el perfil y extraer datos
6. Al terminar, vas a ver el output en `output/instagram/@cuenta/`

La sesion queda guardada en `browser_profile/` y dura ~30-90 dias. Los proximos usos no piden login.

**Revisar el resultado:**
```bash
# Ver el CSV generado
open output/instagram/@cuenta/snapshot_*.csv

# Ver metadata de un post
ls output/instagram/@cuenta/metadata/
```

Si el CSV tiene datos (fecha, caption, likes), todo funciona. Ahora podes correr sin limite.

### Plataformas que NO requieren login

TikTok, YouTube y Twitter funcionan sin login desde el primer uso.

---

## Uso rapido

```bash
# Instagram (requiere login la primera vez)
venv/bin/python3 cli.py instagram snapshot @username

# Facebook (requiere login la primera vez)
venv/bin/python3 cli.py facebook snapshot vivaldi.ve

# TikTok (sin login)
venv/bin/python3 cli.py tiktok snapshot @username

# YouTube (sin login)
venv/bin/python3 cli.py youtube snapshot https://youtube.com/@handle

# X / Twitter (sin login)
venv/bin/python3 cli.py twitter snapshot @username
```

**Tip**: para no escribir `venv/bin/python3 cli.py` cada vez, agregar un alias:
```bash
alias smt="venv/bin/python3 $(pwd)/cli.py"
# Luego:
smt instagram snapshot @username
```

---

## Referencia de comandos

### Instagram

| Comando | Descripcion |
|---------|-------------|
| `instagram snapshot @user` | Pipeline completo: discover + metadata + CSV + media |
| `instagram snapshot @user --no-download` | Solo metadata y CSV, sin descargar archivos |
| `instagram snapshot @user --max-posts 50` | Limitar a N posts (util para pruebas) |
| `instagram discover @user` | Solo scrollear el perfil y guardar los IDs de posts |
| `instagram scrape --from-file chat.txt` | Extraer metadata de URLs en un archivo de texto |
| `instagram download @user` | Descargar media (fotos + videos) de un perfil ya scrapeado |
| `instagram extract-cache @user` | Extraer imagenes del cache del browser sin navegar a ninguna URL |

### Facebook

El `pagename` es el slug de la URL: `facebook.com/vivaldi.ve` → `vivaldi.ve`

| Comando | Descripcion |
|---------|-------------|
| `facebook snapshot vivaldi.ve` | Pipeline completo |
| `facebook snapshot vivaldi.ve --no-download` | Solo metadata y CSV |
| `facebook snapshot vivaldi.ve --max-posts 100` | Limitar posts |
| `facebook discover vivaldi.ve` | Solo scroll del feed |
| `facebook download vivaldi.ve` | Descargar media (fotos + videos) |
| `facebook extract-cache vivaldi.ve` | Extraer fotos del cache del browser (instantaneo, sin red) |

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
| `cookies export` | Re-exportar cookies del browser (usar si yt-dlp falla con autenticacion) |
| `convert /ruta/a/carpeta/` | Convertir todos los videos en una carpeta a H.264 |

---

## Tiempos estimados

Estos tiempos son con los delays configurados por defecto (para no ser detectados como bot):

| Plataforma | Perfil tipico | Metadata | Descarga media |
|------------|--------------|----------|----------------|
| Instagram | 200 posts | ~45 min | ~2-4 hs (fotos full-size) |
| Facebook | 300 posts | ~6 hs | ~30 min (cache) + ~30 min (faltantes) |
| TikTok | 100 videos | ~15 min | ~20 min |
| YouTube | 50 videos | ~5 min | segun duracion |
| Twitter | 500 tweets | ~1 hs | variable |

**Todos los procesos son reanudables.** Si se interrumpen con Ctrl+C, el proximo `snapshot` continua desde donde quedo — no repite lo que ya proceso.

---

## Sobre `extract-cache`

Este comando extrae imagenes que el browser ya descargo durante el scraping de metadata, directo del cache de Chromium. **No hace ninguna request HTTP.**

Cuando usarlo:
```bash
# Flujo optimo para Facebook (la mayoria de fotos salen del cache):
venv/bin/python3 cli.py facebook snapshot vivaldi.ve --no-download  # scraping primero
venv/bin/python3 cli.py facebook extract-cache vivaldi.ve           # extraer cache (instantaneo)
venv/bin/python3 cli.py facebook download vivaldi.ve                # solo descarga lo que falto
```

El `facebook download` ya hace este proceso automaticamente en orden. `extract-cache` existe para correrlo en forma independiente.

---

## Estructura de output

```
output/
└── {platform}/
    └── @username/              (o slug para Facebook)
        ├── profile.json        # Datos del perfil
        ├── discovered.json     # Checkpoint de progreso
        ├── snapshot_YYYY-MM-DD.csv
        ├── metadata/           # Un JSON por post
        └── media/              # Fotos y videos descargados
            ├── 2025-01-15_ABC123.jpg
            ├── 2025-02-20_DEF456.mp4
            └── _post_mapping.json
```

### Columnas del CSV

| Campo | Descripcion |
|-------|-------------|
| `platform` | instagram, facebook, tiktok, youtube, twitter |
| `shortcode` | ID unico del post |
| `url` | URL completa |
| `username` | Nombre de la cuenta |
| `date` | YYYY-MM-DD |
| `content_type` | post, reel, video, tweet, etc. |
| `is_video` | True / False |
| `likes` | Likes (int) |
| `comments` | Comentarios (int) |
| `views` | Reproducciones (int) |
| `shares` | Compartidos (int) |
| `hashtags` | Separados por coma |
| `caption` | Texto del post (max 500 chars) |
| `scraped_at` | Timestamp del scraping |

---

## Configuracion (`config.yaml`)

La mayoria de valores funcionan bien por defecto. Los que puede ser necesario cambiar:

```yaml
browser:
  headless: false       # cambiar a true para correr sin ventana (solo si la sesion es valida)
  locale: "es-MX"       # idioma del browser (afecta fechas y texto del DOM)

conversion:
  ffmpeg: "/opt/homebrew/bin/ffmpeg"   # ajustar segun lo que reporto el setup
  ffprobe: "/opt/homebrew/bin/ffprobe"
  crf: 20               # calidad de video (18 = muy alta, 28 = menor calidad, 20 es buen balance)

output:
  base_dir: "output"    # puede ser ruta absoluta para guardar fuera del toolkit
```

### Si la plataforma bloquea o redirige a login muy seguido

```yaml
rate_limits:
  instagram:
    scrape_delay: [12, 25]     # subir los numeros
    batch_size: 25             # bajar el batch
    batch_pause: [240, 360]    # subir la pausa
```

---

## Usar en un nuevo proyecto

```bash
# Copiar el toolkit
cp -R social-toolkit /ruta/nuevo-proyecto/

cd /ruta/nuevo-proyecto/social-toolkit
bash setup.sh

# Importar sesion existente para no re-hacer login
bash setup.sh /ruta/a/otro-proyecto/social-toolkit/browser_profile
```

Para guardar los datos en otra ubicacion sin mover el toolkit:
```yaml
# config.yaml
output:
  base_dir: "/ruta/absoluta/donde/guardar/datos"
```

---

## Solucionar problemas

**Sesion expirada / redirige a login**
```bash
# Correr cualquier comando — se abre el browser para re-loguearse
venv/bin/python3 cli.py instagram discover @cualquier_cuenta
```

**yt-dlp falla descargando videos**
```bash
venv/bin/pip install -q --upgrade yt-dlp
venv/bin/python3 cli.py cookies export
```

**Videos no se reproducen en QuickTime (macOS)**

Instagram y TikTok entregan videos en VP9, incompatible con QuickTime:
```bash
venv/bin/python3 cli.py convert output/instagram/@username/media/
```

**El proceso se colgó / no avanza**

Los delays son largos por diseño (para no ser detectado). En la terminal deberia ver output como `[47/390] ABC123 -> 2024-03-15 L:4200`. Si no hay output por mas de 5 minutos, Ctrl+C y volver a correr — continua desde donde quedo.

**"No hay metadata" o "0 posts"**

El perfil puede ser privado, o la sesion expiro. Verificar con:
```bash
venv/bin/python3 cli.py instagram discover @cuenta --max-posts 5
```

---

## Dependencias

| Libreria | Uso |
|----------|-----|
| `playwright >= 1.40` | Browser automation (scraping con JavaScript renderizado) |
| `yt-dlp >= 2024.1` | Descarga de videos |
| `pyyaml >= 6.0` | Lectura de `config.yaml` |
| `ffmpeg` (sistema) | Conversion de codecs VP9→H.264 |
