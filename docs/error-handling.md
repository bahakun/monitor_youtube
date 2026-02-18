# エラーハンドリング方針

## 1. 基本方針

- エラーが発生しても**可能な限り処理を継続**する（1チャンネルの失敗が他チャンネルに影響しない）
- すべてのエラーは**Discord同一チャンネルに赤色Embed**で通知する
- リカバリ可能なエラーは自動リトライ、不可能なエラーはスキップして次回実行に委ねる
- 標準出力に`logging`モジュールでログを出力する（GitHub Actionsのログに記録される）

---

## 2. エラー分類と対応方針

### 2.1 RSSフィード取得エラー（`RSSFetchError`）

| エラー | 原因 | 対応 |
|---|---|---|
| HTTP タイムアウト | ネットワーク問題 | 3回リトライ（間隔: 5秒, 10秒, 20秒） |
| HTTP 4xx | チャンネルIDが無効・チャンネル削除 | Discord通知 → 該当チャンネルをスキップ |
| HTTP 5xx | YouTube側の障害 | 3回リトライ → 失敗ならスキップ |
| XMLパースエラー | 不正なフィード | Discord通知 → 該当チャンネルをスキップ |

**影響範囲**: 該当チャンネルのみ。他チャンネルの処理は継続。

### 2.2 Gemini API エラー（`SummarizerError`, `RateLimitError`）

| エラー | 原因 | 対応 |
|---|---|---|
| HTTP 400 | リクエスト不正（動画が解析不能等） | Discord通知 → 該当動画をスキップ |
| HTTP 403 | APIキー無効・権限不足 | Discord通知 → **全処理を停止** |
| HTTP 429 | レートリミット超過 | **残りの動画をすべてスキップ**（次回実行で処理） |
| HTTP 500/503 | サーバーエラー | 3回リトライ（間隔: 10秒, 30秒, 60秒） → 失敗なら該当動画をスキップ |
| レスポンス不正 | `finishReason` が `STOP` でない | Discord通知 → 該当動画をスキップ |

**レートリミット時の重要ルール**:
- 429を受け取った時点で、**そのチャンネルおよび後続チャンネルの要約処理を中断**する
- 通知されなかった動画は `notified.json` に記録しない → 次回実行時に再検出される

### 2.3 Discord Webhook エラー（`DiscordNotifyError`）

| エラー | 原因 | 対応 |
|---|---|---|
| HTTP 429 | レートリミット | `Retry-After` ヘッダの秒数待機してリトライ |
| HTTP 4xx | Webhook URL無効 | ログ出力（Discord通知は不可能）→ **全処理を停止** |
| HTTP 5xx | Discord側の障害 | 3回リトライ（間隔: 5秒, 10秒, 20秒） |
| 送信失敗 | ネットワーク問題 | 3回リトライ → 失敗ならログ出力のみ |

**Discord自体が使えない場合**: ログ出力のみ。GitHub Actionsのログで確認する。

### 2.4 設定ファイルエラー（`ConfigError`）

| エラー | 原因 | 対応 |
|---|---|---|
| ファイル不存在 | `channels.yml` が見つからない | **即座に停止**（致命的エラー） |
| YAML構文エラー | YAMLの書式が不正 | **即座に停止**（致命的エラー） |
| バリデーションエラー | 必須フィールド欠損等 | **即座に停止**（致命的エラー） |

**設定エラーは修正が必要なため、自動リカバリは行わない。**

### 2.5 履歴ファイルエラー

| エラー | 原因 | 対応 |
|---|---|---|
| ファイル不存在 | 初回実行 or 削除された | 空の状態で初期化して続行 |
| JSON構文エラー | ファイル破損 | Discord通知 → 空の状態で初期化して続行（重複通知のリスクあり） |
| 書き込み失敗 | ディスク/権限問題 | Discord通知 → ログ出力（次回起動時に重複通知の可能性） |

---

## 3. リトライ戦略

### 共通設定

```python
RETRY_CONFIG = {
    "rss": {
        "max_retries": 3,
        "backoff_seconds": [5, 10, 20],
    },
    "gemini": {
        "max_retries": 3,
        "backoff_seconds": [10, 30, 60],
    },
    "discord": {
        "max_retries": 3,
        "backoff_seconds": [5, 10, 20],
    },
}
```

