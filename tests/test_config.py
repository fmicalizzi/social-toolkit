"""Tests para shared/config.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from shared.config import load_config


def test_load_config_resolves_paths():
    cfg = load_config(ROOT / "config.yaml", ROOT)
    assert cfg["_root"] == ROOT
    assert cfg["browser"]["profile_dir"].endswith("browser_profile")
    assert "yt-dlp" in cfg["downloads"]["ytdlp_binary"]
    assert cfg["output"]["base_dir"].endswith("output")


def test_load_config_preserves_values():
    cfg = load_config(ROOT / "config.yaml", ROOT)
    assert cfg["rate_limits"]["instagram"]["scrape_delay"] == [6, 14]
    assert cfg["rate_limits"]["instagram"]["download_delay"] == [8, 18]
    assert cfg["rate_limits"]["instagram"]["batch_size"] == 50
    assert cfg["conversion"]["crf"] == 20
    assert cfg["conversion"]["codec"] == "libx264"
    assert cfg["browser"]["headless"] is False


def test_load_config_default_root():
    cfg = load_config()
    assert "_root" in cfg
    assert isinstance(cfg["_root"], Path)


if __name__ == "__main__":
    test_load_config_resolves_paths()
    test_load_config_preserves_values()
    test_load_config_default_root()
    print("test_config: ALL PASSED")
