import logging
from pathlib import Path

import yaml

from src.exceptions import ConfigError
from src.models import AppSettings, ChannelConfig

logger = logging.getLogger(__name__)


def load_config(
    config_path: str = "config/channels.yml",
) -> tuple[list[ChannelConfig], AppSettings]:
    """設定ファイルを読み込む。

    Args:
        config_path: 設定ファイルのパス

    Returns:
        (チャンネル設定リスト, アプリケーション設定) のタプル

    Raises:
        ConfigError: 設定ファイルが存在しない、または形式が不正な場合
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {config_path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML構文エラー: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError("設定ファイルの形式が不正です")

    channels = _parse_channels(data)
    settings = _parse_settings(data)

    logger.info("設定ファイル読み込み完了 - チャンネル数: %d", len(channels))
    return channels, settings


def _parse_channels(data: dict) -> list[ChannelConfig]:
    raw_channels = data.get("channels")
    if not raw_channels or not isinstance(raw_channels, list):
        raise ConfigError("channelsが未定義または空です")

    channels = []
    for i, ch in enumerate(raw_channels):
        if not isinstance(ch, dict):
            raise ConfigError(f"channels[{i}]の形式が不正です")

        channel_id = ch.get("channel_id", "")
        name = ch.get("name", "")

        if not channel_id:
            raise ConfigError(f"channels[{i}].channel_idが未指定です")
        if not channel_id.startswith("UC"):
            raise ConfigError(
                f"channels[{i}].channel_idが不正です（UCで始まる必要があります）: {channel_id}"
            )
        if not name:
            raise ConfigError(f"channels[{i}].nameが未指定です")

        channels.append(
            ChannelConfig(
                channel_id=channel_id,
                name=name,
                prompt_template=ch.get("prompt_template"),
            )
        )

    return channels


def _parse_settings(data: dict) -> AppSettings:
    raw_settings = data.get("settings")
    if not isinstance(raw_settings, dict):
        raise ConfigError("settingsが未定義です")

    default_prompt = raw_settings.get("default_prompt_template", "")
    if not default_prompt or not default_prompt.strip():
        raise ConfigError("settings.default_prompt_templateが未指定です")

    max_summary_length = raw_settings.get("max_summary_length", 3500)
    if not (100 <= max_summary_length <= 4000):
        raise ConfigError(
            f"settings.max_summary_lengthは100〜4000の範囲で指定してください: {max_summary_length}"
        )

    history_retention_days = raw_settings.get("history_retention_days", 90)
    if history_retention_days < 1:
        raise ConfigError(
            f"settings.history_retention_daysは1以上で指定してください: {history_retention_days}"
        )

    return AppSettings(
        check_interval_minutes=raw_settings.get("check_interval_minutes", 5),
        max_summary_length=max_summary_length,
        history_retention_days=history_retention_days,
        default_prompt_template=default_prompt,
    )
