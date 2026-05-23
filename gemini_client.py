from google import genai
from PIL import Image


class GeminiClient:
    """
    Gemini API を使って画像の安全チェックとキャプション生成を行うクラス。

    API 呼び出し回数を節約するため、安全チェックとキャプション生成を
    1回のリクエストにまとめて実行する（analyze_image メソッド）。
    """

    # gemini-2.5-flash：2025年時点の最新標準モデル
    MODEL = "gemini-2.5-flash"

    # 安全チェック＋キャプション生成を1回のAPIで行うプロンプト
    # JSONライクな形式で返答させることでパースしやすくしている
    COMBINED_PROMPT = (
        "この画像について2つのことを確認してください。\n\n"
        "【安全チェック】\n"
        "公序良俗に反する内容（暴力・性的・差別的・危険物・その他不適切なもの）が含まれていますか？\n\n"
        "【キャプション生成】\n"
        "この画像に合うInstagramの投稿キャプションを日本語で作成してください。"
        "絵文字を適度に使い、ハッシュタグを5〜8個含めてください。\n\n"
        "以下の形式で答えてください（他の文章は不要です）：\n"
        "SAFETY: OK\n"
        "CAPTION: （キャプション本文）\n\n"
        "もし不適切な内容が含まれていれば：\n"
        "SAFETY: NG:理由を一言で\n"
        "CAPTION: なし"
    )

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def analyze_image(
        self, image_path: str, custom_prompt: str | None = None
    ) -> tuple[bool, str, str]:
        """
        安全チェックとキャプション生成を1回のAPI呼び出しでまとめて実行する。
        API 呼び出し回数を半減できるため、無料枠の節約になる。

        Args:
            image_path:    解析する画像のパス
            custom_prompt: 設定タブで編集されたカスタムプロンプト。
                           None または空文字の場合は COMBINED_PROMPT を使用する。

        Returns:
            (is_safe, ng_reason, caption)
            - is_safe  : True なら安全、False なら NG
            - ng_reason: NG の場合の理由（安全なら空文字）
            - caption  : 生成されたキャプション（NG なら空文字）
        """
        prompt = custom_prompt if custom_prompt else self.COMBINED_PROMPT
        img = Image.open(image_path)
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=[prompt, img],
        )
        text = response.text.strip()

        # レスポンスを行ごとに解析する
        is_safe = True
        ng_reason = ""
        caption = ""

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("SAFETY:"):
                safety_val = line[len("SAFETY:"):].strip()
                if safety_val.upper().startswith("NG"):
                    is_safe = False
                    ng_reason = safety_val.split(":", 1)[-1].strip() if ":" in safety_val else safety_val
            elif line.startswith("CAPTION:"):
                caption_val = line[len("CAPTION:"):].strip()
                if caption_val != "なし":
                    caption = caption_val

        return is_safe, ng_reason, caption

    # ── 個別メソッド（後方互換・デバッグ用に残す） ─────────────────────

    def check_safety(self, image_path: str) -> tuple[bool, str]:
        """画像の安全チェックのみを行う（analyze_image の利用を推奨）。"""
        is_safe, ng_reason, _ = self.analyze_image(image_path)
        return is_safe, ng_reason

    def generate_caption(self, image_path: str) -> str:
        """キャプション生成のみを行う（analyze_image の利用を推奨）。"""
        _, _, caption = self.analyze_image(image_path)
        return caption
