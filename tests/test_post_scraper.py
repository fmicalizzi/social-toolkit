"""Tests para funciones de parsing en platforms/instagram/post_scraper.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from platforms.instagram.post_scraper import (
    _extract_username,
    _extract_engagement,
    _parse_metric,
    _extract_location,
)


def test_extract_username_english():
    assert _extract_username("John Doe on Instagram: 'Hello'", {}) == "John Doe"


def test_extract_username_spanish():
    assert _extract_username("Maria Lopez en Instagram: 'Hola'", {}) == "Maria Lopez"


def test_extract_username_jsonld():
    jsonld = {"author": {"url": "https://www.instagram.com/jdoe/"}}
    assert _extract_username("Unknown title", jsonld) == "jdoe"


def test_extract_username_jsonld_name():
    jsonld = {"author": {"name": "JDoe Official"}}
    assert _extract_username("Unknown title", jsonld) == "JDoe Official"


def test_extract_username_empty():
    assert _extract_username("No match here", {}) == ""


def test_parse_metric_simple():
    assert _parse_metric("1234") == 1234
    assert _parse_metric("1,234") == 1234
    assert _parse_metric("0") == 0


def test_parse_metric_k():
    assert _parse_metric("41K") == 41000
    assert _parse_metric("1.5k") == 1500
    assert _parse_metric("12.3K") == 12300


def test_parse_metric_m():
    assert _parse_metric("1.2M") == 1200000
    assert _parse_metric("3m") == 3000000


def test_parse_metric_none():
    assert _parse_metric("") is None
    assert _parse_metric(None) is None


def test_extract_engagement_from_description():
    desc = "41K likes, 724 comments - user on September 21, 2025"
    result = _extract_engagement(None, desc)
    assert result["likes"] == 41000
    assert result["comments"] == 724
    assert result["views"] is None  # no views in this desc


def test_extract_engagement_with_views():
    desc = "1.2M views, 50K likes, 3,456 comments"
    result = _extract_engagement(None, desc)
    assert result["views"] == 1200000
    assert result["likes"] == 50000
    assert result["comments"] == 3456


def test_extract_engagement_empty():
    result = _extract_engagement(None, "")
    assert result["likes"] is None
    assert result["comments"] is None
    assert result["views"] is None


def test_extract_location():
    jsonld = {"contentLocation": {"name": "Mexico City"}}
    assert _extract_location(jsonld) == "Mexico City"


def test_extract_location_empty():
    assert _extract_location({}) == ""
    assert _extract_location({"contentLocation": "not a dict"}) == ""


if __name__ == "__main__":
    test_extract_username_english()
    test_extract_username_spanish()
    test_extract_username_jsonld()
    test_extract_username_jsonld_name()
    test_extract_username_empty()
    test_parse_metric_simple()
    test_parse_metric_k()
    test_parse_metric_m()
    test_parse_metric_none()
    test_extract_engagement_from_description()
    test_extract_engagement_with_views()
    test_extract_engagement_empty()
    test_extract_location()
    test_extract_location_empty()
    print("test_post_scraper: ALL PASSED")
