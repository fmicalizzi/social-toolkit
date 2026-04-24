"""Modelos de datos para Instagram."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ProfileInfo:
    username: str
    full_name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    post_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    profile_pic_url: str = ""
    external_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiscoveredPost:
    shortcode: str
    url: str
    is_video: bool = False


@dataclass
class InstagramPost:
    shortcode: str
    url: str
    username: str
    full_name: str = ""
    date: str = ""
    content_type: str = ""  # reel, photo, carousel, video
    is_video: bool = False
    likes: Optional[int] = None
    comments: Optional[int] = None
    views: Optional[int] = None
    shares: Optional[int] = None
    duration_sec: Optional[float] = None
    location: str = ""
    hashtags: str = ""
    caption: str = ""
    scraped_at: str = ""

    def to_csv_row(self) -> dict:
        d = asdict(self)
        d["platform"] = "instagram"
        if isinstance(d.get("hashtags"), list):
            d["hashtags"] = ", ".join(d["hashtags"])
        if d.get("caption"):
            d["caption"] = d["caption"][:500].replace("\n", " ")
        return d
