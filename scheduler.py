import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# post_job.execute_post はモジュールレベル関数なので SQLite に pickle 保存できる
from post_job import execute_post

# APScheduler の INFO ログは冗長なので WARNING 以上のみ表示する
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ジョブ永続化先の SQLite ファイル
JOBSTORE_URL = "sqlite:///jobs.sqlite"


class Scheduler:
    """
    APScheduler を使ったローカルスケジューラー（Phase1 専用）。

    SQLite でジョブを永続化するため、アプリを再起動しても
    投稿予約が消えずに復元される。

    【pickle 問題の解決策】
    APScheduler の SQLite ジョブストアはジョブ関数を pickle（直列化）して保存する。
    クラスのメソッドや tkinter オブジェクトへの参照を含む関数は pickle できないため、
    ジョブ関数は post_job.py のモジュールレベル関数 execute_post を使う。
    """

    def __init__(self):
        jobstores = {"default": SQLAlchemyJobStore(url=JOBSTORE_URL)}
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone="Asia/Tokyo",
        )

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
        指定日時に execute_post(job_id) を実行するジョブを登録する。
        同じ job_id が既に登録済みの場合は上書きする。
        """
        self.scheduler.add_job(
            execute_post,           # モジュールレベル関数 → pickle 可能
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
