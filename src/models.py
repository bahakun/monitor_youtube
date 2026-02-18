from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ChannelConfig:
    """チャンネル設定"""
    channel_id: str
    name: str
    prompt_template: Optional[str]


@dataclass
class AppSettings:
    """アプリケーション設定"""
    check_interval_minutes: int
    max_summary_length: int
    history_retention_days: int
    default_prompt_template: str


@dataclass
class VideoEntry:
    """RSSフィードから取得した動画情報"""
    video_id: str
    title: str
    url: str
    published: datetime
    channel_id: str
