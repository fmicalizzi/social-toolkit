"""Modelos de datos para YouTube."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ChannelInfo:
    channel_id: str
    handle: str = ""
    title: str = ""
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiscoveredVideo:
    video_id: str
    url: str
    title: str = ""


@dataclass
class YouTubeVideo:
    video_id: str
    url: str
    username: str = ""
    full_name: str = ""
    date: str = ""
    content_type: str = "video"
    is_video: bool = True
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
        d["platform"] = "youtube"
        d["shortcode"] = self.video_id
        if d.get("caption"):
            d["caption"] = d["caption"][:500].replace("\n", " ")
        return d
