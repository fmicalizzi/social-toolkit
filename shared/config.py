"""Carga config.yaml y resuelve paths relativos al root del toolkit."""

import shutil
import yaml
from pathlib import Path


def load_config(config_path: Path = None, root: Path = None) -> dict:
    if root is None:
        root = Path(__file__).parent.parent.resolve()
    if config_path is None:
        config_path = root / "config.yaml"

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["_root"] = root

    # Resolver paths relativos al root del toolkit
    cfg["browser"]["profile_dir"] = str(root / cfg["browser"]["profile_dir"])
    cfg["downloads"]["ytdlp_binary"] = str(root / cfg["downloads"]["ytdlp_binary"])
    cfg["downloads"]["cookies_file"] = str(root / cfg["downloads"]["cookies_file"])
    cfg["output"]["base_dir"] = str(root / cfg["output"]["base_dir"])

    # Auto-detectar ffmpeg/ffprobe si la ruta configurada no existe
    for tool in ("ffmpeg", "ffprobe"):
        configured = cfg["conversion"][tool]
        if not Path(configured).exists():
            found = shutil.which(tool)
            if found:
                cfg["conversion"][tool] = found

    return cfg
