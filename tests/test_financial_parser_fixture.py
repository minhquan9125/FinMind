"""Regression check for the general BCTC parser on the reviewed FPT sample.

This fixture was produced with pdfplumber; it is not an independent human gold set.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from financialContent import _coded_statement_table  # noqa: E402


class FinancialParserFixtureTest(unittest.TestCase):
    def test_278_cells_match_reviewed_fixture(self) -> None:
        pdf_path = ROOT / "FPT_2024_498332 (1).pdf"
        fixture_path = ROOT / "tests" / "fixtures" / "fpt-2024-reviewed-financial-tables.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        kinds = {**{page: "balance_sheet" for page in range(148, 153)},
                 153: "income_statement", 154: "income_statement",
                 155: "cash_flow", 156: "cash_flow"}
        expected = {
            page["page"]: page["blocks"][0]
            for group in fixture["tables"] if group["table_id"] != "company_information"
            for page in group["pages"]
        }

        def cells(table: dict) -> dict[tuple[str, str], str]:
            return {(row["code"], column): cell["raw"]
                    for row in table["rows"] if row["code"]
                    for column, cell in row["cells"].items()}

        self.assertEqual(set(expected), set(kinds))
        total = 0
        with pdfplumber.open(pdf_path) as pdf:
            for number, kind in kinds.items():
                with self.subTest(page=number):
                    parsed, _ = _coded_statement_table(pdf.pages[number - 1], kind)
                    reference = cells(expected[number])
                    self.assertEqual(cells(parsed), reference)
                    total += len(reference)
        self.assertEqual(total, 278)


if __name__ == "__main__":
    unittest.main()
