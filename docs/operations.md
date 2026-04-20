# 運用手順書

## 1. 概要

YouTube動画要約 Discord通知システムの日常運用手順書。
GitHub Actions が 5 分間隔で自動実行されるため、通常は手動操作不要。
本書はチャンネル追加・設定変更・障害対応などの手順をまとめたもの。

---

## 2. 日常監視

### 2.1 GitHub Actions ログの確認

1. リポジトリの **Actions** タブを開く
2. ワークフロー `Check New YouTube Videos` を選択
3. 最新の実行結果を確認：
   - ✅ 成功: 緑チェックマーク
   - ❌ 失敗: 赤×マーク → ログを開いてエラー内容を確認

### 2.2 Discord 通知の確認

- 正常時: 新着動画があれば要約 Embed が届く
- 異常時: ⚠️ マークのエラー Embed が届く（エラーの種類と対象チャンネルが記載される）
- 無音の場合: 新着動画がないか、すべての動画が既通知済み

---

## 3. チャンネルの追加・削除

### 3.1 チャンネルの追加

[config/channels.yml](../config/channels.yml) を編集する。

```yaml
channels:
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"  # YouTube チャンネルID
    name: "チャンネル名（管理用）"
    prompt_template: null  # null の場合はデフォルトプロンプトを使用
```

**チャンネルIDの確認方法:**
1. YouTube チャンネルページを開く
2. URL の `/channel/UC...` 部分がチャンネルID
3. または右クリック → ページのソースを表示 → `"channelId"` を検索

**カスタムプロンプトを使用する場合:**
```yaml
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"
    name: "トレード系チャンネル"
    prompt_template: |
      この動画はトレード関連です。以下の観点で要約してください：
      - 紹介された手法やストラテジー
      - 言及された銘柄・通貨ペア
      - リスク管理に関する言及
```

### 3.2 チャンネルの削除

[config/channels.yml](../config/channels.yml) から該当エントリを削除する。
削除しても `data/notified.json` 内の履歴はそのまま残る（次回の 90 日自動削除で消える）。

---

## 4. 設定変更

### 4.1 主な設定項目

[config/channels.yml](../config/channels.yml) の `settings` セクション:

| 項目 | デフォルト値 | 説明 |
|---|---|---|
| `check_interval_minutes` | 5 | チェック間隔（参考値、実際は GitHub Actions の cron で制御） |
| `max_summary_length` | 1500 | 要約の最大文字数（テキスト要約時の参考値） |
| `history_retention_days` | 90 | 通知済み履歴の保持日数 |
| `default_prompt_template` | （長文） | デフォルトの要約プロンプト |

### 4.2 実行間隔の変更

[.github/workflows/check_new_videos.yml](../.github/workflows/check_new_videos.yml) の cron 設定を変更する:

```yaml
schedule:
  - cron: '*/5 * * * *'  # 5分ごと → '*/10 * * * *' で10分ごとに変更可能
```

---

## 5. Secrets（APIキー）の管理

GitHub リポジトリの **Settings → Secrets and variables → Actions** で管理。

| Secret 名 | 説明 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得した Gemini API キー |
| `DISCORD_WEBHOOK_URL` | Discord チャンネルの Webhook URL |

**Secretの更新手順:**
1. GitHub リポジトリ → Settings → Secrets and variables → Actions
2. 該当 Secret の右の「Update」をクリック
3. 新しい値を入力して保存
4. 次回の GitHub Actions 実行から自動的に新しい値が使われる

---

## 6. トラブルシューティング

### 6.1 通知が届かない

| 確認事項 | 対処方法 |
|---|---|
| GitHub Actions が失敗している | Actions タブのログを確認 → エラー内容に応じて対処 |
| `GEMINI_API_KEY` が無効 | ログに `HTTP 403` → Google AI Studio でキーを再発行して Secrets を更新 |
| `DISCORD_WEBHOOK_URL` が無効 | ログに `HTTP 404` → Discord で Webhook を再作成して Secrets を更新 |
| Gemini レートリミット超過 | ログに `HTTP 429` → 次回実行（5分後）で自動リカバリ |
| 監視チャンネルに新着動画がない | 正常。新着動画が投稿されれば自動的に通知される |

### 6.2 特定チャンネルでエラーが出続ける

Discord に `⚠️ RSSフィード取得エラー` が届く場合:
1. チャンネルIDが正しいか確認（YouTube でチャンネルページを開いて URL を確認）
2. チャンネルが削除・非公開になっていないか確認
3. 問題があれば `config/channels.yml` から削除または修正

### 6.3 `notified.json` が壊れた場合

```bash
# バックアップを確認（git log で以前の状態を確認）
git log data/notified.json

# 直前の正常な状態に戻す
git checkout HEAD~1 -- data/notified.json
git commit -m "data/notified.json を修復"
git push
```

または、ファイルを空の状態にリセット（過去の通知済み動画が再通知される可能性あり）:
```bash
echo '{"notified_videos": []}' > data/notified.json
git add data/notified.json
git commit -m "data/notified.json を初期化"
git push
```

### 6.4 手動でワークフローを実行したい

1. GitHub リポジトリ → Actions タブ
2. `Check New YouTube Videos` を選択
3. 右上の「Run workflow」ボタンをクリック

---

## 7. ローカルでのデバッグ実行

```bash
# 依存ライブラリのインストール
pip install -r requirements.txt

# 環境変数をセットして実行
GEMINI_API_KEY=xxx DISCORD_WEBHOOK_URL=xxx python -m src.main
```

詳細なセットアップ手順は [docs/setup-guide.md](setup-guide.md) を参照。

---

## 8. 定期メンテナンス

| 作業 | 頻度 | 内容 |
|---|---|---|
| GitHub Actions ログ確認 | 週1回 | 継続的なエラーがないか確認 |
| Gemini API 使用量確認 | 月1回 | Google AI Studio でトークン使用量を確認（無料枠: 1M tokens/日） |
| 監視チャンネルの見直し | 必要時 | 不要なチャンネルの削除・新チャンネルの追加 |
| `notified.json` の確認 | 必要時 | 異常に肥大化していないか確認（90日で自動削除されるため通常不要） |
