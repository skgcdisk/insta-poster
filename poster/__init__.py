from config_manager import ConfigManager
from queue_manager import QueueManager
from poster.base import PosterBase
from poster.local_poster import LocalPoster


def get_poster(
    config: ConfigManager,
    queue_manager: QueueManager,
    on_post_done=None,
) -> PosterBase:
    """
    Poster インスタンスを返すファクトリ関数。
    現在は LocalPoster のみ対応（Phase1）。
    """
    return LocalPoster(config.config, queue_manager, on_post_done)
