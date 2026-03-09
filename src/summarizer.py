import logging
import re
import time

import requests

from src.exceptions import RateLimitError, SummarizerError, TokenLimitError

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# リトライ設定（タイムアウト600秒×2回 = 最大20分）
MAX_RETRIES = 2
BACKOFF_SECONDS = [10, 30]


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
    for is_fallback in [False, True]:
        prompt = _build_fallback_prompt(video_url) if is_fallback else prompt_template

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
                "maxOutputTokens": 65536,
            },
        }

        response_data = _call_api_with_retry(api_key, request_body, video_url)
        raw_output, finish_reason = _extract_summary(response_data, video_url)

        if finish_reason == "MAX_TOKENS" and not is_fallback:
            logger.warning(
                "MAX_TOKENSで出力が途中終了 - 短縮プロンプトで再試行: %s", video_url
            )
            time.sleep(4)
            continue

        # GeminiがMarkdownコードブロックで囲む場合があるので除去
        html_content = _extract_html(raw_output)

        logger.info(
            "HTML生成完了 - 動画URL: %s (%d文字)%s",
            video_url,
            len(html_content),
            " [短縮プロンプト]" if is_fallback else "",
        )
        return html_content

    # ここには到達しない（ループ内でreturnされるため）
    raise SummarizerError(f"HTML生成に失敗: {video_url}")


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
                timeout=600,
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


def _extract_summary(response_data: dict, video_url: str) -> tuple[str, str]:
    """APIレスポンスから要約テキストとfinishReasonを抽出する。"""
    try:
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise SummarizerError(f"Gemini APIから候補が返されませんでした: {video_url}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason not in ("STOP", "MAX_TOKENS"):
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

        return summary, finish_reason

    except (KeyError, IndexError, TypeError) as e:
        raise SummarizerError(
            f"Gemini APIレスポンスの解析に失敗: {video_url}: {e}"
        ) from e


# 短縮プロンプト（MAX_TOKENS時のフォールバック）
_FALLBACK_PROMPT = """以下のYouTube動画の内容を、シンプルな日本語HTMLインフォグラフィックに変換してください。

## デザイン仕様
- 背景色: #FFF8F0
- アクセントカラー: #F25C05（オレンジ）、#F2E63D（イエロー）
- フォント: @import url('https://fonts.googleapis.com/css2?family=Yomogi&display=swap');
- 横幅: 100%

## レイアウト
- ヘッダー: タイトル（大）＋日付
- 本文: 動画の要点を箇条書き（5〜8項目）
- フッター: 出典情報

## 出力形式
【重要】完全なHTMLドキュメント（<!DOCTYPE html>から</html>まで）を出力してください。
CSSはすべて<style>タグ内にインラインで記述してください。
外部画像は使用せず、CSS・絵文字のみで視覚要素を表現してください。
HTMLコード以外のテキストは一切出力しないでください。
最初の文字は必ず「<」で始めてください。"""


def _build_fallback_prompt(video_url: str) -> str:
    return _FALLBACK_PROMPT


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
