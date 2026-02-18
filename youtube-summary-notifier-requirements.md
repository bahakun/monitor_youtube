# YouTube動画要約 Discord通知システム 要件定義書

## 1. プロジェクト概要

### 1.1 目的
指定したYouTubeチャンネルに新しい動画がアップロードされた際、動画の内容をAIで要約し、Discordチャンネルに自動通知するシステムを構築する。

### 1.2 基本方針
- **完全無料**で運用できること
- メンテナンスの手間を最小限にすること
- チャンネルの追加・削除が容易であること

---

## 2. システム構成

### 2.1 アーキテクチャ概要

```
GitHub Actions (5分間隔 cron)
    ↓
YouTube RSSフィード監視（新動画検出）
    ↓
Gemini API に動画URLを渡して要約生成
    ↓
Discord Webhook で通知
```

### 2.2 技術スタック

| コンポーネント | 技術 | 費用 |
|---|---|---|
| 実行環境 | GitHub Actions（publicリポジトリ） | 無料 |
| 動画検出 | YouTube RSSフィード | 無料（APIキー不要） |
| 要約生成 | Gemini API（無料枠） | 無料 |
| 通知 | Discord Webhook | 無料 |
| 既読管理 | JSONファイル（リポジトリ内） | 無料 |
| 言語 | Python 3.x | - |

---

## 3. 機能要件

### 3.1 チャンネル監視機能

- 複数のYouTubeチャンネルを監視対象として登録できること
- 監視対象チャンネルは設定ファイル（YAML or JSON）で管理すること
- 各チャンネルの設定項目：
  - チャンネルID
  - チャンネル表示名
  - 要約プロンプトテンプレート（チャンネルごとにカスタマイズ可能）
- YouTube RSSフィード（`https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID`）を使用すること
- チェック間隔：**5分**（GitHub Actions cronスケジュール）

### 3.2 動画フィルタリング

- **通常の動画のみ**を対象とする
- YouTube Shorts は除外する（URLパターン `/shorts/` またはメタデータで判別）
- ライブ配信およびライブ配信アーカイブは除外する
- 必要に応じて動画の長さによるフィルタリングも設定可能とする（任意）

### 3.3 要約生成機能

- Gemini APIに動画URLを直接渡して要約を生成する
- 字幕取得の中間工程は不要（Geminiが動画内容を直接解析）
- 要約の形式：
  - 動画内の複数トピックをセクション（タイトル）に分割
  - 各セクションごとに詳細な要約を記載
- 要約プロンプトは設定ファイルで管理し、チャンネルごとにカスタマイズ可能とする
- デフォルトプロンプトの出力形式イメージ：

```
## 📌 トピック1: 〇〇について
詳細な要約文...

## 📌 トピック2: △△の解説
詳細な要約文...

## 📌 トピック3: □□の最新情報
詳細な要約文...
```

### 3.4 Discord通知機能

- Discord Webhookを使用して通知する
- 通知先：**1つのDiscordチャンネル**にまとめて通知
- 通知にはEmbed形式を使用し、リッチな見た目にする
- 通知に含める情報：
  - チャンネル名
  - 動画タイトル
  - 動画リンク（URL）
  - 投稿日時
  - AI生成要約（セクション分割形式）
- Discordメッセージの文字数制限（Embed description: 4,096文字）を考慮し、要約が長い場合は分割送信または末尾を省略する

### 3.5 既読管理（重複通知防止）

- 通知済みの動画IDをJSONファイルでリポジトリ内に保存する
- GitHub Actionsの実行ごとに、JSONファイルを読み込み → 新着判定 → 通知後にJSONを更新 → コミット＆プッシュ
- JSONファイルの肥大化を防ぐため、一定期間（例：90日）以上前のエントリは自動削除する
- JSONファイルの構造例：

```json
{
  "notified_videos": {
    "VIDEO_ID_1": {
      "title": "動画タイトル",
      "channel_id": "CHANNEL_ID",
      "notified_at": "2025-01-01T00:00:00Z"
    }
  }
}
```

### 3.6 エラーハンドリング

- エラー発生時はDiscordの同一チャンネルにエラーログを通知する
- 通知するエラーの種類：
  - RSSフィード取得失敗
  - Gemini API呼び出し失敗（レートリミット、タイムアウト等）
  - Discord Webhook送信失敗
- Gemini APIのレートリミットに達した場合、残りの動画は次回実行時に処理する
- エラー通知のEmbed形式（赤色で区別）

---

## 4. 非機能要件

### 4.1 実行環境

- GitHub Actions（publicリポジトリ）で動作すること
- cronスケジュール：`*/5 * * * *`（5分間隔）
  - ※GitHub Actionsのcronは正確に5分間隔で実行されるとは限らない（数分の遅延あり）。これを許容する
- 1回の実行は10分以内に完了すること

### 4.2 コスト

