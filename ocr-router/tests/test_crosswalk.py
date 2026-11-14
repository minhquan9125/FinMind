"""Unit tests for CrosswalkRegistry and metric ID mapping."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crosswalk import CrosswalkRegistry  # noqa: E402

CATALOG_PATH = ROOT / "templates" / "Thông tin chung.json"


class CrosswalkRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CrosswalkRegistry()

    def test_tt200_core_metrics_lookup(self) -> None:
        # Total Assets in TT200 is code 270
        entry = self.registry.lookup("TT200_NONBANK", "balance_sheet", "270")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.metric_id, "common.total_assets")
        self.assertEqual(entry.sign_convention, "positive_magnitude")

        # Cash & Cash Equivalents is code 110
        entry = self.registry.lookup("TT200_NONBANK", "balance_sheet", "110")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.metric_id, "common.cash_equivalents")

        # Net Revenue in TT200 is code 10
        entry = self.registry.lookup("TT200_NONBANK", "income_statement", "10")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.metric_id, "common.net_revenue")

        # Net Profit After Tax in TT200 is code 60
        entry = self.registry.lookup("TT200_NONBANK", "income_statement", "60")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.metric_id, "common.profit_after_tax")
        self.assertEqual(entry.sign_convention, "signed")

    def test_tt99_core_metrics_lookup(self) -> None:
        # Total Assets in TT99 is code 280 (not 270!)
        entry = self.registry.lookup("TT99_2025", "balance_sheet", "280")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.metric_id, "common.total_assets")

        # In TT99, code 270 is "Tài sản dài hạn khác"
        entry_270 = self.registry.lookup("TT99_2025", "balance_sheet", "270")
        self.assertIsNotNone(entry_270)
        assert entry_270 is not None
        self.assertEqual(entry_270.metric_id, "common.other_noncurrent_assets_total")

    def test_cross_standard_divergence_is_properly_isolated(self) -> None:
        tt200_270 = self.registry.lookup("TT200_NONBANK", "balance_sheet", "270")
        tt99_270 = self.registry.lookup("TT99_2025", "balance_sheet", "270")
        self.assertIsNotNone(tt200_270)
        self.assertIsNotNone(tt99_270)
        assert tt200_270 is not None and tt99_270 is not None
        self.assertEqual(tt200_270.metric_id, "common.total_assets")
        self.assertEqual(tt99_270.metric_id, "common.other_noncurrent_assets_total")
        self.assertNotEqual(tt200_270.metric_id, tt99_270.metric_id)

    def test_all_crosswalk_entries_exist_in_finmind_catalog(self) -> None:
        if CATALOG_PATH.is_file():
            errors = self.registry.validate_against_catalog(CATALOG_PATH)
            self.assertEqual(errors, [], f"Crosswalk contains invalid metric_ids: {errors}")

    def test_unknown_code_or_standard_returns_none(self) -> None:
        self.assertIsNone(self.registry.lookup("TT200_NONBANK", "balance_sheet", "999"))
        self.assertIsNone(self.registry.lookup("UNKNOWN_STANDARD", "balance_sheet", "100"))
        self.assertIsNone(self.registry.lookup("TT200_NONBANK", "balance_sheet", None))


if __name__ == "__main__":
    unittest.main()
