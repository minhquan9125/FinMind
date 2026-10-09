"""Locate audited financial pages and parse coded or bank statement tables.

The reviewed FPT 2024 fixture remains available for comparisons; the runtime
classification and extraction paths use the visible PDF content.
"""

from __future__ import annotations

import copy
import hashlib
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
ACCOUNTING_TEMPLATE = (Path(__file__).resolve().parents[1] / "templates"
                       / "financial-template-lines.json")


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFD", value).casefold().replace("đ", "d")
    return "".join(char for char in value if not unicodedata.combining(char))


def financial_page_class(number: int, section: str | None, digest: str,
                         text: str, running_header: str = "") -> str | None:
    """Classify financial pages from visible titles, regardless of PDF hash/page."""

    # Bank reports may place the statement title in a running header above a
    # multi-column spread.  Inspect that narrow band before the body text.
    header_lines = running_header.splitlines()
    first_line = _plain(header_lines[0]) if header_lines else ""
    header = _plain(" ".join(header_lines[:4])) if header_lines else ""
    # Some PDF fonts duplicate every glyph in the running title.
    header_single = re.sub(r"(.)\1", r"\1", header)
    first_single = re.sub(r"(.)\1", r"\1", first_line)
    if ("thuyet minh bao cao tai chinh hop nhat" in first_line or
            "thuyet minh bao cao tai chinh hop nhat" in first_single):
        return "notes"
    if len(header_lines) > 1 and "thuyet minh bao cao tai chinh hop nhat" in _plain(header_lines[1]):
        return "notes"
    # Only a financial running header warrants looking at the following title
    # lines. Otherwise a mention in the body could change the page class.
    if not ("bao cao tai chinh" in first_line or
            "thanh cong noi tiep cua tech" in first_line):
        header = first_line
        header_single = first_single
    if "bao cao ket qua hoat dong hop nhat" in header or "bao cao ket qua hoat dong hop nhat" in header_single:
        return "income_statement"
    if "bao cao tinh hinh tai chinh hop nhat" in header or "bao cao tinh hinh tai chinh hop nhat" in header_single:
        return "balance_sheet"
    if "bao cao luu chuyen tien te hop nhat" in header or "bao cao luu chuyen tien te hop nhat" in header_single:
        return "cash_flow"
    if "thuyet minh bao cao tai chinh hop nhat" in header or "thuyet minh bao cao tai chinh hop nhat" in header_single:
        return "notes"
    if "bao cao kiem toan doc lap" in header:
        return "auditor_report"
    if ("bao cao tai chinh" in first_line or "thanh cong noi tiep cua tech" in first_line) and any(
            _plain(line.strip()) == "thong tin chung" for line in header_lines[:3]):
        return "company_information"

    # Scan/OCR pages often start with a company name or form code. Search the
    # first ten main-area lines, requiring a title at the start of its line.
    lines = [_plain(line.strip()).lstrip("#*| ") for line in text.splitlines() if line.strip()][:10]
    if lines and lines[0].startswith("bao cao tai chinh") and any(
            "noi dung trang" in line for line in lines[:6]):
        return "toc"
    titles = (
        (r"^bao cao (?:kiem toan|(?:ket qua cong tac )?soat xet)\b", "auditor_report"),
        (r"^ket luan cua kiem toan vien\b", "auditor_report"),
        (r"^(?:bang can doi ke toan|bao cao tinh hinh tai chinh)\b", "balance_sheet"),
        (r"^bao cao ket qua (?:hoat dong )?kinh doanh\b", "income_statement"),
        (r"^bao cao luu chuyen tien te\b", "cash_flow"),
        (r"^thuyet minh bao cao tai chinh\b", "notes"),
        (r"^thong tin ve doanh nghiep\b", "company_information"),
        (r"^bao cao cua ban (?:tong )?giam doc\b", "other"),
    )
    for line in lines:
        for pattern, kind in titles:
            if re.search(pattern, line):
                return kind
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


