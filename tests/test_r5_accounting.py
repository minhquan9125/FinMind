"""R5 regressions for lower-level statement equations, coverage and soft checks."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from financialContent import (  # noqa: E402
    _accounting_soft_checks,
    _load_accounting_template,
    evaluate_accounting,
)


def _page(page: int, kind: str, title: str, rows: list[tuple[str, str]]) -> dict:
    return {
        "page": page,
        "page_class": kind,
        "page_size": {"width": 1920, "height": 1080, "unit": "pt"},
        "blocks": [
            {"type": "heading", "text": title},
            {"type": "table", "id": f"p{page}-t1",
             "columns": [{"key": "c1", "header_lines": ["2024"], "bbox": None}],
             "rows": [{"id": f"r{index}", "code": code, "label_raw": code,
                       "cells": {"c1": {"raw": value, "bbox": None,
                                             "needs_review": False}}}
                      for index, (code, value) in enumerate(rows, 1)]},
        ],
    }


class R5AccountingTests(unittest.TestCase):
    def test_template_has_detailed_subtotals_and_memo_rows(self) -> None:
        template = _load_accounting_template()
        lines = {(line["statement"], line["parent"], line["code"]): line
                 for line in template["template_lines"]}
        for parent, child in (("110", "111"), ("120", "123"), ("130", "131"),
                              ("140", "141"), ("220", "221"), ("221", "222"),
                              ("410", "421"), ("421", "421a")):
            self.assertIn(("balance_sheet", parent, child), lines)
        self.assertTrue(lines[("balance_sheet", "411", "411a")]["is_memo"])
        self.assertTrue(lines[("income_statement", "22", "23")]["is_memo"])
        self.assertIn("income_statement:60_attribution",
                      {rule["name"] for rule in template["arithmetic_rules"]})

    def test_reported_children_are_summed_and_absent_optional_rows_are_not_zero_filled(self) -> None:
        document = [_page(1, "balance_sheet", "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT",
                          [("120", "100"), ("123", "100")])]
        checks, skipped, _failed_pages, template_id = evaluate_accounting(document)
        self.assertEqual(template_id, "vn_nonbank_b01_b02_b03_v1")
        result = next(item for item in checks if item["name"] == "balance_sheet:120")
        self.assertTrue(result["passed"])
        self.assertEqual(result["not_reported_optional_codes"], ["121", "122"])
        self.assertFalse(any(item["name"] == "balance_sheet:120" for item in skipped))

    def test_income_tax_total_and_attribution_are_separate_equations(self) -> None:
        document = [
            _page(1, "balance_sheet", "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT", []),
            _page(2, "income_statement", "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
                  [("50", "200"), ("51", "100"), ("52", "10"),
                   ("60", "90"), ("61", "70"), ("62", "20")]),
        ]
        checks, _skipped, _failed_pages, _template_id = evaluate_accounting(document)
        by_name = {item["name"]: item for item in checks}
        self.assertTrue(by_name["income_statement:60"]["passed"])
        self.assertTrue(by_name["income_statement:60_attribution"]["passed"])

    def test_eps_approximation_uses_labeled_average_shares_and_no_dilution_note(self) -> None:
        income = _page(2, "income_statement",
                       "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
                       [("61", "9.000"), ("70", "9"), ("71", "9")])
        note = {"page": 3, "page_class": "notes", "blocks": [
            {"type": "paragraph", "text": "Bình quân số cổ phiếu phổ thông đang lưu hành (cổ phiếu)",
             "bbox": [100.0, 100.0, 300.0, 140.0]},
            {"type": "paragraph", "text": "1.000", "bbox": [400.0, 100.0, 450.0, 120.0]},
            {"type": "paragraph", "text": "Lãi suy giảm trên cổ phiếu bằng lãi cơ bản trên cổ phiếu. Công ty không có cổ phiếu phổ thông tiềm tàng có tác động suy giảm.",
             "bbox": [100.0, 200.0, 800.0, 240.0]},
        ]}
        checks = _accounting_soft_checks([income, note])
        self.assertEqual([item["status"] for item in checks], ["within_tolerance", "pass"])


if __name__ == "__main__":
    unittest.main()
