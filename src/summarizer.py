import logging
import re
import time

import requests

from src.exceptions import RateLimitError, SummarizerError, TokenLimitError

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# リトライ設定
MAX_RETRIES = 3
BACKOFF_SECONDS = [10, 30, 60]


def summarize(
    video_url: str,
    prompt_template: str,
    api_key: str,
    max_length: int = 3500,
) -> str:
    """Gemini APIで動画を要約する。

    Args:
        video_url: YouTube動画のURL
        prompt_template: 要約プロンプト
        api_key: Gemini APIキー
        max_length: 要約の最大文字数

    Returns:
        要約テキスト（Markdown形式）

    Raises:
        SummarizerError: API呼び出し失敗時
        RateLimitError: レートリミット超過時（429）
    """
    prompt = prompt_template

    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "fileData": {
                            "mimeType": "video/*",
                            "fileUri": video_url,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 16384,
        },
    }

    response_data = _call_api_with_retry(api_key, request_body, video_url)
    raw_output = _extract_summary(response_data, video_url)

    # GeminiがMarkdownコードブロックで囲む場合があるので除去
    html_content = _extract_html(raw_output)

    logger.info(
        "HTML生成完了 - 動画URL: %s (%d文字)",
        video_url,
        len(html_content),
    )
    return html_content


def _call_api_with_retry(
    api_key: str, request_body: dict, video_url: str
) -> dict:
    """リトライ付きでGemini APIを呼び出す。"""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                ENDPOINT,
                params={"key": api_key},
                json=request_body,
                timeout=300,
            )

            if response.status_code == 200:
                return response.json()

            # 429: レートリミット — リトライせず即座に例外
            if response.status_code == 429:
                raise RateLimitError(
                    f"Gemini APIレートリミット超過: {video_url}"
                )

            # 403: APIキー無効 — リトライせず即座に例外
            if response.status_code == 403:
                raise SummarizerError(
                    f"Gemini APIキーが無効または権限不足(HTTP 403): {video_url}"
                )

            # 400: リクエスト不正 — リトライせず
            if response.status_code == 400:
                error_msg = _extract_error_message(response)
                if "token" in error_msg.lower() and "exceed" in error_msg.lower():
                    raise TokenLimitError(
                        f"動画が長すぎてGemini APIのトークン上限を超過: {video_url}"
                    )
                raise SummarizerError(
                    f"Gemini APIリクエストエラー(HTTP 400): {video_url}: {error_msg}"
                )

            # 5xx: サーバーエラー — リトライ
            last_error = SummarizerError(
                f"Gemini APIエラー(HTTP {response.status_code}): {video_url}"
            )

        except requests.exceptions.RequestException as e:
            last_error = SummarizerError(
                f"Gemini APIネットワークエラー: {video_url}: {e}"
            )

        if attempt < MAX_RETRIES - 1:
            wait = BACKOFF_SECONDS[attempt]
            logger.warning(
                "Gemini APIリトライ %d/%d - %d秒待機: %s",
                attempt + 1,
                MAX_RETRIES,
                wait,
                video_url,
            )
            time.sleep(wait)

    raise last_error


def _extract_summary(response_data: dict, video_url: str) -> str:
    """APIレスポンスから要約テキストを抽出する。"""
    try:
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise SummarizerError(f"Gemini APIから候補が返されませんでした: {video_url}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason != "STOP":
            logger.warning(
                "Gemini API finishReason が STOP ではありません: %s (動画: %s)",
                finish_reason,
                video_url,
            )

        parts = candidate.get("content", {}).get("parts", [])
        if not parts:
            raise SummarizerError(f"Gemini APIレスポンスにテキストが含まれていません: {video_url}")

        summary = parts[0].get("text", "")
        if not summary.strip():
            raise SummarizerError(f"Gemini APIから空の要約が返されました: {video_url}")

        # トークン使用量をログ出力
        usage = response_data.get("usageMetadata", {})
        total_tokens = usage.get("totalTokenCount", 0)
        if total_tokens:
            logger.info("トークン使用量: %d (動画: %s)", total_tokens, video_url)

        return summary

    except (KeyError, IndexError, TypeError) as e:
        raise SummarizerError(
            f"Gemini APIレスポンスの解析に失敗: {video_url}: {e}"
        ) from e


def _extract_html(raw_output: str) -> str:
    """Gemini出力からHTMLを抽出する。

    コードブロック（```html ... ```）で囲まれている場合は除去し、
    <!DOCTYPE html>から</html>までを抽出する。
    """
    # ```html ... ``` の除去
    cleaned = re.sub(r"^```html?\s*\n?", "", raw_output.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip())

    # <!DOCTYPE html> から </html> までを抽出
    match = re.search(
        r"(<!DOCTYPE html>.*?</html>)", cleaned, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1)

    # <html> から </html> でも試行
    match = re.search(r"(<html.*?>.*?</html>)", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)

    # HTMLタグが含まれていればそのまま返す
    if "<" in cleaned and ">" in cleaned:
        return cleaned

    raise SummarizerError("Gemini APIの出力にHTMLが含まれていません")


def _extract_error_message(response: requests.Response) -> str:
    """エラーレスポンスからメッセージを抽出する。"""
    try:
        data = response.json()
        return data.get("error", {}).get("message", response.text[:200])
    except (ValueError, KeyError):
        return response.text[:200]
