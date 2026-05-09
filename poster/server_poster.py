import requests

from poster.base import PosterBase
from queue_manager import QueueManager


class ServerPoster(PosterBase):
    """
    Phase2 用のサーバー経由投稿クラス。

    ローカル側は画像補正・安全チェック・キャプション生成のみを行い、
    処理済みデータをサーバー API にアップロードする。
    Instagram への実際の投稿はサーバー側が担当する。

    【サーバー側に必要な API エンドポイント】
        POST   /api/jobs          : ジョブ登録（画像＋キャプション＋日時）
        DELETE /api/jobs/{job_id} : ジョブキャンセル
        GET    /api/jobs/{job_id} : ステータス取得
    """

    def __init__(self, config: dict, queue_manager: QueueManager, on_post_done=None):
        self.server_url    = config["server_url"].rstrip("/")
        self.server_api_key = config["server_api_key"]
        self.queue_manager = queue_manager
        # Phase2 ではサーバー側からの Webhook 等で通知する想定のため
        # on_post_done はポーリングで実現するかサーバー設計に依存する
        self.on_post_done = on_post_done

    def _headers(self) -> dict:
        """認証ヘッダーを返す。"""
        return {"Authorization": f"Bearer {self.server_api_key}"}

    def submit(self, job: dict) -> bool:
        """
        補正済み画像・キャプション・投稿日時をサーバーにアップロードする。
        サーバーが scheduled_at に Instagram へ投稿する。
        """
        try:
            with open(job["corrected_path"], "rb") as f:
                response = requests.post(
                    f"{self.server_url}/api/jobs",
                    headers=self._headers(),
                    files={"image": f},
                    data={
                        "job_id":       job["id"],
                        "caption":      job["caption"],
                        "scheduled_at": job["scheduled_at"],
                    },
                    timeout=60,
                )
            response.raise_for_status()
            self.queue_manager.update(job["id"], status="scheduled")
            return True
        except Exception as e:
            self.queue_manager.update(job["id"], status="error", error_message=str(e))
            return False

    def cancel(self, job_id: str) -> bool:
        """サーバー側のジョブをキャンセルする。"""
        try:
            response = requests.delete(
                f"{self.server_url}/api/jobs/{job_id}",
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            self.queue_manager.update(job_id, status="ready")
            return True
        except Exception:
            return False

    def get_status(self, job_id: str) -> dict:
        """サーバーからジョブのステータスを取得する。"""
        try:
            response = requests.get(
                f"{self.server_url}/api/jobs/{job_id}",
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def shutdown(self):
        """Phase2 ではローカルのスケジューラーは不要なため何もしない。"""
        pass
