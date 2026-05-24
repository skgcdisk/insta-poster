import base64
import time
import requests


class InstagramClient:
    """
    Instagram Graph API と imgbb API を組み合わせて画像を投稿するクラス。

    Instagram Graph API は「公開されている画像 URL」を要求するため、
    ローカルファイルをそのまま渡せない。そのため imgbb（無料の画像ホスティング）
    に一時アップロードして公開 URL を取得してから Instagram に渡す。

    投稿フロー:
        1. imgbb に画像をアップロードして公開 URL を取得
        2. Instagram にメディアコンテナを作成
        3. コンテナの処理が完了（FINISHED）するまでポーリングで待機
        4. FINISHED を確認してから publish（公開）

    ステップ3が重要: Instagram はコンテナ作成後に画像を非同期処理するため、
    完了を確認せずに即 publish すると 400 エラーになる。
    """

    GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
    IMGBB_API_URL  = "https://api.imgbb.com/1/upload"

    # コンテナのステータスポーリング設定
    POLL_INTERVAL_SEC = 3    # 確認する間隔（秒）
    POLL_MAX_RETRIES  = 20   # 最大試行回数（3秒 × 20回 = 最大60秒待機）

    def __init__(self, user_id: str, access_token: str, imgbb_api_key: str):
        self.user_id       = user_id
        self.access_token  = access_token
        self.imgbb_api_key = imgbb_api_key

    def upload_to_imgbb(self, image_path: str) -> str:
        """
        ローカル画像を imgbb にアップロードして公開 URL を返す。

        Returns:
            画像の公開 URL
        """
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            self.IMGBB_API_URL,
            data={"key": self.imgbb_api_key, "image": image_data},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["data"]["url"]

    def create_media_container(self, image_url: str, caption: str) -> str:
        """
        Instagram にメディアコンテナを作成して、そのコンテナ ID を返す。
        Instagram の投稿は「コンテナ作成 → 処理待ち → 公開」の 3 ステップ方式。

        Returns:
            メディアコンテナ ID
        """
        response = requests.post(
            f"{self.GRAPH_API_BASE}/{self.user_id}/media",
            data={
                "image_url":    image_url,
                "caption":      caption,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        # エラー時は Instagram からの詳細メッセージをターミナルに出力する
        if not response.ok:
            print(f"[instagram] create_media_container エラー詳細: {response.text}")
        response.raise_for_status()
        return response.json()["id"]

    def wait_until_ready(self, container_id: str):
        """
        メディアコンテナの処理が完了するまでポーリングして待機する。

        Instagram はコンテナ作成後に画像を非同期で処理する。
        処理完了前に publish を呼ぶと 400 エラーになるため、
        status_code が FINISHED になるまで一定間隔で確認し続ける。

        status_code の種類:
            IN_PROGRESS : 処理中（待機継続）
            FINISHED    : 処理完了（publish 可能）
            ERROR       : 処理失敗（例外を投げる）
            EXPIRED     : コンテナ期限切れ（24時間以上経過）

        Raises:
            RuntimeError: ERROR / EXPIRED ステータス、またはタイムアウト時
        """
        for attempt in range(1, self.POLL_MAX_RETRIES + 1):
            response = requests.get(
                f"{self.GRAPH_API_BASE}/{container_id}",
                params={
                    "fields":       "status_code",
                    "access_token": self.access_token,
                },
                timeout=15,
            )
            if not response.ok:
                print(f"[instagram] wait_until_ready エラー詳細: {response.text}")
            response.raise_for_status()

            status = response.json().get("status_code", "")
            print(f"[instagram] コンテナステータス確認 ({attempt}/{self.POLL_MAX_RETRIES}): {status}")

            if status == "FINISHED":
                return   # 処理完了 → publish へ進む
            elif status == "ERROR":
                raise RuntimeError("Instagram のメディア処理でエラーが発生しました（status_code: ERROR）")
            elif status == "EXPIRED":
                raise RuntimeError("メディアコンテナの有効期限が切れました（status_code: EXPIRED）")
            # IN_PROGRESS の場合は待機して再試行

            time.sleep(self.POLL_INTERVAL_SEC)

        # POLL_MAX_RETRIES 回試みても FINISHED にならなかった
        raise RuntimeError(
            f"メディア処理が {self.POLL_MAX_RETRIES * self.POLL_INTERVAL_SEC} 秒以内に完了しませんでした"
        )

    def publish(self, container_id: str) -> str:
        """
        作成済みのメディアコンテナを Instagram に公開する。
        呼び出し前に wait_until_ready() でコンテナが FINISHED であることを確認すること。

        Returns:
            Instagram の投稿 ID
        """
        response = requests.post(
            f"{self.GRAPH_API_BASE}/{self.user_id}/media_publish",
            data={
                "creation_id":  container_id,
                "access_token": self.access_token,
            },
            timeout=30,
        )
        # エラー時は Instagram からの詳細メッセージをターミナルに出力する
        if not response.ok:
            print(f"[instagram] publish エラー詳細: {response.text}")
        response.raise_for_status()
        return response.json()["id"]

    def post(self, image_path: str, caption: str) -> str:
        """
        imgbb アップロード → コンテナ作成 → 処理完了待ち → 公開
        の一連の投稿処理を実行する。

        Returns:
            Instagram の投稿 ID
        """
        image_url    = self.upload_to_imgbb(image_path)
        container_id = self.create_media_container(image_url, caption)
        self.wait_until_ready(container_id)   # FINISHED を確認してから publish
        post_id      = self.publish(container_id)
        return post_id
