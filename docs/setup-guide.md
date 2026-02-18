# セットアップガイド

## 1. 前提条件

- Python 3.12 以上
- Git
- GitHubアカウント
- Gemini APIキー（Google AI Studio で取得）
- Discord Webhook URL（Discordサーバーの設定で取得）

---

## 2. ローカル開発環境のセットアップ

### 2.1 リポジトリのクローン

```bash
git clone https://github.com/<your-username>/monitor_youtube.git
cd monitor_youtube
```

### 2.2 Python仮想環境の作成

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2.3 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2.4 環境変数の設定

ローカル実行時は環境変数を直接設定する（`.env` ファイルはリポジトリに含めないこと）。

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY = "your-gemini-api-key"
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/xxxx/yyyy"

# macOS/Linux
export GEMINI_API_KEY="your-gemini-api-key"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxxx/yyyy"
```

### 2.5 チャンネル設定

`config/channels.yml` を編集して監視対象チャンネルを設定する。

チャンネルIDの確認方法:
1. YouTubeでチャンネルページを開く
2. URLが `https://www.youtube.com/channel/UCxxxxxxxxxx` の場合 → `UCxxxxxxxxxx` がチャンネルID
3. URLが `https://www.youtube.com/@handle` の場合 → ページソースまたは外部ツールでチャンネルIDを確認

### 2.6 ローカル実行

```bash
python src/main.py
```

---

## 3. Gemini APIキーの取得手順

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. Googleアカウントでログイン
3. 左メニュー「Get API key」→「Create API key」
4. 生成されたAPIキーをコピー

### 無料枠の制限
- 15 RPM（1分あたり15リクエスト）
- 100万トークン/日
- モデル: `gemini-2.0-flash` を使用

---

## 4. Discord Webhook URLの取得手順

1. Discordサーバーの「サーバー設定」→「連携サービス」→「ウェブフック」
2. 「新しいウェブフック」をクリック
3. 通知を送信したいチャンネルを選択
4. ウェブフック名を設定（例: 「YouTube要約Bot」）
5. 「ウェブフックURLをコピー」

---

## 5. GitHub Actionsのセットアップ

### 5.1 リポジトリの作成

- **publicリポジトリ**で作成すること（GitHub Actions無料利用のため）

### 5.2 GitHub Secretsの設定

リポジトリの「Settings」→「Secrets and variables」→「Actions」で以下を設定:

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Gemini APIキー |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |

### 5.3 ワークフローファイルの確認

`.github/workflows/check_new_videos.yml` が以下の内容で存在すること:

```yaml
name: YouTube Summary Notifier
on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:

permissions:
  contents: write

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

### 5.4 動作確認

1. リポジトリの「Actions」タブを開く
2. 「YouTube Summary Notifier」ワークフローを選択
3. 「Run workflow」ボタンで手動実行
4. ログを確認し、Discordに通知が届くことを確認

---

## 6. チャンネルの追加・削除

### チャンネル追加

`config/channels.yml` の `channels` リストに追加:

```yaml
channels:
  # 既存チャンネル...

  - channel_id: "UC新しいチャンネルID"
    name: "新しいチャンネル名"
    prompt_template: null  # デフォルトプロンプトを使用する場合
```

### チャンネル削除

`config/channels.yml` から該当エントリを削除するだけでよい。
`notified.json` 内の過去の通知履歴は90日後に自動削除される。

### カスタムプロンプトの設定

チャンネルごとに要約の指示をカスタマイズできる:

```yaml
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"
    name: "料理チャンネル"
    prompt_template: |
      この動画は料理系です。以下の観点で要約してください：
      - 紹介されたレシピ名と材料
      - 調理の手順（簡潔に）
      - コツやポイント
      各トピックにはタイトルをつけ、詳細に要約してください。
      日本語で出力してください。
```

---

## 7. トラブルシューティング

### 通知が届かない
1. GitHub Actionsのログでエラーがないか確認
2. GitHub Secretsが正しく設定されているか確認
3. Discord Webhook URLが有効か確認（ブラウザでアクセスして確認）
4. `data/notified.json` に既に該当動画が記録されていないか確認

### Gemini APIエラー (429)
- 無料枠のレートリミット超過。次回の実行（5分後）に自動で再処理される
- 監視チャンネル数が多すぎる場合は削減を検討

### GitHub Actionsが実行されない
- cronスケジュールは5〜15分の遅延があり得る（GitHub側の制約）
- リポジトリに60日以上コミットがないとcronが無効になる
- 「Actions」タブでワークフローが有効になっているか確認

### notified.json のコミットが競合する
- 複数の実行が同時に走った場合に発生する可能性がある
- GitHub Actionsのconcurrencyオプションで対策可能:
  ```yaml
  concurrency:
    group: youtube-notifier
    cancel-in-progress: false
  ```
