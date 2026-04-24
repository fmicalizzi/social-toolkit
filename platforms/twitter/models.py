"""Modelos de datos para X (Twitter)."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class TwitterProfile:
    username: str
    full_name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    tweet_count: int = 0
    is_verified: bool = False
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiscoveredTweet:
    tweet_id: str
    url: str
    is_video: bool = False


@dataclass
class Tweet:
    tweet_id: str
    url: str
    username: str = ""
    full_name: str = ""
    date: str = ""
    content_type: str = ""  # tweet, reply, retweet, video
    is_video: bool = False
    likes: Optional[int] = None
    comments: Optional[int] = None
    views: Optional[int] = None
    shares: Optional[int] = None  # retweets
    duration_sec: Optional[float] = None
    location: str = ""
    hashtags: str = ""
    caption: str = ""
    scraped_at: str = ""

    def to_csv_row(self) -> dict:
        d = asdict(self)
        d["platform"] = "twitter"
        d["shortcode"] = self.tweet_id
        if d.get("caption"):
            d["caption"] = d["caption"][:500].replace("\n", " ")
        return d
