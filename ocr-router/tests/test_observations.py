"""Unit and integration tests for financial observation generator."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crosswalk import CrosswalkRegistry  # noqa: E402
from financialContent import (  # noqa: E402
    _accounting_template_profile,
    _load_accounting_template,
    _select_accounting_template_path,
    evaluate_accounting,
)
from observations import (  # noqa: E402
    _detect_unit_multiplier,
    build_financial_observations,
)

FPT_FIXTURE = ROOT / "tests" / "fixtures" / "fpt-2024-reviewed-financial-tables.json"
SAFOCO_FIXTURE = ROOT / "tests" / "fixtures" / "safoco_q1_2026_tt99_ocr.json"


class FinancialObservationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CrosswalkRegistry()

    def test_unit_multiplier_detection(self) -> None:
        self.assertEqual(_detect_unit_multiplier("Đơn vị: VNĐ"), (1, "VND"))
        self.assertEqual(_detect_unit_multiplier("Đơn vị tính: Triệu đồng"), (1_000_000, "VND"))
        self.assertEqual(_detect_unit_multiplier("Đơn vị: Tỷ VNĐ"), (1_000_000_000, "VND"))
        self.assertEqual(_detect_unit_multiplier("Đơn vị: nghìn đồng"), (1_000, "VND"))
        self.assertEqual(_detect_unit_multiplier("Unit: USD"), (1, "USD"))
        self.assertEqual(_detect_unit_multiplier(None), (1, "VND"))

    def test_synthetic_observations_and_verification_state_machine(self) -> None:
        # Construct mock document with balance sheet:
        # Code 100 (Total Current Assets) = Code 110 (Cash) + Code 120 (Investments)
        document = [{
            "page": 1,
            "page_class": "balance_sheet",
            "blocks": [
                {"type": "form_code", "text": "Mẫu số B01-DN"},
                {"type": "heading", "text": "BẢNG CÂN ĐỐI KẾ TOÁN"},
                {
                    "type": "table",
                    "id": "p1-t1",
                    "unit_text": "Đơn vị: VNĐ",
                    "columns": [{"key": "c1", "header_lines": ["31/12/2024"]}],
                    "rows": [
                        {
                            "id": "r1", "code": "100", "label_raw": "TÀI SẢN NGẮN HẠN",
                            "cells": {"c1": {"raw": "300.000", "bbox": [10, 10, 50, 20]}}
                        },
                        {
                            "id": "r2", "code": "110", "label_raw": "Tiền",
                            "cells": {"c1": {"raw": "100.000", "bbox": [10, 30, 50, 40]}}
                        },
                        {
                            "id": "r3", "code": "120", "label_raw": "Đầu tư",
                            "cells": {"c1": {"raw": "200.000", "bbox": [10, 50, 50, 60]}}
                        },
                        {
                            "id": "r4", "code": "150", "label_raw": "Tài sản khác",
                            "cells": {"c1": {"raw": "bad_num", "bbox": [10, 70, 50, 80]}}
                        },
                    ]
                }
            ]
        }]

        # Check where equation passed
        checks = [{
            "name": "balance_sheet:100",
            "year": "2024",
            "period_end": "2024-12-31",
            "period_type": "instant",
            "period_role": "current",
            "passed": True,
            "result_code": "100",
            "actual": "300000",
            "expected": "300000",
            "pdf_pages": [1],
            "source": "template_lines"
        }]

        template_data = {
            "template_lines": [
                {"statement": "balance_sheet", "parent": "100", "code": "110", "sign": 1, "is_memo": False},
                {"statement": "balance_sheet", "parent": "100", "code": "120", "sign": 1, "is_memo": False},
            ]
        }

        observations, summary = build_financial_observations(
            documents=document,
            accounting_standard="TT200_NONBANK",
            checks=checks,
            skipped_checks=[],
            template_data=template_data,
            crosswalk=self.registry,
        )

        obs_by_metric = {o["metric_id"]: o for o in observations}
        self.assertIn("common.current_assets", obs_by_metric)
        self.assertEqual(obs_by_metric["common.current_assets"]["numeric_value"], 300000)
        self.assertEqual(obs_by_metric["common.current_assets"]["verification_status"], "arithmetic_verified")

        self.assertIn("common.cash_equivalents", obs_by_metric)
        self.assertEqual(obs_by_metric["common.cash_equivalents"]["numeric_value"], 100000)
        self.assertEqual(obs_by_metric["common.cash_equivalents"]["verification_status"], "arithmetic_verified")

        # Code 150 had bad_num -> needs_review
        self.assertIn("common.other_current_assets_total", obs_by_metric)
        self.assertIsNone(obs_by_metric["common.other_current_assets_total"]["numeric_value"])
        self.assertEqual(obs_by_metric["common.other_current_assets_total"]["verification_status"], "needs_review")

        self.assertEqual(summary["total_observations"], 4)
        self.assertEqual(summary["verified_observations"], 3)
        self.assertEqual(summary["needs_review_observations"], 1)

    def test_sign_conventions_normalization(self) -> None:
        document = [{
            "page": 2,
            "page_class": "income_statement",
            "blocks": [
                {"type": "heading", "text": "BÁO CÁO KẾT QUẢ KINH DOANH"},
                {
                    "type": "table",
                    "id": "p2-t1",
                    "unit_text": "Đơn vị: VNĐ",
                    "columns": [{"key": "c1", "header_lines": ["Năm 2024"]}],
                    "rows": [
                        {
                            "id": "r1", "code": "11", "label_raw": "Giá vốn hàng bán",
                            # In BCTC, cost is printed in parentheses (negative)
                            "cells": {"c1": {"raw": "(45.000.000)", "bbox": None}}
                        },
                        {
                            "id": "r2", "code": "60", "label_raw": "Lợi nhuận sau thuế",
                            # In BCTC, a loss is printed in parentheses (negative)
                            "cells": {"c1": {"raw": "(5.000.000)", "bbox": None}}
                        },
                    ]
                }
            ]
        }]

        observations, _ = build_financial_observations(
            documents=document,
            accounting_standard="TT200_NONBANK",
            checks=[],
            skipped_checks=[],
            crosswalk=self.registry,
        )

        obs_by_metric = {o["metric_id"]: o for o in observations}

        # Cost of sales has positive_magnitude convention -> normalized to positive 45,000,000
        cost_obs = obs_by_metric["common.cost_of_sales"]
        self.assertEqual(cost_obs["sign_convention"], "positive_magnitude")
        self.assertEqual(cost_obs["numeric_value"], 45000000)
        self.assertEqual(cost_obs["raw"], "(45.000.000)")

        # Profit after tax has signed convention -> preserved as negative -5,000,000
        profit_obs = obs_by_metric["common.profit_after_tax"]
        self.assertEqual(profit_obs["sign_convention"], "signed")
        self.assertEqual(profit_obs["numeric_value"], -5000000)
        self.assertEqual(profit_obs["raw"], "(5.000.000)")

    def test_real_fpt_2024_reviewed_fixture_generates_verified_observations(self) -> None:
        if not FPT_FIXTURE.is_file():
            self.skipTest("FPT fixture file not found")

        fixture_data = json.loads(FPT_FIXTURE.read_text(encoding="utf-8"))
        documents = [
            page for group in fixture_data.get("tables", [])
            if group.get("table_id") != "company_information"
            for page in group.get("pages", [])
        ]
        if not documents:
            self.skipTest("No documents in FPT fixture")

        for page in documents:
            if page.get("page_class") == "balance_sheet":
                page["blocks"].insert(0, {"type": "heading", "text": "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT"})
                break

        profile = _accounting_template_profile(documents)
        self.assertEqual(profile, "TT200_NONBANK")

        template_path = _select_accounting_template_path(documents)
        assert template_path is not None
        template_data = _load_accounting_template(template_path)

        checks, skipped, failed_pages, template_id = evaluate_accounting(documents, template_path)
        self.assertEqual(failed_pages, set())

        observations, summary = build_financial_observations(
            documents=documents,
            accounting_standard=profile,
            checks=checks,
            skipped_checks=skipped,
            template_data=template_data,
            crosswalk=self.registry,
        )

        # Ensure high coverage and verification rate on real FPT report
        self.assertGreater(summary["total_observations"], 100)
        self.assertGreater(summary["verified_observations"], 90)
        self.assertEqual(summary["failed_observations"], 0)

        # Check presence of fundamental metrics
        obs_metric_ids = {o["metric_id"] for o in observations}
        self.assertIn("common.total_assets", obs_metric_ids)
        self.assertIn("common.total_liabilities", obs_metric_ids)
        self.assertIn("common.equity", obs_metric_ids)
        self.assertIn("common.net_revenue", obs_metric_ids)
        self.assertIn("common.profit_after_tax", obs_metric_ids)
        self.assertIn("common.operating_cash_flow", obs_metric_ids)

        # Verify Total Assets value matches FPT 2024 balance sheet (~72 trillion VND)
        total_assets_obs = [
            o for o in observations
            if o["metric_id"] == "common.total_assets" and o["period_end"] == "2024-12-31"
        ]
        self.assertEqual(len(total_assets_obs), 1)
        self.assertEqual(total_assets_obs[0]["verification_status"], "arithmetic_verified")
        self.assertEqual(total_assets_obs[0]["numeric_value"], 71999995678620)

    def test_real_safoco_tt99_fixture_maps_code_280_to_total_assets(self) -> None:
        if not SAFOCO_FIXTURE.is_file():
            self.skipTest("Safoco fixture file not found")

        from buildDocumentIr import _ai_ir_blocks, _record_text_for_classification
        from financialContent import financial_page_class

        fixture = json.loads(SAFOCO_FIXTURE.read_text(encoding="utf-8"))
        documents = []
        for page in fixture["pages"]:
            text = _record_text_for_classification({"text": "", "aiBlocks": page["aiBlocks"]})
            kind = financial_page_class(page["page"], None, fixture["source_pdf_sha256"], text)
            blocks, _, _ = _ai_ir_blocks(page["aiBlocks"], [], page["page"], 1000, 1000, "gemini", flag_unverified=True)
            documents.append({"page": page["page"], "page_class": kind, "blocks": blocks})

        profile = _accounting_template_profile(documents)
        self.assertEqual(profile, "TT99_2025")

        template_path = _select_accounting_template_path(documents)
        assert template_path is not None
        template_data = _load_accounting_template(template_path)

        checks, skipped, failed_pages, template_id = evaluate_accounting(documents, template_path)
        observations, summary = build_financial_observations(
            documents=documents,
            accounting_standard=profile,
            checks=checks,
            skipped_checks=skipped,
            template_data=template_data,
            crosswalk=self.registry,
        )

        self.assertGreaterEqual(summary["total_observations"], 50)
        self.assertEqual(summary["mapped_metrics_count"], 29)

        # Confirm code 280 mapped to common.total_assets (not other noncurrent assets)
        total_assets_obs = [o for o in observations if o["code"] == "280"]
        self.assertTrue(len(total_assets_obs) >= 1)
        self.assertEqual(total_assets_obs[0]["metric_id"], "common.total_assets")
        self.assertEqual(total_assets_obs[0]["unit_multiplier"], 1)  # VND, not billion
        self.assertEqual(total_assets_obs[0]["numeric_value"], 258972002748)


if __name__ == "__main__":
    unittest.main()
