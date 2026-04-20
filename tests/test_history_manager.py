"""HistoryManager の単体テスト"""
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from src.history_manager import HistoryManager
from src.models import VideoEntry


def _make_video(video_id: str = "vid001", title: str = "テスト動画") -> VideoEntry:
    """テスト用 VideoEntry を生成するヘルパー"""
    return VideoEntry(
        video_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        published=datetime(2026, 1, 1, tzinfo=timezone.utc),
        channel_id="UCtest",
    )


class TestHistoryManagerLoad:
    """load() のテスト"""

    def test_ファイルが存在しない場合は空で初期化される(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm.load()
        assert hm._notified == {}

    def test_正常なJSONを読み込める(self, tmp_path: Path):
        path = tmp_path / "notified.json"
        path.write_text(
            json.dumps({
                "notified_videos": {
                    "vid001": {
                        "title": "テスト動画",
                        "channel_id": "UCtest",
                        "notified_at": "2026-01-01T00:00:00+00:00",
                    }
                }
            }),
            encoding="utf-8",
        )
        hm = HistoryManager(str(path))
        hm.load()
        assert "vid001" in hm._notified

    def test_破損したJSONは空で初期化される(self, tmp_path: Path):
        path = tmp_path / "notified.json"
        path.write_text("{ invalid json }", encoding="utf-8")
        hm = HistoryManager(str(path))
        hm.load()
        assert hm._notified == {}


class TestHistoryManagerIsNotified:
    """is_notified() のテスト"""

    def test_通知済み動画はTrueを返す(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {"vid001": {}}
        assert hm.is_notified("vid001") is True

    def test_未通知動画はFalseを返す(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {}
        assert hm.is_notified("vid001") is False


class TestHistoryManagerFilterNew:
    """filter_new() のテスト"""

    def test_通知済み動画を除外して新着のみ返す(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {"vid001": {}}

        videos = [_make_video("vid001"), _make_video("vid002")]
        result = hm.filter_new(videos)

        assert len(result) == 1
        assert result[0].video_id == "vid002"

    def test_全件新着の場合はそのまま返す(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {}

        videos = [_make_video("vid001"), _make_video("vid002")]
        result = hm.filter_new(videos)
        assert len(result) == 2

    def test_空リストを渡すと空リストが返る(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {}
        assert hm.filter_new([]) == []


class TestHistoryManagerMarkNotified:
    """mark_notified() のテスト"""

    def test_動画が通知済みとして記録される(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {}
        video = _make_video("vid001", "テスト動画")

        hm.mark_notified(video)

        assert "vid001" in hm._notified
        assert hm._notified["vid001"]["title"] == "テスト動画"
        assert hm._notified["vid001"]["channel_id"] == "UCtest"
        assert "notified_at" in hm._notified["vid001"]


class TestHistoryManagerCleanupOldEntries:
    """cleanup_old_entries() のテスト"""

    def test_古いエントリが削除される(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        # 100日前のエントリ
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        hm._notified = {
            "old_vid": {"title": "古い動画", "channel_id": "UCtest", "notified_at": old_date},
        }

        removed = hm.cleanup_old_entries(retention_days=90)
        assert removed == 1
        assert "old_vid" not in hm._notified

    def test_新しいエントリは削除されない(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        # 10日前のエントリ
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        hm._notified = {
            "new_vid": {"title": "新しい動画", "channel_id": "UCtest", "notified_at": recent_date},
        }

        removed = hm.cleanup_old_entries(retention_days=90)
        assert removed == 0
        assert "new_vid" in hm._notified

    def test_パース不能な日付のエントリは削除される(self, tmp_path: Path):
        hm = HistoryManager(str(tmp_path / "notified.json"))
        hm._notified = {
            "bad_vid": {"title": "壊れた動画", "channel_id": "UCtest", "notified_at": "invalid"},
        }

        removed = hm.cleanup_old_entries(retention_days=90)
        assert removed == 1


class TestHistoryManagerSave:
    """save() のテスト"""

    def test_ファイルに保存される(self, tmp_path: Path):
        path = tmp_path / "notified.json"
        hm = HistoryManager(str(path))
        hm._notified = {
            "vid001": {
                "title": "テスト動画",
                "channel_id": "UCtest",
                "notified_at": "2026-01-01T00:00:00+00:00",
            }
        }

        hm.save()

        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "vid001" in data["notified_videos"]

    def test_親ディレクトリが存在しなくても保存できる(self, tmp_path: Path):
        path = tmp_path / "new_dir" / "notified.json"
        hm = HistoryManager(str(path))
        hm._notified = {}

        hm.save()
        assert path.exists()
