"""Regression checks for rebuilding text and confidence from Tesseract TSV."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import tesseract as tess_module


class TesseractTsvTest(unittest.TestCase):
    def test_lines_paragraphs_and_confidence(self) -> None:
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
        rows = [
            "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t90\tA",
            "5\t1\t1\t1\t1\t2\t2\t0\t1\t1\t50\tB",
            "5\t1\t1\t1\t2\t1\t0\t2\t1\t1\t75\tC",
            "5\t1\t1\t2\t1\t1\t0\t4\t1\t1\t100\tD",
            "5\t1\t1\t2\t1\t2\t2\t4\t1\t1\t-1\t",
        ]
        result = subprocess.CompletedProcess(["tesseract"], 0, header + "\n" + "\n".join(rows), "")
        with patch.object(tess_module, "required_command", return_value="tesseract"), \
             patch.object(tess_module, "run", return_value=result):
            value = tess_module.tesseract(Path("page.png"), {})
        self.assertEqual(value["text"], "A B\nC\n\nD")
        self.assertEqual(value["chars"], 4)
        self.assertEqual(value["words"], 4)
        self.assertEqual(value["meanConf"], 79)
        self.assertEqual(value["lowConfRatio"], 0.25)


if __name__ == "__main__":
    unittest.main()
