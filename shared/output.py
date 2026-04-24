"""CSV/JSON writers con campos estandarizados para todas las plataformas."""

import csv
import json
from pathlib import Path


STANDARD_FIELDS = [
    "platform", "shortcode", "url", "username", "full_name",
    "date", "content_type", "is_video",
    "likes", "comments", "views", "shares",
    "duration_sec", "location", "hashtags", "caption",
    "scraped_at",
]


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_metadata(metadata_dir: Path) -> list[dict]:
    """Carga todos los JSON de un directorio de metadata."""
    rows = []
    if not metadata_dir.exists():
        return rows
    for p in sorted(metadata_dir.glob("*.json")):
        try:
            rows.append(load_json(p))
        except Exception as e:
            print(f"  [warn] Error leyendo {p.name}: {e}")
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str] = None):
    """Escribe un CSV con campos estandarizados."""
    if fields is None:
        fields = STANDARD_FIELDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV generado: {path} ({len(rows)} filas)")
