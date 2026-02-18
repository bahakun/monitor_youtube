import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from src.exceptions import RSSFetchError
from src.models import VideoEntry

logger = logging.getLogger(__name__)

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
TIMEOUT_SECONDS = 30

# XML名前空間
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

# リトライ設定
MAX_RETRIES = 3
BACKOFF_SECONDS = [5, 10, 20]


def fetch_feed(channel_id: str) -> list[VideoEntry]:
    """指定チャンネルのRSSフィードを取得し、動画エントリを返す。

    Args:
        channel_id: YouTubeチャンネルID

    Returns:
        動画エントリのリスト（公開日時の新しい順）

    Raises:
        RSSFetchError: フィード取得またはパースに失敗した場合
    """
    url = RSS_URL_TEMPLATE.format(channel_id=channel_id)
    xml_text = _fetch_with_retry(url, channel_id)
    videos = _parse_feed(xml_text, channel_id)
    videos.sort(key=lambda v: v.published, reverse=True)
    logger.info(
        "チャンネル(%s)のRSSフィード取得完了 - 動画数: %d", channel_id, len(videos)
    )
    return videos


def _fetch_with_retry(url: str, channel_id: str) -> str:
    """リトライ付きでRSSフィードを取得する。"""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=TIMEOUT_SECONDS)

            if response.status_code == 200:
                return response.text

            # 4xx はリトライしない
            if 400 <= response.status_code < 500:
                raise RSSFetchError(
                    f"RSSフィード取得失敗(HTTP {response.status_code}): "
                    f"チャンネル {channel_id}"
                )

            # 5xx はリトライ
            last_error = RSSFetchError(
                f"RSSフィード取得失敗(HTTP {response.status_code}): "
                f"チャンネル {channel_id}"
            )

        except requests.exceptions.RequestException as e:
            last_error = RSSFetchError(
                f"RSSフィード取得失敗(ネットワークエラー): チャンネル {channel_id}: {e}"
            )

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_SECONDS[attempt]
            logger.warning(
                "RSSフィード取得リトライ %d/%d - %d秒待機: %s",
                attempt + 1,
                MAX_RETRIES,
                wait,
                channel_id,
            )
            time.sleep(wait)

    raise last_error


def _parse_feed(xml_text: str, channel_id: str) -> list[VideoEntry]:
    """RSSフィードのXMLをパースして動画エントリのリストを返す。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise RSSFetchError(
            f"RSSフィードのXMLパースに失敗: チャンネル {channel_id}: {e}"
        ) from e

    videos = []
    for entry in root.findall("atom:entry", NS):
        video_id_elem = entry.find("yt:videoId", NS)
        title_elem = entry.find("atom:title", NS)
        link_elem = entry.find("atom:link[@rel='alternate']", NS)
        published_elem = entry.find("atom:published", NS)
        channel_id_elem = entry.find("yt:channelId", NS)

        if video_id_elem is None or title_elem is None:
            continue

        video_id = video_id_elem.text or ""
        title = title_elem.text or ""
        url = link_elem.get("href", "") if link_elem is not None else ""
        published_str = published_elem.text or "" if published_elem is not None else ""
        entry_channel_id = (
            channel_id_elem.text or "" if channel_id_elem is not None else channel_id
        )

        try:
            published = datetime.fromisoformat(published_str)
        except (ValueError, TypeError):
            published = datetime.now(timezone.utc)

        if video_id and title:
            videos.append(
                VideoEntry(
                    video_id=video_id,
                    title=title,
                    url=url,
                    published=published,
                    channel_id=entry_channel_id,
                )
            )

    return videos
