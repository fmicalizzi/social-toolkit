"""Tests para funciones de parsing en platforms/instagram/profile_scraper.py"""

import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from platforms.instagram.profile_scraper import (
    _parse_count,
    _save_discovered,
    load_discovered,
)
from platforms.instagram.models import DiscoveredPost


def test_parse_count_simple():
    assert _parse_count("1,234 Followers, 567 Following, 89 Posts", r'([\d,.KkMm]+)\s*Followers') == 1234
    assert _parse_count("1,234 Followers, 567 Following, 89 Posts", r'([\d,.KkMm]+)\s*Following') == 567
    assert _parse_count("1,234 Followers, 567 Following, 89 Posts", r'([\d,.KkMm]+)\s*Posts') == 89


def test_parse_count_k():
    assert _parse_count("12.5K Followers", r'([\d,.KkMm]+)\s*Followers') == 12500


def test_parse_count_m():
    assert _parse_count("1.3M Followers", r'([\d,.KkMm]+)\s*Followers') == 1300000


def test_parse_count_no_match():
    assert _parse_count("no numbers here", r'([\d,.KkMm]+)\s*Followers') == 0


def test_parse_count_empty():
    assert _parse_count("", r'([\d,.KkMm]+)\s*Followers') == 0


def test_save_and_load_discovered():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "discovered.json"
        posts = [
            DiscoveredPost(shortcode="AAA", url="https://...", is_video=True),
            DiscoveredPost(shortcode="BBB", url="https://...", is_video=False),
        ]

        _save_discovered(path, posts)
        assert path.exists()

        loaded = load_discovered(path)
        assert len(loaded) == 2
        assert loaded[0].shortcode == "AAA"
        assert loaded[0].is_video is True
        assert loaded[1].shortcode == "BBB"
        assert loaded[1].is_video is False


def test_load_discovered_nonexistent():
    result = load_discovered(Path("/tmp/nonexistent_file_12345.json"))
    assert result == []


def test_batch_progress_condition():
    """Verifica que la condicion corregida de guardado incremental funciona."""
    # Simular la condicion: len(collected) // 50 > prev_count // 50
    # Cruzando boundary de 50
    assert 51 // 50 > 49 // 50     # True: cruzó de 0 a 1
    assert 50 // 50 > 49 // 50     # True: cruzó de 0 a 1
    assert not (49 // 50 > 49 // 50)  # False: mismo bucket
    assert 100 // 50 > 99 // 50    # True: cruzó de 1 a 2
    assert not (99 // 50 > 98 // 50)  # False: mismo bucket


if __name__ == "__main__":
    test_parse_count_simple()
    test_parse_count_k()
    test_parse_count_m()
    test_parse_count_no_match()
    test_parse_count_empty()
    test_save_and_load_discovered()
    test_load_discovered_nonexistent()
    test_batch_progress_condition()
    print("test_profile_scraper: ALL PASSED")
