"""
ImageProcessor のテスト。

EXIF 回転の適用・補正後ファイルの保存・出力先フォルダの自動作成などを検証する。
"""

import os
import pytest
from PIL import Image
from unittest.mock import patch

import image_processor as ip_module


@pytest.fixture
def tmp_processor(tmp_path, monkeypatch):
    """一時ディレクトリを processed/ フォルダとして使う ImageProcessor。"""
    processed_dir = str(tmp_path / "processed")
    monkeypatch.setattr(ip_module, "PROCESSED_DIR", processed_dir)
    from image_processor import ImageProcessor
    return ImageProcessor(), tmp_path, processed_dir


def make_test_image(path: str, size=(100, 200), color=(100, 150, 200)):
    """テスト用のシンプルな JPEG 画像を作成して保存する。"""
    img = Image.new("RGB", size, color=color)
    img.save(path, "JPEG")
    return path


# ──────────────────────────────────────────
# 基本動作
# ──────────────────────────────────────────

class TestBasicCorrection:
    def test_output_file_is_created(self, tmp_processor):
        processor, tmp_path, processed_dir = tmp_processor
        src = make_test_image(str(tmp_path / "test.jpg"))
        result = processor.auto_correct(src)
        assert os.path.exists(result)

    def test_output_is_in_processed_dir(self, tmp_processor):
        processor, tmp_path, processed_dir = tmp_processor
        src = make_test_image(str(tmp_path / "test.jpg"))
        result = processor.auto_correct(src)
        assert result.startswith(processed_dir)

    def test_output_filename_matches_input(self, tmp_processor):
        processor, tmp_path, processed_dir = tmp_processor
        src = make_test_image(str(tmp_path / "photo.jpg"))
        result = processor.auto_correct(src)
        assert os.path.basename(result) == "photo.jpg"

    def test_processed_dir_is_auto_created(self, tmp_processor):
        processor, tmp_path, processed_dir = tmp_processor
        # processed ディレクトリは ImageProcessor() 生成時に作られる
        assert os.path.isdir(processed_dir)

    def test_output_is_readable_image(self, tmp_processor):
        """補正後ファイルが壊れておらず PIL で開けること。"""
        processor, tmp_path, _ = tmp_processor
        src = make_test_image(str(tmp_path / "test.jpg"))
        result = processor.auto_correct(src)
        img = Image.open(result)
        assert img.size[0] > 0


# ──────────────────────────────────────────
# EXIF 回転
# ──────────────────────────────────────────

class TestExifTranspose:
    def test_exif_transpose_is_applied(self, tmp_processor):
        """
        exif_transpose が呼び出されていることを確認する。
        実際の EXIF データを持つ画像の用意が難しいため、
        モックで呼び出し有無を検証する。
        """
        processor, tmp_path, _ = tmp_processor
        src = make_test_image(str(tmp_path / "rotated.jpg"))

        with patch("image_processor.ImageOps.exif_transpose",
                   wraps=ip_module.ImageOps.exif_transpose) as mock_transpose:
            processor.auto_correct(src)
            mock_transpose.assert_called_once()

    def test_vertical_image_stays_vertical(self, tmp_processor):
        """縦長画像（高さ > 幅）が補正後も縦長であること（EXIF なしの場合）。"""
        processor, tmp_path, _ = tmp_processor
        # 100×200 の縦長画像
        src = make_test_image(str(tmp_path / "vertical.jpg"), size=(100, 200))
        result = processor.auto_correct(src)
        img = Image.open(result)
        w, h = img.size
        assert h >= w  # 縦長または正方形


# ──────────────────────────────────────────
# 補正係数の確認
# ──────────────────────────────────────────

class TestCorrectionFactors:
    def test_factors_are_positive(self):
        from image_processor import ImageProcessor
        assert ImageProcessor.BRIGHTNESS_FACTOR > 0
        assert ImageProcessor.CONTRAST_FACTOR > 0
        assert ImageProcessor.SATURATION_FACTOR > 0

    def test_factors_are_reasonable(self):
        """補正係数が過剰でないこと（0.5〜2.0 の範囲）。"""
        from image_processor import ImageProcessor
        for factor in [
            ImageProcessor.BRIGHTNESS_FACTOR,
            ImageProcessor.CONTRAST_FACTOR,
            ImageProcessor.SATURATION_FACTOR,
        ]:
            assert 0.5 <= factor <= 2.0
