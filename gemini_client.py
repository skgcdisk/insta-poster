import google.generativeai as genai
from PIL import Image


class GeminiClient:
    """
    Gemini API を使って画像の安全チェックとキャプション生成を行うクラス。
    2つの機能を1クラスにまとめているのは、どちらも同じモデル・同じAPIキーを使うため。
    """

    MODEL = "gemini-1.5-flash"

    # 安全チェック用プロンプト
    # "OK" または "NG:理由" という短い形式で返答させることで、パースを簡単にしている
    SAFETY_PROMPT = (
        "この画像を確認してください。"
        "公序良俗に反する内容（暴力・性的・差別的・危険物・その他不適切なもの）が含まれていますか？"
        "含まれていれば「NG:理由を一言で」、問題なければ「OK」とだけ答えてください。"
    )

    # キャプション生成用プロンプト
    CAPTION_PROMPT = (
        "この画像に合うInstagramの投稿キャプションを日本語で作成してください。"
        "絵文字を適度に使い、ハッシュタグを5〜8個含めてください。"
        "キャプション本文のみ出力し、説明や前置きは不要です。"
    )

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.MODEL)

    def check_safety(self, image_path: str) -> tuple[bool, str]:
        """
        画像が投稿に適切かどうかを Gemini で判定する。

        Returns:
            (is_safe, reason): is_safe=True なら安全、False なら reason に理由が入る
        """
        img = Image.open(image_path)
        response = self.model.generate_content([self.SAFETY_PROMPT, img])
        text = response.text.strip()

        if text.upper().startswith("OK"):
            return True, ""

        # "NG:理由" の形式から理由を取り出す
        reason = text.split(":", 1)[-1].strip() if ":" in text else text
        return False, reason

    def generate_caption(self, image_path: str) -> str:
        """
        画像から Instagram 用キャプションを生成する。

        Returns:
            キャプション文字列（ハッシュタグ含む）
        """
        img = Image.open(image_path)
        response = self.model.generate_content([self.CAPTION_PROMPT, img])
        return response.text.strip()
