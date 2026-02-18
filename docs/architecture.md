# アーキテクチャ設計書

## 1. システム全体構成

```
┌─────────────────────────────────────────────────────┐
│  GitHub Actions (cron: */5 * * * *)                 │
│                                                     │
│  ┌─────────────┐    ┌──────────────┐               │
│  │ channels.yml│───→│ config_loader│               │
│  └─────────────┘    └──────┬───────┘               │
│                            │                        │
│  ┌──────────────┐   ┌──────▼───────┐               │
│  │notified.json │◄─→│history_manager│               │
│  └──────────────┘   └──────┬───────┘               │
│                            │                        │
│                     ┌──────▼───────┐               │
│                     │  main.py     │               │
│                     └──┬───┬───┬──┘               │
│                        │   │   │                    │
│            ┌───────────┘   │   └───────────┐       │
│            ▼               ▼               ▼       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ rss_checker  │  │  summarizer  │  │  discord   │ │
│  │             │  │              │  │ _notifier  │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                │        │
│  ┌──────▼──────┐         │                │        │
│  │video_filter │         │                │        │
│  └─────────────┘         │                │        │
└─────────────────────────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
   YouTube RSS        Gemini API     Discord Webhook
   フィード            (無料枠)       (Embed形式)
```

## 2. 処理フロー（シーケンス）

```
main.py
  │
  ├─ 1. config_loader.load_config()
  │     └─ channels.yml を読み込み、チャンネルリストと設定を返す
  │
  ├─ 2. history_manager.load_history()
  │     └─ notified.json を読み込み、通知済み動画IDセットを返す
  │
  ├─ 3. チャンネルごとのループ:
  │     │
  │     ├─ 3a. rss_checker.fetch_feed(channel_id)
  │     │       └─ YouTube RSSフィードをHTTP GET → XMLパース → 動画リスト返却
  │     │
  │     ├─ 3b. video_filter.filter_videos(videos)
  │     │       └─ Shorts除外、ライブ配信除外 → 通常動画のみ返却
  │     │
  │     ├─ 3c. history_manager.filter_new(videos)
  │     │       └─ 通知済み動画を除外 → 新着動画のみ返却
  │     │
  │     └─ 3d. 新着動画ごとのループ:
  │           │
  │           ├─ summarizer.summarize(video_url, prompt_template)
  │           │   └─ Gemini APIに動画URLとプロンプトを送信 → 要約テキスト返却
  │           │
  │           ├─ discord_notifier.send_notification(video_info, summary)
  │           │   └─ Discord Webhook にEmbed形式でPOST
  │           │
  │           └─ history_manager.mark_notified(video_id, video_info)
  │               └─ 通知済みとして記録
  │
  ├─ 4. history_manager.cleanup_old_entries(retention_days=90)
  │     └─ 90日以上前のエントリを削除
  │
  └─ 5. history_manager.save_history()
        └─ notified.json をファイルに書き出し
```

## 3. データフロー

```
YouTube RSS Feed (XML)
    │
    ▼
動画エントリ: {video_id, title, url, published, channel_id}
    │
    ├─ フィルタリング (Shorts除外, ライブ除外, 既読除外)
    │
    ▼
新着動画情報
    │
    ├─ Gemini API → 要約テキスト (Markdown形式)
    │
    ▼
Discord通知データ: {channel_name, title, url, published, summary}
    │
    ├─ Discord Webhook (Embed JSON)
    │
    ▼
通知履歴: {video_id → {title, channel_id, notified_at}}
    │
    └─ notified.json に永続化
```

## 4. 外部サービス依存関係

| サービス | 用途 | 認証 | レート制限 |
|---|---|---|---|
| YouTube RSS | 動画検出 | 不要 | 特になし（常識的な範囲で） |
| Gemini API | 動画要約生成 | APIキー (`GEMINI_API_KEY`) | 15 RPM / 100万トークン/日 |
| Discord Webhook | 通知送信 | Webhook URL (`DISCORD_WEBHOOK_URL`) | 30リクエスト/60秒 |
| GitHub Actions | 定期実行 | リポジトリ権限 | publicリポジトリは無制限 |

## 5. ファイル構成

```
monitor_youtube/
├── .github/
│   └── workflows/
│       └── check_new_videos.yml    # GitHub Actions ワークフロー
├── config/
│   └── channels.yml                # チャンネル設定（手動編集）
├── data/
│   └── notified.json               # 既読管理データ（自動更新）
├── docs/                           # 開発ドキュメント
├── src/
│   ├── __main__.py                 # python -m src.main 用エントリーポイント
│   ├── main.py                     # メイン処理フロー・オーケストレーション
│   ├── models.py                   # 共有データ型（ChannelConfig, AppSettings, VideoEntry）
│   ├── exceptions.py               # カスタム例外クラス
│   ├── config_loader.py            # 設定ファイル読み込み・バリデーション
│   ├── rss_checker.py              # RSSフィード取得・XMLパース（リトライ付き）
│   ├── video_filter.py             # Shorts・ライブ配信フィルタリング（oEmbed API）
│   ├── summarizer.py               # Gemini API要約生成（fileData方式・リトライ付き）
│   ├── discord_notifier.py         # Discord Webhook通知（Embed分割・リトライ付き）
│   └── history_manager.py          # 既読管理（JSON永続化・自動クリーンアップ）
├── requirements.txt                # Python依存パッケージ
├── CLAUDE.md                       # Claude Code用ガイド
└── README.md                       # セットアップ手順
```
