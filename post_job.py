"""
APScheduler から呼び出される投稿処理モジュール。

モジュールレベルの関数として定義することで、APScheduler の SQLite ジョブストアが
pickle（直列化）できるようにしている。クラスのメソッドや tkinter オブジェクトへの
参照を持つ関数は pickle できないため、このファイルに独立させている。
"""

def execute_post(job_id: str):
    """
    指定されたジョブIDの画像を Instagram に投稿する。
    APScheduler が指定日時にこの関数を自動的に呼び出す。

    Args:
        job_id: QueueManager が管理するジョブの UUID
    """
    # 各モジュールをここでインポートすることで、循環インポートを防ぎつつ
    # 実行時に最新の設定・キュー状態を読み込む
    from config_manager import ConfigManager
    from queue_manager import QueueManager
    from instagram_client import InstagramClient

    config = ConfigManager()
    queue  = QueueManager()
    job    = queue.get(job_id)

    if not job:
        print(f"[post_job] ジョブが見つかりません: {job_id}")
        return

    print(f"[post_job] 投稿開始: {job_id} ({job.get('original_path', '')})")

    instagram = InstagramClient(
        user_id=config.get("instagram_user_id"),
        access_token=config.get("instagram_access_token"),
        imgbb_api_key=config.get("imgbb_api_key"),
    )

    try:
        post_id = instagram.post(job["corrected_path"], job["caption"])
        queue.update(job_id, status="posted", instagram_post_id=post_id)
        print(f"[post_job] 投稿完了: Instagram投稿ID = {post_id}")
    except Exception as e:
        queue.update(job_id, status="error", error_message=str(e))
        print(f"[post_job] 投稿エラー: {e}")