- すべてのコンポーネントが無料枠内で運用できること
- Gemini API無料枠：15 RPM / 100万トークン/日 を超えないこと
- GitHub Actions無料枠：publicリポジトリのため実質無制限

### 4.3 セキュリティ

- Gemini APIキーはGitHub Secrets（`GEMINI_API_KEY`）で管理する
- Discord Webhook URLはGitHub Secrets（`DISCORD_WEBHOOK_URL`）で管理する
- publicリポジトリのため、機密情報がコードに含まれないこと

### 4.4 保守性

- 設定ファイルの変更のみでチャンネルの追加・削除が可能
- 要約プロンプトの変更がコード修正なしで行えること
- ログ出力により、問題発生時の原因特定が容易であること

---

## 5. 設定ファイル仕様

### 5.1 チャンネル設定（`config/channels.yml`）

```yaml
channels:
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"
    name: "チャンネルA"
    prompt_template: null  # nullの場合デフォルトプロンプトを使用

  - channel_id: "UCyyyyyyyyyyyyyyyyyy"
    name: "チャンネルB"
    prompt_template: |
      この動画はトレード関連です。以下の観点で要約してください：
      - 紹介された手法やストラテジー
      - 言及された通貨ペアや銘柄
      - リスク管理に関する言及
      各トピックにはタイトルをつけ、詳細に要約してください。

settings:
  check_interval_minutes: 5
  max_summary_length: 3500  # Discord Embed制限を考慮
  history_retention_days: 90
  default_prompt_template: |
    以下のYouTube動画の内容を要約してください。
    動画内で扱われているトピックごとにセクション分けし、
    各セクションにはタイトルをつけて詳細に要約してください。
    日本語で出力してください。
```

### 5.2 既読管理ファイル（`data/notified.json`）

- 前述の3.5で定義した構造に従う
- GitHub Actionsから自動コミットされる

---

## 6. ファイル構成

```
youtube-summary-notifier/
├── .github/
│   └── workflows/
│       └── check_new_videos.yml    # GitHub Actions ワークフロー
├── config/
│   └── channels.yml                # チャンネル設定
├── data/
│   └── notified.json               # 既読管理データ
├── src/
│   ├── main.py                     # メインエントリーポイント
│   ├── rss_checker.py              # RSSフィード取得・パース
│   ├── video_filter.py             # Shorts・ライブ配信フィルタリング
│   ├── summarizer.py               # Gemini API要約生成
│   ├── discord_notifier.py         # Discord Webhook通知
│   ├── history_manager.py          # 既読管理
│   └── config_loader.py            # 設定ファイル読み込み
├── requirements.txt                # Python依存パッケージ
└── README.md                       # セットアップ手順
```

---

## 7. GitHub Actions ワークフロー概要

```yaml
name: YouTube Summary Notifier
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:  # 手動実行も可能

permissions:
  contents: write  # notified.json の自動コミットに必要

jobs:
  check-and-notify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python src/main.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
      - name: Commit notified.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/notified.json
          git diff --staged --quiet || git commit -m "Update notified videos"
          git push
```

---

## 8. 処理フロー

```
1. 設定ファイル（channels.yml）を読み込む
2. 既読管理ファイル（notified.json）を読み込む
3. 各チャンネルについて：
   a. YouTube RSSフィードを取得
   b. フィード内の動画一覧を取得
   c. Shorts・ライブ配信を除外
   d. 既に通知済みの動画を除外
   e. 新着動画が存在する場合：
      i.   Gemini APIに動画URLを渡して要約を生成
      ii.  Discord Webhookで通知（Embed形式）
      iii. notified.jsonに動画IDを追加
4. 古いエントリ（90日以上前）をnotified.jsonから削除
5. notified.jsonを保存
```

---

## 9. 制約事項・注意点

- GitHub Actionsのcronは正確ではなく、5〜15分程度の遅延が発生する場合がある
- Gemini APIの無料枠にはレートリミットがある（15 RPM）。大量のチャンネル登録や同時に複数動画がアップされた場合は処理が遅延する可能性がある
- YouTube RSSフィードの更新反映にも遅延（数分〜数十分）が発生する場合がある
- publicリポジトリのため、notified.jsonの内容（動画ID・タイトル）は公開される
- Geminiの動画解析精度は動画の内容・言語・長さによって変動する
- Discord Embed descriptionの上限は4,096文字。要約がこれを超える場合は分割送信で対応する

---

## 10. 将来の拡張候補（スコープ外）

- YouTube Shorts対応
- ライブ配信アーカイブ対応
- チャンネルごとに異なるDiscordチャンネルへの通知
- サムネイル画像のEmbed表示
- 要約の言語自動検出・翻訳
- WebSub（PubSubHubbub）によるリアルタイム検出への移行
- 通知済み動画のダッシュボード（GitHub Pages）
