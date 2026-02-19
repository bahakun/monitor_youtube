class AppError(Exception):
    """アプリケーション基底例外"""
    pass


class RSSFetchError(AppError):
    """RSSフィード取得失敗"""
    pass


class SummarizerError(AppError):
    """要約生成失敗"""
    pass


class RateLimitError(SummarizerError):
    """Gemini APIレートリミット超過"""
    pass


class TokenLimitError(SummarizerError):
    """Gemini APIトークン上限超過（動画が長すぎる）"""
    pass


class DiscordNotifyError(AppError):
    """Discord通知送信失敗"""
    pass


class ConfigError(AppError):
    """設定ファイル関連エラー"""
    pass


class ImageGenerationError(AppError):
    """インフォグラフィック画像生成失敗"""
    pass
