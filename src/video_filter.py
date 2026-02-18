import logging
from typing import Optional

import requests

from src.models import VideoEntry

logger = logging.getLogger(__name__)

OEMBED_URL = "https://www.youtube.com/oembed"
TIMEOUT_SECONDS = 10

LIVE_KEYWORDS = ["【live】", "【ライブ】", "live stream", "生配信", "生放送"]


def filter_videos(videos: list[VideoEntry]) -> list[VideoEntry]:
    """Shorts・ライブ配信を除外する。

    Args:
        videos: フィルタリング前の動画リスト

    Returns:
        通常動画のみのリスト
    """
    result = []
    shorts_count = 0
    live_count = 0

    for video in videos:
        oembed = _fetch_oembed(video)
        if _is_short(oembed):
            shorts_count += 1
            continue
        if _is_live_stream(video, oembed):
            live_count += 1
            continue
        result.append(video)

    logger.info(
        "フィルタ後 - 通常動画: %d, 除外(Shorts): %d, 除外(ライブ): %d",
        len(result),
        shorts_count,
        live_count,
    )
    return result


def _fetch_oembed(video: VideoEntry) -> Optional[dict]:
    """oEmbed APIで動画情報を取得する。失敗時はNoneを返す。"""
    try:
        resp = requests.get(
            OEMBED_URL,
            params={"url": video.url, "format": "json"},
            timeout=TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            return resp.json()
    except (requests.exceptions.RequestException, ValueError):
        pass
    return None


def _is_short(oembed: Optional[dict]) -> bool:
    """oEmbedレスポンスからShortsかどうか判定する。"""
    if oembed is None:
        return False

    # thumbnail_urlに /shorts/ が含まれる
    thumbnail_url = oembed.get("thumbnail_url", "")
    if "/shorts/" in thumbnail_url:
        return True

    # 縦長動画 = Shorts
    width = oembed.get("width", 0)
    height = oembed.get("height", 0)
    if width > 0 and height > 0 and height > width:
        return True

    return False


def _is_live_stream(video: VideoEntry, oembed: Optional[dict]) -> bool:
    """ライブ配信（またはアーカイブ）かどうか判定する。"""
    # oEmbedまたは元のタイトルにライブ配信キーワードが含まれるか
    titles_to_check = [video.title.lower()]
    if oembed is not None:
        titles_to_check.append(oembed.get("title", "").lower())

    for title in titles_to_check:
        for keyword in LIVE_KEYWORDS:
            if keyword.lower() in title:
                return True

    return False
