"""Locate audited financial pages and parse coded or bank statement tables.

Classification and extraction use the visible PDF content.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ir_types import Column, Row, TableBlock


ACCOUNTING_TEMPLATE = (Path(__file__).resolve().parents[1] / "templates"
                       / "financial-template-lines.json")
TT99_ACCOUNTING_TEMPLATE = (Path(__file__).resolve().parents[1] / "templates"
                            / "tt99-2025-b01-b02-b03.json")


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
    # OCR engines may emit columns before headings (or push the heading after
    # the rows). A contents page is still identifiable by its printed label.
    all_lines = [_plain(line.strip()).lstrip("#*| ") for line in text.splitlines() if line.strip()]
    if any(line in ("muc luc", "noi dung") for line in all_lines[:16]) and any(
            "bao cao ket qua hoat dong kinh doanh" in line or
            "bang can doi ke toan" in line or "bao cao luu chuyen tien te" in line
            for line in all_lines[:20]):
        return "toc"
    if lines and lines[0].startswith("bao cao tai chinh") and any(
            "noi dung trang" in line for line in lines[:6]):
        return "toc"
    titles = (
        (r"^bao cao (?:kiem toan|(?:ket qua cong tac )?soat xet)\b", "auditor_report"),
        (r"^ket luan cua kiem toan vien\b", "auditor_report"),
        (r"^(?:bang can doi ke toan|(?:bao|bang) cao tinh hinh tai chinh)\b", "balance_sheet"),
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
    # On scanned Vietnamese statements, OCR reading order can put the form
    # code/title well below the first ten lines. Require both independent
    # printed clues before classifying from the full page.
    form = " ".join(all_lines)
    if re.search(r"mau so b\s*0[1-5]\s*[-/]\s*(?:dn|tctd)", form):
        for line in all_lines:
            for pattern, kind in titles[:6]:
                if re.search(pattern, line):
                    return kind
    return None


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
    def value_heads(line: list[dict[str, Any]]) -> list[dict[str, Any]]:
        dated = sorted((word for word in line
                        if re.fullmatch(r"20\d{2}|\d{1,2}[./-]\d{1,2}[./-]20\d{2}",
                                        word["text"])), key=lambda word: word["x0"])
        if len(dated) == 2:
            return dated
        ordered = sorted(line, key=lambda word: word["x0"])
        result = []
        for position, word in enumerate(ordered[:-1]):
            phrase = _plain(word["text"] + " " + ordered[position + 1]["text"])
            if phrase in ("so cuoi", "so dau", "ky nay", "ky truoc",
                          "nam nay", "nam truoc"):
                last = ordered[position + 2] if phrase.startswith("so ") and position + 2 < len(ordered) else ordered[position + 1]
                if phrase.startswith("so ") and _plain(last["text"]) not in ("ky", "nam"):
                    continue
                result.append({**word, "text": " ".join(item["text"] for item in
                               ordered[position:ordered.index(last) + 1]),
                               "x1": last["x1"], "bottom": max(word["bottom"], last["bottom"])})
        return result if len(result) == 2 else []

    header = next((line for line in header_lines
                   if any(word["text"] == "Mã" for word in line)
                   and any(word["text"] == "Thuyết" for word in line)
                   and len(value_heads(line)) == 2), None)
    if header is None:
        raise ValueError(f"BCTC trang {number}: không tìm thấy Mã số/Thuyết minh/2 cột kỳ")
    code_header = next(word for word in header if word["text"] == "Mã")
    note_header = next(word for word in header if word["text"] == "Thuyết")
    years = sorted(value_heads(header), key=lambda word: word["x0"])
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
        # Preserve an aligned but malformed printed value. The page IR marks it
        # BAD_NUMBER_FORMAT so it cannot silently enter accounting checks.

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
    if kind == "balance_sheet":
        visible_title = next((line for line in _printed_lines(words)
                              if _plain(line).startswith("bao cao tinh hinh tai chinh")), None)
        if visible_title:
            titles[kind] = visible_title
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
_BANK_YEAR = re.compile(r"(?:\d{1,2}[./-]\d{1,2}[./-])?20\d{2}$")


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
            cell.get("raw") is None or cell.get("needs_review", False)
            for block in page["blocks"] if block["type"] == "table"
            for row in block["rows"] for cell in row["cells"].values())
        if has_structured_table:
            structured.append(number)
            if unresolved_cells:
                needs_review.append({"pdf_page": number,
                                     "reason": "cell_unreadable_or_needs_human_review",
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
    profile = _accounting_template_profile(documents)
    selected_template = _select_accounting_template_path(documents, template_path)
    checks, skipped_checks, failed_pages, template_id = evaluate_accounting(documents, template_path)
    soft_checks = _accounting_soft_checks(documents)
    cell_coverage = _accounting_cell_coverage(documents, selected_template, soft_checks)
    if template_id == "TEMPLATE_UNKNOWN":
        for page in documents:
            if page["page_class"] in _ACCOUNTING_STATEMENTS and not any(
                    item["pdf_page"] == page["page"] for item in needs_review):
                needs_review.append({"pdf_page": page["page"],
                                     "reason": "arithmetic_template_unknown"})
    for target_page in sorted(failed_pages):
        if not any(item["pdf_page"] == target_page for item in needs_review):
            unresolved = any(item["name"] == "period_unresolved" and item["page"] == target_page
                             for item in skipped_checks)
            invalid = any(item["name"] == "invalid_numeric_cell" and item["page"] == target_page
                          for item in skipped_checks)
            needs_review.append({"pdf_page": target_page,
                                 "reason": ("period_unresolved" if unresolved else
                                            "invalid_numeric_cell" if invalid else
                                            "arithmetic_check_failed")})
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
        **cell_coverage,
        "accounting_soft_checks": soft_checks,
        "accounting_template_profile": profile,
        "arithmetic_template_id": template_id,
        "arithmetic_template_sha256": (hashlib.sha256(
            selected_template.read_bytes()).hexdigest()
            if selected_template is not None else None),
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


_MONEY_GROUPS = re.compile(r"\d{1,3}(?:[.,]\d{3})*")


def parse_money(raw: str | None) -> tuple[Decimal | None, str | None]:
    """Parse whole VND amounts only after checking every thousands group."""
    if raw is None:
        return None, None
    text = raw.strip().replace("\u00a0", "").replace("\u202f", "")
    if text in ("-", "–", "—"):
        return Decimal(0), "PRINTED_DASH"
    if text.startswith("(") != text.endswith(")"):
        return None, "BAD_NUMBER_FORMAT"
    negative = text.startswith(("(", "-"))
    if text.startswith("("):
        text = text[1:-1]
    elif text.startswith("-"):
        text = text[1:]
    if not _MONEY_GROUPS.fullmatch(text):
        return None, "BAD_NUMBER_FORMAT"
    value = Decimal(text.replace(".", "").replace(",", ""))
    return (-value if negative else value), None


def _parse_accounting_number(raw: str | None) -> Decimal | None:
    return parse_money(raw)[0]


def flag_bad_financial_cells(document: dict[str, Any]) -> None:
    """Keep OCR text verbatim while excluding malformed cells from equations."""
    if document.get("page_class") not in _ACCOUNTING_STATEMENTS:
        return
    for block in document.get("blocks", []):
        if block.get("type") != "table":
            continue
        for row in block.get("rows", []):
            for cell in row.get("cells", {}).values():
                if parse_money(cell.get("raw"))[1] == "BAD_NUMBER_FORMAT":
                    cell["needs_review"] = True
                    cell["review_reason"] = "BAD_NUMBER_FORMAT"


def _printed_date(value: str) -> date | None:
    """Read a printed Vietnamese date without guessing missing day or month."""
    plain = _plain(value)
    patterns = (
        r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](20\d{2})(?!\d)",
        r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(20\d{2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, plain)
        if match:
            try:
                return date(int(match[3]), int(match[2]), int(match[1]))
            except ValueError:
                return None
    return None


def _accounting_period(header_lines: list[str], statement: str,
                       page_text: str = "") -> tuple[str, str, str] | None:
    """Return (period_end, period_type, role) for a printed value column.

    A relative heading is resolved only when the page states the reporting
    date. An unresolved column must never be checked against a guessed year.
    """
    header = _plain(" ".join(header_lines))
    period_type = "instant" if statement == "balance_sheet" else "duration"
    explicit_date = _printed_date(header)
    if explicit_date is not None:
        return explicit_date.isoformat(), period_type, "explicit"
    relative = None
    if ("so cuoi ky" in header or "so cuoi nam" in header or
            "ky nay" in header or "nam nay" in header):
        relative = "current"
    elif ("so dau ky" in header or "so dau nam" in header or
          "ky truoc" in header or "nam truoc" in header):
        relative = "comparative"
    # Prefer the reporting-date line over dates in unrelated notes or rows.
    context_lines = [_plain(line) for line in page_text.splitlines()[:20]]
    reporting_line = next((line for line in context_lines
                           if ("tai ngay" in line or "ket thuc ngay" in line or
                               "den ngay" in line)
                           and _printed_date(line) is not None), None)
    # "Từ ngày 01/01 đến ngày 31/03" states the period end after "đến ngày".
    # The first date in that line is the start, never the column period end.
    report_date_text = (reporting_line.rsplit("den ngay", 1)[-1]
                        if reporting_line and "den ngay" in reporting_line
                        else reporting_line)
    report_date = _printed_date(report_date_text) if report_date_text else None
    if relative is None:
        years = re.findall(r"\b20\d{2}\b", header)
        if not years:
            return None
        year = int(years[-1])
        scope = ("year_to_date" if "luy ke" in header else
                 "quarter" if "quy" in header else None)
        if report_date is not None and year == report_date.year:
            role = f"{scope}_current" if scope else "explicit"
            return report_date.isoformat(), period_type, role
        if report_date is not None and year == report_date.year - 1 and period_type == "duration":
            try:
                prior = report_date.replace(year=year)
            except ValueError:
                prior = report_date.replace(year=year, day=28)
            role = f"{scope}_comparative" if scope else "explicit"
            return prior.isoformat(), period_type, role
        role = f"{scope}_explicit" if scope else "explicit"
        return f"{year}-12-31", period_type, role

    if report_date is None:
        return None
    if relative == "current":
        resolved = report_date
    elif "so dau ky" in header or "so dau nam" in header:
        resolved = date(report_date.year - 1, 12, 31)
    else:
        try:
            resolved = report_date.replace(year=report_date.year - 1)
        except ValueError:  # 29 February comparison year
            resolved = report_date.replace(year=report_date.year - 1, day=28)
    return resolved.isoformat(), period_type, relative


def _load_accounting_template(template_path: Path | None = None) -> dict[str, Any]:
    template = json.loads(_accounting_template_path(template_path).read_text(encoding="utf-8"))
    seen: set[tuple[str, str, str]] = set()
    for line in template["template_lines"]:
        key = (line["statement"], line["parent"], line["code"])
        if (line["statement"] not in _ACCOUNTING_STATEMENTS or key in seen or
                line["sign"] not in (-1, 1) or
                not isinstance(line.get("optional", False), bool)):
            raise ValueError(f"template_lines không hợp lệ: {key}")
        seen.add(key)
    rule_names: set[str] = set()
    for rule in template.get("arithmetic_rules", []):
        name = rule.get("name")
        if (not name or name in rule_names or rule.get("statement") not in _ACCOUNTING_STATEMENTS or
                not rule.get("parent") or not rule.get("children")):
            raise ValueError(f"arithmetic_rules không hợp lệ: {rule}")
        rule_names.add(name)
        for child in rule["children"]:
            if not child.get("code") or child.get("sign") not in (-1, 1):
                raise ValueError(f"arithmetic_rules child không hợp lệ: {rule}")
    return template


def _accounting_numeric_values(
    documents: list[dict[str, Any]],
) -> dict[str, dict[tuple[str, str, str], dict[str, tuple[Decimal, int]]]]:
    """Collect readable coded statement values using the same period rules as checks."""
    result: dict[str, dict[tuple[str, str, str], dict[str, tuple[Decimal, int]]]] = defaultdict(
        lambda: defaultdict(dict))
    for page in documents:
        kind = page.get("page_class")
        if kind not in _ACCOUNTING_STATEMENTS:
            continue
        context = "\n".join(str(block.get("text", "")) for block in page.get("blocks", [])
                            if block.get("type") in ("heading", "paragraph"))
        for block in page.get("blocks", []):
            if block.get("type") != "table":
                continue
            periods = {column["key"]: _accounting_period(
                column.get("header_lines", []), kind, context)
                for column in block.get("columns", [])}
            for row in block.get("rows", []):
                code = row.get("code")
                if not code:
                    continue
                for column, cell in row.get("cells", {}).items():
                    period = periods.get(column)
                    if period is None or cell.get("needs_review", False):
                        continue
                    number = _parse_accounting_number(cell.get("raw"))
                    if number is not None:
                        previous = result[kind][period].get(str(code))
                        if previous is not None and previous[0] != number:
                            raise ValueError(f"Trùng mã {kind}/{period}/{code} với hai giá trị")
                        result[kind][period][str(code)] = (number, page["page"])
    return result


def _average_share_counts(
    documents: list[dict[str, Any]],
    statement_values: dict[str, dict[tuple[str, str, str], dict[str, tuple[Decimal, int]]]],
) -> tuple[dict[str, tuple[Decimal, int]], set[int]]:
    """Read the labeled weighted-average share row from EPS note text blocks."""
    years = sorted({period[0][:4]
                    for period, rows in statement_values.get("income_statement", {}).items()
                    if "61" in rows and "70" in rows}, reverse=True)
    shares: dict[str, tuple[Decimal, int]] = {}
    evidence_pages: set[int] = set()
    number_pattern = re.compile(r"\(?-?\d{1,3}(?:\.\d{3})+\)?|\(?-?\d+\)?")
    for page in documents:
        if page.get("page_class") != "notes":
            continue
        blocks = page.get("blocks", [])
        for label in blocks:
            if label.get("type") != "paragraph" or not label.get("bbox"):
                continue
            normalized = _plain(" ".join(str(label.get("text", "")).split()))
            if ("binh quan so co phieu pho thong dang luu hanh" not in normalized or
                    "binh quan gia quyen" in normalized):
                continue
            # Labels can wrap across two baselines; number blocks align with
            # the first baseline (bbox top), not the label's vertical center.
            y = label["bbox"][1]
            candidates: list[tuple[float, Decimal]] = []
            for block in blocks:
                bbox = block.get("bbox")
                raw = str(block.get("text", "")).strip().replace("\u00a0", " ")
                if block is label or block.get("type") != "paragraph" or not bbox:
                    continue
                if abs(bbox[1] - y) > 3.0:
                    continue
                if not number_pattern.fullmatch(raw):
                    continue
                value = _parse_accounting_number(raw)
                if value is not None and value > 0:
                    candidates.append(((bbox[0] + bbox[2]) / 2, value))
            candidates.sort(key=lambda item: item[0])
            if not candidates:
                continue
            target_years = years[:len(candidates)]
            if len(candidates) == 1 and years:
                target_years = years[:1]
            if len(target_years) != len(candidates):
                continue
            for year, (_x, value) in zip(target_years, candidates):
                # The note may repeat a year in an adjusted comparative table;
                # prefer the main labeled row, which appears before that table.
                if year not in shares:
                    shares[year] = (value, page["page"])
                    evidence_pages.add(page["page"])
    return shares, evidence_pages


def _accounting_soft_checks(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run advisory EPS checks; soft findings never fail arithmetic pages."""
    values = _accounting_numeric_values(documents)
    shares_by_year, _share_pages = _average_share_counts(documents, values)
    checks: list[dict[str, Any]] = []
    note_pages = [page for page in documents if page.get("page_class") == "notes"]
    note_text = _plain(" ".join(" ".join(str(block.get("text", "")).split())
                                 for page in note_pages for block in page.get("blocks", [])))
    no_dilution = ("lai suy giam tren co phieu bang lai co ban tren co phieu" in note_text
                   and "khong co co phieu pho thong tiem tang" in note_text)
    basic_rows = values.get("income_statement", {})
    for period, rows in sorted(basic_rows.items()):
        profit = rows.get("61")
        eps = rows.get("70")
        if profit is None or eps is None:
            continue
        year = period[0][:4]
        share_data = shares_by_year.get(year)
        if share_data is None:
            checks.append({"name": "eps_basic_approximation", "period_end": period[0],
                           "period_type": period[1], "period_role": period[2],
                           "status": "not_evaluated", "reason": "average_shares_not_found",
                           "pdf_pages": sorted({profit[1], eps[1]})})
            continue
        expected = profit[0] / share_data[0]
        deviation = abs(eps[0] - expected) / max(abs(expected), Decimal(1))
        checks.append({"name": "eps_basic_approximation", "period_end": period[0],
                       "period_type": period[1], "period_role": period[2],
                       "status": "within_tolerance" if deviation <= Decimal("0.10") else "review",
                       "passed": deviation <= Decimal("0.10"),
                       "actual_eps": str(eps[0]), "approximate_eps_from_parent_profit": str(expected),
                       "average_shares": str(share_data[0]),
                       "relative_deviation": str(deviation), "tolerance": "0.10",
                       "pdf_pages": sorted({profit[1], eps[1], share_data[1]})})
        diluted = rows.get("71")
        if no_dilution and diluted is not None:
            checks.append({"name": "eps_diluted_equals_basic_when_no_dilution",
                           "period_end": period[0], "period_type": period[1],
                           "period_role": period[2],
                           "status": "pass" if diluted[0] == eps[0] else "review",
                           "passed": diluted[0] == eps[0], "actual_diluted_eps": str(diluted[0]),
                           "actual_basic_eps": str(eps[0]),
                           "pdf_pages": sorted({diluted[1], eps[1]})})
    return checks


