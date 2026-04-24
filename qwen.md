# Social Media Toolkit — Contexto para Qwen y modelos alternativos

## Mapa de documentación

| Archivo | Para quién | Contenido |
|---------|-----------|-----------|
| [`README.md`](./README.md) | Usuarios humanos | Instalación, primer uso, comandos, troubleshooting |
| [`AI_CONTEXT.md`](./AI_CONTEXT.md) | Agentes de IA | Arquitectura completa, pipeline, reglas, cómo extender |

**Antes de modificar código**: leer `AI_CONTEXT.md` completo.
**Si el usuario pregunta cómo usar el toolkit**: referirse a `README.md`.

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
6. Documentación de uso → `README.md`. Documentación de arquitectura → `AI_CONTEXT.md`. Sin duplicar.
