# データスキーマ定義書

## 1. チャンネル設定ファイル（`config/channels.yml`）

### 概要
監視対象のYouTubeチャンネルとアプリケーション設定を定義するYAMLファイル。
手動で編集する。GitHub Actionsからは読み取り専用。

### スキーマ

```yaml
# チャンネルリスト（必須）
channels:
  - channel_id: string    # 必須: YouTubeチャンネルID（"UC" で始まる24文字）
    name: string          # 必須: 表示名（Discord通知で使用）
    prompt_template: string | null  # 任意: カスタムプロンプト（nullでデフォルト使用）

# アプリケーション設定（必須）
settings:
  check_interval_minutes: integer   # 必須: チェック間隔（分）、デフォルト: 5
  max_summary_length: integer       # 必須: 要約最大文字数、デフォルト: 3500
  history_retention_days: integer   # 必須: 履歴保持日数、デフォルト: 90
  default_prompt_template: string   # 必須: デフォルト要約プロンプト
```

### フィールド詳細

#### channels[]

| フィールド | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| `channel_id` | string | Yes | YouTubeチャンネルID | `"UCxxxxxxxxxxxxxxxxxx"` |
| `name` | string | Yes | 表示用チャンネル名 | `"テック系チャンネル"` |
| `prompt_template` | string \| null | No | チャンネル固有の要約プロンプト。nullの場合 `settings.default_prompt_template` を使用 | 後述 |

#### settings

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `check_interval_minutes` | integer | Yes | 5 | GitHub Actions cronの間隔（ドキュメント用途、実際はcronで制御） |
| `max_summary_length` | integer | Yes | 3500 | Geminiに指示する要約の最大文字数。Discord Embed制限(4096)を考慮 |
| `history_retention_days` | integer | Yes | 90 | notified.jsonの保持日数。超過したエントリは自動削除 |
| `default_prompt_template` | string | Yes | - | デフォルトの要約プロンプトテンプレート |

### サンプル

```yaml
channels:
  - channel_id: "UCxxxxxxxxxxxxxxxxxx"
    name: "チャンネルA"
    prompt_template: null

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
  max_summary_length: 3500
  history_retention_days: 90
  default_prompt_template: |
    以下のYouTube動画の内容を要約してください。
    動画内で扱われているトピックごとにセクション分けし、
    各セクションにはタイトルをつけて詳細に要約してください。
    日本語で出力してください。
```

### バリデーションルール
- `channels` は1つ以上のエントリが必要
- `channel_id` は空文字不可、`"UC"` で始まること
- `name` は空文字不可
- `max_summary_length` は 100 以上 4000 以下
- `history_retention_days` は 1 以上
- `default_prompt_template` は空文字不可

---

## 2. 既読管理ファイル（`data/notified.json`）

### 概要
通知済み動画を記録するJSONファイル。重複通知を防止する。
GitHub Actionsの実行ごとに自動更新・自動コミットされる。

### スキーマ

```json
{
  "notified_videos": {
    "<VIDEO_ID>": {
      "title": "string",
      "channel_id": "string",
      "notified_at": "string (ISO 8601)"
    }
  }
}
```

### フィールド詳細

#### ルート

| フィールド | 型 | 説明 |
|---|---|---|
| `notified_videos` | object | 通知済み動画のマップ。キーは動画ID |

#### notified_videos[VIDEO_ID]

| フィールド | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| `title` | string | Yes | 動画タイトル | `"【解説】最新ニュースまとめ"` |
| `channel_id` | string | Yes | チャンネルID | `"UCxxxxxxxxxxxxxxxxxx"` |
| `notified_at` | string | Yes | 通知日時（ISO 8601 UTC） | `"2025-01-01T00:00:00Z"` |

### サンプル

```json
{
  "notified_videos": {
    "dQw4w9WgXcQ": {
      "title": "サンプル動画タイトル",
      "channel_id": "UCxxxxxxxxxxxxxxxxxx",
      "notified_at": "2025-06-15T08:30:00Z"
    },
    "jNQXAC9IVRw": {
      "title": "別の動画タイトル",
      "channel_id": "UCyyyyyyyyyyyyyyyyyy",
      "notified_at": "2025-06-14T12:00:00Z"
    }
  }
}
```

### 初期状態

ファイルが存在しない場合、以下の内容で新規作成する:

```json
{
  "notified_videos": {}
}
```

### 自動メンテナンス
- **エントリ追加**: 動画通知成功時に `mark_notified()` で追加
- **エントリ削除**: `cleanup_old_entries()` で `notified_at` が `history_retention_days`（デフォルト90日）以上前のエントリを削除
- **ファイル保存**: 毎回の実行終了時に `save()` で書き出し
- **Gitコミット**: GitHub Actions のワークフローステップで自動コミット＆プッシュ

### 注意事項
- publicリポジトリのため、このファイルの内容（動画ID・タイトル）は公開される
- 手動編集は推奨しない（GitHub Actionsとの競合が起きる可能性がある）
- エントリ数の目安: 5チャンネル × 1日1動画 × 90日 = 最大約450エントリ

---

## 3. YouTube RSSフィード（参考: 入力データ）

RSSから取得したXMLのうち、システムが使用するフィールド:

| XMLパス | 抽出データ | マッピング先 |
|---|---|---|
| `entry/yt:videoId` | 動画ID | `VideoEntry.video_id` |
| `entry/title` | 動画タイトル | `VideoEntry.title` |
| `entry/link[@rel='alternate']/@href` | 動画URL | `VideoEntry.url` |
| `entry/published` | 公開日時 | `VideoEntry.published` |
| `entry/yt:channelId` | チャンネルID | `VideoEntry.channel_id` |

XML名前空間:
```
xmlns:yt="http://www.youtube.com/xml/schemas/2015"
xmlns:media="http://search.yahoo.com/mrss/"
xmlns="http://www.w3.org/2005/Atom"
```