def _accounting_cell_coverage(
    documents: list[dict[str, Any]], template_path: Path | None,
    soft_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Count coded value cells protected by a hard or applicable soft rule."""
    protected: dict[str, set[str]] = defaultdict(set)
    if template_path is not None or _select_accounting_template_path(documents) is not None:
        template = _load_accounting_template(template_path or
                                             _select_accounting_template_path(documents))
        for line in template.get("template_lines", []):
            if line.get("is_memo", False):
                continue
            protected[line["statement"]].update((line["parent"], line["code"]))
        for rule in template.get("arithmetic_rules", []):
            protected[rule["statement"]].add(rule["parent"])
            protected[rule["statement"]].update(child["code"] for child in rule["children"])
        for rule in template.get("cross_statement_rules", []):
            for side in ("left", "right"):
                ref = rule[side]
                protected[ref["statement"]].add(ref["code"])
    for check in soft_checks:
        if check["name"] == "eps_basic_approximation" and check.get("status") != "not_evaluated":
            protected["income_statement"].add("70")
        elif check["name"] == "eps_diluted_equals_basic_when_no_dilution":
            protected["income_statement"].update(("70", "71"))

    by_statement: dict[str, dict[str, int]] = defaultdict(
        lambda: {"cells_protected": 0, "cells_total": 0})
    for page in documents:
        kind = page.get("page_class")
        if kind not in _ACCOUNTING_STATEMENTS:
            continue
        for block in page.get("blocks", []):
            if block.get("type") != "table":
                continue
            columns = [column["key"] for column in block.get("columns", [])]
            for row in block.get("rows", []):
                code = row.get("code")
                if not code:
                    continue
                for column in columns:
                    if column not in row.get("cells", {}):
                        continue
                    by_statement[kind]["cells_total"] += 1
                    if str(code) in protected[kind]:
                        by_statement[kind]["cells_protected"] += 1
    total = sum(item["cells_total"] for item in by_statement.values())
    total_protected = sum(item["cells_protected"] for item in by_statement.values())
    return {
        "cells_protected": total_protected,
        "cells_total": total,
        "cell_coverage_ratio": round(total_protected / total, 6) if total else 0.0,
        "cell_coverage_passed": bool(total and total_protected / total >= 0.95),
        "cell_coverage_by_statement": {
            statement: {**counts,
                        "coverage_ratio": round(counts["cells_protected"] / counts["cells_total"], 6)
                        if counts["cells_total"] else 0.0}
            for statement, counts in sorted(by_statement.items())
        },
    }


def compare_accounting_reports(
    left_documents: list[dict[str, Any]],
    right_documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Compare same-period coded values between two report versions, preserving raw text."""
    def collect(documents: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        result: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for page in documents:
            kind = page.get("page_class")
            if kind not in _ACCOUNTING_STATEMENTS:
                continue
            context = "\n".join(str(block.get("text", "")) for block in page.get("blocks", [])
                                if block.get("type") in ("heading", "paragraph"))
            for block in page.get("blocks", []):
                if block.get("type") != "table":
                    continue
                periods = {column["key"]: _accounting_period(
                    column.get("header_lines", []), kind, context)
                    for column in block.get("columns", [])}
                for row in block.get("rows", []):
                    code = row.get("code")
                    if not code:
                        continue
                    for column, cell in row.get("cells", {}).items():
                        period = periods.get(column)
                        raw = cell.get("raw")
                        if period is None or raw is None:
                            continue
                        key = (kind, str(code), period[0], period[1])
                        result[key] = {"raw": str(raw), "page": page["page"],
                                       "column": column,
                                       "needs_review": bool(cell.get("needs_review", False))}
        return result

    left_values = collect(left_documents)
    right_values = collect(right_documents)
    checks: list[dict[str, Any]] = []
    for key in sorted(left_values.keys() & right_values.keys()):
        kind, code, period_end, period_type = key
        left = left_values[key]
        right = right_values[key]
        raw_equal = left["raw"] == right["raw"]
        left_number = _parse_accounting_number(left["raw"])
        right_number = _parse_accounting_number(right["raw"])
        numeric_equal = (left_number is not None and right_number is not None and
                         left_number == right_number)
        checks.append({"statement": kind, "code": code, "period_end": period_end,
                       "period_type": period_type,
                       "status": "match" if raw_equal and not left["needs_review"] and
                                not right["needs_review"] else "review",
                       "reason": (None if raw_equal else
                                 "raw_format_differs_but_numeric_value_matches" if numeric_equal else
                                 "CROSS_PERIOD_MISMATCH"),
                       "left_raw": left["raw"], "right_raw": right["raw"],
                       "numeric_equal": numeric_equal,
                       "pdf_pages": sorted({left["page"], right["page"]})})
    flagged = sum(check["status"] != "match" for check in checks)
    return checks, {"compared": len(checks), "matched": len(checks) - flagged,
                    "flagged_for_review": flagged}


def _accounting_template_supported(documents: list[dict[str, Any]]) -> bool:
    """Apply the legacy code template only to its identified balance-sheet form.

    A title such as 'Báo cáo tình hình tài chính' is used by TT99 and banks,
    whose row codes and arithmetic may differ.  Missing title evidence is not
    sufficient grounds to select the legacy template either.
    """
    balance_pages = [page for page in documents if page.get("page_class") == "balance_sheet"]
    if not balance_pages:
        return False
    titles = [
        _plain(str(block.get("text", "")))
        for page in balance_pages
        for block in page.get("blocks", [])[:12]
        if block.get("type") in ("heading", "paragraph")
    ]
    if any(re.search(r"(?:bao|bang) cao tinh hinh tai chinh", title) for title in titles):
        return False
    return any("bang can doi ke toan" in title for title in titles)


def _accounting_template_profile(documents: list[dict[str, Any]]) -> str | None:
    """Use printed form and row labels; a title or year alone is not enough."""
    balance_pages = [page for page in documents if page.get("page_class") == "balance_sheet"]
    if not balance_pages:
        return None
    blocks = [block for page in balance_pages for block in page.get("blocks", [])]
    titles = [_plain(str(block.get("text", ""))) for block in blocks
              if block.get("type") in ("heading", "paragraph", "form_code")]
    form_text = " ".join([*titles, *(
        _plain(str(block.get("title", ""))) for block in blocks
        if block.get("type") == "table")])
    # B02/B03/B04/B05-TCTD are the banking schedules prescribed by TT49.
    # No bank arithmetic template is bundled yet, so these must not fall
    # through to the non-bank equations.
    if re.search(r"\bb0?[2345]\s*/\s*tctd(?:\s*[-–—]\s*hn)?\b", form_text):
        return "TT49_BANK"
    if any("hop nhat" in title for title in titles if
           re.search(r"(?:bao|bang) cao tinh hinh tai chinh", title)):
        return None  # B01-DN is not the consolidated DN/HN form.
    if any(re.search(r"(?:bao|bang) cao tinh hinh tai chinh", title) for title in titles):
        if re.search(r"\bb\s*0?1\s*[-–—]\s*dn\s*[/\\-]\s*hn\b", form_text):
            return None  # The consolidated form needs its own rules.
        exact_b01_dn = re.search(
            r"\bb\s*0?1\s*[-–—]\s*dn\b(?!\s*[/\\-]\s*hn)", form_text)
        rows = [row for block in blocks if block.get("type") == "table"
                for row in block.get("rows", [])]
        labels = {str(row.get("code")): _plain(str(row.get("label_raw", "")))
                  for row in rows if row.get("code")}
        row_evidence = ("tong cong tai san" in labels.get("280", "") and
                        "tai san dai han khac" in labels.get("270", ""))
        if exact_b01_dn or row_evidence:
            return "TT99_2025"
        return None
    if _accounting_template_supported(documents):
        return "TT200_NONBANK"
    return None


def _select_accounting_template_path(documents: list[dict[str, Any]],
                                     template_path: Path | None = None) -> Path | None:
    """Select an applicable template; unknown forms receive no arithmetic checks."""
    profile = _accounting_template_profile(documents)
    if profile is None:
        return None
    if profile == "TT49_BANK" and template_path is None:
        return None
    candidate = (template_path if template_path is not None else
                 TT99_ACCOUNTING_TEMPLATE if profile == "TT99_2025" else ACCOUNTING_TEMPLATE)
    path = _accounting_template_path(candidate)
    template = json.loads(path.read_text(encoding="utf-8"))
    standard = template.get("accounting_standard", "LEGACY_NONBANK")
    compatible = {"TT200_NONBANK": {"LEGACY_NONBANK", "TT200_NONBANK"},
                  "TT99_2025": {"TT99_2025"},
                  "TT49_BANK": {"TT49_BANK"}}
    if standard not in compatible.get(profile, {profile}):
        raise ValueError(f"Template {path.name} thuộc {standard}, báo cáo thuộc {profile}")
    return path


def evaluate_accounting(documents: list[dict[str, Any]], template_path: Path | None = None
                        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int], str]:
    """Evaluate template sums and cross-statement checks by year, preserving missing data."""
    selected_template = _select_accounting_template_path(documents, template_path)
    if selected_template is None:
        profile = _accounting_template_profile(documents)
        return [], [{"name": "template_unknown",
                     "reason": ("template_not_implemented" if profile else
                                "accounting_form_not_identified"),
                     "detected_profile": profile,
                     "pdf_pages": [page["page"] for page in documents
                                   if page.get("page_class") in _ACCOUNTING_STATEMENTS]}], \
               set(), "TEMPLATE_UNKNOWN"
    template = _load_accounting_template(selected_template)
    values: dict[str, dict[tuple[str, str, str], dict[str, tuple[Decimal, int]]]] = defaultdict(lambda: defaultdict(dict))
    invalid_cells: list[dict[str, Any]] = []
    unresolved_periods: list[dict[str, Any]] = []
    review_cells: list[dict[str, Any]] = []
    failed_pages: set[int] = set()
    seen_codes: dict[str, dict[tuple[str, str, str], set[str]]] = defaultdict(
        lambda: defaultdict(set))
    for page in documents:
        kind = page["page_class"]
        if kind not in _ACCOUNTING_STATEMENTS:
            continue
        for block in page["blocks"]:
            if block["type"] != "table":
                continue
            context = "\n".join(str(item.get("text", "")) for item in page["blocks"]
                                if item["type"] in ("heading", "paragraph"))
            periods = {column["key"]: _accounting_period(
                column["header_lines"], kind, context)
                for column in block["columns"]}
            for column in block["columns"]:
                if periods[column["key"]] is None:
                    unresolved_periods.append({"name": "period_unresolved", "page": page["page"],
                                               "table_id": block["id"], "column": column["key"],
                                               "header_lines": column["header_lines"]})
                    failed_pages.add(page["page"])
            for row in block["rows"]:
                code = row.get("code")
                if not code:
                    continue
                for column, cell in row["cells"].items():
                    period = periods.get(column)
                    if period is not None:
                        seen_codes[kind][period].add(code)
                    if cell.get("needs_review", False):
                        review_cells.append({"name": "needs_review_cell",
                                             "reason": cell.get("review_reason"),
                                             "period_end": period[0] if period else None,
                                             "page": page["page"], "code": code,
                                             "column": column, "raw": cell.get("raw")})
                        failed_pages.add(page["page"])
                        continue
                    number = _parse_accounting_number(cell.get("raw"))
                    if period is not None and number is None and cell.get("raw") is not None:
                        invalid_cells.append({"name": "invalid_numeric_cell",
                                              "reason": "BAD_NUMBER_FORMAT", "year": period[0][:4],
                                              "period_end": period[0], "period_type": period[1],
                                              "page": page["page"], "code": code,
                                              "column": column, "raw": cell["raw"]})
                        failed_pages.add(page["page"])
                    if period is not None and number is not None:
                        previous = values[kind][period].get(code)
                        if previous is not None and previous[0] != number:
                            raise ValueError(f"Trùng mã {kind}/{period}/{code} với hai giá trị")
                        values[kind][period][code] = (number, page["page"])

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in template["template_lines"]:
        if not line["is_memo"]:
            groups[line["statement"], line["parent"]].append(line)
    equations = [(kind, parent, children, f"{kind}:{parent}", "template_lines")
                 for (kind, parent), children in groups.items()]
    equations.extend((rule["statement"], rule["parent"],
                      [{**child, "optional": False} for child in rule["children"]],
                      rule["name"], "arithmetic_rules")
                     for rule in template.get("arithmetic_rules", []))
    checks: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = invalid_cells + unresolved_periods + review_cells
    for kind, parent, children, name, source in equations:
        for period in sorted(values.get(kind, {})):
            rows = values.get(kind, {}).get(period, {})
            printed = seen_codes.get(kind, {}).get(period, set())
            missing = [code for code in [parent] if code not in rows]
            missing.extend(child["code"] for child in children
                           if child["code"] in printed and child["code"] not in rows)
            missing.extend(child["code"] for child in children
                           if not child.get("optional", False) and
                           child["code"] not in printed and child["code"] not in missing)
            reported_children = [child for child in children
                                 if child["code"] in printed and child["code"] in rows]
            if parent not in printed and not any(child["code"] in printed for child in children):
                # This subtotal and all its detail lines are absent from this
                # report, so the form does not declare this equation applicable.
                continue
            if missing or not reported_children:
                skipped.append({"name": name, "year": period[0][:4],
                                "period_end": period[0], "period_type": period[1],
                                "period_role": period[2], "missing_codes": missing,
                                "not_reported_optional_codes": [
                                    child["code"] for child in children
                                    if child.get("optional", False) and child["code"] not in printed],
                                **({"reason": "no_reported_children"} if not reported_children else {})})
                continue
            actual = rows[parent][0]
            expected = sum((rows[child["code"]][0] * child["sign"]
                            for child in reported_children), Decimal(0))
            passed = abs(actual - expected) <= 1
            codes = [parent, *(child["code"] for child in reported_children)]
            pages = sorted({rows[code][1] for code in codes})
            checks.append({"name": name, "year": period[0][:4],
                           "period_end": period[0], "period_type": period[1],
                           "period_role": period[2], "passed": passed,
                           "result_code": parent, "actual": str(actual), "expected": str(expected),
                           "not_reported_optional_codes": [
                               child["code"] for child in children
                               if child.get("optional", False) and child["code"] not in printed],
                           "pdf_pages": pages, "source": source})
            if not passed:
                failed_pages.update(pages)

    for rule in template["cross_statement_rules"]:
        left = rule["left"]
        right = rule["right"]
        for period, left_rows in values.get(left["statement"], {}).items():
            target = date.fromisoformat(period[0])
            offset = rule.get("right_year_offset", 0)
            if offset:
                # A beginning cash balance refers to the prior year end.
                target = date(target.year + offset, 12, 31)
            candidates = [(candidate_period, rows[right["code"]])
                          for candidate_period, rows in values.get(right["statement"], {}).items()
                          if candidate_period[0] == target.isoformat()
                          and right["code"] in rows]
            lhs = left_rows.get(left["code"])
            rhs = candidates[0][1] if len(candidates) == 1 else None
            if lhs is None or rhs is None:
                missing = []
                if lhs is None:
                    missing.append(f"{left['statement']}:{left['code']}:{period[0]}")
                if rhs is None:
                    missing.append(f"{right['statement']}:{right['code']}:{target.isoformat()}")
                skipped.append({"name": rule["name"], "year": period[0][:4],
                                "period_end": period[0], "period_type": period[1],
                                "period_role": period[2], "missing_codes": missing})
                continue
            passed = abs(lhs[0] - rhs[0]) <= 1
            pages = sorted({lhs[1], rhs[1]})
            checks.append({"name": rule["name"], "year": period[0][:4],
                           "period_end": period[0], "period_type": period[1],
                           "period_role": period[2], "passed": passed,
                           "actual": str(lhs[0]), "expected": str(rhs[0]),
                           "pdf_pages": pages, "source": "cross_statement"})
            if not passed:
                failed_pages.update(pages)
    return checks, skipped, failed_pages, template["template_id"]
