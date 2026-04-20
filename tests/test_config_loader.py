"""config_loader の単体テスト"""
from pathlib import Path

import pytest

from src.config_loader import load_config
from src.exceptions import ConfigError


# テスト用の最小限の有効なYAML（default_prompt_templateは短縮版）
VALID_YAML = """
channels:
  - channel_id: "UCtest123456789012345"
    name: "テストチャンネル"
    prompt_template: null

settings:
  check_interval_minutes: 5
  max_summary_length: 1500
  history_retention_days: 90
  default_prompt_template: "動画を要約してください。"
"""


class TestLoadConfigSuccess:
    """正常系テスト"""

    def test_正常なYAMLを読み込める(self, tmp_path: Path):
        path = tmp_path / "channels.yml"
        path.write_text(VALID_YAML, encoding="utf-8")

        channels, settings = load_config(str(path))

        assert len(channels) == 1
        assert channels[0].channel_id == "UCtest123456789012345"
        assert channels[0].name == "テストチャンネル"
        assert channels[0].prompt_template is None

    def test_設定値が正しく読み込まれる(self, tmp_path: Path):
        path = tmp_path / "channels.yml"
        path.write_text(VALID_YAML, encoding="utf-8")

        _, settings = load_config(str(path))

        assert settings.check_interval_minutes == 5
        assert settings.max_summary_length == 1500
        assert settings.history_retention_days == 90

    def test_カスタムpromptが読み込まれる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace(
            "prompt_template: null",
            "prompt_template: 'カスタムプロンプト'",
        )
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        channels, _ = load_config(str(path))
        assert channels[0].prompt_template == "カスタムプロンプト"


class TestLoadConfigFileErrors:
    """ファイル不存在・形式エラーのテスト"""

    def test_ファイルが存在しない場合はConfigErrorが発生する(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="設定ファイルが見つかりません"):
            load_config(str(tmp_path / "nonexistent.yml"))

    def test_YAML構文エラーはConfigErrorになる(self, tmp_path: Path):
        path = tmp_path / "channels.yml"
        path.write_text("{ invalid: yaml: content", encoding="utf-8")

        with pytest.raises(ConfigError, match="YAML構文エラー"):
            load_config(str(path))

    def test_空ファイルはConfigErrorになる(self, tmp_path: Path):
        path = tmp_path / "channels.yml"
        path.write_text("", encoding="utf-8")

        with pytest.raises(ConfigError):
            load_config(str(path))


class TestLoadConfigChannelValidation:
    """チャンネルバリデーションのテスト"""

    def test_channelsが未定義の場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = """
settings:
  default_prompt_template: "要約してください"
  max_summary_length: 1500
  history_retention_days: 90
"""
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="channelsが未定義または空です"):
            load_config(str(path))

    def test_channel_idがUCで始まらない場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace(
            'channel_id: "UCtest123456789012345"',
            'channel_id: "INVALID_ID"',
        )
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="UCで始まる必要があります"):
            load_config(str(path))

    def test_nameが未指定の場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace('name: "テストチャンネル"', 'name: ""')
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="nameが未指定です"):
            load_config(str(path))


class TestLoadConfigSettingsValidation:
    """設定値バリデーションのテスト"""

    def test_max_summary_lengthが範囲外の場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace("max_summary_length: 1500", "max_summary_length: 99")
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="100〜4000"):
            load_config(str(path))

    def test_history_retention_daysが0の場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace("history_retention_days: 90", "history_retention_days: 0")
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="1以上で指定してください"):
            load_config(str(path))

    def test_default_prompt_templateが空の場合はConfigErrorになる(self, tmp_path: Path):
        yaml_content = VALID_YAML.replace(
            'default_prompt_template: "動画を要約してください。"',
            'default_prompt_template: ""',
        )
        path = tmp_path / "channels.yml"
        path.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="default_prompt_templateが未指定です"):
            load_config(str(path))
