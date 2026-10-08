"""Build the four requested FPT 2024 tables from the PDF text layer.

The output groups one-page Document IR objects by logical table. Only table
blocks are emitted; navigation and other repeated page furniture are omitted.
Matches to the common template remain candidates, never approved facts.
"""

from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[5]
POC = Path(__file__).resolve().parents[1]
PDF_PATH = POC / "FPT_2024_498332 (1).pdf"
IR_DIR = POC / "Document IR"
OUTPUT = IR_DIR / "fpt-2024-four-tables.ir.json"
MAPPINGS_OUTPUT = IR_DIR / "fpt-2024-four-tables.mappings.json"
BBOX_ARRAY_RE = re.compile(r'("bbox": )\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]')
TEMPLATE_PATH = ROOT / "templates" / "Thông tin chung.json"
TEMPLATE = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8-sig"))
METRICS = {m["metric_id"]: m for m in TEMPLATE["metrics"]}
P148_REVIEWED = json.loads((IR_DIR / "fpt-2024-p148.pdf-reviewed.mapped.json").read_text(encoding="utf-8"))

REPORTS = [
    ("company_information", "THÔNG TIN VỀ DOANH NGHIỆP", [144]),
    ("balance_sheet", "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT", list(range(148, 153))),
    ("income_statement", "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT", [153, 154]),
    ("cash_flow_statement", "BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT", [155, 156]),
]

ROW_CODE = re.compile(r"\d{2,3}[a-z]?", re.I)
AMOUNT = re.compile(r"(?:\(?-?[\d.,]+\)?|[-–])")
NOTE = re.compile(r"\d+(?:\([a-z]\))?(?:,\d+(?:\([a-z]\))?)*", re.I)

# These choices require layout or wording evidence beyond one exact alias.
# Their status remains source_review_candidate in the output.
OVERRIDES = {
    (149, "222"): ("common.tangible_fixed_assets_gross", "pdf_hierarchy", "Dòng con của mã 221: tài sản cố định hữu hình."),
    (149, "223"): ("common.tangible_fixed_assets_accumulated_depreciation", "pdf_hierarchy", "Dòng con của mã 221: khấu hao lũy kế TSCĐ hữu hình."),
    (149, "225"): ("common.finance_lease_fixed_assets_gross", "pdf_hierarchy", "Dòng con của mã 224: tài sản cố định thuê tài chính."),
    (149, "226"): ("common.finance_lease_fixed_assets_accumulated_depreciation", "pdf_hierarchy", "Dòng con của mã 224: khấu hao lũy kế tài sản thuê tài chính."),
    (149, "228"): ("common.intangible_fixed_assets_gross", "pdf_hierarchy", "Dòng con của mã 227: tài sản cố định vô hình."),
    (149, "229"): ("common.intangible_fixed_assets_accumulated_depreciation", "pdf_hierarchy", "Dòng con của mã 227: khấu hao lũy kế TSCĐ vô hình."),
    (149, "255"): ("common.held_to_maturity_noncurrent", "pdf_hierarchy", "Nằm trong nhóm đầu tư tài chính dài hạn, mã 250."),
    (150, "260"): ("common.other_noncurrent_assets_total", "pdf_hierarchy", "Dòng tổng của các mã 261, 262, 269."),
    (151, "313"): ("common.taxes_payable_current", "pdf_hierarchy", "Nằm trong nhóm nợ ngắn hạn, mã 310."),
    (152, "400"): ("common.equity", "pdf_hierarchy", "Dòng tổng vốn chủ sở hữu, bao gồm nhóm 410 và 430."),
    (152, "410"): ("common.equity_core", "pdf_hierarchy", "Nhóm vốn chủ sở hữu riêng dưới mã 400; nguồn kinh phí ở mã 430."),
    (152, "421"): ("common.retained_earnings", "pdf_label_semantics", "LNST là lợi nhuận sau thuế; dòng tổng chưa phân phối."),
    (152, "421a"): ("common.retained_earnings_prior", "pdf_label_semantics", "Nhãn ghi rõ số dư lũy kế các năm trước."),
    (152, "421b"): ("common.retained_earnings_current", "pdf_label_semantics", "Nhãn ghi rõ phần chưa phân phối của năm nay."),
    (153, "24"): ("common.associate_profit_share", "pdf_label_semantics", "Phần lãi từ công ty liên doanh, liên kết."),
    (154, "60"): ("common.profit_after_tax", "pdf_label_semantics", "Dòng lợi nhuận sau thuế toàn tập đoàn theo công thức in."),
    (154, "61"): ("common.profit_parent", "pdf_label_semantics", "Phần lợi nhuận phân bổ cho cổ đông công ty mẹ."),
    (154, "62"): ("common.profit_noncontrolling", "pdf_label_semantics", "Phần lợi nhuận phân bổ cho cổ đông không kiểm soát."),
    (155, "01"): ("common.profit_before_tax", "pdf_label_semantics", "Lợi nhuận kế toán trước thuế trong báo cáo lưu chuyển tiền tệ."),
    (155, "17"): ("common.operating_cash_outflow_other", "pdf_label_semantics", "Tiền chi khác thuộc hoạt động kinh doanh."),
    (155, "22"): ("common.investing_cash_inflow_disposal_fixed_assets", "pdf_label_semantics", "Tiền thu thanh lý, nhượng bán tài sản dài hạn."),
    (156, "31"): ("common.financing_cash_inflow_equity_issued", "pdf_label_semantics", "Tiền thu từ phát hành cổ phiếu."),
    (156, "34"): ("common.financing_cash_outflow_borrowings_repaid", "pdf_label_semantics", "Tiền chi trả nợ gốc vay."),
    (156, "35"): ("common.financing_cash_outflow_finance_lease_principal", "pdf_label_semantics", "Tiền chi trả nợ gốc thuê tài chính."),
    (156, "36"): ("common.cash_dividends_paid", "pdf_label_semantics", "Tiền cổ tức, lợi nhuận đã trả cho chủ sở hữu."),
    (156, "50"): ("common.net_cash_change", "pdf_label_semantics", "Lưu chuyển tiền thuần trong năm tương ứng biến động tiền trong kỳ."),
    (156, "60"): ("common.cash_beginning", "pdf_label_semantics", "Số dư tiền đầu năm trên lưu chuyển tiền tệ."),
    (156, "70"): ("common.cash_ending", "pdf_label_semantics", "Số dư tiền cuối năm trên lưu chuyển tiền tệ."),
}