_BANK_AMOUNT = re.compile(r"(?:\(?-?[\d.,]+\)?|[-–—])$")
_BANK_YEAR = re.compile(r"(?:31/12/)?20\d{2}$")


def _bank_panel_kind(page: Any, left: float, right: float,
                     header_top: float, fallback: str) -> tuple[str | None, str | None, bool]:
    lines = (page.crop((left, 0, right, header_top)).extract_text() or "").splitlines()
    # The first line is usually running furniture, sometimes shared by both
    # printed pages. Read the actual statement caption beneath it.
    captions = lines[1:6]
    normalized = _plain(" ".join(captions))
    if "thuyet minh bao cao tai chinh" in normalized:
        return None, None, False
    patterns = (
        ("bao cao ket qua hoat dong", "income_statement"),
        ("bao cao luu chuyen tien te", "cash_flow"),
        ("bao cao tinh hinh tai chinh", "balance_sheet"),
        ("chi tieu ngoai bao cao tinh hinh tai chinh", "balance_sheet"),
    )
    for phrase, kind in patterns:
        if phrase in normalized:
            title = next((line.strip() for line in captions if phrase in _plain(line)), None)
            return kind, title, "tiep theo" in normalized
    return fallback, None, False


def _bank_panel_table(page: Any, words: list[dict[str, Any]], left: float,
                      right: float, kind: str, sequence: int,
                      header_index: int = 0) -> tuple[TableBlock, list[float]]:
    """Read one printed bank statement page from aligned note and year columns."""
    panel_width = right - left
    panel_words = [word for word in words if left + 5 <= word["x0"] < right - 3]
    lines = _line_groups(panel_words)
    headers = []
    for line in lines:
        if line[0]["top"] > page.height * .88:
            break
        years = sorted((word for word in line if _BANK_YEAR.fullmatch(word["text"])
                        and word["x0"] > left + panel_width * .55),
                       key=lambda word: word["x0"])
        nearby_note = any(abs(word["top"] - line[0]["top"]) < 18
                          and _plain(word["text"]).startswith("thuyet")
                          and left + panel_width * .4 < word["x0"] < years[0]["x0"] - 35
                          for word in panel_words) if years else False
        if len(years) == 2 and years[1]["x0"] - years[0]["x0"] > 55 and nearby_note:
            headers.append((line[0]["top"], years))
    if len(headers) <= header_index:
        raise ValueError("Không tìm thấy hai kỳ số liệu ở đầu bảng ngân hàng")
    header_y, years = headers[header_index]
    next_header_y = (headers[header_index + 1][0] - 5
                     if header_index + 1 < len(headers) else page.height * .96)
    note_words = [word for word in panel_words
                  if abs(word["top"] - header_y) < 18
                  and _plain(word["text"]).startswith("thuyet")
                  and left + panel_width * .4 < word["x0"] < years[0]["x0"] - 35]
    if not note_words:
        raise ValueError("Không tìm thấy cột Thuyết minh")
    note_x = note_words[0]["x0"]
    label_right = note_x - 12
    unit_words: list[list[dict[str, Any]]] = []
    for year in years:
        unit_words.append([word for word in panel_words
                           if header_y + 3 < word["top"] < header_y + 22
                           and year["x0"] - 10 <= word["x0"] <= year["x1"] + 5
                           and _plain(word["text"]) in ("trieu", "dong")])
    header_bottom = max([word["bottom"] for word in years]
                        + [word["bottom"] for group in unit_words for word in group],
                        default=years[0]["bottom"])

    numeric_lines: list[dict[str, Any]] = []
    for line in lines:
        y = line[0]["top"]
        if y < header_bottom + 4 or y >= next_header_y:
            continue
        cells = [[word for word in line if _BANK_AMOUNT.fullmatch(word["text"])
                  and abs(word["x1"] - year["x1"]) < 9]
                 for year in years]
        if len(cells[0]) == len(cells[1]) == 1:
            numeric_lines.append({"y": y, "values": [cells[0][0], cells[1][0]],
                                  "labels": [], "notes": []})
    if len(numeric_lines) < 5:
        raise ValueError("Bảng ngân hàng có quá ít dòng số khớp hai cột")

    last_bottom = numeric_lines[-1]["values"][0]["bottom"] + 9
    value_ids = {id(word) for row in numeric_lines for word in row["values"]}
    other_lines = _line_groups([word for word in panel_words
                                if header_bottom + 4 <= word["top"] < last_bottom
                                and id(word) not in value_ids])
    loose: list[list[dict[str, Any]]] = []
    for line in other_lines:
        label_words = [word for word in line if word["x0"] < label_right]
        note_items = [word for word in line if note_x - 15 <= word["x0"]
                      < years[0]["x0"] - 20]
        for items, field in ((label_words, "labels"), (note_items, "notes")):
            if not items:
                continue
            target = min(numeric_lines, key=lambda row: abs(row["y"] - items[0]["top"]))
            if field in ("labels", "notes"):
                preceding = [row for row in numeric_lines
                             if 0 <= items[0]["top"] - row["y"] <= 6]
                if preceding:
                    target = preceding[-1]
            # A wrapped parenthetical label belongs to the preceding row.
            if (field == "labels" and items[0]["text"].startswith(("(", "“"))
                    and numeric_lines.index(target) > 0
                    and items[0]["top"] < target["y"]):
                target = numeric_lines[numeric_lines.index(target) - 1]
            if abs(target["y"] - items[0]["top"]) <= 13:
                target[field].extend(items)
            elif field == "labels":
                loose.append(items)

    rows: list[Row] = []
    used_words: list[dict[str, Any]] = []
    for item in numeric_lines:
        label_words = sorted(item["labels"], key=lambda word: (word["top"], word["x0"]))
        if not label_words and item is not numeric_lines[-1]:
            raise ValueError(f"Dòng số tại y={item['y']:.1f} thiếu nhãn tương ứng")
        first, second = item["values"]
        note_items = sorted(item["notes"], key=lambda word: (word["top"], word["x0"]))
        row_words = label_words + note_items + [first, second]
        used_words.extend(row_words)
        rows.append({"id": f"r{len(rows) + 1}", "code": None,
                     "label_raw": " ".join(_printed_lines(label_words)),
                     "note": " ".join(_printed_lines(note_items)) or None,
                     "indent": round(min(word["x0"] for word in label_words), 2)
                     if label_words else None,
                     "bbox": _word_box(row_words),
                     "cells": {"c1": {"raw": first["text"], "bbox": _word_box([first])},
                               "c2": {"raw": second["text"], "bbox": _word_box([second])}}})
    for items in loose:
        used_words.extend(items)
        rows.append({"id": "", "code": None,
                     "label_raw": " ".join(_printed_lines(items)), "note": None,
                     "indent": round(min(word["x0"] for word in items), 2),
                     "bbox": _word_box(items), "cells": {}})
    rows.sort(key=lambda row: (row["bbox"][1], row["bbox"][0]))
    for position, row in enumerate(rows, 1):
        row["id"] = f"r{position}"
    if len(rows) < 5:
        raise ValueError("Bảng ngân hàng không đủ dòng có nhãn và ô")

    # Keep headers and section captions as text blocks. Exclude only the row
    # area after every visible word in it has a row/note/cell destination.
    row_bbox = [round(left + 5, 2), round(min(word["top"] for word in used_words) - 2, 2),
                round(right - 3, 2), round(max(word["bottom"] for word in used_words) + 2, 2)]
    body_words = [word for word in panel_words
                  if row_bbox[1] <= word["top"] < row_bbox[3]]
    represented = set(map(id, used_words))
    missing = [word for word in body_words if id(word) not in represented]
    if missing:
        raise ValueError(f"Còn {len(missing)} từ trong vùng dòng chưa gắn vào ô: "
                         + " ".join(word["text"] for word in missing[:8]))

    columns: list[Column] = []
    for position, (year, unit) in enumerate(zip(years, unit_words), 1):
        unit_line = " ".join(word["text"] for word in sorted(unit, key=lambda word: word["x0"]))
        columns.append({"key": f"c{position}",
                        "header_lines": [year["text"]] + ([unit_line] if unit_line else []),
                        "bbox": _word_box([year] + unit)})
    panel_kind, title, continued = _bank_panel_kind(page, left, right, header_y, kind)
    if panel_kind is None:
        raise ValueError("Vùng chữ thuộc thuyết minh, không phải ba báo cáo chính")
    table_words = used_words + years + [word for group in unit_words for word in group]
    table: TableBlock = {"id": f"p{page.page_number}-t{sequence}", "type": "table",
                         "title": title, "continued": continued,
                         "logical_table_id": panel_kind,
                         "bbox": _word_box(table_words), "unit_text": None,
                         "columns": columns, "rows": rows}
    return table, row_bbox


