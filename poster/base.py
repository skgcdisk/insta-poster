from abc import ABC, abstractmethod


class PosterBase(ABC):
    """
    投稿方法の抽象基底クラス。

    Phase1（LocalPoster）と Phase2（ServerPoster）は、このクラスを継承して
    同じインターフェースを実装する。app.py はこのクラスの型だけを知っていれば
    どちらのモードでも動作するため、モード切替の影響がUIに波及しない。
    """

    @abstractmethod
    def submit(self, job: dict) -> bool:
        """
        処理済みジョブを投稿キューに登録する。

        Args:
            job: QueueManager が管理するジョブ辞書
        Returns:
            登録成功なら True、失敗なら False
        """
        pass

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """
        投稿予約をキャンセルする。

        Returns:
            キャンセル成功なら True
        """
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> dict:
        """ジョブのステータスを取得する。{"status": str, "error": str} 形式で返す。"""
        pass

    @abstractmethod
    def shutdown(self):
        """アプリ終了時のクリーンアップ処理。不要な場合は pass でよい。"""
        pass
