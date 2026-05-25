"""
ConfigManager のテスト。

設定の読み書き・デフォルト値のマージ・後方互換性などを検証する。
"""

import json
import pytest

import config_manager as cm_module


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """一時ディレクトリに config.json を作成し、テスト後に自動削除する。"""
    config_file = str(tmp_path / "config.json")
    monkeypatch.setattr(cm_module, "CONFIG_FILE", config_file)
    from config_manager import ConfigManager
    return ConfigManager


# ──────────────────────────────────────────
# デフォルト値
# ──────────────────────────────────────────

class TestDefaults:
    def test_all_default_keys_exist(self, tmp_config):
        mgr = tmp_config()
        for key in cm_module.ConfigManager.DEFAULT_CONFIG:
            assert mgr.get(key) is not None  # キーが存在する

    def test_default_api_keys_are_empty(self, tmp_config):
        mgr = tmp_config()
        assert mgr.get("gemini_api_key") == ""
        assert mgr.get("instagram_access_token") == ""


# ──────────────────────────────────────────
# 読み書き
# ──────────────────────────────────────────

class TestReadWrite:
    def test_set_and_get(self, tmp_config):
        mgr = tmp_config()
        mgr.set("gemini_api_key", "AIza_test_key")
        assert mgr.get("gemini_api_key") == "AIza_test_key"

    def test_save_and_reload(self, tmp_config):
        mgr = tmp_config()
        mgr.set("instagram_user_id", "17841000000000")
        mgr.save()

        # 別のインスタンスで読み直す
        mgr2 = tmp_config()
        assert mgr2.get("instagram_user_id") == "17841000000000"

    def test_save_creates_valid_json(self, tmp_config):
        mgr = tmp_config()
        mgr.set("gemini_api_key", "test")
        mgr.save()

        with open(cm_module.CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        assert data["gemini_api_key"] == "test"


# ──────────────────────────────────────────
# 後方互換性（新キーの自動補完）
# ──────────────────────────────────────────

class TestBackwardCompatibility:
    def test_missing_key_gets_default(self, tmp_config):
        """
        古い config.json に存在しないキーは DEFAULT_CONFIG の値で補完される。
        新機能を追加したときに既存ユーザーの設定が壊れないことを確認する。
        """
        # caption_prompt が存在しない古い設定ファイルを模擬する
        old_config = {
            "gemini_api_key": "old_key",
        }
        with open(cm_module.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(old_config, f)

        mgr = tmp_config()
        assert mgr.get("gemini_api_key") == "old_key"  # 既存値は保持
        assert mgr.get("caption_prompt") == ""          # 新キーはデフォルト値

    def test_existing_values_not_overwritten(self, tmp_config):
        """既存の設定値がデフォルト値で上書きされないこと。"""
        existing = {"gemini_api_key": "my_key", "imgbb_api_key": "imgbb_key"}
        with open(cm_module.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f)

        mgr = tmp_config()
        assert mgr.get("gemini_api_key") == "my_key"
        assert mgr.get("imgbb_api_key") == "imgbb_key"
