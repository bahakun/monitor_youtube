# Changelog

このプロジェクトの変更履歴。[Semantic Versioning](https://semver.org/lang/ja/) に準拠。

## [Unreleased]

## [1.2.0] - 2026-03-06

### Changed
- Gemini API の `maxOutputTokens` を 65536 に拡大
- トークン上限（MAX_TOKENS）到達時にコンパクトプロンプトで自動リトライするよう改善

## [1.1.0] - 2026-02-19

### Added
- Gemini トークン上限を超える動画をスキップして履歴に記録する機能を追加

## [1.0.1] - 2026-02-18

### Fixed
- RSS フィードエラー時の Discord 通知を抑制（エラーログのみに変更）
- YouTube RSS フィード取得で HTTP 404 が返った場合のリトライ処理を追加
- GitHub Actions の `workflow_dispatch` トリガーが機能しない問題を修正

### Added
- 監視チャンネルを 2 件追加

## [1.0.0] - 2026-02-18

### Added
- 初回リリース：YouTube 動画要約 Discord 通知システム
- GitHub Actions による 5 分間隔の定期実行（cron）
- YouTube RSS フィード経由の新着動画検出
- Gemini API による動画要約（日本語）
- Discord Webhook 経由の Embed 形式通知
- Shorts・ライブ配信の自動フィルタリング
- 通知済み動画の履歴管理（`data/notified.json`、90日自動削除）
- チャンネルごとのカスタム要約プロンプト設定
