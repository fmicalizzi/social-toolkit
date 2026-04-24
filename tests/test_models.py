"""Tests para platforms/instagram/models.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from platforms.instagram.models import ProfileInfo, DiscoveredPost, InstagramPost


def test_profile_info_defaults():
    p = ProfileInfo(username="test")
    assert p.username == "test"
    assert p.followers == 0
    assert p.following == 0
    assert p.post_count == 0
    assert p.is_private is False
    assert p.is_verified is False


def test_profile_info_to_dict():
    p = ProfileInfo(username="yaiza", full_name="Yaiza T", followers=1500)
    d = p.to_dict()
    assert d["username"] == "yaiza"
    assert d["full_name"] == "Yaiza T"
    assert d["followers"] == 1500
    assert isinstance(d, dict)


def test_discovered_post():
    dp = DiscoveredPost(shortcode="ABC123", url="https://instagram.com/p/ABC123/")
    assert dp.shortcode == "ABC123"
    assert dp.is_video is False


def test_instagram_post_to_csv_row():
    post = InstagramPost(
        shortcode="XYZ",
        url="https://instagram.com/p/XYZ/",
        username="testuser",
        date="2025-06-15",
        content_type="reel",
        is_video=True,
        likes=5000,
        comments=120,
        views=50000,
        hashtags="ai, tech, coding",
        caption="Un reel sobre IA\ncon salto de linea",
        scraped_at="2025-06-15T10:30:00",
    )
    row = post.to_csv_row()
    assert row["platform"] == "instagram"
    assert row["shortcode"] == "XYZ"
    assert row["likes"] == 5000
    assert row["is_video"] is True
    assert "\n" not in row["caption"]  # newlines replaced


def test_instagram_post_caption_truncation():
    long_caption = "x" * 1000
    post = InstagramPost(
        shortcode="A", url="", username="u",
        caption=long_caption,
    )
    row = post.to_csv_row()
    assert len(row["caption"]) <= 500


def test_instagram_post_hashtags_list():
    """Si hashtags es una lista, to_csv_row debe convertirla a string."""
    post = InstagramPost(
        shortcode="A", url="", username="u",
        hashtags=["ai", "tech"],
    )
    row = post.to_csv_row()
    assert row["hashtags"] == "ai, tech"


def test_instagram_post_hashtags_string():
    """Si hashtags ya es string, debe quedarse como string."""
    post = InstagramPost(
        shortcode="A", url="", username="u",
        hashtags="ai, tech",
    )
    row = post.to_csv_row()
    assert row["hashtags"] == "ai, tech"


if __name__ == "__main__":
    test_profile_info_defaults()
    test_profile_info_to_dict()
    test_discovered_post()
    test_instagram_post_to_csv_row()
    test_instagram_post_caption_truncation()
    test_instagram_post_hashtags_list()
    test_instagram_post_hashtags_string()
    print("test_models: ALL PASSED")
