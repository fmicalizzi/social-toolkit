# Social Media Toolkit — Instrucciones para Claude Code

## Documentación del repositorio

| Archivo | Para quién | Contenido |
|---------|-----------|-----------|
| [`README.md`](./README.md) | Usuarios humanos | Instalación, primer uso, comandos, troubleshooting |
| [`AI_CONTEXT.md`](./AI_CONTEXT.md) | Agentes de IA | Arquitectura completa, pipeline, reglas de diseño, cómo extender |

**Antes de cualquier tarea técnica**: leer `AI_CONTEXT.md` completo.
**Si el usuario pregunta cómo usar el toolkit**: referirse a `README.md`.

---

## Comportamiento en este repo

**Al modificar un `snapshot.py`**, verificar que:
- El discovery sigue siendo saltable si `discovered.json` existe
- `run_download` pasa `also_check_dirs=[videos_dir]` a `download_missing_media`
- `extract_from_cache` se llama antes de `download_missing_media`

**Al agregar una plataforma nueva**, seguir el template de `AI_CONTEXT.md → "Cómo agregar una nueva plataforma"` exactamente. Los nombres de función estándar son `run_snapshot`, `run_discover`, `run_download` — no inventar variantes.

**Al tocar `shared/media_downloader.py`**, preservar las tres capas (cache → browser → yt-dlp) y la lógica de `_post_mapping.json`. Es el módulo más delicado del repo.

**Al actualizar documentación**: el contenido de uso va en `README.md`, el contenido de arquitectura va en `AI_CONTEXT.md`. Nunca duplicar entre los dos.

## Qué NO hacer

- No hardcodear delays: leer siempre de `config["rate_limits"][platform][key]`
- No abrir dos `BrowserContext` simultáneos con el mismo `browser_profile/`
- No guardar media en `videos/`: usar `media/`, pasar `videos/` como `also_check_dirs`
- No agregar campos al CSV sin actualizar `STANDARD_FIELDS` en `shared/output.py`
- No duplicar contenido entre `README.md` y `AI_CONTEXT.md`

## Sincronización entre copias del toolkit

```bash
rsync -av --exclude='output/' --exclude='venv/' --exclude='browser_profile/' \
  --exclude='__pycache__/' origen/ destino/
```
