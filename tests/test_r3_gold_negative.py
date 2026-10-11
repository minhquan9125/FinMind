"""An OCR value placed in the wrong year must fail keyed gold evaluation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluateDocumentIr import _spreadsheet_gold_result  # noqa: E402


class R3NegativeGoldTest(unittest.TestCase):
    def test_swapping_year_columns_lowers_agreement(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as name:
            root = Path(name)
            table_dir = root / "table"
            table_dir.mkdir()
            page_path = table_dir / "p-001.ir.json"
            page = {
                "page_class": "income_statement",
                "blocks": [
                    {"type": "heading", "text": "Ngày 31 tháng 12 năm 2024"},
                    {"type": "table", "logical_table_id": "income_statement",
                     "columns": [{"key": "c1", "header_lines": ["2024"]},
                                 {"key": "c2", "header_lines": ["2023"]}],
                     "rows": [{"code": "10", "cells": {
                         "c1": {"raw": "100"}, "c2": {"raw": "80"}}}]},
                ],
            }
            index = {"structured_table_ranges": [{"start": 1, "end": 1}],
                     "page_index": [{"pdf_page": 1, "printed_page": 1}],
                     "document_sha256": "example"}
            gold_path = root / "gold.csv"
            with gold_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "statement", "code", "period_end", "period_type",
                    "value_raw", "pdf_page", "transcriber", "review_status"])
                writer.writeheader()
                writer.writerow({"statement": "income_statement", "code": "10",
                                 "period_end": "2024-12-31", "period_type": "duration",
                                 "value_raw": "100", "pdf_page": "1",
                                 "transcriber": "reviewer_a",
                                 "review_status": "self_checked"})
            page_path.write_text(json.dumps(page), encoding="utf-8")
            baseline = _spreadsheet_gold_result(table_dir, index, gold_path)
            self.assertEqual(baseline["matched"], 1)
            self.assertEqual(baseline["review_method"], "self_checked")
            self.assertIsNone(baseline["gold_accuracy"])
            page["blocks"][1]["rows"][0]["cells"] = {
                "c1": {"raw": "80"}, "c2": {"raw": "100"}}
            page_path.write_text(json.dumps(page), encoding="utf-8")
            corrupted = _spreadsheet_gold_result(table_dir, index, gold_path)
            self.assertEqual(corrupted["matched"], 0)
            self.assertEqual(corrupted["cells_wrong_value"], 1)


if __name__ == "__main__":
    unittest.main()
