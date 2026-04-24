"""Modelos de datos para Facebook."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PageInfo:
    page_id: str
    name: str = ""
    description: str = ""
    followers: int = 0
    likes: int = 0
    category: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiscoveredPost:
    post_id: str
    url: str
    is_video: bool = False


@dataclass
class FacebookPost:
    post_id: str
    url: str
    username: str = ""
    full_name: str = ""
    date: str = ""
    content_type: str = ""  # photo, video, link, status
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
        d["platform"] = "facebook"
        d["shortcode"] = self.post_id
        if d.get("caption"):
            d["caption"] = d["caption"][:500].replace("\n", " ")
        return d
