import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# APScheduler の INFO ログは冗長なので WARNING 以上のみ表示する
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ジョブ永続化先の SQLite ファイル
JOBSTORE_URL = "sqlite:///jobs.sqlite"


class Scheduler:
    """
    APScheduler を使ったローカルスケジューラー（Phase1 専用）。

    SQLite でジョブを永続化するため、アプリを再起動しても
    投稿予約が消えずに復元される。
    """

    def __init__(self, post_func):
        """
        Args:
            post_func: job_id (str) を引数に取る投稿実行関数
        """
        jobstores = {"default": SQLAlchemyJobStore(url=JOBSTORE_URL)}
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone="Asia/Tokyo",
        )
        self.post_func = post_func

    def start(self):
        """スケジューラーを起動する。既に起動済みの場合は何もしない。"""
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        """スケジューラーを停止する。アプリ終了時に必ず呼ぶこと。"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def add_job(self, job_id: str, scheduled_at: datetime):
        """
        指定日時に post_func(job_id) を実行するジョブを登録する。
        同じ job_id が既に登録済みの場合は上書きする。
        """
        self.scheduler.add_job(
            self.post_func,
            trigger="date",
            run_date=scheduled_at,
            args=[job_id],
            id=job_id,
            replace_existing=True,
        )

    def remove_job(self, job_id: str):
        """ジョブを削除する。存在しない場合は何もしない。"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

    def get_next_run_time(self) -> datetime | None:
        """直近のジョブ実行予定時刻を返す。ジョブがなければ None。"""
        jobs = self.scheduler.get_jobs()
        times = [j.next_run_time for j in jobs if j.next_run_time]
        return min(times) if times else None
