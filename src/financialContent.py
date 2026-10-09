"""Locate audited financial pages and reuse reviewed FPT statement tables.

The reviewed table fixture is only applied to the exact FPT 2024 PDF SHA-256.
Other reports retain their source text until their tables are reviewed.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from ir_types import Column, Row, TableBlock
from reportContent import FPT_2024_SHA256


REVIEWED_TABLES = (Path(__file__).resolve().parents[1] / "Document IR"
                   / "fpt-2024-reviewed-financial-tables.json")
FPT_FINANCIAL_FIRST = 143
FPT_FINANCIAL_LAST = 209


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFD", value).casefold().replace("đ", "d")
    return "".join(char for char in value if not unicodedata.combining(char))


def financial_page_class(number: int, section: str | None, digest: str,
                         text: str) -> str | None:
    """Classify the reviewed sample exactly; classify other PDFs conservatively."""
    if digest == FPT_2024_SHA256:
        if not FPT_FINANCIAL_FIRST <= number <= FPT_FINANCIAL_LAST:
            return None
        if number == 143:
            return "toc"
        if number == 144:
            return "company_information"
        if number == 145:
            return "other"  # Management's responsibility for the statements.
        if number in (146, 147):
            return "auditor_report"
        if 148 <= number <= 152:
            return "balance_sheet"
        if 153 <= number <= 154:
            return "income_statement"
        if 155 <= number <= 156:
            return "cash_flow"
        return "notes"

    # The caller supplies text from the main page area, excluding the sidebar.
    # A heading must be at the top of that area; a TOC mention is insufficient.
    lines = [_plain(line.strip()) for line in text.splitlines() if line.strip()]
    heading = lines[0] if lines else ""
    if heading.startswith("bao cao kiem toan"):
        return "auditor_report"
    if heading.startswith("bang can doi ke toan"):
        return "balance_sheet"
    if heading.startswith("bao cao ket qua hoat dong kinh doanh"):
        return "income_statement"
    if heading.startswith("bao cao luu chuyen tien te"):
        return "cash_flow"
    if heading.startswith("thuyet minh bao cao tai chinh"):
        return "notes"
    if heading.startswith("thong tin ve doanh nghiep"):
        return "company_information"
    if heading.startswith("bao cao cua ban tong giam doc"):
        return "other"
    if (heading.startswith("bao cao tai chinh") and
            any("noi dung trang" in line for line in lines[:6])):
        return "toc"
    return None


@lru_cache(maxsize=1)
def _reviewed_tables() -> dict[int, dict[str, Any]]:
    document = json.loads(REVIEWED_TABLES.read_text(encoding="utf-8"))
    result: dict[int, dict[str, Any]] = {}
    for group in document["tables"]:
        for page in group["pages"]:
            if page["source"]["document_sha256"] != FPT_2024_SHA256:
                raise ValueError("Bảng FPT đã rà soát không khớp SHA-256 PDF mẫu")
            if page["page"] in result:
                raise ValueError(f"Trùng bảng đã rà soát ở trang {page['page']}")
            if group["table_id"] != "company_information":
                result[page["page"]] = page["blocks"][0]
    return result


def reviewed_statement_tables(number: int, digest: str) -> list[dict[str, Any]]:
    if digest != FPT_2024_SHA256:
        return []
    table = _reviewed_tables().get(number)
    return [copy.deepcopy(table)] if table is not None else []


def _word_box(words: list[dict[str, Any]]) -> list[float]:
    return [round(min(word["x0"] for word in words), 2),
            round(min(word["top"] for word in words), 2),
            round(max(word["x1"] for word in words), 2),
            round(max(word["bottom"] for word in words), 2)]


def _line_groups(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) < 4:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def _printed_lines(words: list[dict[str, Any]]) -> list[str]:
    return [" ".join(word["text"] for word in sorted(line, key=lambda item: item["x0"]))
            for line in _line_groups(words)]


def _coded_statement_table(page: Any, kind: str) -> tuple[TableBlock, list[float]]:
    """Locate coded rows from printed headers and aligned year columns."""
    number = page.page_number
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    header_lines = _line_groups([word for word in words
                                 if word["top"] < page.height * .35
                                 and word["x0"] >= page.width * .22])
    header = next((line for line in header_lines
                   if any(word["text"] == "Mã" for word in line)
                   and any(word["text"] == "Thuyết" for word in line)
                   and len([word for word in line if re.fullmatch(r"20\d{2}", word["text"])]) == 2), None)
    if header is None:
        raise ValueError(f"BCTC trang {number}: không tìm thấy tiêu đề cột Mã số/Thuyết minh/2 năm")
    code_header = next(word for word in header if word["text"] == "Mã")
    note_header = next(word for word in header if word["text"] == "Thuyết")
    years = sorted((word for word in header if re.fullmatch(r"20\d{2}", word["text"])),
                   key=lambda word: word["x0"])
    codes = sorted((word for word in words
                    if abs(word["x0"] - code_header["x0"]) < 22
                    and header[0]["bottom"] + 5 <= word["top"] < page.height * .9
                    and re.fullmatch(r"\d{2,3}[a-z]?", word["text"])),
                   key=lambda word: word["top"])
    if len(codes) < 3:
        raise ValueError(f"BCTC trang {number}: không tìm đủ mã dòng")

    headers: list[Column] = [{"key": f"c{i + 1}", "header_lines": [year["text"]],
                              "bbox": _word_box([year])} for i, year in enumerate(years)]

    rows: list[Row] = []
    all_row_words: list[dict[str, Any]] = []
    for position, code in enumerate(codes):
        top = code["top"] - 4
        bottom = (codes[position + 1]["top"] - 3 if position + 1 < len(codes)
                  else min(page.height * .9, code["top"] + 45))
        band = [word for word in words if code_header["x0"] - 4 <= word["x0"] < page.width
                and top <= word["top"] < bottom]
        values = [[word for word in band if abs(word["x1"] - year["x1"]) < 10]
                  for year in years]
        value_words = values[0] + values[1]
        notes = [word for word in band if note_header["x0"] - 10 <= word["x0"]
                 < years[0]["x0"] - 65 and word not in value_words]
        labels = [word for word in band if code_header["x1"] + 10 <= word["x0"]
                  < note_header["x0"] - 10 and word not in value_words]
        first, second = values
        if not labels or len(first) != 1 or len(second) != 1:
            raise ValueError(f"BCTC trang {number}, mã {code['text']}: thiếu nhãn hoặc giá trị")
        if any(not re.fullmatch(r"\(?[\d.]+\)?|-", word["text"])
               for word in first + second):
            raise ValueError(f"BCTC trang {number}, mã {code['text']}: ô số không rõ")

        label_lines = [(" ".join(word["text"] for word in sorted(group, key=lambda w: w["x0"])),
                        group) for group in _line_groups(labels)]
        # Standalone section headings inside a statement are kept as rows
        # without code or cells, rather than appended to the preceding label.
        main_label: list[str] = []
        section_lines: list[tuple[str, list[dict[str, Any]]]] = []
        for line, line_words in label_lines:
            is_section = (line_words[0]["top"] > code["top"] + 8
                          and (line.endswith(":") or
                               (line == line.upper() and any(char.isalpha() for char in line))))
            if is_section:
                section_lines.append((line, line_words))
            else:
                main_label.append(line)
        if not main_label:
            raise ValueError(f"BCTC trang {number}, mã {code['text']}: thiếu nhãn chính")
        main_words = [code] + [word for word in labels
                               if not any(word in section_words for _, section_words in section_lines)]
        main_words += notes + first + second
        all_row_words.extend(main_words)
        rows.append({"id": f"r{len(rows) + 1}", "code": code["text"],
                     "label_raw": " ".join(main_label),
                     "note": " ".join(_printed_lines(notes)) or None,
                     "bbox": _word_box(main_words),
                     "cells": {"c1": {"raw": first[0]["text"], "bbox": _word_box(first)},
                               "c2": {"raw": second[0]["text"], "bbox": _word_box(second)}}})
        for line, line_words in section_lines:
            all_row_words.extend(line_words)
            rows.append({"id": f"r{len(rows) + 1}", "code": None,
                         "label_raw": line, "note": None,
                         "bbox": _word_box(line_words), "cells": {}})

    titles = {"balance_sheet": "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT",
              "income_statement": "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
              "cash_flow": "BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT"}
    table_bbox = _word_box(all_row_words + [word for word in words
                                              if code_header["x0"] - 15 <= word["x0"] < page.width
                                              and header[0]["top"] - 5 <= word["top"] < codes[0]["top"]])
    row_bbox = [round(code_header["x0"] - 4, 2), round(codes[0]["top"] - 4, 2),
                round(max(year["x1"] for year in years) + 5, 2),
                round(max(word["bottom"] for word in all_row_words) + 1, 2)]
    table: TableBlock = {
        "id": f"p{number}-t1", "type": "table", "title": titles[kind],
        "continued": any("tiep theo" in _plain(line) for line in
                         _printed_lines([word for word in words if word["top"] < header[0]["top"]])),
        "logical_table_id": kind,
        "bbox": table_bbox, "unit_text": "Đơn vị: VNĐ",
        "columns": headers, "rows": rows,
    }
    return table, row_bbox


def statement_tables(page: Any, digest: str, kind: str) -> tuple[list[dict[str, Any]], list[list[float]] | None]:
    """Use the reviewed 2024 override or parse a coded statement dynamically."""
    if digest == FPT_2024_SHA256:
        return reviewed_statement_tables(page.page_number, digest), None
    if kind not in ("balance_sheet", "income_statement", "cash_flow"):
        return [], None
    try:
        table, row_bbox = _coded_statement_table(page, kind)
    except ValueError:
        return [], None  # Keep the page as text and flag it in table/index.json.
    return [table], [row_bbox]


def compact_page_ranges(numbers: list[int]) -> list[dict[str, int]]:
    """Store consecutive PDF pages once while keeping nonconsecutive gaps."""
    result: list[dict[str, int]] = []
    for number in sorted(set(numbers)):
        if result and result[-1]["end"] + 1 == number:
            result[-1]["end"] = number
        else:
            result.append({"start": number, "end": number})
    return result


def expand_page_ranges(ranges: list[dict[str, int]]) -> list[int]:
    return [number for item in ranges
            for number in range(item["start"], item["end"] + 1)]


_NOTE_TITLE = re.compile(r"^(\d{1,2})(\.?)\s+([^\n]+)")
_REPEATED_HEADINGS = (
    "THUYẾT MINH BÁO CÁO TÀI CHÍNH HỢP NHẤT",
    "THUYẾT MINH BÁO CÀO TÀI CHÍNH HỢP NHẤT",
    "CHO NĂM TÀI CHÍNH KẾT THÚC",
)


def _page_topics(page: dict[str, Any]) -> list[str]:
    """Use visible note headings; never infer a topic from table cell values."""
    topics: list[str] = []
    for block in page["blocks"]:
        if block["type"] not in ("heading", "paragraph"):
            continue
        if block.get("bbox") is None or block["bbox"][0] < page["page_size"]["width"] * 0.22:
            continue
        value = " ".join(block.get("text", "").split()).strip()
        match = _NOTE_TITLE.match(value)
        if not match or int(match.group(1)) > 38:
            continue
        title = match.group(3).strip()
        if len(title) < 4 or not any(char.isalpha() for char in title):
            continue
        if not match.group(2) and title != title.upper():
            continue
        topic = f"{match.group(1)}. {title}"
        if topic not in topics:
            topics.append(topic)
    return topics


def _page_title(page: dict[str, Any], current_topic: str | None,
                topics: list[str]) -> str:
    if page["page_class"] == "notes":
        if topics:
            return topics[0]
        appendix = next((" ".join(block["text"].split()) for block in page["blocks"]
                         if block["type"] in ("heading", "paragraph") and block.get("bbox")
                         and block["bbox"][0] >= page["page_size"]["width"] * 0.22
                         and _plain(block["text"]).startswith("phu luc")), None)
        if appendix:
            return appendix
        for block in page["blocks"]:
            if block["type"] != "heading":
                continue
            if block.get("bbox") is None or block["bbox"][0] < page["page_size"]["width"] * 0.22:
                continue
            value = " ".join(block.get("text", "").split()).strip()
            if value and not any(value.startswith(prefix) for prefix in _REPEATED_HEADINGS):
                return value
        return current_topic or "Thuyết minh báo cáo tài chính hợp nhất"
    return next((" ".join(block["text"].split()) for block in page["blocks"]
                 if block["type"] == "heading" and block.get("bbox")
                 and block["bbox"][0] >= page["page_size"]["width"] * 0.22),
                page["page_class"] or "Khác")


def financial_index(documents: list[dict[str, Any]], digest: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    page_index: list[dict[str, Any]] = []
    numbers: list[int] = []
    structured: list[int] = []
    needs_review: list[dict[str, Any]] = []
    text_only_notes: list[int] = []
    current_topic: str | None = None
    for page in documents:
        number = page["page"]
        kind = page["page_class"] or "other"
        numbers.append(number)
        if sections and sections[-1]["page_class"] == kind and sections[-1]["end"] + 1 == number:
            sections[-1]["end"] = number
        else:
            sections.append({"page_class": kind, "start": number, "end": number})
        has_structured_table = any(block["type"] == "table" and block["rows"]
                                   for block in page["blocks"])
        if has_structured_table:
            structured.append(number)
        elif kind == "notes":
            text_only_notes.append(number)
        elif kind in ("balance_sheet", "income_statement", "cash_flow"):
            needs_review.append({"pdf_page": number, "reason": "statement_columns_or_rows_unverified"})
        topics = _page_topics(page) if kind == "notes" else []
        if topics:
            current_topic = topics[-1]
        appendix = next((" ".join(block["text"].split()) for block in page["blocks"]
                         if kind == "notes" and block["type"] in ("heading", "paragraph")
                         and block.get("bbox")
                         and block["bbox"][0] >= page["page_size"]["width"] * 0.22
                         and _plain(block.get("text", "")).startswith("phu luc")), None)
        if appendix:
            current_topic = appendix
        if kind != "notes":
            current_topic = None
        page_index.append({
            "pdf_page": number,
            "printed_page": page.get("printed_page"),
            "file": f"p-{number:03d}.ir.json",
            "page_class": kind,
            "title": _page_title(page, current_topic, topics),
            "topics": topics,
            "has_structured_table": has_structured_table,
            "needs_review": any(item["pdf_page"] == number for item in needs_review),
        })
    checks, skipped_checks, failed_pages, template_id = evaluate_accounting(documents)
    for target_page in sorted(failed_pages):
        if not any(item["pdf_page"] == target_page for item in needs_review):
            invalid = any(item["name"] == "invalid_numeric_cell" and item["page"] == target_page
                          for item in skipped_checks)
            needs_review.append({"pdf_page": target_page,
                                 "reason": "invalid_numeric_cell" if invalid else "arithmetic_check_failed"})
    for entry in page_index:
        entry["needs_review"] = any(item["pdf_page"] == entry["pdf_page"] for item in needs_review)
    return {
        "document_sha256": digest,
        "scope": "audited_financial_statements",
        "pages": len(documents),
        "page_ranges": compact_page_ranges(numbers),
        "sections": sections,
        "page_index": page_index,
        "structured_table_ranges": compact_page_ranges(structured),
        "needs_review": needs_review,
        "arithmetic_checks": checks,
        "arithmetic_checks_skipped": skipped_checks,
        "arithmetic_template_id": template_id,
        "notes_text_only_ranges": compact_page_ranges(text_only_notes),
        "file_pattern": "p-{page:03d}.ir.json",
        "coverage_note": "Notes without table blocks preserve text; their tables are not yet verified as rows and cells.",
    }


# Accounting checks use the shared workspace template without changing IR cells.
_ACCOUNTING_STATEMENTS = {"balance_sheet", "income_statement", "cash_flow"}


def _accounting_template_path() -> Path:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / "templates" / "financial-template-lines.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Thiếu templates/financial-template-lines.json trong cây workspace")


def _parse_accounting_number(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    text = raw.strip().replace("\u00a0", "")
    if text in ("-", "–", "—"):
        return Decimal(0)
    if text.startswith("(") != text.endswith(")"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(".", "").replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


def _accounting_period_year(header_lines: list[str]) -> str | None:
    years = re.findall(r"\b20\d{2}\b", " ".join(header_lines))
    return years[-1] if years else None


def _load_accounting_template() -> dict[str, Any]:
    template = json.loads(_accounting_template_path().read_text(encoding="utf-8"))
    seen: set[tuple[str, str, str]] = set()
    for line in template["template_lines"]:
        key = (line["statement"], line["parent"], line["code"])
        if line["statement"] not in _ACCOUNTING_STATEMENTS or key in seen or line["sign"] not in (-1, 1):
            raise ValueError(f"template_lines không hợp lệ: {key}")
        seen.add(key)
    return template


def evaluate_accounting(documents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int], str]:
    """Evaluate template sums and cross-statement checks by year, preserving missing data."""
    template = _load_accounting_template()
    values: dict[str, dict[str, dict[str, tuple[Decimal, int]]]] = defaultdict(lambda: defaultdict(dict))
    invalid_cells: list[dict[str, Any]] = []
    failed_pages: set[int] = set()
    for page in documents:
        kind = page["page_class"]
        if kind not in _ACCOUNTING_STATEMENTS:
            continue
        for block in page["blocks"]:
            if block["type"] != "table":
                continue
            years = {column["key"]: _accounting_period_year(column["header_lines"])
                     for column in block["columns"]}
            for row in block["rows"]:
                code = row.get("code")
                if not code:
                    continue
                for column, cell in row["cells"].items():
                    year = years.get(column)
                    number = _parse_accounting_number(cell.get("raw"))
                    if year is not None and number is None and cell.get("raw") is not None:
                        invalid_cells.append({"name": "invalid_numeric_cell", "year": year,
                                              "page": page["page"], "code": code,
                                              "column": column, "raw": cell["raw"]})
                        failed_pages.add(page["page"])
                    if year is not None and number is not None:
                        previous = values[kind][year].get(code)
                        if previous is not None and previous[0] != number:
                            raise ValueError(f"Trùng mã {kind}/{year}/{code} với hai giá trị")
                        values[kind][year][code] = (number, page["page"])

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in template["template_lines"]:
        if not line["is_memo"]:
            groups[line["statement"], line["parent"]].append(line)
    checks: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = invalid_cells.copy()
    all_years = sorted({year for periods in values.values() for year in periods})
    for (kind, parent), children in groups.items():
        for year in all_years:
            rows = values.get(kind, {}).get(year, {})
            codes = [parent, *(child["code"] for child in children)]
            missing = [code for code in codes if code not in rows]
            name = f"{kind}:{parent}"
            if missing:
                skipped.append({"name": name, "year": year, "missing_codes": missing})
                continue
            actual = rows[parent][0]
            expected = sum((rows[child["code"]][0] * child["sign"] for child in children), Decimal(0))
            passed = abs(actual - expected) <= 1
            pages = sorted({rows[code][1] for code in codes})
            checks.append({"name": name, "year": year, "passed": passed,
                           "result_code": parent, "actual": str(actual), "expected": str(expected),
                           "pdf_pages": pages, "source": "template_lines"})
            if not passed:
                failed_pages.update(pages)

    for rule in template["cross_statement_rules"]:
        left = rule["left"]
        right = rule["right"]
        for year in all_years:
            right_year = str(int(year) + rule.get("right_year_offset", 0))
            lhs = values.get(left["statement"], {}).get(year, {}).get(left["code"])
            rhs = values.get(right["statement"], {}).get(right_year, {}).get(right["code"])
            if lhs is None or rhs is None:
                missing = []
                if lhs is None:
                    missing.append(f"{left['statement']}:{left['code']}:{year}")
                if rhs is None:
                    missing.append(f"{right['statement']}:{right['code']}:{right_year}")
                skipped.append({"name": rule["name"], "year": year, "missing_codes": missing})
                continue
            passed = abs(lhs[0] - rhs[0]) <= 1
            pages = sorted({lhs[1], rhs[1]})
            checks.append({"name": rule["name"], "year": year, "passed": passed,
                           "actual": str(lhs[0]), "expected": str(rhs[0]),
                           "pdf_pages": pages, "source": "cross_statement"})
            if not passed:
                failed_pages.update(pages)
    return checks, skipped, failed_pages, template["template_id"]
