from datetime import datetime

from queue_manager import QueueManager
from scheduler import Scheduler
from poster.base import PosterBase


class LocalPoster(PosterBase):
    """
    Phase1 用のローカル投稿クラス。

    APScheduler がバックグラウンドで動き続け、指定日時になると
    post_job.execute_post() を自動的に呼び出して Instagram へ投稿する。
    スケジュールは SQLite に保存されるためアプリ再起動後も維持される。

    【設計上の注意】
    投稿処理は post_job.py のモジュールレベル関数が担う。
    tkinter オブジェクトへの参照を持つメソッドは pickle できないため、
    このクラスは「スケジュール登録・管理」のみを責務とする。
    UI への完了通知はアプリ側のポーリングで行う。
    """

    def __init__(self, config: dict, queue_manager: QueueManager, on_post_done=None):
        """
        Args:
            config:        ConfigManager.config 辞書
            queue_manager: 共有の QueueManager インスタンス
            on_post_done:  現バージョンでは未使用（将来の拡張用に保持）
        """
        self.queue_manager = queue_manager
        self.scheduler = Scheduler()
        self.scheduler.start()

    def submit(self, job: dict) -> bool:
        """APScheduler にジョブを登録する。"""
        try:
            scheduled_at = datetime.fromisoformat(job["scheduled_at"])
            self.scheduler.add_job(job["id"], scheduled_at)
            self.queue_manager.update(job["id"], status="scheduled")
            return True
        except Exception as e:
            self.queue_manager.update(job["id"], status="error", error_message=str(e))
            return False

    def cancel(self, job_id: str) -> bool:
        """スケジュール登録を取り消してステータスを "ready" に戻す。"""
        try:
            self.scheduler.remove_job(job_id)
            self.queue_manager.update(job_id, status="ready")
            return True
        except Exception:
            return False

    def get_status(self, job_id: str) -> dict:
        """ローカルの queue からステータスを返す。"""
        job = self.queue_manager.get(job_id)
        if not job:
            return {"status": "not_found", "error": ""}
        return {"status": job["status"], "error": job.get("error_message", "")}

    def shutdown(self):
        """アプリ終了時にスケジューラーを安全に停止する。"""
        self.scheduler.shutdown()

    def get_next_run_time(self) -> datetime | None:
        """次回投稿予定時刻を返す。ステータスバー表示用。"""
        return self.scheduler.get_next_run_time()
