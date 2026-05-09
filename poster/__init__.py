from config_manager import ConfigManager
from queue_manager import QueueManager
from poster.base import PosterBase
from poster.local_poster import LocalPoster
from poster.server_poster import ServerPoster


def get_poster(
    config: ConfigManager,
    queue_manager: QueueManager,
    on_post_done=None,
) -> PosterBase:
    """
    設定の posting_mode に応じて適切な Poster インスタンスを返すファクトリ関数。

    app.py はこの関数だけを呼ぶ。Phase を切り替えるときもここだけを変更すれば
    UI 側のコードに一切影響しない。

        "local"  → LocalPoster  （Phase1: APScheduler が直接 Instagram に投稿）
        "server" → ServerPoster （Phase2: サーバーに画像とジョブをアップロード）
    """
    mode = config.get("posting_mode", "local")
    cfg  = config.config  # 辞書として各 Poster に渡す

    if mode == "server":
        return ServerPoster(cfg, queue_manager, on_post_done)
    else:
        return LocalPoster(cfg, queue_manager, on_post_done)
