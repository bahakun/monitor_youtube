import logging
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.exceptions import ImageGenerationError

logger = logging.getLogger(__name__)

VIEWPORT_WIDTH = 1200
DEVICE_SCALE_FACTOR = 2


def generate_infographic(
    html_content: str,
    video_title: str,
) -> str:
    """Geminiが生成したHTMLからインフォグラフィック画像（PNG）を生成する。

    Args:
        html_content: Geminiが生成した完全なHTMLドキュメント
        video_title: ログ用の動画タイトル

    Returns:
        生成されたPNG画像のファイルパス（一時ファイル）

    Raises:
        ImageGenerationError: 画像生成に失敗した場合
    """
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix="yt_summary_", delete=False
        )
        tmp.close()
        output_path = tmp.name

        _render_html_to_png(html_content, output_path)

        file_size = Path(output_path).stat().st_size
        logger.info(
            "インフォグラフィック生成完了 - 動画「%s」 (%.1f KB)",
            video_title,
            file_size / 1024,
        )
        return output_path

    except ImageGenerationError:
        raise
    except Exception as e:
        raise ImageGenerationError(
            f"インフォグラフィック生成失敗: {video_title}: {e}"
        ) from e


def cleanup_temp_image(image_path: str) -> None:
    """一時画像ファイルを削除する。"""
    try:
        path = Path(image_path)
        if path.exists():
            path.unlink()
            logger.debug("一時画像ファイル削除: %s", image_path)
    except OSError as e:
        logger.warning("一時画像ファイルの削除に失敗: %s: %s", image_path, e)


def _render_html_to_png(html_content: str, output_path: str) -> None:
    """PlaywrightでHTMLをレンダリングしPNGスクリーンショットを取得する。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": VIEWPORT_WIDTH, "height": 800},
            device_scale_factor=DEVICE_SCALE_FACTOR,
        )
        page.set_content(html_content, wait_until="networkidle")

        # Google Fontsの読み込み待ち
        page.wait_for_timeout(2000)

        # ページ全体をフルページスクリーンショット
        page.screenshot(path=output_path, full_page=True)

        browser.close()
