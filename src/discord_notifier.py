import json
import logging
import re
import time
from datetime import datetime, timezone

import requests

from src.exceptions import DiscordNotifyError
from src.models import VideoEntry

logger = logging.getLogger(__name__)

# Embed制限
MAX_EMBED_DESCRIPTION = 4096
MAX_EMBED_TITLE = 256
MAX_EMBEDS_PER_MESSAGE = 10

# カラーコード
COLOR_NORMAL = 3447003   # 青系 (#3498DB)
COLOR_ERROR = 15158332   # 赤系 (#E74C3C)

# リトライ設定
MAX_RETRIES = 3
BACKOFF_SECONDS = [5, 10, 20]


def send_notification(
    webhook_url: str,
    video: VideoEntry,
    channel_name: str,
    summary: str,
) -> None:
    """動画の要約をDiscordに通知する。

    要約が4,096文字を超える場合は複数Embedに分割して送信する。

    Args:
        webhook_url: Discord Webhook URL
        video: 動画情報
        channel_name: チャンネル表示名
        summary: 要約テキスト

    Raises:
        DiscordNotifyError: Webhook送信失敗時
    """
    summary_parts = _split_summary_into_embeds(summary)
    embeds = []

    for i, part in enumerate(summary_parts):
        if i == 0:
            # 最初のEmbedに動画情報を含める
            title = video.title
            if len(title) > MAX_EMBED_TITLE - 2:
                title = title[: MAX_EMBED_TITLE - 3] + "..."

            embed = {
                "title": f"\U0001f3ac {title}",
                "url": video.url,
                "description": part,
                "color": COLOR_NORMAL,
                "fields": [
                    {"name": "チャンネル", "value": channel_name, "inline": True},
                    {
                        "name": "投稿日時",
                        "value": video.published.strftime("%Y-%m-%d %H:%M"),
                        "inline": True,
                    },
                ],
                "footer": {"text": "AI要約 by Gemini"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            embed = {
                "title": f"\U0001f3ac {video.title[:50]}...（続き {i + 1}/{len(summary_parts)}）",
                "description": part,
                "color": COLOR_NORMAL,
            }

        embeds.append(embed)

        if len(embeds) >= MAX_EMBEDS_PER_MESSAGE:
            break

    _send_webhook(webhook_url, {"embeds": embeds})
    logger.info("通知送信完了 - 動画「%s」", video.title)


def send_image_notification(
    webhook_url: str,
    video: VideoEntry,
    channel_name: str,
    image_path: str,
) -> None:
    """動画の要約インフォグラフィック画像をDiscordに送信する。

    画像ファイルをmultipart/form-dataでアップロードし、
    動画URLをcontentテキストとして添付する（クリック可能なリンク）。

    Args:
        webhook_url: Discord Webhook URL
        video: 動画情報
        channel_name: チャンネル表示名
        image_path: インフォグラフィックPNG画像のパス

    Raises:
        DiscordNotifyError: Webhook送信失敗時
    """
    payload = {
        "content": f"**{channel_name}** の新着動画\n<{video.url}>",
    }

    _send_webhook_with_file(webhook_url, payload, image_path)
    logger.info("画像通知送信完了 - 動画「%s」", video.title)


def send_error_notification(
    webhook_url: str,
    error_title: str,
    error_detail: str,
) -> None:
    """エラー情報をDiscordに通知する（赤色Embed）。

    Args:
        webhook_url: Discord Webhook URL
        error_title: エラーの種類
        error_detail: エラーの詳細メッセージ

    Raises:
        DiscordNotifyError: Webhook送信失敗時
    """
    embed = {
        "title": error_title,
        "description": error_detail[:MAX_EMBED_DESCRIPTION],
        "color": COLOR_ERROR,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _send_webhook(webhook_url, {"embeds": [embed]})
        logger.info("エラー通知送信完了: %s", error_title)
    except DiscordNotifyError as e:
        # エラー通知の送信自体が失敗した場合はログのみ
        logger.error("エラー通知の送信に失敗: %s: %s", error_title, e)


def _split_summary_into_embeds(
    summary: str, max_length: int = MAX_EMBED_DESCRIPTION
) -> list[str]:
    """要約テキストをEmbed description上限に収まるよう分割する。

    セクション（## ）単位で分割する。
    """
    if len(summary) <= max_length:
        return [summary]

    # セクション区切りで分割
    sections = re.split(r"(?=^## )", summary, flags=re.MULTILINE)
    sections = [s for s in sections if s.strip()]

    if not sections:
        # セクション区切りがない場合は文字数で分割
        return _split_by_length(summary, max_length)

    parts = []
    current = ""

    for section in sections:
        if len(current) + len(section) <= max_length:
            current += section
        else:
            if current:
                parts.append(current)
            # 単一セクションが上限を超える場合はさらに分割
            if len(section) > max_length:
                parts.extend(_split_by_length(section, max_length))
            else:
                current = section
                continue
            current = ""

    if current:
        parts.append(current)

    return parts if parts else [summary[:max_length]]


def _split_by_length(text: str, max_length: int) -> list[str]:
    """テキストを最大文字数で分割する（改行位置で区切る）。"""
    parts = []
    while len(text) > max_length:
        # 改行位置で区切る
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos <= 0:
            split_pos = max_length
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


def _send_webhook(webhook_url: str, payload: dict) -> None:
    """Discord Webhookにペイロードを送信する（リトライ付き）。"""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
            )

            # 204: 成功
            if response.status_code == 204:
                return

            # 200もOK（一部のWebhookで返る）
            if response.status_code == 200:
                return

            # 429: Discord レートリミット — Retry-Afterに従う
            if response.status_code == 429:
                retry_after = _get_retry_after(response)
                logger.warning(
                    "Discord レートリミット - %d秒待機", retry_after
                )
                time.sleep(retry_after)
                continue

            # 4xx: クライアントエラー — リトライしない
            if 400 <= response.status_code < 500:
                raise DiscordNotifyError(
                    f"Discord Webhookエラー(HTTP {response.status_code}): "
                    f"{response.text[:200]}"
                )

            # 5xx: サーバーエラー — リトライ
            last_error = DiscordNotifyError(
                f"Discord Webhookエラー(HTTP {response.status_code})"
            )

        except requests.exceptions.RequestException as e:
            last_error = DiscordNotifyError(
                f"Discord Webhookネットワークエラー: {e}"
            )

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_SECONDS[attempt]
            logger.warning(
                "Discord Webhookリトライ %d/%d - %d秒待機",
                attempt + 1,
                MAX_RETRIES,
                wait,
            )
            time.sleep(wait)

    raise last_error


def _send_webhook_with_file(
    webhook_url: str,
    payload: dict,
    image_path: str,
) -> None:
    """Discord Webhookに画像ファイル付きペイロードを送信する（リトライ付き）。"""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            with open(image_path, "rb") as f:
                files = {
                    "payload_json": (None, json.dumps(payload), "application/json"),
                    "files[0]": ("summary.png", f, "image/png"),
                }
                response = requests.post(
                    webhook_url,
                    files=files,
                    timeout=30,
                )

            if response.status_code in (200, 204):
                return

            if response.status_code == 429:
                retry_after = _get_retry_after(response)
                logger.warning(
                    "Discord レートリミット - %d秒待機", retry_after
                )
                time.sleep(retry_after)
                continue

            if 400 <= response.status_code < 500:
                raise DiscordNotifyError(
                    f"Discord Webhookエラー(HTTP {response.status_code}): "
                    f"{response.text[:200]}"
                )

            last_error = DiscordNotifyError(
                f"Discord Webhookエラー(HTTP {response.status_code})"
            )

        except requests.exceptions.RequestException as e:
            last_error = DiscordNotifyError(
                f"Discord Webhookネットワークエラー: {e}"
            )

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_SECONDS[attempt]
            logger.warning(
                "Discord Webhookリトライ %d/%d - %d秒待機",
                attempt + 1,
                MAX_RETRIES,
                wait,
            )
            time.sleep(wait)

    raise last_error


def _get_retry_after(response: requests.Response) -> int:
    """Retry-Afterヘッダから待機秒数を取得する。"""
    try:
        # ヘッダから取得
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            return int(float(retry_after)) + 1

        # JSONボディから取得
        data = response.json()
        retry_after_ms = data.get("retry_after", 5000)
        return int(retry_after_ms / 1000) + 1
    except (ValueError, KeyError, TypeError):
        return 5
