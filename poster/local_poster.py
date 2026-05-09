from datetime import datetime

from instagram_client import InstagramClient
from queue_manager import QueueManager
from scheduler import Scheduler
from poster.base import PosterBase


class LocalPoster(PosterBase):
    """
    Phase1 用のローカル投稿クラス。

    APScheduler がバックグラウンドで動き続け、指定日時になると
    自動的に Instagram へ投稿する。スケジュールは SQLite に保存されるため
    アプリを再起動しても予約が維持される。
    """

    def __init__(self, config: dict, queue_manager: QueueManager, on_post_done=None):
        """
        Args:
            config:        ConfigManager.config 辞書
            queue_manager: 共有の QueueManager インスタンス
            on_post_done:  投稿完了時に呼ばれるコールバック関数（UI 通知用）
        """
        self.queue_manager = queue_manager
        self.on_post_done  = on_post_done

        self.instagram = InstagramClient(
            user_id=config["instagram_user_id"],
            access_token=config["instagram_access_token"],
            imgbb_api_key=config["imgbb_api_key"],
        )

        # スケジューラーに投稿実行関数を渡して初期化・起動
        self.scheduler = Scheduler(post_func=self._execute_post)
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

    def _execute_post(self, job_id: str):
        """
        APScheduler から呼ばれる実際の投稿処理。
        バックグラウンドスレッドで実行される。
        """
        job = self.queue_manager.get(job_id)
        if not job:
            return

        try:
            post_id = self.instagram.post(job["corrected_path"], job["caption"])
            self.queue_manager.update(job_id, status="posted", instagram_post_id=post_id)
        except Exception as e:
            self.queue_manager.update(job_id, status="error", error_message=str(e))
        finally:
            # UI への通知は after() 経由でメインスレッドに渡す（app.py 側で処理）
            if self.on_post_done:
                self.on_post_done(job_id)

    def shutdown(self):
        """アプリ終了時にスケジューラーを安全に停止する。"""
        self.scheduler.shutdown()

    def get_next_run_time(self) -> datetime | None:
        """次回投稿予定時刻を返す。ステータスバー表示用。"""
        return self.scheduler.get_next_run_time()
