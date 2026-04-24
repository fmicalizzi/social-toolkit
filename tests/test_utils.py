"""Tests para shared/utils.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from shared.utils import sanitize, today, timestamp_iso, normalize_username


def test_sanitize_basic():
    assert sanitize("Hello World") == "Hello World"
    assert sanitize("@usuario") == "usuario"
    assert sanitize("  spaces  ") == "spaces"


def test_sanitize_special_chars():
    assert sanitize('file/name:bad*"<>|') == "filenamebad"
    assert sanitize("") == "unknown"
    assert sanitize("   ") == "unknown"


def test_sanitize_max_length():
    long_name = "a" * 100
    assert len(sanitize(long_name)) == 60
    assert len(sanitize(long_name, max_len=30)) == 30


def test_normalize_username():
    assert normalize_username("@yaiza") == "yaiza"
    assert normalize_username("yaiza") == "yaiza"
    assert normalize_username("  @yaiza  ") == "yaiza"


def test_today_format():
    result = today()
    assert len(result) == 10
    parts = result.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4  # year
    assert len(parts[1]) == 2  # month
    assert len(parts[2]) == 2  # day


def test_timestamp_iso_format():
    result = timestamp_iso()
    assert "T" in result
    assert len(result) == 19  # YYYY-MM-DDTHH:MM:SS


if __name__ == "__main__":
    test_sanitize_basic()
    test_sanitize_special_chars()
    test_sanitize_max_length()
    test_normalize_username()
    test_today_format()
    test_timestamp_iso_format()
    print("test_utils: ALL PASSED")
