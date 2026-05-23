"""
QueueManager のテスト。

キューの追加・更新・削除・ステータス遷移など、
アプリの中核となるロジックを検証する。
"""

import json
import os
import tempfile
import pytest

# テスト用に QUEUE_FILE を一時ファイルに差し替える
import queue_manager as qm_module


@pytest.fixture
def tmp_queue(tmp_path, monkeypatch):
    """一時ディレクトリに queue.json を作成し、テスト後に自動削除する。"""
    queue_file = str(tmp_path / "queue.json")
    monkeypatch.setattr(qm_module, "QUEUE_FILE", queue_file)
    # QueueManager は import 時に QUEUE_FILE を参照するため、パスを変えてから生成する
    from queue_manager import QueueManager
    return QueueManager()


# ──────────────────────────────────────────
# add
# ──────────────────────────────────────────

class TestAdd:
    def test_add_returns_job_dict(self, tmp_queue):
        job = tmp_queue.add("/path/to/image.jpg")
        assert job["original_path"] == "/path/to/image.jpg"
        assert job["status"] == "pending"

    def test_add_creates_unique_id(self, tmp_queue):
        job1 = tmp_queue.add("/img1.jpg")
        job2 = tmp_queue.add("/img2.jpg")
        assert job1["id"] != job2["id"]

    def test_add_duplicate_returns_existing(self, tmp_queue):
        job1 = tmp_queue.add("/img.jpg")
        job2 = tmp_queue.add("/img.jpg")
        assert job1["id"] == job2["id"]
        assert len(tmp_queue.jobs) == 1

    def test_add_persists_to_file(self, tmp_queue, monkeypatch):
        tmp_queue.add("/img.jpg")
        # ファイルを直接読んで確認
        with open(qm_module.QUEUE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["original_path"] == "/img.jpg"


# ──────────────────────────────────────────
# update
# ──────────────────────────────────────────

class TestUpdate:
    def test_update_status(self, tmp_queue):
        job = tmp_queue.add("/img.jpg")
        tmp_queue.update(job["id"], status="processing")
        updated = tmp_queue.get(job["id"])
        assert updated["status"] == "processing"

    def test_update_multiple_fields(self, tmp_queue):
        job = tmp_queue.add("/img.jpg")
        tmp_queue.update(job["id"], status="ready", caption="テストキャプション")
        updated = tmp_queue.get(job["id"])
        assert updated["status"] == "ready"
        assert updated["caption"] == "テストキャプション"

    def test_update_nonexistent_id_does_nothing(self, tmp_queue):
        # 存在しない ID を更新してもエラーにならないこと
        tmp_queue.update("nonexistent-id", status="error")


# ──────────────────────────────────────────
# remove
# ──────────────────────────────────────────

class TestRemove:
    def test_remove_decreases_count(self, tmp_queue):
        job = tmp_queue.add("/img.jpg")
        assert len(tmp_queue.jobs) == 1
        tmp_queue.remove(job["id"])
        assert len(tmp_queue.jobs) == 0

    def test_remove_nonexistent_does_nothing(self, tmp_queue):
        tmp_queue.remove("nonexistent-id")
        assert len(tmp_queue.jobs) == 0


# ──────────────────────────────────────────
# get_ready_jobs
# ──────────────────────────────────────────

class TestGetReadyJobs:
    def test_returns_only_ready(self, tmp_queue):
        j1 = tmp_queue.add("/img1.jpg")
        j2 = tmp_queue.add("/img2.jpg")
        j3 = tmp_queue.add("/img3.jpg")
        tmp_queue.update(j1["id"], status="ready")
        tmp_queue.update(j2["id"], status="pending")
        tmp_queue.update(j3["id"], status="ready")

        ready = tmp_queue.get_ready_jobs()
        assert len(ready) == 2
        statuses = {j["status"] for j in ready}
        assert statuses == {"ready"}

    def test_empty_when_no_ready(self, tmp_queue):
        tmp_queue.add("/img.jpg")
        assert tmp_queue.get_ready_jobs() == []


# ──────────────────────────────────────────
# ステータス遷移
# ──────────────────────────────────────────

class TestStatusTransition:
    """pending → processing → ready → scheduled → posted の遷移を検証する。"""

    def test_full_happy_path(self, tmp_queue):
        job = tmp_queue.add("/img.jpg")
        assert job["status"] == "pending"

        tmp_queue.update(job["id"], status="processing")
        assert tmp_queue.get(job["id"])["status"] == "processing"

        tmp_queue.update(job["id"], status="ready", caption="キャプション")
        assert tmp_queue.get(job["id"])["status"] == "ready"

        tmp_queue.update(job["id"], status="scheduled", scheduled_at="2026-06-01T10:00:00")
        assert tmp_queue.get(job["id"])["status"] == "scheduled"

        tmp_queue.update(job["id"], status="posted", instagram_post_id="123456")
        j = tmp_queue.get(job["id"])
        assert j["status"] == "posted"
        assert j["instagram_post_id"] == "123456"

    def test_ng_path(self, tmp_queue):
        job = tmp_queue.add("/img.jpg")
        tmp_queue.update(job["id"], status="ng", ng_reason="暴力的な内容")
        j = tmp_queue.get(job["id"])
        assert j["status"] == "ng"
        assert j["ng_reason"] == "暴力的な内容"
