import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.models import VideoEntry

logger = logging.getLogger(__name__)


class HistoryManager:
    """通知済み動画の履歴を管理する。"""

    def __init__(self, data_path: str = "data/notified.json"):
        self._path = Path(data_path)
        self._notified: dict[str, dict] = {}

    def load(self) -> None:
        """履歴ファイルを読み込む。ファイルが存在しない場合は空の状態で初期化する。"""
        if not self._path.exists():
            logger.info("履歴ファイルが存在しないため新規作成します: %s", self._path)
            self._notified = {}
            return

        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._notified = data.get("notified_videos", {})
            logger.info("履歴ファイル読み込み完了 - 登録数: %d", len(self._notified))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("履歴ファイルが破損しています。空の状態で初期化します: %s", e)
            self._notified = {}

    def is_notified(self, video_id: str) -> bool:
        """指定した動画IDが通知済みかどうかを返す。"""
        return video_id in self._notified

    def filter_new(self, videos: list[VideoEntry]) -> list[VideoEntry]:
        """通知済み動画を除外して新着のみ返す。"""
        new_videos = [v for v in videos if not self.is_notified(v.video_id)]
        logger.info("新着動画: %d件（全%d件中）", len(new_videos), len(videos))
        return new_videos

    def mark_notified(self, video: VideoEntry) -> None:
        """動画を通知済みとして記録する。"""
        self._notified[video.video_id] = {
            "title": video.title,
            "channel_id": video.channel_id,
            "notified_at": datetime.now(timezone.utc).isoformat(),
        }

    def cleanup_old_entries(self, retention_days: int = 90) -> int:
        """指定日数以上前のエントリを削除する。

        Returns:
            削除したエントリ数
        """
        now = datetime.now(timezone.utc)
        to_remove = []

        for video_id, info in self._notified.items():
            notified_at_str = info.get("notified_at", "")
            try:
                notified_at = datetime.fromisoformat(notified_at_str)
                if (now - notified_at).days >= retention_days:
                    to_remove.append(video_id)
            except (ValueError, TypeError):
                # パースできないエントリは削除対象
                to_remove.append(video_id)

        for video_id in to_remove:
            del self._notified[video_id]

        if to_remove:
            logger.info("古いエントリを%d件削除しました", len(to_remove))
        return len(to_remove)

    def save(self) -> None:
        """履歴をファイルに保存する。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(
                {"notified_videos": self._notified},
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info("履歴ファイル保存完了 - 登録数: %d", len(self._notified))