### リトライ対象の判定

```
リトライする:
  - ネットワークタイムアウト
  - HTTP 5xx（サーバーエラー）
  - Discord HTTP 429（Retry-Afterに従う）

リトライしない:
  - HTTP 4xx（クライアントエラー） ※Discord 429を除く
  - Gemini HTTP 429（レートリミット — 次回実行に委ねる）
  - パースエラー
  - 設定エラー
```

---

## 4. Discord エラー通知のフォーマット

### 通常エラー

```json
{
  "embeds": [{
    "title": "⚠️ [エラー種別]",
    "description": "エラーの詳細メッセージ",
    "color": 15158332,
    "fields": [
      {"name": "チャンネル", "value": "チャンネル名", "inline": true},
      {"name": "動画", "value": "動画タイトル（該当する場合）", "inline": true}
    ],
    "timestamp": "2025-01-01T12:00:00Z"
  }]
}
```

### エラー種別ラベル

| 種別 | title |
|---|---|
| RSS取得失敗 | `⚠️ RSSフィード取得エラー` |
| 要約生成失敗 | `⚠️ 要約生成エラー` |
| レートリミット | `⚠️ Gemini APIレートリミット` |
| Discord送信失敗 | （Discord通知不可のためログのみ） |
| 設定エラー | `⚠️ 設定ファイルエラー` |
| 履歴ファイルエラー | `⚠️ 履歴ファイルエラー` |

---

## 5. ロギング

### ログレベルの使い分け

| レベル | 用途 |
|---|---|
| `INFO` | 正常処理の進行状況（チャンネル処理開始、動画検出数、通知成功等） |
| `WARNING` | リカバリ可能なエラー（リトライ成功、スキップした動画等） |
| `ERROR` | リカバリ不可能なエラー（リトライ失敗、致命的エラー） |

### ログフォーマット

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

### ログ出力例

```
2025-01-01 12:00:00 [INFO] main: 処理開始 - 監視チャンネル数: 3
2025-01-01 12:00:01 [INFO] rss_checker: チャンネル「テック系」のRSSフィード取得完了 - 動画数: 15
2025-01-01 12:00:01 [INFO] video_filter: フィルタ後 - 通常動画: 12, 除外(Shorts): 2, 除外(ライブ): 1
2025-01-01 12:00:01 [INFO] history_manager: 新着動画: 2件
2025-01-01 12:00:15 [INFO] summarizer: 要約生成完了 - 動画「最新ニュース」(1234トークン)
2025-01-01 12:00:16 [INFO] discord_notifier: 通知送信完了 - 動画「最新ニュース」
2025-01-01 12:00:30 [WARNING] summarizer: Gemini APIエラー(500) - リトライ 1/3
2025-01-01 12:01:00 [ERROR] summarizer: Gemini APIエラー(500) - リトライ上限到達、スキップ
```

---

## 6. 処理フロー内のエラーハンドリング（疑似コード）

```python
def main():
    try:
        config, settings = load_config()
    except ConfigError as e:
        logging.error(f"設定エラー: {e}")
        # Discord通知を試みる（Webhook URLが環境変数にあれば）
        sys.exit(1)

    history = HistoryManager()
    history.load()  # ファイル不存在・破損時は空で初期化

    rate_limited = False

    for channel in config:
        if rate_limited:
            logging.warning(f"レートリミット中のためスキップ: {channel.name}")
            continue

        try:
            videos = fetch_feed(channel.channel_id)
        except RSSFetchError as e:
            send_error_notification(...)
            continue  # 次のチャンネルへ

        filtered = filter_videos(videos)
        new_videos = history.filter_new(filtered)

        for video in new_videos:
            try:
                summary = summarize(video.url, ...)
            except RateLimitError:
                send_error_notification(...)
                rate_limited = True
                break  # このチャンネルと後続チャンネルをスキップ
            except SummarizerError as e:
                send_error_notification(...)
                continue  # 次の動画へ

            try:
                send_notification(...)
            except DiscordNotifyError as e:
                logging.error(f"Discord通知失敗: {e}")
                continue  # 通知失敗しても notified.json には記録しない

            history.mark_notified(video)

    history.cleanup_old_entries(settings.history_retention_days)
    history.save()
```
