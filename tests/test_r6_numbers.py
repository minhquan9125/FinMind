"""Reject malformed OCR amounts before they enter financial equations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from financialContent import (  # noqa: E402
    evaluate_accounting,
    flag_bad_financial_cells,
    parse_money,
)


class R6NumberFormatTests(unittest.TestCase):
    def test_grouping_and_parentheses(self) -> None:
        self.assertEqual(parse_money("(16.932.187.108)"),
                         (Decimal("-16932187108"), None))
        self.assertEqual(parse_money("3,405.535.984"),
                         (Decimal("3405535984"), None))
        self.assertEqual(parse_money("4.944"), (Decimal("4944"), None))
        self.assertEqual(parse_money("-"), (Decimal(0), "PRINTED_DASH"))
        for raw in ("3.451.002.5587", "(280.683.727.283", "1/233.277.527"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_money(raw), (None, "BAD_NUMBER_FORMAT"))

    def test_bad_cell_is_kept_for_review_and_excluded_from_checks(self) -> None:
        document = {"page": 1, "page_class": "balance_sheet", "blocks": [
            {"type": "heading", "text": "BẢNG CÂN ĐỐI KẾ TOÁN"},
            {"type": "table", "id": "p1-t1",
             "columns": [{"key": "c1", "header_lines": ["2024"]}],
             "rows": [{"id": "r1", "code": "100", "label_raw": "Tài sản ngắn hạn",
                       "cells": {"c1": {"raw": "3.451.002.5587", "bbox": None}}}]},
        ]}
        flag_bad_financial_cells(document)
        cell = document["blocks"][1]["rows"][0]["cells"]["c1"]
        self.assertEqual(cell["raw"], "3.451.002.5587")
        self.assertTrue(cell["needs_review"])
        self.assertEqual(cell["review_reason"], "BAD_NUMBER_FORMAT")
        checks, skipped, _, _ = evaluate_accounting([document])
        self.assertEqual(checks, [])
        self.assertTrue(any(item.get("reason") == "BAD_NUMBER_FORMAT"
                            for item in skipped))


if __name__ == "__main__":
    unittest.main()
