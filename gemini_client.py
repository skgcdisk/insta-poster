from google import genai
from PIL import Image


class GeminiClient:
    """
    Gemini API を使って画像の安全チェックとキャプション生成を行うクラス。

    API 呼び出し回数を節約するため、安全チェックとキャプション生成を
    1回のリクエストにまとめて実行する（analyze_image メソッド）。

    プロンプト設計:
        安全チェック部分 → SAFETY_PROMPT（固定・編集不可）
        キャプション指示 → DEFAULT_CAPTION_PROMPT（設定タブから編集可能）
        返答フォーマット → RESPONSE_FORMAT（固定・編集不可）
    """

    # gemini-2.5-flash：2025年時点の最新標準モデル
    MODEL = "gemini-2.5-flash"

    # ── 安全チェック指示（固定・ユーザーが編集できない部分） ──────────────
    # 公序良俗チェックは一定の基準で行う必要があるため変更不可にする。
    _SAFETY_PROMPT = (
        "この画像に公序良俗に反する内容が含まれているか確認してください。\n"
        "（暴力・性的・差別的・危険物・その他不適切なもの）\n\n"
    )

    # ── キャプション指示のデフォルト（ユーザーが設定タブで上書き可能） ────
    DEFAULT_CAPTION_PROMPT = (
        "この画像に合うInstagramの投稿キャプションを日本語で作成してください。\n"
        "絵文字を適度に使い、ハッシュタグを5〜8個含めてください。"
    )

    # ── 返答フォーマット指示（固定・AIの出力を安定させるために変更不可） ──
    _RESPONSE_FORMAT = (
        "\n\n以下の形式だけで答えてください（余分な文章は不要です）：\n"
        "SAFETY: OK\n"
        "CAPTION: （キャプション本文）\n\n"
        "もし不適切な内容が含まれていれば：\n"
        "SAFETY: NG:理由を一言で\n"
        "CAPTION: なし"
    )

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _build_prompt(self, custom_caption_prompt: str | None) -> str:
        """
        安全チェック（固定）＋ キャプション指示（カスタムまたはデフォルト）＋
        フォーマット指示（固定）を結合して最終プロンプトを組み立てる。
        """
        caption_instruction = custom_caption_prompt or self.DEFAULT_CAPTION_PROMPT
        return self._SAFETY_PROMPT + caption_instruction + self._RESPONSE_FORMAT

    def analyze_image(
        self, image_path: str, custom_caption_prompt: str | None = None
    ) -> tuple[bool, str, str]:
        """
        安全チェックとキャプション生成を1回のAPI呼び出しでまとめて実行する。
        API 呼び出し回数を半減できるため、無料枠の節約になる。

        Args:
            image_path:            解析する画像のパス
            custom_caption_prompt: 設定タブで編集されたキャプション指示文。
                                   None または空文字の場合は DEFAULT_CAPTION_PROMPT を使用する。
                                   安全チェック部分は常に固定プロンプトが使われる。

        Returns:
            (is_safe, ng_reason, caption)
            - is_safe  : True なら安全、False なら NG
            - ng_reason: NG の場合の理由（安全なら空文字）
            - caption  : 生成されたキャプション（NG なら空文字）
        """
        prompt = self._build_prompt(custom_caption_prompt)
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

        # CAPTION: 以降は複数行にまたがる場合があるため、
        # CAPTION: 行を見つけたらそれ以降の全行をキャプションとして結合する。
        lines = text.splitlines()
        caption_start = None
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("SAFETY:"):
                safety_val = line[len("SAFETY:"):].strip()
                if safety_val.upper().startswith("NG"):
                    is_safe = False
                    ng_reason = safety_val.split(":", 1)[-1].strip() if ":" in safety_val else safety_val
            elif line.startswith("CAPTION:"):
                caption_val = line[len("CAPTION:"):].strip()
                if caption_val == "なし":
                    caption_start = None
                else:
                    caption_start = i
                    caption = caption_val

        # CAPTION: 行以降に続きがあれば結合する
        if caption_start is not None and caption_start + 1 < len(lines):
            rest = "\n".join(l.strip() for l in lines[caption_start + 1:]).strip()
            if rest:
                caption = (caption + "\n" + rest).strip()

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
