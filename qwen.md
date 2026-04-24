# Social Media Toolkit — Contexto para Qwen y modelos alternativos

**Archivo maestro:**
→ [`AI_CONTEXT.md`](./AI_CONTEXT.md) — todo lo necesario para trabajar en este repositorio

---

## Resumen ejecutivo

Toolkit Python CLI con 5 plataformas de redes sociales. El pipeline va:
`Discovery → Metadata → CSV → Descarga de media → Conversión H.264`

**Punto de entrada**: `cli.py`
**Configuración**: `config.yaml` (rate limits, paths, browser config)
**Módulo más importante**: `shared/media_downloader.py` (estrategia cache → browser → yt-dlp)

## Al trabajar en este repo

1. Leer `AI_CONTEXT.md` completo antes de modificar código
2. Respetar la idempotencia: cada fase detecta trabajo previo y lo salta
3. Seguir el patrón de las plataformas existentes al agregar una nueva
4. Rate limits siempre desde `config.yaml`, nunca hardcodeados
5. Media siempre en `media/`, no en `videos/` (ese es el directorio legacy)
