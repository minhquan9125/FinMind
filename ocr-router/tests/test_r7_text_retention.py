"""Keep visible text that a structured table crop did not represent."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from buildDocumentIr import (  # noqa: E402
    _preserve_unrepresented_source_words,
    _represented_words,
    _tokens,
)


class _Page:
    page_number = 1
    height = 100

    def extract_words(self, **_kwargs: object) -> list[dict]:
        return [
            {"text": text, "x0": 10 + index * 20, "x1": 20 + index * 20,
             "top": 10, "bottom": 20, "size": 12}
            for index, text in enumerate(("Dòng", "tổng", "Chi", "tiết"))
        ]


class TextRetentionTests(unittest.TestCase):
    def test_cropped_table_words_remain_in_ir_once(self) -> None:
        page = _Page()
        blocks = [{"id": "p1-b1", "type": "paragraph", "text": "Dòng tổng",
                   "bbox": [10, 10, 40, 20]}]
        _preserve_unrepresented_source_words(page, blocks)
        self.assertEqual([block["text"] for block in blocks[1:]], ["Chi", "tiết"])
        self.assertTrue(all(block["bbox"] for block in blocks))
        source = Counter(_tokens(" ".join(word["text"] for word in page.extract_words())))
        self.assertEqual(source - _represented_words(blocks), Counter())


if __name__ == "__main__":
    unittest.main()
