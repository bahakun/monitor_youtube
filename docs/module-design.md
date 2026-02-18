# モジュール設計書

## 概要

各モジュールのインターフェース（関数シグネチャ・データ型・責務）を定義する。
実装時はこのドキュメントに従い、モジュール間の依存を最小限に保つ。

---

## 1. データ型定義（`src/models.py`）

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ChannelConfig:
    """チャンネル設定"""
    channel_id: str
    name: str
    prompt_template: Optional[str]  # None の場合デフォルトプロンプトを使用


@dataclass
class AppSettings:
    """アプリケーション設定"""
    check_interval_minutes: int      # 5
    max_summary_length: int          # 3500
    history_retention_days: int      # 90
    default_prompt_template: str     # デフォルト要約プロンプト


@dataclass
class VideoEntry:
    """RSSフィードから取得した動画情報"""
    video_id: str
    title: str
    url: str
    published: datetime
    channel_id: str
```

> **実装メモ**: `NotifiedVideo` は独立した dataclass とせず、`history_manager.py` 内で辞書として管理している。

---

## 2. config_loader.py

### 責務
`config/channels.yml` を読み込み、チャンネルリストとアプリケーション設定を返す。

### インターフェース

```python
def load_config(config_path: str = "config/channels.yml") -> tuple[list[ChannelConfig], AppSettings]:
    """
    設定ファイルを読み込む。

    Args:
        config_path: 設定ファイルのパス

    Returns:
        (チャンネル設定リスト, アプリケーション設定) のタプル

    Raises:
        FileNotFoundError: 設定ファイルが存在しない場合
        ValueError: 設定ファイルの形式が不正な場合
    """
```

### 依存
- 標準ライブラリ: `pathlib`
- 外部ライブラリ: `pyyaml`

---

## 3. rss_checker.py

### 責務
YouTube RSSフィードをHTTPで取得し、XMLをパースして動画エントリのリストを返す。

### インターフェース

```python
import xml.etree.ElementTree as ET

def fetch_feed(channel_id: str) -> list[VideoEntry]:
    """
    指定チャンネルのRSSフィードを取得し、動画エントリを返す。

    Args:
        channel_id: YouTubeチャンネルID

    Returns:
        動画エントリのリスト（公開日時の新しい順）

    Raises:
        RSSFetchError: フィード取得またはパースに失敗した場合
    """
```

### RSS URL
```
https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}
```

### 依存
- 標準ライブラリ: `xml.etree.ElementTree`, `urllib.request` (or `requests`)
- 外部ライブラリ: `requests`（推奨）

---

## 4. video_filter.py

### 責務
動画リストからShorts・ライブ配信を除外し、通常動画のみを返す。

### インターフェース

```python
def filter_videos(videos: list[VideoEntry]) -> list[VideoEntry]:
    """
    Shorts・ライブ配信を除外する。

    判定ロジック:
    - Shorts: URLに '/shorts/' が含まれる、または動画の長さが60秒以下
    - ライブ配信: YouTube oEmbed API or ページメタデータで判別

    Args:
        videos: フィルタリング前の動画リスト

    Returns:
        通常動画のみのリスト
    """


def is_short(video: VideoEntry) -> bool:
    """Shortsかどうか判定する。"""


def is_live_stream(video: VideoEntry) -> bool:
    """ライブ配信（またはアーカイブ）かどうか判定する。"""
