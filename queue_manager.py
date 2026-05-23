import json
import os
import uuid
from datetime import datetime

QUEUE_FILE = "queue.json"


class QueueManager:
    """
    投稿キューを queue.json で永続管理するクラス。

    各ジョブは辞書形式で保持する。この構造は Phase1（ローカル）と
    Phase2（サーバー）で共通して使えるよう設計している。

    ステータス遷移:
        pending → processing → ready → scheduled → posted
                            ↘ ng（安全チェック失敗）
                                      ↘ error（投稿失敗）
    """

    def __init__(self):
        self.jobs: list[dict] = self._load()

    def _load(self) -> list[dict]:
        """queue.json を読み込む。存在しない場合は空リストを返す。"""
        if os.path.exists(QUEUE_FILE):
            # utf-8-sig は BOM あり・なし両方に対応する
            with open(QUEUE_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        return []

    def save(self):
        """現在のキューを queue.json に書き出す。"""
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.jobs, f, ensure_ascii=False, indent=2, default=str)

    def add(self, original_path: str) -> dict:
        """
        新しいジョブをキューに追加して返す。
        同じパスのファイルが既にキューにある場合は追加しない。
        """
        # 重複追加を防ぐ
        if any(j["original_path"] == original_path for j in self.jobs):
            return next(j for j in self.jobs if j["original_path"] == original_path)

        job = {
            "id":              str(uuid.uuid4()),
            "original_path":   original_path,
            "corrected_path":  "",
            "caption":         "",
            "scheduled_at":    "",      # ISO 8601 形式の文字列
            "status":          "pending",
            "ng_reason":       "",
            "error_message":   "",
            "instagram_post_id": "",
            "created_at":      datetime.now().isoformat(),
        }
        self.jobs.append(job)
        self.save()
        return job

    def update(self, job_id: str, **kwargs):
        """指定 ID のジョブを部分更新する。"""
        for job in self.jobs:
            if job["id"] == job_id:
                job.update(kwargs)
                self.save()
                return

    def get(self, job_id: str) -> dict | None:
        """指定 ID のジョブを返す。見つからない場合は None。"""
        return next((j for j in self.jobs if j["id"] == job_id), None)

    def remove(self, job_id: str):
        """指定 ID のジョブをキューから削除する。"""
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        self.save()

    def get_ready_jobs(self) -> list[dict]:
        """処理済み（スケジュール未登録）のジョブを返す。"""
        return [j for j in self.jobs if j["status"] == "ready"]
