"""Utilidades compartidas: sanitize, progress, paths."""

import re
from datetime import datetime


def sanitize(name: str, max_len: int = 60) -> str:
    """Limpia un nombre para usar como carpeta."""
    name = name.lstrip("@").strip()
    name = re.sub(r'[/\\:*?"<>|]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len] or "unknown"


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def timestamp_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_username(username: str) -> str:
    """Quita @ si lo tiene, strip."""
    return username.strip().lstrip("@").strip()
