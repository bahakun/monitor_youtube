# 外部API仕様書

## 1. YouTube RSSフィード

### エンドポイント

```
GET https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}
```

### 認証
不要（公開フィード）

### レスポンス形式
Atom XML フィード

### レスポンス例

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <title>チャンネル名</title>
  <link rel="alternate" href="https://www.youtube.com/channel/UCxxxxxxxxxx"/>
  <entry>
    <id>yt:video:VIDEO_ID</id>
    <yt:videoId>VIDEO_ID</yt:videoId>
    <yt:channelId>CHANNEL_ID</yt:channelId>
    <title>動画タイトル</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=VIDEO_ID"/>
    <published>2025-01-01T12:00:00+00:00</published>
    <updated>2025-01-01T12:30:00+00:00</updated>
    <media:group>
      <media:title>動画タイトル</media:title>
      <media:description>動画説明文...</media:description>
      <media:thumbnail url="https://i.ytimg.com/vi/VIDEO_ID/hqdefault.jpg"
                       width="480" height="360"/>
      <media:content url="https://www.youtube.com/v/VIDEO_ID?version=3"
                     type="application/x-shockwave-flash" width="640" height="390"/>
    </media:group>
  </entry>
  <!-- 最新15件程度のエントリが含まれる -->
</feed>
```

### 使用するフィールド

| フィールド | XPath | 用途 |
|---|---|---|
| 動画ID | `entry/yt:videoId` | 一意識別子・既読判定 |
| タイトル | `entry/title` | 通知表示用 |
| URL | `entry/link[@rel='alternate']/@href` | 動画リンク・Gemini入力 |
| 公開日時 | `entry/published` | 通知表示用・ソート |
| チャンネルID | `entry/yt:channelId` | チャンネル識別 |

### 注意事項
- フィードには最新15件程度の動画のみ含まれる
- フィードの更新反映に数分〜数十分の遅延がある
- Shorts や ライブ配信もフィードに含まれる（フィルタリングが必要）

---

## 2. Gemini API

### エンドポイント

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}
```

### 認証
クエリパラメータ `key` にAPIキーを指定

### リクエストボディ

```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "以下のYouTube動画の内容を要約してください。..."
        },
        {
          "fileData": {
            "mimeType": "video/*",
            "fileUri": "https://www.youtube.com/watch?v=VIDEO_ID"
          }
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.4,
    "maxOutputTokens": 2048
  }
}
```

> **補足**: Gemini APIはYouTube動画URLを直接解析できる。字幕取得などの中間処理は不要。
> `fileData` を使う方法と、プロンプトテキスト内にURLを含める方法の両方が可能。
> 実装時にどちらが安定するか検証すること。

### レスポンス例

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "## 📌 トピック1: 〇〇について\n詳細な要約文...\n\n## 📌 トピック2: △△の解説\n詳細な要約文..."
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP"
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 1234,
    "candidatesTokenCount": 567,
    "totalTokenCount": 1801
  }
}
```

### 使用するフィールド

| フィールド | JSONPath | 用途 |
|---|---|---|
| 要約テキスト | `candidates[0].content.parts[0].text` | Discord通知の本文 |
| 終了理由 | `candidates[0].finishReason` | 正常完了判定（`STOP` であること） |
| トークン数 | `usageMetadata.totalTokenCount` | ログ記録（消費量監視） |

### レート制限（無料枠）
- **15 RPM**（1分あたり15リクエスト）
- **100万トークン/日**
- 超過時は HTTP 429 が返る

### エラーレスポンス

```json
{
  "error": {
    "code": 429,
    "message": "Resource has been exhausted...",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

| ステータスコード | 意味 | 対応 |
|---|---|---|
| 400 | リクエスト不正 | ログ記録しスキップ |
| 403 | APIキー無効 | エラー通知して停止 |
| 429 | レートリミット超過 | 残りの動画を次回に回す |
| 500, 503 | サーバーエラー | リトライ（最大3回） |

---

## 3. Discord Webhook

### エンドポイント

```
POST {DISCORD_WEBHOOK_URL}
```

Webhook URL形式: `https://discord.com/api/webhooks/{webhook_id}/{webhook_token}`

### 認証
URLにトークンが含まれるため追加認証不要

### リクエストヘッダ

```
Content-Type: application/json
```

### リクエストボディ（通常通知 — Embed形式）

```json
{
  "embeds": [
    {
      "title": "🎬 動画タイトル",
      "url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "description": "## 📌 トピック1: 〇〇について\n要約文...\n\n## 📌 トピック2: △△の解説\n要約文...",
      "color": 16711680,
      "fields": [
        {
          "name": "チャンネル",
          "value": "チャンネル名",
          "inline": true
        },
        {
          "name": "投稿日時",
          "value": "2025-01-01 12:00",
          "inline": true
        }
      ],
      "footer": {
        "text": "AI要約 by Gemini"
      },
      "timestamp": "2025-01-01T12:00:00Z"
    }
  ]
}
```

### リクエストボディ（エラー通知）

```json
{
  "embeds": [
    {
      "title": "⚠️ エラー通知",
      "description": "RSSフィード取得に失敗しました\nチャンネル: チャンネルA\nエラー: Connection timeout",
      "color": 15158332,
      "timestamp": "2025-01-01T12:00:00Z"
    }
  ]
}
```

### Embed カラーコード

| 用途 | 色 | 値（10進数） |
|---|---|---|
| 通常通知 | 青系 | `3447003` (#3498DB) |
| エラー通知 | 赤系 | `15158332` (#E74C3C) |

### 制限事項

| 項目 | 上限 |
|---|---|
| Embed description | 4,096文字 |
| Embed title | 256文字 |
| Embed全体 | 6,000文字 |
| 1メッセージあたりのEmbed数 | 10個 |
| レートリミット | 30リクエスト/60秒 |

### 要約の分割送信ルール
description が 4,096文字を超える場合:
1. セクション（`## 📌`）単位で分割
2. 1つ目のEmbedに動画情報 + 前半の要約
3. 2つ目以降のEmbedに残りの要約（titleは「（続き）」）
4. 10 Embed を超える場合は末尾を省略

### レスポンス
- 成功: HTTP 204 No Content
- レートリミット: HTTP 429 + `Retry-After` ヘッダ
- エラー: HTTP 4xx/5xx + JSON エラーメッセージ
