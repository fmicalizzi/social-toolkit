"""Tests para shared/output.py"""

import sys
import csv
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from shared.output import save_json, load_json, load_all_metadata, write_csv, STANDARD_FIELDS


def test_save_and_load_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sub" / "test.json"
        data = {"shortcode": "ABC123", "likes": 42, "caption": "Hola mundo"}
        save_json(path, data)

        assert path.exists()
        loaded = load_json(path)
        assert loaded == data


def test_save_json_unicode():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "unicode.json"
        data = {"caption": "Texto con acentos: cafe, nino, espanol"}
        save_json(path, data)
        loaded = load_json(path)
        assert loaded["caption"] == data["caption"]


def test_load_all_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # Crear algunos JSON de metadata
        save_json(tmpdir / "AAA.json", {"shortcode": "AAA", "date": "2025-01-01"})
        save_json(tmpdir / "BBB.json", {"shortcode": "BBB", "date": "2025-02-01"})
        save_json(tmpdir / "CCC.json", {"shortcode": "CCC", "date": "2025-03-01"})

        rows = load_all_metadata(tmpdir)
        assert len(rows) == 3
        shortcodes = [r["shortcode"] for r in rows]
        assert "AAA" in shortcodes
        assert "BBB" in shortcodes
        assert "CCC" in shortcodes


def test_load_all_metadata_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        rows = load_all_metadata(Path(tmpdir))
        assert rows == []


def test_load_all_metadata_nonexistent():
    rows = load_all_metadata(Path("/tmp/nonexistent_dir_12345"))
    assert rows == []


def test_write_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.csv"
        rows = [
            {"platform": "instagram", "shortcode": "AAA", "url": "https://...",
             "username": "user1", "likes": 100, "date": "2025-01-01"},
            {"platform": "instagram", "shortcode": "BBB", "url": "https://...",
             "username": "user2", "likes": 200, "date": "2025-02-01"},
        ]
        write_csv(path, rows)

        assert path.exists()
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            read_rows = list(reader)
        assert len(read_rows) == 2
        assert read_rows[0]["shortcode"] == "AAA"
        assert read_rows[1]["shortcode"] == "BBB"


def test_standard_fields_completeness():
    required = ["platform", "shortcode", "url", "username", "date",
                "likes", "comments", "views", "caption"]
    for field in required:
        assert field in STANDARD_FIELDS, f"Missing field: {field}"


if __name__ == "__main__":
    test_save_and_load_json()
    test_save_json_unicode()
    test_load_all_metadata()
    test_load_all_metadata_empty()
    test_load_all_metadata_nonexistent()
    test_write_csv()
    test_standard_fields_completeness()
    print("test_output: ALL PASSED")
