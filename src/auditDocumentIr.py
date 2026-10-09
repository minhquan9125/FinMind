"""Audit generated Document IR against its schema and source PDF text layer.

Usage: python src/auditDocumentIr.py "FPT_2024_498332 (1).pdf"
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import pdfplumber
from jsonschema import Draft202012Validator

from buildDocumentIr import _represented_words, _tokens
from financialContent import evaluate_accounting, expand_page_ranges
from util import hash_file
from validate_ir import SCHEMA, validate_page


def audit(pdf_path: Path, ir_dir: Path) -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    manifest = json.loads((ir_dir / "index.json").read_text(encoding="utf-8"))
    content_dir = ir_dir / manifest["content"]["directory"]
    index = json.loads((content_dir / "index.json").read_text(encoding="utf-8"))
    indexed_pages = expand_page_ranges(index["pageRanges"])
    expected_annual_files = [f"p-{number:03d}.ir.json" for number in indexed_pages]
    documents = [json.loads((content_dir / name).read_text(encoding="utf-8"))
                 for name in expected_annual_files if (content_dir / name).is_file()]
    errors: list[str] = []
    if sorted(path.name for path in content_dir.glob("p-*.ir.json")) != expected_annual_files:
        errors.append("content/index.json không khớp các file p-NNN.ir.json")
    if manifest["document_sha256"] != hash_file(pdf_path):
        errors.append("annual_ir/index.json không cùng PDF gốc")
    with pdfplumber.open(pdf_path) as pdf:
        numbers = [document["page"] for document in documents]
        if numbers != indexed_pages or any(number < 1 or number > len(pdf.pages) for number in numbers):
            errors.append("Danh sách trang IR trùng, sai thứ tự hoặc ngoài PDF")
        if index["pages"] != len(documents) or manifest["content"]["pages"] != len(documents):
            errors.append("index.pages không khớp số file")
        text_pages = 0
        schema_valid_pages = 0
        for document in documents:
            number = document["page"]
            validation_issues = validate_page(document, validator)
            if not validation_issues:
                schema_valid_pages += 1
            for issue in validation_issues:
                errors.append(f"Trang {number}: {issue}")
            if document["source"]["engine"] != "TEXT_LAYER":
                continue
            text_pages += 1
            source_page = pdf.pages[number - 1]
            # Some PDFs embed duplicate text above the physical page (negative
            # coordinates). It is invisible and deliberately absent from IR.
            source_words = Counter(_tokens(" ".join(
                word["text"] for word in source_page.extract_words(
                    x_tolerance=2, y_tolerance=3, extra_attrs=["size"])
                if 0 <= word["top"] < source_page.height)))
            missing = source_words - _represented_words(document["blocks"])
            if missing:
                errors.append(f"Trang {number}: thiếu {sum(missing.values())} từ của lớp text")
    actual_types = Counter(block["type"] for document in documents for block in document["blocks"])
    if dict(actual_types) != index["blockTypes"]:
        errors.append("index.blockTypes không khớp các trang IR")
    sections = json.loads((content_dir / "sections.json").read_text(encoding="utf-8"))
    covered = [number for item in sections["sections"]
               for number in range(item["first_page"], item["last_page"] + 1)]
    if sorted(covered + sections["unclassified_pages"]) != [doc["page"] for doc in documents]:
        errors.append("sections.json thiếu hoặc trùng trang")
    by_page = {document["page"]: document for document in documents}
    topic_pages = {number for topic in sections["topics"] for number in topic["pdf_pages"]}
    if topic_pages != set(by_page):
        errors.append("Chỉ mục chủ đề không khớp các trang IR")
    for target in sections["table_targets"]:
        document = by_page.get(target["pdf_page"])
        if document is None or target["ir_file"] != f"p-{target['pdf_page']:03d}.ir.json":
            errors.append(f"Bảng mục tiêu trang {target['pdf_page']} thiếu liên kết IR")
            continue
        matches = [block for block in document["blocks"] if block["type"] == "table"
                   and block["id"] == target.get("table_block_id")
                   and block.get("title") == target["title"]]
        if target.get("status") == "structured":
            if len(matches) != 1 or not matches[0]["columns"] or not matches[0]["rows"]:
                errors.append(f"Bảng mục tiêu trang {target['pdf_page']} chưa có dòng/ô hợp lệ")
        elif target.get("status") == "text_only":
            visible = " ".join(block.get("text", "") for block in document["blocks"]
                               if block["type"] in ("heading", "paragraph"))
            if target["title"] not in visible:
                errors.append(f"Bảng mục tiêu trang {target['pdf_page']} thiếu tiêu đề nguồn")
        else:
            errors.append(f"Bảng mục tiêu trang {target['pdf_page']} có trạng thái không hợp lệ")
    kpis = json.loads((content_dir / "kpi_review.json").read_text(encoding="utf-8"))["items"]
    for item in kpis:
        if item["review_status"] != "verified":
            continue
        matches = [block for block in by_page[item["page"]]["blocks"]
                   if block["id"] == item.get("block_id")]
        if len(matches) != 1 or matches[0]["type"] != "kpi" \
                or matches[0]["text"] != item["value_raw"]:
            errors.append(f"Trang {item['page']}: KPI {item['value_raw']} mất liên kết IR")
    financial_pages = 0
    financial = manifest.get("table")
    if financial:
        table_dir = ir_dir / financial["directory"]
        table_index = json.loads((table_dir / "index.json").read_text(encoding="utf-8"))
        indexed_numbers = expand_page_ranges(table_index["page_ranges"])
        expected_files = [f"p-{number:03d}.ir.json" for number in indexed_numbers]
        actual_files = sorted(path.name for path in table_dir.glob("p-*.ir.json"))
        if actual_files != expected_files:
            errors.append("table/index.json không khớp các file p-NNN.ir.json")
        financial_documents = [json.loads((table_dir / name).read_text(encoding="utf-8"))
                               for name in expected_files if (table_dir / name).is_file()]
        financial_pages = len(financial_documents)
        numbers = [page["page"] for page in financial_documents]
        if numbers != indexed_numbers or table_index["pages"] != financial_pages \
                or financial_pages != financial["pages"]:
            errors.append("table/index.json thiếu trang, trùng trang hoặc sai thứ tự")
        page_entries = table_index.get("page_index", [])
        if len(page_entries) != financial_pages or any(
                entry.get("pdf_page") != page["page"]
                or entry.get("printed_page") != page.get("printed_page")
                or entry.get("file") != f"p-{page['page']:03d}.ir.json"
                or entry.get("page_class") != page["page_class"]
                or not entry.get("title")
                or entry.get("has_structured_table") != any(
                    block["type"] == "table" and block["rows"] for block in page["blocks"])
                for entry, page in zip(page_entries, financial_documents)):
            errors.append("table/index.json có page_index thiếu hoặc sai liên kết trang")
        section_numbers = [number for section in table_index["sections"]
                           for number in range(section["start"], section["end"] + 1)]
        if section_numbers != indexed_numbers:
            errors.append("table/index.json có sections thiếu hoặc trùng trang")
        if table_index["document_sha256"] != hash_file(pdf_path):
            errors.append("table/index.json không cùng PDF với IR thường niên")
        actual_structured = []
        actual_notes_text_only = []
        for page in financial_documents:
            number = page["page"]
            for issue in validate_page(page, validator):
                errors.append(f"BCTC trang {number}: {issue}")
            if page["source"]["document_sha256"] != table_index["document_sha256"]:
                errors.append(f"BCTC trang {number}: SHA-256 PDF không khớp index")
            if any(block["type"] == "table" and block["rows"] for block in page["blocks"]):
                actual_structured.append(number)
            elif page["page_class"] == "notes":
                actual_notes_text_only.append(number)
        if actual_structured != expand_page_ranges(table_index["structured_table_ranges"]):
            errors.append("table/index.json sai danh sách trang có bảng cấu trúc")
        if actual_notes_text_only != expand_page_ranges(table_index["notes_text_only_ranges"]):
            errors.append("table/index.json sai danh sách thuyết minh chỉ có text")
        checks, skipped, _, template_id = evaluate_accounting(financial_documents)
        if checks != table_index.get("arithmetic_checks") or skipped != table_index.get(
                "arithmetic_checks_skipped") or template_id != table_index.get("arithmetic_template_id"):
            errors.append("table/index.json có luật đẳng thức không khớp IR/template_lines")
    furniture_path = ir_dir / "furniture_audit.json"
    if furniture_path.is_file():
        furniture = json.loads(furniture_path.read_text(encoding="utf-8"))
        pages_path = ir_dir.parent / "pages.jsonl"
        if pages_path.is_file():
            layer_pages = sum(json.loads(line)["route"] == "text_layer"
                              for line in pages_path.read_text(encoding="utf-8").splitlines()
                              if line.strip())
            if furniture["pages_checked"] != layer_pages:
                errors.append("furniture_audit.json chưa bao phủ toàn bộ trang lớp chữ")
        if furniture["minimum_repeated_pages"] != math.ceil(furniture["pages_checked"] * .5) \
                or any(group["pages"] < furniture["minimum_repeated_pages"]
                       for group in furniture["repeated_groups"]):
            errors.append("furniture_audit.json sai ngưỡng lặp 50%")
        if furniture["furniture_table_overlaps"]:
            errors.append("Có furniture chồng lên bảng")
    return {"ir_pages": len(documents), "text_layer_pages_checked": text_pages,
            "schema_valid_pages": schema_valid_pages,
            "financial_ir_pages": financial_pages,
            "block_types": dict(actual_types),
            "verified_kpis": sum(item["review_status"] == "verified" for item in kpis),
            "table_targets": len(sections["table_targets"]),
            "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--ir-dir", type=Path)
    args = parser.parse_args()
    ir_dir = args.ir_dir or Path("ocr_router_out") / args.pdf.stem / "annual_ir"
    result = audit(args.pdf, ir_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
