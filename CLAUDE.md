# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube動画要約 Discord通知システム — Monitors YouTube channels via RSS, summarizes new videos with Gemini API, and sends notifications to Discord via Webhook. Runs on GitHub Actions (5-min cron) with zero cost (public repo).

## Architecture

```
GitHub Actions (cron */5) → RSS Feed Check → Gemini API Summarization → Discord Webhook Notification
```

Key modules in `src/`:
- **main.py** — Entry point. Orchestrates the full pipeline: load config → load history → check RSS → filter → summarize → notify → save history
- **models.py** — Shared dataclasses (`ChannelConfig`, `AppSettings`, `VideoEntry`)
- **exceptions.py** — Custom exception hierarchy (`RSSFetchError`, `SummarizerError`, `RateLimitError`, `DiscordNotifyError`, `ConfigError`)
- **config_loader.py** — Reads `config/channels.yml` (channel list, prompts, settings) with validation
- **rss_checker.py** — Fetches YouTube RSS feeds (`/feeds/videos.xml?channel_id=...`) with retry
- **video_filter.py** — Excludes Shorts and live streams via YouTube oEmbed API (single call per video)
- **summarizer.py** — Sends video URL to Gemini API (`fileData` method) for summarization with retry
- **discord_notifier.py** — Posts Embed-formatted messages via Discord Webhook (auto-splits long summaries)
- **history_manager.py** — Manages `data/notified.json` (tracks notified video IDs, auto-prunes entries older than 90 days)

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires env vars)
GEMINI_API_KEY=xxx DISCORD_WEBHOOK_URL=xxx python -m src.main
```

## Configuration

- **Channel config**: `config/channels.yml` — add/remove channels and customize per-channel summarization prompts
- **Notified history**: `data/notified.json` — auto-committed by GitHub Actions, do not manually edit
- **Secrets** (GitHub Secrets): `GEMINI_API_KEY`, `DISCORD_WEBHOOK_URL`

## Development Docs

実装時は `docs/` 配下のドキュメントを参照すること:

- **docs/architecture.md** — システム構成図・処理フロー・データフロー
- **docs/api-specifications.md** — 外部API仕様（YouTube RSS, Gemini API, Discord Webhook）
- **docs/module-design.md** — 各モジュールのインターフェース設計（関数シグネチャ・データ型・例外クラス）
- **docs/data-schema.md** — 設定ファイル・履歴ファイルのスキーマ定義
- **docs/error-handling.md** — エラー分類・リトライ戦略・Discord通知フォーマット
- **docs/setup-guide.md** — ローカル開発・GitHub Actionsセットアップ手順

元の要件定義書: `youtube-summary-notifier-requirements.md`

## Key Constraints

- Discord Embed description limit: 4,096 chars — summaries exceeding this must be split across multiple messages
- Gemini API free tier: 15 RPM, 1M tokens/day — add delays between API calls when processing multiple videos
- YouTube RSS feed updates can lag by several minutes
- All output (summaries, notifications) must be in Japanese
- `notified.json` is public (public repo) — it only stores video IDs, titles, and timestamps