def _bank_statement_tables(page: Any, kind: str) -> tuple[list[dict[str, Any]], list[list[float]]]:
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    middle = page.width * .5
    tables: list[dict[str, Any]] = []
    exclude: list[list[float]] = []
    for left, right in ((0, middle), (middle, page.width)):
        for header_index in range(3):
            try:
                table, box = _bank_panel_table(page, words, left, right, kind,
                                               len(tables) + 1, header_index)
            except ValueError:
                continue
            tables.append(table)
            exclude.append(box)
    return tables, exclude


def statement_tables(page: Any, digest: str, kind: str) -> tuple[list[dict[str, Any]], list[list[float]] | None]:
    """Parse coded and bank statement layouts from the current PDF page."""
    if kind not in ("balance_sheet", "income_statement", "cash_flow"):
        return [], None
    try:
        table, row_bbox = _coded_statement_table(page, kind)
    except ValueError:
        bank_tables, bank_boxes = _bank_statement_tables(page, kind)
        return bank_tables, bank_boxes or None
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


def financial_index(documents: list[dict[str, Any]], digest: str,
                    template_path: Path | None = None) -> dict[str, Any]:
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
        unresolved_cells = sum(
            cell.get("raw") is None
            for block in page["blocks"] if block["type"] == "table"
            for row in block["rows"] for cell in row["cells"].values())
        if has_structured_table:
            structured.append(number)
            if unresolved_cells:
                needs_review.append({"pdf_page": number,
                                     "reason": "cell_votes_disagree_or_unreadable",
                                     "unresolved_cells": unresolved_cells})
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
    checks, skipped_checks, failed_pages, template_id = evaluate_accounting(documents, template_path)
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
        "arithmetic_template_sha256": hashlib.sha256(
            _accounting_template_path(template_path).read_bytes()).hexdigest(),
        "notes_text_only_ranges": compact_page_ranges(text_only_notes),
        "file_pattern": "p-{page:03d}.ir.json",
        "coverage_note": "Notes without table blocks preserve text; their tables are not yet verified as rows and cells.",
    }


# Accounting checks use the versioned repository template without changing IR cells.
_ACCOUNTING_STATEMENTS = {"balance_sheet", "income_statement", "cash_flow"}


def _accounting_template_path(template_path: Path | None = None) -> Path:
    path = (template_path or ACCOUNTING_TEMPLATE).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Thiếu template BCTC: {path}")
    return path


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


def _load_accounting_template(template_path: Path | None = None) -> dict[str, Any]:
    template = json.loads(_accounting_template_path(template_path).read_text(encoding="utf-8"))
    seen: set[tuple[str, str, str]] = set()
    for line in template["template_lines"]:
        key = (line["statement"], line["parent"], line["code"])
        if line["statement"] not in _ACCOUNTING_STATEMENTS or key in seen or line["sign"] not in (-1, 1):
            raise ValueError(f"template_lines không hợp lệ: {key}")
        seen.add(key)
    return template


def evaluate_accounting(documents: list[dict[str, Any]], template_path: Path | None = None
                        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int], str]:
    """Evaluate template sums and cross-statement checks by year, preserving missing data."""
    template = _load_accounting_template(template_path)
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
