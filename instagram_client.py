import base64
import requests


class InstagramClient:
    """
    Instagram Graph API と imgbb API を組み合わせて画像を投稿するクラス。

    Instagram Graph API は「公開されている画像 URL」を要求するため、
    ローカルファイルをそのまま渡せない。そのため imgbb（無料の画像ホスティング）
    に一時アップロードして公開 URL を取得してから Instagram に渡す。
    """

    GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
    IMGBB_API_URL  = "https://api.imgbb.com/1/upload"

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
        Instagram の投稿は「コンテナ作成 → 公開」の 2 ステップ方式。

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
        response.raise_for_status()
        return response.json()["id"]

    def publish(self, container_id: str) -> str:
        """
        作成済みのメディアコンテナを Instagram に公開する。

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
        response.raise_for_status()
        return response.json()["id"]

    def post(self, image_path: str, caption: str) -> str:
        """
        imgbb アップロード → コンテナ作成 → 公開 の一連の投稿処理を実行する。

        Returns:
            Instagram の投稿 ID
        """
        image_url    = self.upload_to_imgbb(image_path)
        container_id = self.create_media_container(image_url, caption)
        post_id      = self.publish(container_id)
        return post_id
