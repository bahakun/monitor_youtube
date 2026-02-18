# YouTube動画要約 Discord通知システム

指定したYouTubeチャンネルの新着動画をAIで要約し、Discordに自動通知するシステム。

## 仕組み

```
GitHub Actions (5分間隔) → YouTube RSS監視 → Gemini APIで要約 → Discord Webhook通知
```

- 完全無料で運用（GitHub Actions + Gemini API無料枠 + Discord Webhook）
- `config/channels.yml` を編集するだけでチャンネルの追加・削除が可能
- YouTube Shortsやライブ配信は自動で除外

## セットアップ

### 1. リポジトリをフォーク/クローン

### 2. APIキーの取得

- **Gemini API**: [Google AI Studio](https://aistudio.google.com/) → 「Get API key」で取得
- **Discord Webhook**: サーバー設定 → 連携サービス → ウェブフック → URLをコピー

### 3. GitHub Secretsの設定

リポジトリの Settings → Secrets and variables → Actions で設定:

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Gemini APIキー |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |

### 4. チャンネル設定

`config/channels.yml` を編集:

```yaml
channels:
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"  # チャンネルIDに置き換え
    name: "チャンネル名"
    prompt_template: null  # デフォルトプロンプト使用
```

### 5. 動作確認

Actions タブ → 「YouTube Summary Notifier」→ 「Run workflow」で手動実行

## ローカル実行

```bash
pip install -r requirements.txt
GEMINI_API_KEY=xxx DISCORD_WEBHOOK_URL=xxx python -m src.main
```

## 設定

### チャンネルごとのカスタムプロンプト

```yaml
channels:
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"
    name: "料理チャンネル"
    prompt_template: |
      この動画は料理系です。以下の観点で要約してください：
      - レシピ名と材料
      - 調理手順（簡潔に）
      - コツやポイント
      日本語で出力してください。
```

### アプリケーション設定

```yaml
settings:
  max_summary_length: 3500  # 要約の最大文字数
  history_retention_days: 90  # 通知履歴の保持日数
```

## ファイル構成

```
├── .github/workflows/     # GitHub Actionsワークフロー
├── config/channels.yml    # チャンネル設定
├── data/notified.json     # 通知履歴（自動更新）
├── docs/                  # 開発ドキュメント
├── src/                   # ソースコード
│   ├── main.py            # エントリーポイント
│   ├── config_loader.py   # 設定読み込み
│   ├── rss_checker.py     # RSSフィード取得
│   ├── video_filter.py    # Shorts・ライブ除外
│   ├── summarizer.py      # Gemini API要約
│   ├── discord_notifier.py # Discord通知
│   ├── history_manager.py # 通知履歴管理
│   ├── models.py          # データ型定義
│   └── exceptions.py      # 例外クラス
└── requirements.txt       # 依存パッケージ
```
