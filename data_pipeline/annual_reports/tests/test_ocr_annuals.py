"""Regression checks for annual-report source paths and text-layer quality."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import OCR_annuals as ocr


class AnnualOcrInputTests(unittest.TestCase):
    def test_manifest_file_resolves_to_local_pdf_mirror(self):
        with tempfile.TemporaryDirectory(dir=ocr.ROOT / "tmp") as directory:
            root = Path(directory)
            source = root / "data/references/vietstock/annual_reports"
            mirror = source / "files_pdf/CMG/2024/report.pdf"
            mirror.parent.mkdir(parents=True)
            mirror.write_bytes(b"pdf fixture")
            with patch.object(ocr, "ROOT", root), patch.object(ocr, "SOURCE_ROOT", source):
                self.assertEqual(
                    ocr.safe_repo_file("data/references/vietstock/annual_reports/files/CMG/2024/report.pdf"),
                    mirror,
                )
                with self.assertRaises(ValueError):
                    ocr.safe_repo_file("../outside.pdf")

    def test_garbled_vietnamese_text_layer_requires_ocr(self):
        self.assertFalse(ocr.native_text_usable("BÉO CÉO TH¶òNG NI£N 2024"))
        self.assertFalse(ocr.native_text_usable("MÙc lÙc\n" + "CHƯƠNG 1 " * 8))
        self.assertTrue(ocr.native_text_usable("BÁO CÁO THƯỜNG NIÊN 2024 " * 4))


if __name__ == "__main__":
    unittest.main()