SUGGESTIONS = {
    (149, "250"): "common.long_term_financial_investments",
    (151, "317"): "common.construction_contract_payables_current",
}


def key(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip().casefold()


def bbox(words: list[dict]) -> list[float] | None:
    if not words:
        return None
    return [
        round(min(w["x0"] for w in words), 2),
        round(min(w["top"] for w in words), 2),
        round(max(w["x1"] for w in words), 2),
        round(max(w["bottom"] for w in words), 2),
    ]


def ordered_text(words: list[dict]) -> str:
    return " ".join(w["text"] for w in sorted(words, key=lambda w: (round(w["top"] / 4), w["x0"]))).strip()


def match(label: str, page: int, code: str | None) -> dict:
    if (page, code) in OVERRIDES:
        metric_id, method, evidence = OVERRIDES[(page, code)]
        metric = METRICS[metric_id]
        return {
            "status": "source_review_candidate", "metric_id": metric_id,
            "candidate_ids": [metric_id], "matched_alias": metric["label_vi"],
            "template_label_vi": metric["label_vi"],
            "candidate_labels": [{"metric_id": metric_id, "label_vi": metric["label_vi"]}],
            "template_schema_version": TEMPLATE["schema_version"],
            "match_method": method, "review_evidence": evidence,
        }

    cleaned = re.sub(r"^[-•]\s*", "", label.strip())
    cleaned = re.sub(r"\s*\(\s*\d+\s*=.*\)\s*$", "", cleaned).strip()
    hits = [(m, alias) for m in TEMPLATE["metrics"] for alias in m.get("aliases", []) if key(alias) == key(cleaned)]
    ids = sorted({m["metric_id"] for m, _ in hits})
    result = {
        "status": "no_match", "metric_id": None, "candidate_ids": ids,
        "matched_alias": hits[0][1] if hits else None,
        "template_label_vi": None,
        "candidate_labels": [{"metric_id": mid, "label_vi": METRICS[mid]["label_vi"]} for mid in ids],
        "template_schema_version": TEMPLATE["schema_version"],
        "match_method": "template_alias_missing",
    }
    if len(ids) > 1:
        result.update(status="ambiguous", match_method="exact_alias")
    elif len(ids) == 1:
        metric = METRICS[ids[0]]
        contextual = any(key(a) == key(cleaned) for a in metric.get("context_required_aliases", []))
        if contextual:
            result.update(status="context_required", match_method="exact_alias")
        elif cleaned != label.strip():
            result.update(
                status="source_review_candidate", metric_id=ids[0],
                template_label_vi=metric["label_vi"], match_method="pdf_label_semantics",
                review_evidence="Nhãn khớp alias sau khi bỏ ký hiệu đầu dòng hoặc công thức in kèm.",
            )
        else:
            result.update(status="candidate", metric_id=ids[0], template_label_vi=metric["label_vi"], match_method="exact_alias")

    suggested = SUGGESTIONS.get((page, code))
    if suggested and result["status"] == "no_match":
        result["suggested_metric_id"] = suggested
        result["suggested_label_vi"] = METRICS[suggested]["label_vi"]
        result["review_evidence"] = "Nhãn trong PDF không trùng alias template; chỉ ghi gợi ý để review."
    return result


def cell(raw: str, words: list[dict]) -> dict | None:
    return {"raw": raw, "bbox": bbox(words)} if raw else None


def printed_cells(values: dict[str, tuple[str, list[dict]]]) -> dict:
    return {key: item for key, (raw, words) in values.items()
            if (item := cell(raw, words)) is not None}


def financial_rows(page: pdfplumber.page.Page, page_no: int) -> tuple[list[dict], list[dict]]:
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    codes = [w for w in words if 420 <= w["x0"] < 510 and ROW_CODE.fullmatch(w["text"])]
    rows: list[dict] = []
    centers: list[float] = []
    reviewed = {}
    if page_no == 148:
        reviewed = {r["ma_so"]: r["metric_match"] for b in P148_REVIEWED["blocks"] if b["type"] == "table" for r in b["rows"]}

    for code_word in sorted(codes, key=lambda w: w["top"]):
        cy = (code_word["top"] + code_word["bottom"]) / 2
        if any(abs(cy - prior) < 1.1 for prior in centers):
            continue
        line = sorted(
            [w for w in words if w["x0"] >= 420 and abs((w["top"] + w["bottom"]) / 2 - cy) < 2.8],
            key=lambda w: w["x0"],
        )
        label_words = [w for w in line if code_word["x1"] - 1 <= w["x0"] < 1175 and w is not code_word]
        note_words = [w for w in line if 1175 <= w["x0"] < 1400 and NOTE.fullmatch(w["text"])]
        amounts = [w for w in line if w["x0"] >= 1400 and AMOUNT.fullmatch(w["text"])]
        current = [w for w in amounts if w["x0"] < 1660]
        prior = [w for w in amounts if w["x0"] >= 1660]
        label_raw = ordered_text(label_words)
        extra_words: list[dict] = []
        if page_no == 153 and code_word["text"] == "30":
            extra_words = [w for w in words if 520 <= w["x0"] < 1175 and cy + 4 < (w["top"] + w["bottom"]) / 2 < cy + 35]
        if page_no == 155 and code_word["text"] == "04":
            extra_words = [w for w in words if 460 <= w["x0"] < 1175 and cy + 4 < (w["top"] + w["bottom"]) / 2 < cy + 35]
        if extra_words:
            label_raw += " " + ordered_text(extra_words)
        code = code_word["text"]
        metric_match = dict(reviewed[code]) if code in reviewed else match(label_raw, page_no, code)
        metric_id = metric_match.get("metric_id")
        if metric_id in METRICS:
            metric_match.setdefault("template_label_vi", METRICS[metric_id]["label_vi"])
        suggested = metric_match.get("suggested_metric_id")
        if suggested in METRICS:
            metric_match.setdefault("suggested_label_vi", METRICS[suggested]["label_vi"])
        metric_match.setdefault("candidate_labels", [{"metric_id": mid, "label_vi": METRICS[mid]["label_vi"]} for mid in metric_match.get("candidate_ids", []) if mid in METRICS])
        rows.append({
            "id": f"r{len(rows) + 1}", "code": code, "label_raw": label_raw,
            "note": ordered_text(note_words) or None,
            "indent": min((w["x0"] for w in label_words), default=None), "bold": None,
            "bbox": bbox(line + extra_words),
            "cells": printed_cells({"c1": (ordered_text(current), current),
                                    "c2": (ordered_text(prior), prior)}),
            "metric_match": metric_match,
        })
        centers.append(cy)
    return rows, words


def company_match(metric_id: str | None, evidence: str = "") -> dict:
    if metric_id is None:
        return {"status": "no_match", "metric_id": None, "candidate_ids": [], "matched_alias": None,
                "template_label_vi": None, "candidate_labels": [], "template_schema_version": TEMPLATE["schema_version"],
                "match_method": "template_alias_missing"}
    metric = METRICS[metric_id]
    return {"status": "source_review_candidate", "metric_id": metric_id, "candidate_ids": [metric_id],
            "matched_alias": metric["label_vi"], "template_label_vi": metric["label_vi"],
            "candidate_labels": [{"metric_id": metric_id, "label_vi": metric["label_vi"]}],
            "template_schema_version": TEMPLATE["schema_version"], "match_method": "pdf_label_semantics",
            "review_evidence": evidence or "Nhãn mục và nội dung ô trên bảng cho thấy chỉ tiêu tương ứng."}


def company_rows(page: pdfplumber.page.Page) -> tuple[list[dict], list[dict]]:
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    rows: list[dict] = []

    def at_line(center: float, x0: float, x1: float) -> list[dict]:
        return [w for w in words if x0 <= w["x0"] < x1 and abs((w["top"] + w["bottom"]) / 2 - center) < 4]

    def put(label: str, info_words: list[dict], role_words: list[dict], label_words: list[dict],
            metric_id: str | None, info_label: str, role_label: str = "Chức vụ", evidence: str = "") -> None:
        rows.append({"id": f"r{len(rows) + 1}", "code": None, "label_raw": label, "note": None,
                     "indent": min((w["x0"] for w in label_words), default=None), "bold": None,
                     "bbox": bbox(info_words + role_words + label_words),
                     "cells": printed_cells({"c1": (ordered_text(info_words), info_words),
                                             "c2": (ordered_text(role_words), role_words)}),
                     "metric_match": company_match(metric_id, evidence)})

    certificate_label = "Giấy Chứng nhận Đăng ký Doanh nghiệp"
    certificate_words = [w for w in words if 420 <= w["x0"] < 700 and 125 <= w["top"] <= 180]
    put(certificate_label, at_line(144, 740, 1900), [], certificate_words,
        "common.registration_number", "Số giấy chứng nhận và ngày cấp", "",
        "Ô chứa số 0101248141 cùng ngày cấp; cần tách riêng số khi tạo observation.")
    certificate_detail = [w for w in words if 740 <= w["x0"] < 1900 and 170 <= (w["top"] + w["bottom"]) / 2 <= 215]
    put(certificate_label, certificate_detail, [], [], None, "Diễn giải đăng ký doanh nghiệp", "")

    groups = [
        ("Hội đồng Quản trị", [240, 273, 307, 341, 375, 408, 442], "common.board_composition"),
        ("Ban Tổng Giám đốc", [509, 543, 577, 611], None),
        ("Ban Kiểm soát", [678, 712, 745], None),
        ("Người đại diện theo pháp luật", [813, 846], None),
    ]
    for group_label, centers, metric_id in groups:
        for i, center in enumerate(centers):
            put(group_label, at_line(center, 740, 1510), at_line(center, 1510, 1900),
                at_line(center, 420, 740) if i == 0 else [], metric_id,
                "Họ tên", "Chức vụ", "Từng dòng là một người trong Hội đồng Quản trị; cần lưu tên và chức vụ như thuộc tính riêng." if metric_id else "")

    put("Trụ sở chính", at_line(880, 740, 1900), [], at_line(880, 420, 740),
        "common.head_office", "Địa chỉ trụ sở chính", "")
    put("Công ty kiểm toán", at_line(948, 740, 1900), [], at_line(948, 420, 740),
        "common.audit_firm", "Tên công ty kiểm toán", "")
    return rows, words


def make_page(pdf: pdfplumber.PDF, page_no: int, table_id: str, title: str,
              first_page: int, document_sha256: str) -> dict:
    page = pdf.pages[page_no - 1]
    if table_id == "company_information":
        rows, words = company_rows(page)
        columns = [
            {"key": "c1", "header_lines": [], "bbox": None},
            {"key": "c2", "header_lines": [], "bbox": None},
        ]
        unit = None
        header_words = []
    else:
        rows, words = financial_rows(page, page_no)
        years = [w for w in words if w["text"] in ("2024", "2023") and w["x0"] >= 1400 and 120 <= w["top"] <= 220]
        header_words = [w for w in words if w["x0"] >= 1490 and 110 <= w["top"] <= 210
                        and (w["text"] in ("2024", "2023", "VND") or
                             w["top"] < min((y["top"] for y in years), default=0))]
        period_words = [w for w in header_words if w["text"] not in ("2024", "2023", "VND")]
        period_line = ordered_text(period_words)
        columns = [
            {"key": "c1", "header_lines": ([period_line] if period_line else []) + ["2024", "VND"],
             "bbox": bbox([w for w in header_words if 1400 <= w["x0"] < 1660])},
            {"key": "c2", "header_lines": ([period_line] if period_line else []) + ["2023", "VND"],
             "bbox": bbox([w for w in header_words if w["x0"] >= 1660])},
        ]
        unit = None
    table = {"id": f"p{page_no}-t1", "type": "table", "title": title,
             "continued": page_no != first_page, "logical_table_id": table_id,
             "bbox": bbox([w for row in rows for w in words if row["bbox"] and
                            row["bbox"][0] <= w["x0"] <= row["bbox"][2] and
                            row["bbox"][1] <= w["top"] <= row["bbox"][3]]),
             "unit_text": unit, "columns": columns, "rows": rows}
    # Row boxes give a precise content-only rectangle. Avoid including the side menu.
    row_boxes = [r["bbox"] for r in rows if r["bbox"]]
    if row_boxes:
        table["bbox"] = [min(b[0] for b in row_boxes), min(b[1] for b in row_boxes),
                         max(b[2] for b in row_boxes), max(b[3] for b in row_boxes)]
    if header_words and table["bbox"]:
        header_box = bbox(header_words)
        table["bbox"] = [min(table["bbox"][0], header_box[0]), min(table["bbox"][1], header_box[1]),
                         max(table["bbox"][2], header_box[2]), max(table["bbox"][3], header_box[3])]
    return {"ir_version": "1", "page": page_no, "page_class":
            "cash_flow" if table_id == "cash_flow_statement" else table_id,
            "page_size": {"width": page.width, "height": page.height, "unit": "pt"},
            "source": {"engine": "TEXT_LAYER", "tool": f"pdfplumber {pdfplumber.__version__}",
                       "document_sha256": document_sha256, "file_name": PDF_PATH.name},
            "blocks": [table]}
def main() -> None:
    groups = []
    mappings = []
    with PDF_PATH.open("rb") as source_pdf:
        document_sha256 = hashlib.file_digest(source_pdf, "sha256").hexdigest()
    with pdfplumber.open(PDF_PATH) as pdf:
        for table_id, title, page_numbers in REPORTS:
            pages = []
            for n in page_numbers:
                ir = make_page(pdf, n, table_id, title, page_numbers[0], document_sha256)
                table = ir["blocks"][0]
                for row in table["rows"]:
                    mappings.append({"page": n, "block_id": table["id"], "row_id": row["id"],
                                     "legacy_match": row.pop("metric_match")})
                pages.append(ir)
            groups.append({"table_id": table_id, "title": title, "pages": pages})
    output = {"ir_version": "1", "document_name": PDF_PATH.name, "tables": groups}
    pretty_json = json.dumps(output, ensure_ascii=False, indent=2)
    pretty_json = BBOX_ARRAY_RE.sub(r'\1[\2, \3, \4, \5]', pretty_json)
    OUTPUT.write_text(pretty_json + "\n", encoding="utf-8")
    MAPPINGS_OUTPUT.write_text(json.dumps({"document_sha256": document_sha256,
                                          "mappings": mappings}, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    for group in groups:
        count = sum(len(page["blocks"][0]["rows"]) for page in group["pages"])
        print(f"{group['title']}: {len(group['pages'])} page(s), {count} row(s)")
    print(OUTPUT)
if __name__ == "__main__":
    main()
