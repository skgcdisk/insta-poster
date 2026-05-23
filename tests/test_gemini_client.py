"""
GeminiClient のテスト。

実際の API は呼び出さず、レスポンスのパース処理（最もバグりやすい部分）を
モックを使って検証する。
"""

import pytest
from unittest.mock import MagicMock, patch

from gemini_client import GeminiClient


@pytest.fixture
def client():
    """API キーなしでクライアントを生成するフィクスチャ。"""
    with patch("gemini_client.genai.Client"):
        return GeminiClient(api_key="dummy_key")


def make_mock_response(text: str):
    """指定テキストを返す Gemini レスポンスのモックを作る。"""
    mock = MagicMock()
    mock.text = text
    return mock


# ──────────────────────────────────────────
# _build_prompt
# ──────────────────────────────────────────

class TestBuildPrompt:
    def test_uses_default_when_no_custom(self, client):
        prompt = client._build_prompt(None)
        assert GeminiClient.DEFAULT_CAPTION_PROMPT in prompt
        assert "SAFETY:" in prompt
        assert "CAPTION:" in prompt

    def test_uses_custom_caption_when_provided(self, client):
        custom = "カジュアルなトーンで書いてください"
        prompt = client._build_prompt(custom)
        assert custom in prompt
        # デフォルトキャプションは含まれない
        assert GeminiClient.DEFAULT_CAPTION_PROMPT not in prompt

    def test_safety_prompt_always_included(self, client):
        """カスタムプロンプトがあっても安全チェック指示は必ず含まれる。"""
        prompt = client._build_prompt("任意のキャプション指示")
        assert "公序良俗" in prompt

    def test_response_format_always_included(self, client):
        """返答フォーマット指示は常に含まれる。"""
        for custom in [None, "カスタム指示"]:
            prompt = client._build_prompt(custom)
            assert "SAFETY: OK" in prompt
            assert "CAPTION:" in prompt


# ──────────────────────────────────────────
# analyze_image のレスポンスパース
# ──────────────────────────────────────────

class TestAnalyzeImageParsing:
    """
    実際の API 呼び出しはモックして、テキストパース部分だけを検証する。
    """

    def _call(self, client, response_text: str):
        """analyze_image を実行してレスポンステキストをモックで返す。"""
        mock_response = make_mock_response(response_text)
        with patch("gemini_client.Image.open"), \
             patch.object(client.client.models, "generate_content", return_value=mock_response):
            return client.analyze_image("/dummy/path.jpg")

    def test_ok_response(self, client):
        text = "SAFETY: OK\nCAPTION: 素敵な写真です🌸 #写真 #日常"
        is_safe, ng_reason, caption = self._call(client, text)
        assert is_safe is True
        assert ng_reason == ""
        assert caption == "素敵な写真です🌸 #写真 #日常"

    def test_ng_response(self, client):
        text = "SAFETY: NG:暴力的な内容\nCAPTION: なし"
        is_safe, ng_reason, caption = self._call(client, text)
        assert is_safe is False
        assert ng_reason == "暴力的な内容"
        assert caption == ""

    def test_caption_none_returns_empty_string(self, client):
        text = "SAFETY: NG:不適切\nCAPTION: なし"
        _, _, caption = self._call(client, text)
        assert caption == ""

    def test_extra_whitespace_handled(self, client):
        """前後のスペースやインデントがあってもパースできること。"""
        text = "  SAFETY:  OK  \n  CAPTION:  きれいな空 ☀️  "
        is_safe, _, caption = self._call(client, text)
        assert is_safe is True
        assert "きれいな空" in caption

    def test_ng_without_reason(self, client):
        """NG の後に理由がない形式でも安全チェックが NG になること。"""
        text = "SAFETY: NG\nCAPTION: なし"
        is_safe, _, _ = self._call(client, text)
        assert is_safe is False

    def test_custom_caption_prompt_is_passed(self, client):
        """カスタムプロンプトが API リクエストに含まれることを確認。"""
        custom = "英語でキャプションを書いて"
        mock_response = make_mock_response("SAFETY: OK\nCAPTION: Beautiful day!")

        with patch("gemini_client.Image.open"), \
             patch.object(client.client.models, "generate_content",
                          return_value=mock_response) as mock_call:
            client.analyze_image("/dummy.jpg", custom_caption_prompt=custom)

        # generate_content に渡された contents の中にカスタムプロンプトが含まれること
        call_args = mock_call.call_args
        contents = call_args.kwargs.get("contents", [])
        prompt_str = contents[0] if contents else ""
        assert custom in prompt_str