```

### Shorts判定の方法
1. **oEmbed API** で動画ページの情報を取得し、URLに `/shorts/` が含まれるか確認
   ```
   GET https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json
   ```
2. レスポンスが取得できない場合はShortsでないとみなす

### ライブ配信判定の方法
- oEmbed API のレスポンスや、RSSフィードの `media:group` 情報から判断
- 確実な判定が難しい場合は、YouTube Data API v3 の `liveStreamingDetails` を使う手もあるが、APIキーが必要になるため要検討

### 依存
- 外部ライブラリ: `requests`

---

## 5. summarizer.py

### 責務
Gemini APIに動画URLとプロンプトを送り、要約テキストを取得する。

### インターフェース

```python
def summarize(
    video_url: str,
    prompt_template: str,
    api_key: str,
    max_length: int = 3500
) -> str:
    """
    Gemini APIで動画を要約する。

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
```

### APIリクエスト構成

```python
# モデル: gemini-2.0-flash（無料枠対象）
MODEL = "gemini-2.0-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# fileData方式でYouTube動画URLを直接渡す
request_body = {
    "contents": [{
        "parts": [
            {"text": prompt},
            {"fileData": {"mimeType": "video/*", "fileUri": video_url}},
        ]
    }],
    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
}
```

> **レートリミット対策**: `main.py` で連続呼び出し間に4秒のディレイを挿入している（15RPM = 4秒/リクエスト）。

### 依存
- 外部ライブラリ: `requests`
- 環境変数: `GEMINI_API_KEY`

---

## 6. discord_notifier.py

### 責務
Discord Webhookを使ってEmbed形式で通知を送信する。

### インターフェース

```python
def send_notification(
    webhook_url: str,
    video: VideoEntry,
    channel_name: str,
    summary: str
) -> None:
    """
    動画の要約をDiscordに通知する。

    要約が4,096文字を超える場合は複数Embedに分割して送信する。

    Args:
        webhook_url: Discord Webhook URL
        video: 動画情報
        channel_name: チャンネル表示名
        summary: 要約テキスト

    Raises:
        DiscordNotifyError: Webhook送信失敗時
    """


def send_error_notification(
    webhook_url: str,
    error_title: str,
    error_detail: str
) -> None:
    """
    エラー情報をDiscordに通知する（赤色Embed）。

    Args:
        webhook_url: Discord Webhook URL
        error_title: エラーの種類
        error_detail: エラーの詳細メッセージ

    Raises:
        DiscordNotifyError: Webhook送信失敗時
    """


def _split_summary_into_embeds(
    summary: str,
    max_length: int = 4096
) -> list[str]:
    """
    要約テキストをEmbed description上限に収まるよう分割する。
    セクション（## 📌）単位で分割する。
    """
```

### 依存
- 外部ライブラリ: `requests`
- 環境変数: `DISCORD_WEBHOOK_URL`

---

## 7. history_manager.py

### 責務
通知済み動画の履歴（`data/notified.json`）を管理する。読み込み・書き込み・既読判定・古いエントリの削除。

### インターフェース

```python
class HistoryManager:
    def __init__(self, data_path: str = "data/notified.json"):
        """履歴ファイルを指定してインスタンスを生成する。"""

    def load(self) -> None:
        """履歴ファイルを読み込む。ファイルが存在しない場合は空の状態で初期化する。"""

    def is_notified(self, video_id: str) -> bool:
        """指定した動画IDが通知済みかどうかを返す。"""

    def filter_new(self, videos: list[VideoEntry]) -> list[VideoEntry]:
        """通知済み動画を除外して新着のみ返す。"""

    def mark_notified(self, video: VideoEntry) -> None:
        """動画を通知済みとして記録する。"""

    def cleanup_old_entries(self, retention_days: int = 90) -> int:
        """
        指定日数以上前のエントリを削除する。

        Returns:
            削除したエントリ数
        """

    def save(self) -> None:
        """履歴をファイルに保存する。"""
```

### 依存
- 標準ライブラリ: `json`, `datetime`, `pathlib`

---

## 8. main.py

### 責務
全モジュールを組み合わせたオーケストレーション。エントリーポイント。

### インターフェース

```python
def main() -> None:
    """
    メイン処理フロー:
    1. 設定読み込み
    2. 履歴読み込み
    3. チャンネルごとにRSS取得→フィルタ→要約→通知
    4. 古いエントリの削除
    5. 履歴保存
    """
```

### 環境変数
| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Gemini APIキー |
| `DISCORD_WEBHOOK_URL` | Yes | Discord Webhook URL |

### 依存
- 上記すべてのモジュール

---

## 9. 例外クラス定義

```python
# src/exceptions.py

class AppError(Exception):
    """アプリケーション基底例外"""
    pass

class RSSFetchError(AppError):
    """RSSフィード取得失敗"""
    pass

class SummarizerError(AppError):
    """要約生成失敗"""
    pass

class RateLimitError(SummarizerError):
    """Gemini APIレートリミット超過"""
    pass

class DiscordNotifyError(AppError):
    """Discord通知送信失敗"""
    pass

class ConfigError(AppError):
    """設定ファイル関連エラー"""
    pass
```

---

## 10. モジュール依存関係

```
main.py
  ├── models.py            (外部依存なし)       ← 全モジュールから参照
  ├── exceptions.py        (外部依存なし)       ← 全モジュールから参照
  ├── config_loader.py     (pyyaml)
  ├── history_manager.py   (外部依存なし)
  ├── rss_checker.py       (requests)
  ├── video_filter.py      (requests)
  ├── summarizer.py        (requests)
  └── discord_notifier.py  (requests)
```

- 各モジュールは `main.py` からのみ呼び出され、モジュール間の直接依存はない
- `models.py` と `exceptions.py` は共有ライブラリとして全モジュールから参照される
- `__main__.py` は `python -m src.main` 実行用のエントリーポイント
