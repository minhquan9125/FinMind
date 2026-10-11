"""Regression tests for OCR financial tables and the real TT49 bank layout.

The Techcombank fixture is verbatim pdfplumber word output from the cited PDF
page, stored with its SHA-256 so the bank parser test does not need the full PDF.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from buildDocumentIr import (_ai_ir_blocks, _record_text_for_classification, _text_blocks,
                             _recover_missing_tesseract_cells,
                             _tess_statement_table)  # noqa: E402
from financialContent import (  # noqa: E402
    _accounting_period,
    _accounting_template_profile,
    _select_accounting_template_path,
    evaluate_accounting,
    financial_page_class,
    statement_tables,
)
from validate_ir import SCHEMA, validate_page  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "techcombank_2025_p149.json"
FPT_INCOME_FIXTURE = ROOT / "tests" / "fixtures" / "fpt_income_statement_p7_psm4.json"
TT99_OCR_FIXTURE = ROOT / "tests" / "fixtures" / "safoco_q1_2026_tt99_ocr.json"


class _Crop:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _FixturePage:
    def __init__(self, fixture: dict) -> None:
        self.page_number = fixture["pdf_page"]
        self.width = fixture["width"]
        self.height = fixture["height"]
        self.words = fixture["word_items"]
        self.panel_header_text = fixture["panel_header_text"]

    def extract_words(self, **_kwargs: object) -> list[dict]:
        return self.words

    def crop(self, box: tuple[float, float, float, float]) -> _Crop:
        left, _top, right, _bottom = box
        side = "left" if (left + right) / 2 < self.width / 2 else "right"
        return _Crop(self.panel_header_text[side])


class R4OCRFinancialRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_tt99_scan_title_with_ocr_bang_typo_is_balance_sheet(self) -> None:
        text = ("CÔNG TY CỔ PHẦN SAFOCO\n"
                "Mẫu số B01-DN (Thông tư 99/2025/TT-BTC)\n"
                "BẢNG CÁO TÌNH HÌNH TÀI CHÍNH\n"
                "Số cuối kỳ 31/03/2026  Số đầu kỳ 01/01/2026")
        self.assertEqual(financial_page_class(5, None, "scan", text), "balance_sheet")

    def test_ai_metadata_columns_do_not_shift_four_period_columns(self) -> None:
        headers = ["Chỉ tiêu", "Mã số", "Thuyết minh", "Quý này năm nay",
                   "Quý này năm trước", "Lũy kế năm nay", "Lũy kế năm trước"]
        block = {"type": "table", "text": None, "title": "Kết quả kinh doanh",
                 "unit_text": None, "box_2d": None,
                 "columns": [{"key": f"c{i + 1}", "header_lines": [header],
                              "box_2d": None} for i, header in enumerate(headers)],
                 "rows": [{"code": "01", "label_raw": "Doanh thu",
                           "note": None, "box_2d": None,
                           "cells": [{"column_key": f"c{i + 1}", "raw": raw,
                                      "box_2d": None}
                                     for i, raw in enumerate(("Doanh thu", "01", "6.1",
                                                              "100", "80", "400", "320"))]}]}
        blocks, _votes, _disagreements = _ai_ir_blocks(
            [block], [], 7, 1000, 1000, "gemini", flag_unverified=True)
        table = blocks[0]
        self.assertEqual([column["key"] for column in table["columns"]],
                         ["c1", "c2", "c3", "c4"])
        self.assertEqual(table["rows"][0]["note"], "6.1")
        self.assertEqual([cell["raw"] for cell in table["rows"][0]["cells"].values()],
                         ["100", "80", "400", "320"])

    def test_ai_cash_flow_code_and_note_columns_are_metadata(self) -> None:
        block = {"type": "table", "text": None, "title": None, "unit_text": None,
                 "box_2d": None,
                 "columns": [{"key": f"c{i + 1}", "header_lines": [header],
                              "box_2d": None}
                             for i, header in enumerate(("Mã chỉ tiêu", "Thuyết minh",
                                                         "Quý 1/2026", "Quý 1/2025"))],
                 "rows": [{"code": "01", "label_raw": "Thu tiền", "note": None,
                           "box_2d": None,
                           "cells": [{"column_key": f"c{i + 1}", "raw": raw,
                                      "box_2d": None}
                                     for i, raw in enumerate(("01", "6.2", "100", "80"))]}]}
        blocks, _, _ = _ai_ir_blocks([block], [], 8, 1000, 1000, "gemini")
        self.assertEqual(len(blocks[0]["columns"]), 2)
        self.assertEqual(blocks[0]["rows"][0]["note"], "6.2")
        self.assertEqual([cell["raw"] for cell in blocks[0]["rows"][0]["cells"].values()],
                         ["100", "80"])

    def test_ai_tesseract_disagreement_keeps_both_readings_for_review(self) -> None:
        block = {"type": "table", "text": None, "title": None, "unit_text": None,
                 "box_2d": None,
                 "columns": [{"key": "c1", "header_lines": ["31/03/2026"],
                              "box_2d": None}],
                 "rows": [{"code": "100", "label_raw": "Tài sản", "note": None,
                           "box_2d": None,
                           "cells": [{"column_key": "c1", "raw": "1.000",
                                      "box_2d": [100, 100, 140, 200]}]}]}
        words = [{"text": "1.800", "bbox": [110, 105, 190, 135], "conf": 90}]
        blocks, votes, disagreements = _ai_ir_blocks(
            [block], words, 5, 1000, 1000, "gemini", flag_unverified=True)
        cell = blocks[0]["rows"][0]["cells"]["c1"]
        self.assertEqual(cell["raw"], "1.000")
        self.assertTrue(cell["needs_review"])
        self.assertEqual(cell["votes"]["TESSERACT"]["raw"], "1.800")
        self.assertEqual((votes, disagreements), (1, 1))

    def test_real_tt99_ocr_fixture_builds_all_four_statement_pages(self) -> None:
        fixture = json.loads(TT99_OCR_FIXTURE.read_text(encoding="utf-8"))
        documents = []
        for page in fixture["pages"]:
            text = _record_text_for_classification({"text": "", "aiBlocks": page["aiBlocks"]})
            kind = financial_page_class(page["page"], None,
                                        fixture["source_pdf_sha256"], text)
            blocks, _, _ = _ai_ir_blocks(page["aiBlocks"], [], page["page"],
                                          1000, 1000, "gemini", flag_unverified=True)
            tables = [block for block in blocks if block["type"] == "table"]
            self.assertEqual(len(tables), 1, page["page"])
            documents.append({"page": page["page"], "page_class": kind,
                              "blocks": blocks})
        self.assertEqual([item["page_class"] for item in documents],
                         ["balance_sheet", "balance_sheet", "income_statement", "cash_flow"])
        self.assertEqual([len(next(block for block in item["blocks"]
                                   if block["type"] == "table")["columns"])
                          for item in documents], [2, 2, 4, 2])
        self.assertEqual(_accounting_template_profile(documents), "TT99_2025")

    def test_real_techcombank_page_is_classified_and_parsed(self) -> None:
        fixture = self.fixture
        page = _FixturePage(fixture)
        kind = financial_page_class(
            fixture["pdf_page"], None, fixture["document_sha256"],
            fixture["main_text"], fixture["running_header"])
        self.assertEqual(kind, "balance_sheet")

        tables, _boxes = statement_tables(page, fixture["document_sha256"], kind)
        self.assertEqual(len(tables), 1)
        self.assertGreaterEqual(len(tables[0]["rows"]), 30)
        self.assertEqual(tables[0]["rows"][0]["code"], None)
        self.assertEqual(tables[0]["columns"][0]["header_lines"],
                         ["31/12/2025", "Triệu đồng"])
        self.assertEqual(tables[0]["columns"][1]["header_lines"],
                         ["31/12/2024", "Triệu đồng"])
        self.assertEqual(
            _accounting_period(tables[0]["columns"][0]["header_lines"], kind)[0],
            "2025-12-31")
        self.assertEqual(
            _accounting_period(tables[0]["columns"][1]["header_lines"], kind)[0],
            "2024-12-31")

        document = [{
            "page": fixture["pdf_page"],
            "page_class": kind,
            "blocks": [
                {"type": "form_code", "text": "B02/TCTD-HN"},
                {"type": "heading", "text": "Báo cáo tình hình tài chính hợp nhất"},
                tables[0],
            ],
        }]
        self.assertEqual(_accounting_template_profile(document), "TT49_BANK")
        checks, skipped, _failed_pages, template_id = evaluate_accounting(document)
        self.assertEqual(checks, [])
        self.assertEqual(template_id, "TEMPLATE_UNKNOWN")
        self.assertEqual(skipped[0]["detected_profile"], "TT49_BANK")
        self.assertEqual(skipped[0]["reason"], "template_not_implemented")

    def test_ocr_markdown_table_has_null_geometry_and_review_flags(self) -> None:
        text = (
            "BÁO CÁO TÌNH HÌNH TÀI CHÍNH\n"
            "```markdown\n"
            "| Mã số | Chỉ tiêu | Số cuối kỳ | Số đầu kỳ |\n"
            "| --- | --- | --- | --- |\n"
            "| 100 | TÀI SẢN | 1.000 | 900 |\n"
            "```"
        )
        blocks = _text_blocks(text, 7, needs_review=True)
        tables = [block for block in blocks if block["type"] == "table"]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertIsNone(table["bbox"])
        self.assertTrue(all(column["bbox"] is None for column in table["columns"]))
        cell = table["rows"][0]["cells"]["c1"]
        self.assertIsNone(cell["bbox"])
        self.assertTrue(cell["needs_review"])
        self.assertEqual(cell["review_reason"], "OCR_MARKDOWN_SINGLE_SOURCE")
        page_ir = {
            "ir_version": "1", "page": 7,
            "page_size": {"width": 1000, "height": 1000, "unit": "pt"},
            "source": {"engine": "GEMINI", "tool": "fixture", "document_sha256": "a" * 64,
                       "image_sha256": "b" * 64, "prompt_version": "fixture"},
            "blocks": [{"id": f"p7-b{index}", **block}
                       for index, block in enumerate(blocks, 1)],
        }
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        self.assertEqual(validate_page(page_ir, validator), [])

    def test_structured_ocr_titles_are_used_when_transcript_is_empty(self) -> None:
        text = _record_text_for_classification({
            "text": "",
            "aiBlocks": [
                {"type": "heading", "text": "BÁO CÁO TÌNH HÌNH TÀI CHÍNH"},
                {"type": "table", "title": "Mẫu B01-DN",
                 "columns": [{"header_lines": ["Số cuối kỳ"]}],
                 "rows": [{"code": "100", "label_raw": "Tài sản"}]},
            ],
        })
        self.assertIn("BÁO CÁO TÌNH HÌNH TÀI CHÍNH", text)
        self.assertEqual(
            financial_page_class(10, None, "sha", text), "balance_sheet")

    def test_scanned_statement_title_after_tesseract_reading_order_is_found(self) -> None:
        # FPT's scanned B02-DN page places the main title after row labels in
        # the OCR reading order; the form code and title together identify it.
        text = "\n".join([f"row {number}" for number in range(12)] + [
            "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",
            "MẪU SỐ B 02-DN",
        ])
        self.assertEqual(financial_page_class(7, None, "sha", text), "income_statement")

    def test_fpt_contents_page_is_not_misclassified_as_a_statement(self) -> None:
        text = ("CÔNG TY CỔ PHẦN FPT\nBÁO CÁO TÀI CHÍNH RIÊNG\nMỤC LỤC\n"
                "NỘI DUNG\nBẢNG CÂN ĐỐI KẾ TOÁN\n"
                "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH")
        self.assertEqual(financial_page_class(4, None, "sha", text), "toc")

    def test_fpt_scanned_income_statement_recovers_four_columns(self) -> None:
        fixture = json.loads(FPT_INCOME_FIXTURE.read_text(encoding="utf-8"))
        table, _used = _tess_statement_table(
            fixture["word_items"], fixture["pdf_page"], fixture["width"])
        self.assertIsNotNone(table)
        assert table is not None
        recovered = _recover_missing_tesseract_cells(table, fixture["psm3_word_items"])
        self.assertEqual(len(table["columns"]), 4)
        self.assertEqual(len(table["rows"]), 18)  # 17 form rows plus the printed detail row.
        self.assertEqual(recovered, 1)
        self.assertEqual(table["columns"][0]["header_lines"], ["Quý 4", "Năm 2025"])
        self.assertEqual(table["columns"][1]["header_lines"], ["Quý 4", "Năm 2024"])
        self.assertEqual(table["columns"][2]["header_lines"],
                         ["Lũy kế từ đầu năm đến cuối quý này", "Năm 2025"])
        self.assertEqual(table["columns"][3]["header_lines"],
                         ["Lũy kế từ đầu năm đến cuối quý này", "Năm 2024"])
        by_code = {row["code"]: row for row in table["rows"] if row["code"]}
        self.assertEqual(by_code["02"]["cells"]["c1"]["raw"], "-")
        self.assertEqual(by_code["25"]["cells"]["c2"]["raw"], "1/233.277.527")
        self.assertEqual(by_code["32"]["cells"]["c2"]["raw"], "32")
        self.assertEqual(by_code["32"]["cells"]["c2"]["review_reason"],
                         "TESSERACT_PSM3_RECOVERED_NEEDS_REVIEW")
        self.assertEqual(by_code["60"]["cells"]["c4"]["raw"], "5.506.633.850.047")
        self.assertTrue(all(cell["needs_review"] for row in table["rows"]
                            for cell in row["cells"].values()))

    def test_tt200_tt99_and_tt49_do_not_share_templates(self) -> None:
        tt200 = [{"page": 1, "page_class": "balance_sheet", "blocks": [
            {"type": "form_code", "text": "Mẫu số B01-DN"},
            {"type": "heading", "text": "BẢNG CÂN ĐỐI KẾ TOÁN"},
        ]}]
        tt99 = [{"page": 1, "page_class": "balance_sheet", "blocks": [
            {"type": "form_code", "text": "Mẫu số B01-DN"},
            {"type": "heading", "text": "BÁO CÁO TÌNH HÌNH TÀI CHÍNH"},
            {"type": "table", "rows": [
                {"code": "270", "label_raw": "Tài sản dài hạn khác"},
                {"code": "280", "label_raw": "Tổng cộng tài sản"},
            ]},
        ]}]
        tt99_consolidated = [{"page": 1, "page_class": "balance_sheet", "blocks": [
            {"type": "form_code", "text": "Mẫu số B01-DN/HN"},
            {"type": "heading", "text": "BÁO CÁO TÌNH HÌNH TÀI CHÍNH HỢP NHẤT"},
        ]}]
        self.assertEqual(_accounting_template_profile(tt200), "TT200_NONBANK")
        self.assertEqual(_select_accounting_template_path(tt200).name,
                         "financial-template-lines.json")
        self.assertEqual(_accounting_template_profile(tt99), "TT99_2025")
        self.assertEqual(_select_accounting_template_path(tt99).name,
                         "tt99-2025-b01-b02-b03.json")
        self.assertIsNone(_accounting_template_profile(tt99_consolidated))

    def test_relative_column_periods_use_report_date(self) -> None:
        self.assertEqual(
            _accounting_period(["Quý này năm nay"], "income_statement",
                               "Từ ngày 01/01/2026 đến ngày 31/03/2026"),
            ("2026-03-31", "duration", "current"))
        self.assertEqual(
            _accounting_period(["Số cuối kỳ VND"], "balance_sheet",
                               "Báo cáo tình hình tài chính tại ngày 30 tháng 6 năm 2026")[0],
            "2026-06-30")
        self.assertEqual(
            _accounting_period(["Số đầu kỳ VND"], "balance_sheet",
                               "Báo cáo tình hình tài chính tại ngày 30 tháng 6 năm 2026")[0],
            "2025-12-31")
        self.assertEqual(
            _accounting_period(["Kỳ này VND"], "income_statement",
                               "Kỳ kế toán 6 tháng kết thúc ngày 30 tháng 6 năm 2026")[0],
            "2026-06-30")
        self.assertEqual(
            _accounting_period(["Kỳ trước VND"], "income_statement",
                               "Kỳ kế toán 6 tháng kết thúc ngày 30 tháng 6 năm 2026")[0],
            "2025-06-30")

    def test_quarter_and_year_to_date_columns_keep_distinct_roles(self) -> None:
        context = "Báo cáo kết quả kinh doanh kết thúc ngày 31 tháng 12 năm 2025"
        self.assertEqual(_accounting_period(["Quý 4", "Năm 2025"],
                                            "income_statement", context),
                         ("2025-12-31", "duration", "quarter_current"))
        self.assertEqual(_accounting_period(["Quý 4", "Năm 2024"],
                                            "income_statement", context),
                         ("2024-12-31", "duration", "quarter_comparative"))
        self.assertEqual(_accounting_period(["Lũy kế từ đầu năm đến cuối quý này", "Năm 2025"],
                                            "income_statement", context),
                         ("2025-12-31", "duration", "year_to_date_current"))

    def test_needs_review_ocr_cells_are_not_used_for_arithmetic(self) -> None:
        document = [{
            "page": 148,
            "page_class": "balance_sheet",
            "blocks": [
                {"type": "heading", "text": "BẢNG CÂN ĐỐI KẾ TOÁN"},
                {"type": "table", "id": "p148-t1", "columns": [
                    {"key": "c1", "header_lines": ["2024"], "bbox": None}],
                 "rows": [{"id": "r1", "code": "100", "label_raw": "Tài sản",
                           "cells": {"c1": {"raw": "1.000", "bbox": None,
                                              "needs_review": True,
                                              "review_reason": "OCR_MARKDOWN_SINGLE_SOURCE"}}}]},
            ],
        }]
        checks, skipped, _failed_pages, template_id = evaluate_accounting(document)
        self.assertEqual(template_id, "vn_nonbank_b01_b02_b03_v1")
        self.assertEqual(checks, [])
        self.assertTrue(any(item["name"] == "needs_review_cell" for item in skipped))


if __name__ == "__main__":
    unittest.main()
