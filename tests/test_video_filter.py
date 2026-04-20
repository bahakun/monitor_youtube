"""video_filter の単体テスト"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from src.video_filter import filter_videos, _is_short, _is_live_stream
from src.models import VideoEntry


def _make_video(video_id: str = "vid001", title: str = "通常動画タイトル") -> VideoEntry:
    """テスト用 VideoEntry を生成するヘルパー"""
    return VideoEntry(
        video_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        published=datetime(2026, 1, 1, tzinfo=timezone.utc),
        channel_id="UCtest",
    )


def _mock_oembed(thumbnail_url: str = "", width: int = 1280, height: int = 720, title: str = "通常動画"):
    """テスト用 oEmbed レスポンスを生成するヘルパー"""
    return {
        "thumbnail_url": thumbnail_url,
        "width": width,
        "height": height,
        "title": title,
    }


class TestIsShort:
    """_is_short() のテスト"""

    def test_oEmbedがNoneの場合はFalseを返す(self):
        assert _is_short(None) is False

    def test_thumbnail_urlにshortsが含まれる場合はTrueを返す(self):
        oembed = _mock_oembed(thumbnail_url="https://i.ytimg.com/vi/xxx/shorts/default.jpg")
        assert _is_short(oembed) is True

    def test_縦長動画はTrueを返す(self):
        oembed = _mock_oembed(width=720, height=1280)
        assert _is_short(oembed) is True

    def test_横長の通常動画はFalseを返す(self):
        oembed = _mock_oembed(width=1280, height=720)
        assert _is_short(oembed) is False

    def test_正方形動画はFalseを返す(self):
        oembed = _mock_oembed(width=720, height=720)
        assert _is_short(oembed) is False


class TestIsLiveStream:
    """_is_live_stream() のテスト"""

    def test_タイトルにliveが含まれる場合はTrueを返す(self):
        video = _make_video(title="【LIVE】テスト配信")
        assert _is_live_stream(video, None) is True

    def test_タイトルにライブが含まれる場合はTrueを返す(self):
        video = _make_video(title="【ライブ】テスト配信")
        assert _is_live_stream(video, None) is True

    def test_タイトルに生配信が含まれる場合はTrueを返す(self):
        video = _make_video(title="生配信 今日のニュース")
        assert _is_live_stream(video, None) is True

    def test_oEmbedのタイトルにライブキーワードが含まれる場合はTrueを返す(self):
        video = _make_video(title="普通のタイトル")
        oembed = _mock_oembed(title="【ライブ】実際のタイトル")
        assert _is_live_stream(video, oembed) is True

    def test_ライブキーワードがない場合はFalseを返す(self):
        video = _make_video(title="普通の動画タイトル")
        oembed = _mock_oembed(title="普通のタイトル")
        assert _is_live_stream(video, oembed) is False

    def test_大文字小文字を区別しない(self):
        video = _make_video(title="Live Stream Test")
        assert _is_live_stream(video, None) is True


class TestFilterVideos:
    """filter_videos() のテスト（外部API呼び出しはモック）"""

    def test_通常動画はそのまま通過する(self):
        videos = [_make_video("vid001", "普通の動画")]
        normal_oembed = _mock_oembed()

        with patch("src.video_filter._fetch_oembed", return_value=normal_oembed):
            result = filter_videos(videos)

        assert len(result) == 1
        assert result[0].video_id == "vid001"

    def test_Shorts動画は除外される(self):
        videos = [_make_video("vid001", "Shorts動画")]
        shorts_oembed = _mock_oembed(thumbnail_url="https://i.ytimg.com/vi/xxx/shorts/default.jpg")

        with patch("src.video_filter._fetch_oembed", return_value=shorts_oembed):
            result = filter_videos(videos)

        assert len(result) == 0

    def test_ライブ配信は除外される(self):
        videos = [_make_video("vid001", "【LIVE】テスト配信")]
        normal_oembed = _mock_oembed()

        with patch("src.video_filter._fetch_oembed", return_value=normal_oembed):
            result = filter_videos(videos)

        assert len(result) == 0

    def test_oEmbedがNoneでも通常動画は通過する(self):
        videos = [_make_video("vid001", "普通の動画")]

        with patch("src.video_filter._fetch_oembed", return_value=None):
            result = filter_videos(videos)

        assert len(result) == 1

    def test_混合リストで正しくフィルタリングされる(self):
        videos = [
            _make_video("vid001", "普通の動画"),
            _make_video("vid002", "【LIVE】ライブ配信"),
            _make_video("vid003", "普通の動画2"),
        ]
        normal_oembed = _mock_oembed()

        with patch("src.video_filter._fetch_oembed", return_value=normal_oembed):
            result = filter_videos(videos)

        assert len(result) == 2
        assert result[0].video_id == "vid001"
        assert result[1].video_id == "vid003"

    def test_空リストを渡すと空リストが返る(self):
        with patch("src.video_filter._fetch_oembed", return_value=None):
            result = filter_videos([])

        assert result == []
