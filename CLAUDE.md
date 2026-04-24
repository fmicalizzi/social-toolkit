# Social Media Toolkit — Instrucciones para Claude Code

**Leer antes de cualquier tarea:**
→ [`AI_CONTEXT.md`](./AI_CONTEXT.md) — arquitectura completa, pipeline, reglas, cómo extender

---

## Comportamiento en este repo

**Antes de escribir código**, leer `AI_CONTEXT.md` completo. Contiene el mapa de cada archivo, los patrones que se deben seguir, y los errores frecuentes a evitar.

**Al modificar un `snapshot.py`**, verificar que:
- El discovery sigue siendo saltable si `discovered.json` existe
- `run_download` pasa `also_check_dirs=[videos_dir]` a `download_missing_media`
- `extract_from_cache` se llama antes de `download_missing_media`

**Al agregar una plataforma nueva**, seguir el template de `AI_CONTEXT.md → "Cómo agregar una nueva plataforma"` exactamente. No inventar nombres de funciones distintos a los estándar (`run_snapshot`, `run_discover`, `run_download`).

**Al tocar `shared/media_downloader.py`**, preservar las tres capas (cache → browser → yt-dlp) y la lógica de `_post_mapping.json`. Es el módulo más delicado del repo.

## Qué NO hacer

- No hardcodear delays: leer siempre de `config["rate_limits"][platform][key]`
- No abrir dos `BrowserContext` simultáneos con el mismo `browser_profile/`
- No guardar media directamente en `videos/`: usar `media/` y pasar `videos/` como `also_check_dirs`
- No agregar campos al CSV sin actualizar `STANDARD_FIELDS` en `shared/output.py`
- No crear archivos de documentación (MD) que dupliquen contenido de `AI_CONTEXT.md`

## Sincronización entre copias del toolkit

Si el usuario trabaja con múltiples copias del toolkit (ej: una por proyecto), el código de `shared/` y `platforms/` debe estar sincronizado. Usar `rsync` excluyendo `output/`, `venv/`, `browser_profile/`:

```bash
rsync -av --exclude='output/' --exclude='venv/' --exclude='browser_profile/' \
  --exclude='__pycache__/' origen/ destino/
```
