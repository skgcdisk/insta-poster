import os
from PIL import Image, ImageEnhance, ImageOps

# 補正後の画像を保存するフォルダ（アプリ起動ディレクトリ直下に自動作成）
PROCESSED_DIR = "processed"


class ImageProcessor:
    """
    Pillow を使って画像の明るさ・コントラスト・彩度を自動補正するクラス。
    補正後の画像は processed/ フォルダに保存される。
    """

    # 補正係数（1.0 = 変化なし。値を上げると強く補正される）
    BRIGHTNESS_FACTOR = 1.10   # 明るさ：10% アップ
    CONTRAST_FACTOR   = 1.20   # コントラスト：20% アップ
    SATURATION_FACTOR = 1.15   # 彩度：15% アップ

    def __init__(self):
        os.makedirs(PROCESSED_DIR, exist_ok=True)

    def auto_correct(self, original_path: str) -> str:
        """
        指定画像を補正して processed/ フォルダに保存する。

        Args:
            original_path: 元画像の絶対パスまたは相対パス
        Returns:
            補正後の画像ファイルパス
        """
        img = Image.open(original_path)

        # スマホで撮影した縦長写真などは EXIF に回転情報が記録されている。
        # exif_transpose() を適用しないと Pillow が向きを無視して保存し、
        # 開いたときに90度回転して見える問題が起きる。
        img = ImageOps.exif_transpose(img)

        # 明るさ → コントラスト → 彩度 の順に補正する
        img = ImageEnhance.Brightness(img).enhance(self.BRIGHTNESS_FACTOR)
        img = ImageEnhance.Contrast(img).enhance(self.CONTRAST_FACTOR)
        img = ImageEnhance.Color(img).enhance(self.SATURATION_FACTOR)

        # 元ファイル名のまま processed/ に保存（上書き可）
        filename = os.path.basename(original_path)
        corrected_path = os.path.join(PROCESSED_DIR, filename)
        img.save(corrected_path, quality=95)

        return corrected_path
