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

        # スケジューラー起動直後に期限切れジョブを処理する。
        # APScheduler は起動時に past-due ジョブを即座に実行しようとするが、
        # remove_job → status="expired" に変更することで実行を防ぐ。
        self._expire_past_jobs()

    def _expire_past_jobs(self):
        """
        投稿日時が既に過ぎているジョブを APScheduler から削除し
        ステータスを "expired" に変更する。
        アプリ停止中に投稿日時を経過した場合の意図しない投稿を防ぐ。
        """
        now = datetime.now()
        for job in self.queue_manager.jobs:
            if job["status"] == "scheduled" and job.get("scheduled_at"):
                try:
                    scheduled_at = datetime.fromisoformat(job["scheduled_at"])
                    if scheduled_at < now:
                        self.scheduler.remove_job(job["id"])
                        self.queue_manager.update(
                            job["id"],
                            status="expired",
                            error_message="アプリ停止中に投稿日時を過ぎました",
                        )
                except ValueError:
                    pass

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
