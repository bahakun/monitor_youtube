import logging
import os
import sys
import time

from dotenv import load_dotenv

from src.config_loader import load_config
from src.discord_notifier import send_error_notification, send_image_notification
from src.exceptions import (
    ConfigError,
    DiscordNotifyError,
    ImageGenerationError,
    RateLimitError,
    RSSFetchError,
    SummarizerError,
)
from src.image_generator import cleanup_temp_image, generate_infographic
from src.history_manager import HistoryManager
from src.rss_checker import fetch_feed
from src.summarizer import summarize
from src.video_filter import filter_videos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """メイン処理フロー。

    1. 環境変数の検証
    2. 設定読み込み
    3. 履歴読み込み
    4. チャンネルごとにRSS取得 → フィルタ → 要約 → 通知
    5. 古いエントリの削除
    6. 履歴保存
    """
    # .envファイルから環境変数を読み込み（存在しない場合は無視）
    load_dotenv()

    # 環境変数の検証
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    if not gemini_api_key:
        logger.error("環境変数 GEMINI_API_KEY が設定されていません")
        sys.exit(1)
    if not discord_webhook_url:
        logger.error("環境変数 DISCORD_WEBHOOK_URL が設定されていません")
        sys.exit(1)

    # 設定ファイルの読み込み
    try:
        channels, settings = load_config()
    except ConfigError as e:
        logger.error("設定エラー: %s", e)
        try:
            send_error_notification(
                discord_webhook_url,
                "\u26a0\ufe0f 設定ファイルエラー",
                str(e),
            )
        except Exception:
            pass
        sys.exit(1)

    # 履歴の読み込み
    history = HistoryManager()
    history.load()

    logger.info("処理開始 - 監視チャンネル数: %d", len(channels))

    # Gemini API 15RPM対策: 呼び出し間に4秒のディレイを入れる
    API_CALL_DELAY_SECONDS = 4
    rate_limited = False
    is_first_summary = True

    for channel in channels:
        if rate_limited:
            logger.warning("レートリミット中のためスキップ: %s", channel.name)
            continue

        logger.info("チャンネル処理開始: %s (%s)", channel.name, channel.channel_id)

        # RSSフィード取得
        try:
            videos = fetch_feed(channel.channel_id)
        except RSSFetchError as e:
            logger.error("RSSフィード取得失敗: %s: %s", channel.name, e)
            try:
                send_error_notification(
                    discord_webhook_url,
                    "\u26a0\ufe0f RSSフィード取得エラー",
                    f"チャンネル: {channel.name}\n{e}",
                )
            except Exception:
                pass
            continue

        # フィルタリング
        filtered = filter_videos(videos)

        # 新着判定
        new_videos = history.filter_new(filtered)

        if not new_videos:
            logger.info("新着動画なし: %s", channel.name)
            continue

        # プロンプトの決定
        prompt_template = channel.prompt_template or settings.default_prompt_template

        # 新着動画ごとに要約・通知
        for video in new_videos:
            # Gemini APIレートリミット対策: 連続呼び出し間にディレイ
            if not is_first_summary:
                logger.info("%d秒待機（API レートリミット対策）", API_CALL_DELAY_SECONDS)
                time.sleep(API_CALL_DELAY_SECONDS)
            is_first_summary = False

            # 要約生成
            try:
                summary = summarize(
                    video_url=video.url,
                    prompt_template=prompt_template,
                    api_key=gemini_api_key,
                    max_length=settings.max_summary_length,
                )
            except RateLimitError as e:
                logger.warning("Gemini APIレートリミット: %s - 残りは次回実行時に処理", e)
                rate_limited = True
                break
            except SummarizerError as e:
                logger.error("要約生成失敗: %s: %s", video.title, e)
                try:
                    send_error_notification(
                        discord_webhook_url,
                        "\u26a0\ufe0f 要約生成エラー",
                        f"チャンネル: {channel.name}\n動画: {video.title}\n{e}",
                    )
                except Exception:
                    pass
                continue

            # インフォグラフィック画像生成
            image_path = None
            try:
                image_path = generate_infographic(
                    html_content=summary,
                    video_title=video.title,
                )
            except ImageGenerationError as e:
                logger.error("画像生成失敗: %s: %s", video.title, e)
                try:
                    send_error_notification(
                        discord_webhook_url,
                        "\u26a0\ufe0f 画像生成エラー",
                        f"チャンネル: {channel.name}\n動画: {video.title}\n{e}",
                    )
                except Exception:
                    pass
                continue

            # Discord画像通知
            try:
                send_image_notification(
                    webhook_url=discord_webhook_url,
                    video=video,
                    channel_name=channel.name,
                    image_path=image_path,
                )
            except DiscordNotifyError as e:
                logger.error("Discord通知失敗: %s: %s", video.title, e)
                continue
            finally:
                if image_path:
                    cleanup_temp_image(image_path)

            # 通知成功 → 履歴に記録
            history.mark_notified(video)

    # 古いエントリの削除
    history.cleanup_old_entries(settings.history_retention_days)

    # 履歴の保存
    history.save()

    logger.info("処理完了")


if __name__ == "__main__":
    main()
