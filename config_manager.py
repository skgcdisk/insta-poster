import json
import os

CONFIG_FILE = "config.json"


class ConfigManager:
    """
    APIキーや投稿モードなどの設定を config.json で管理するクラス。
    新しいキーが追加されてもデフォルト値とマージするため後方互換性を保てる。
    """

    # アプリ全体のデフォルト設定値
    DEFAULT_CONFIG = {
        "gemini_api_key": "",
        "instagram_user_id": "",
        "instagram_access_token": "",
        "imgbb_api_key": "",
        # --- 投稿モード ---
        # "local"  : Phase1 - このPCのAPSchedulerが直接Instagramに投稿する
        # "server" : Phase2 - サーバーに画像・キャプション・日時をアップロードし、サーバーが投稿する
        "posting_mode": "local",
        "server_url": "",
        "server_api_key": "",
        # キャプション生成の指示文（空文字のときは GeminiClient のデフォルトを使用）
        # 安全チェックの指示は GeminiClient 内で固定されており、ここでは変更できない。
        "caption_prompt": "",
    }

    def __init__(self):
        self.config = self._load()

    def _load(self) -> dict:
        """config.json を読み込む。存在しない場合はデフォルト値を返す。"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 既存の保存値を優先しつつ、新キーはデフォルト値で補完する
            return {**self.DEFAULT_CONFIG, **saved}
        return self.DEFAULT_CONFIG.copy()

    def save(self):
        """現在の設定を config.json に書き出す。"""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: str = "") -> str:
        return self.config.get(key, default)

    def set(self, key: str, value: str):
        self.config[key] = value

    def is_local_mode(self) -> bool:
        return self.config.get("posting_mode", "local") == "local"
