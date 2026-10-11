"""Dựng Document IR từ kết quả OCR, rồi tách nội dung thường niên và BCTC.

Usage:
    python src/buildDocumentIr.py "report.pdf"
    python src/buildDocumentIr.py "report.pdf" --pages-jsonl "ocr_router_out/report/pages.jsonl"

Luồng chính: pages.jsonl -> make_page_ir() -> lọc furniture -> kiểm schema
-> annual_ir/content/ và annual_ir/table/. annual_ir/index.json nối hai nhánh.
Mỗi p-NNN.ir.json ứng với trang PDF NNN, không phải số trang in trên báo cáo.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import struct
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

import pdfplumber
from jsonschema import Draft202012Validator

from ir_types import Block, Cell, Column, PageClass, PageIR, Row, Source, TableBlock
from model import PROMPT_VERSION
from financialContent import (compact_page_ranges, expand_page_ranges,
                              financial_index, financial_page_class,
                              flag_bad_financial_cells,
                              statement_tables)
from render import page_name
from reportContent import (annual_content_index, annual_kpi,
                           annual_table_topics,
                           annual_topics, annual_topics_from_header,
                           load_annual_override, reviewed_annual_tables, reviewed_kpis, section_from_sidebar,
                           section_index)
from util import hash_file, save_json
from validate_ir import SCHEMA, validate_page


# 1. Tiện ích biểu diễn JSON và chuẩn hóa chữ/tọa độ.
# _readable_json chỉ đổi cách xuống dòng cho dễ đọc; dữ liệu IR không đổi.
def _readable_json(value: Any, depth: int = 0) -> str:
    """Keep coordinates and short values on one line without changing the JSON data."""
    if not isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        compact = json.dumps(value, ensure_ascii=False)
        if not value or (all(not isinstance(item, (dict, list)) for item in value)
                         and len(compact) <= 100):
            return compact
        entries = [" " * (2 * (depth + 1)) + _readable_json(item, depth + 1)
                   for item in value]
        return "[\n" + ",\n".join(entries) + "\n" + " " * (2 * depth) + "]"
    if not value:
        return "{}"
    if set(value) == {"width", "height", "unit"}:
        return json.dumps(value, ensure_ascii=False)
    if "id" in value and "type" in value:
        keys = ["id", "type"] + [key for key in value if key not in ("id", "type")]
    else:
        keys = list(value)
    if (set(value) in ({"id", "type", "text", "bbox"},
                       {"raw", "bbox"}, {"key", "header_lines", "bbox"})):
        compact = json.dumps({key: value[key] for key in keys}, ensure_ascii=False)
        if len(compact) <= 160:
            return compact
    entries = [" " * (2 * (depth + 1)) + json.dumps(key, ensure_ascii=False)
               + ": " + _readable_json(value[key], depth + 1) for key in keys]
    return "{\n" + ",\n".join(entries) + "\n" + " " * (2 * depth) + "}"


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text).casefold()
    return "".join(char for char in normalized if not unicodedata.combining(char)).replace("đ", "d")


def _box(items: list[dict[str, Any]]) -> list[float] | None:
    if not items:
        return None
    return [round(min(item["x0"] for item in items), 2),
            round(min(item["top"] for item in items), 2),
            round(max(item["x1"] for item in items), 2),
            round(max(item["bottom"] for item in items), 2)]


# 2. Trang có lớp chữ: lấy từ + vị trí bằng pdfplumber, tách dòng ở khoảng
# trắng lớn, rồi gom thành heading/paragraph theo cột và thứ tự đọc.
def _fragments(page: pdfplumber.page.Page) -> list[dict[str, Any]]:
    """Separate words on the same baseline at visible horizontal gutters."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3, extra_attrs=["size"])
    if not words:
        return []
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 3:
            lines[-1].append(word)
        else:
            lines.append([word])
    fragments = []
    for line in lines:
        run: list[dict[str, Any]] = []
        for word in sorted(line, key=lambda item: item["x0"]):
            if run:
                gap = word["x0"] - run[-1]["x1"]
                font_size = min(word.get("size", 12), run[-1].get("size", 12))
                if gap > max(24, min(font_size * 1.3, 50)):
                    fragments.append(_fragment(run))
                    run = []
            run.append(word)
        if run:
            fragments.append(_fragment(run))
    return fragments


def _fragment(words: list[dict[str, Any]]) -> dict[str, Any]:
    x0, top, x1, bottom = _box(words)
    return {"x0": x0, "top": top, "x1": x1, "bottom": bottom,
            "size": statistics.median(word.get("size", 12) for word in words),
            "text": " ".join(word["text"] for word in words)}


def _anchors(fragments: list[dict[str, Any]], width: float) -> list[float]:
    """Find common starting x coordinates, including four-column KPI pages."""
    starts = Counter(round(item["x0"] / 50) * 50 for item in fragments
                     if len(item["text"]) >= 12)
    anchors: list[float] = []
    for x, _count in starts.most_common():
        if all(abs(x - selected) > width * 0.16 for selected in anchors):
            anchors.append(float(x))
        if len(anchors) == 4:
            break
    return sorted(anchors) or [0.0]


def _heading(fragment: dict[str, Any], body_size: float) -> bool:
    text = fragment["text"].strip()
    letters = [char for char in text if char.isalpha()]
    uppercase = bool(letters) and sum(char.isupper() for char in letters) / len(letters) >= 0.85
    return (fragment["size"] >= max(27, body_size * 1.45) or
            (uppercase and len(text) <= 140 and len(text.split()) >= 2 and
             fragment["size"] >= body_size * 1.1))


def _group_fragments(items: list[dict[str, Any]], body_size: float,
                     block_type: str) -> list[dict[str, Any]]:
    """Merge vertically adjacent lines while retaining one block per paragraph."""
    if not items:
        return []
    ordered = sorted(items, key=lambda item: (item["top"], item["x0"]))
    groups: list[list[dict[str, Any]]] = []
    for item in ordered:
        previous = groups[-1][-1] if groups else None
        gap = item["top"] - previous["top"] if previous else 0
        horizontal_overlap = max(0, min(item["x1"], previous["x1"])
                                 - max(item["x0"], previous["x0"])) if previous else 0
        near_same_column = (previous is not None and
                            (abs(item["x0"] - previous["x0"]) <= 75 or
                             horizontal_overlap >= 0.4 * min(item["x1"] - item["x0"],
                                                              previous["x1"] - previous["x0"])))
        if not groups or gap > max(body_size * 1.65, previous["size"] * 1.65) or not near_same_column:
            groups.append([item])
        else:
            groups[-1].append(item)
    return [{"type": block_type, "text": "\n".join(piece["text"] for piece in group),
             "bbox": _box(group)} for group in groups]


def _layout_blocks(page: pdfplumber.page.Page,
                   table_boxes: list[list[float]] | None = None) -> list[dict[str, Any]]:
    """Dựng khối chữ có bbox; bỏ vùng bảng để chữ trong ô không bị lặp."""
    fragments = _fragments(page)
    if table_boxes:
        fragments = [fragment for fragment in fragments if not any(
            x0 <= fragment["x0"] < x1 and y0 <= fragment["top"] < y1
            for x0, y0, x1, y1 in table_boxes)]
    if not fragments:
        return []
    body_size = statistics.median(item["size"] for item in fragments)
    titles = [item for item in fragments if _heading(item, body_size) and
              item["x0"] >= page.width * 0.18 and item["top"] < page.height * 0.85]
    content = [item for item in fragments if item not in titles]
    anchors = _anchors([item for item in content if item["top"] < page.height * 0.9], page.width)
    columns: dict[float, list[dict[str, Any]]] = {anchor: [] for anchor in anchors}
    furniture: list[dict[str, Any]] = []
    for item in content:
        if item["top"] >= page.height * 0.91:
            furniture.append(item)
            continue
        anchor = min(anchors, key=lambda x: abs(x - item["x0"]))
        if len(anchors) > 1 and anchor == anchors[0] and item["x1"] < page.width * 0.24 \
                and anchors[1] > page.width * 0.18:
            furniture.append(item)
        else:
            columns[anchor].append(item)

    # Large titles divide the page into vertical sections. Within each section,
    # read the left column top-to-bottom, then the right column.
    title_tops = sorted({item["top"] for item in titles})
    blocks: list[dict[str, Any]] = []
    for section in range(len(title_tops) + 1):
        if section:
            at_top = [item for item in titles if item["top"] == title_tops[section - 1]]
            blocks.extend(_group_fragments(at_top, body_size, "heading"))
        low = title_tops[section - 1] if section else -1
        high = title_tops[section] if section < len(title_tops) else float("inf")
        for anchor in anchors:
            # A body line can share the exact baseline of a title in the
            # adjacent column.  Keep it in this section instead of dropping it.
            lines = [item for item in columns[anchor] if low <= item["top"] < high]
            for block in _group_fragments(lines, body_size, "paragraph"):
                if "\n" not in block["text"] and _heading({**block, "size": body_size * 1.15}, body_size):
                    block["type"] = "heading"
                blocks.append(block)
    blocks.extend(_group_fragments(furniture, body_size, "furniture"))
    return blocks


# 3. Trang OCR: ưu tiên bbox của từng từ Tesseract; nếu bản AI đã sửa chữ
# khác bản Tesseract thì giữ text nhưng không gán nhầm tọa độ Tesseract.
def _markdown_table(lines: list[str], number: int, sequence: int,
                    needs_review: bool = False) -> TableBlock | None:
    """Đổi bảng Markdown từ AI thành columns/rows/cells khi có đủ dấu cột."""
    lines = [line.strip() for line in lines
             if line.strip() and not re.fullmatch(r"```(?:markdown|md)?", line.strip(), re.I)]
    if len(lines) < 3 or "|" not in lines[0]:
        return None
    split = lambda line: [cell.strip() for cell in line.strip().strip("|").split("|")]
    headers = split(lines[0])
    divider = split(lines[1])
    if len(headers) < 2 or len(divider) != len(headers) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in divider):
        return None
    code_index = 0 if _plain(headers[0]) in ("ma", "ma so", "code") and len(headers) >= 3 else None
    label_index = 1 if code_index is not None else 0
    note_index = next((i for i, header in enumerate(headers)
                       if _plain(header) in ("thuyet minh", "ghi chu", "note")), None)
    value_indices = [i for i in range(len(headers)) if i not in (code_index, label_index, note_index)]
    if not value_indices:
        return None
    columns: list[Column] = [{"key": f"c{index}", "header_lines": [headers[i]] if headers[i] else [],
                              "bbox": None} for index, i in enumerate(value_indices, 1)]
    rows: list[Row] = []
    for line in lines[2:]:
        if "|" not in line:
            return None
        parts = split(line)
        if len(parts) != len(headers):
            return None
        cells: dict[str, Cell] = {}
        for index, i in enumerate(value_indices, 1):
            cell: Cell = {"raw": parts[i] or None, "bbox": None}
            if needs_review:
                cell.update(needs_review=True,
                            review_reason="OCR_MARKDOWN_SINGLE_SOURCE")
            cells[f"c{index}"] = cell
        rows.append({"id": f"r{len(rows) + 1}", "code": parts[code_index] or None if code_index is not None else None,
                     "label_raw": parts[label_index], "note": parts[note_index] or None if note_index is not None else None,
                     "bbox": None, "cells": cells})
    table: TableBlock = {"id": f"p{number}-t{sequence}", "type": "table", "bbox": None,
                         "unit_text": None, "columns": columns, "rows": rows}
    return table


def _text_blocks(text: str, number: int, *, needs_review: bool = False) -> list[dict[str, Any]]:
    """Fallback for raster OCR: preserve text without claiming false geometry."""
    blocks: list[dict[str, Any]] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines = [line.strip() for line in paragraph.splitlines()
                 if line.strip() and not re.fullmatch(r"```(?:markdown|md)?", line.strip(), re.I)]
        text_lines: list[str] = []

        def flush_text() -> None:
            if not text_lines:
                return
            joined = "\n".join(text_lines).strip()
            text_lines.clear()
            if not joined or re.fullmatch(r"```(?:markdown|md)?", joined, re.I):
                return
            letters = [char for char in joined if char.isalpha()]
            uppercase = bool(letters) and sum(char.isupper() for char in letters) / len(letters) > 0.85
            block_type = "heading" if uppercase and len(joined) < 140 else "paragraph"
            if joined.startswith("[stamp]"):
                block_type = "stamp"
            blocks.append({"type": block_type, "text": joined, "bbox": None})

        index = 0
        while index < len(lines):
            if (index + 1 < len(lines) and "|" in lines[index]
                    and "|" in lines[index + 1]
                    and all(re.fullmatch(r":?-{3,}:?", cell.strip())
                            for cell in lines[index + 1].strip().strip("|").split("|"))):
                end = index + 2
                while end < len(lines) and "|" in lines[end]:
                    end += 1
                table = _markdown_table(
                    lines[index:end], number,
                    1 + sum(block["type"] == "table" for block in blocks),
                    needs_review=needs_review)
                if table is not None:
                    flush_text()
                    blocks.append(table)
                    index = end
                    continue
            text_lines.append(lines[index])
            index += 1
        flush_text()
    return blocks


def _ocr_blocks(word_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build positioned paragraphs from Tesseract's block/paragraph/line TSV rows.

    Coordinates remain pixels of the upright OCR image. TSV line identifiers keep
    words from neighbouring columns or baselines in separate text lines.
    """
    paragraphs: dict[tuple[int, int], dict[int, list[dict[str, Any]]]] = {}
    for word in word_items:
        key = (word["block"], word["paragraph"])
        paragraphs.setdefault(key, {}).setdefault(word["line"], []).append(word)

    blocks: list[dict[str, Any]] = []
    for lines in paragraphs.values():
        ordered_lines = [sorted(words, key=lambda item: (item["bbox"][0], item["bbox"][1]))
                         for words in lines.values()]
        text = "\n".join(" ".join(word["text"] for word in words)
                         for words in ordered_lines)
        all_words = [word for words in ordered_lines for word in words]
        bbox = [min(word["bbox"][0] for word in all_words),
                min(word["bbox"][1] for word in all_words),
                max(word["bbox"][2] for word in all_words),
                max(word["bbox"][3] for word in all_words)]
        letters = [char for char in text if char.isalpha()]
        uppercase = bool(letters) and sum(char.isupper() for char in letters) / len(letters) > 0.85
        block_type = "heading" if uppercase and len(text) < 140 else "paragraph"
        blocks.append({"type": block_type, "text": text, "bbox": bbox})
    return blocks


def _tess_four_column_statement_table(
        word_items: list[dict[str, Any]], number: int, width: int
        ) -> tuple[TableBlock | None, set[int]]:
    """Recover a four-column statement from positioned OCR words conservatively."""
    numeric = re.compile(r"\(?-?\d[\d.,/]*\)?$|^[-–—]$")
    amount_words = [word for word in word_items
                    if re.fullmatch(r"\(?-?\d[\d.,/]*\)?", word["text"])
                    and len(re.sub(r"\D", "", word["text"])) >= 4
                    and word["bbox"][2] >= width * .55]
    anchors: list[tuple[float, list[dict[str, Any]]]] = []
    for word in amount_words:
        edge = word["bbox"][2]
        cluster = next((item for item in anchors if abs(item[0] - edge) <= 18), None)
        if cluster is None:
            anchors.append((edge, [word]))
        else:
            cluster[1].append(word)
    strong = sorted((item for item in anchors if len(item[1]) >= 5), key=lambda item: item[0])
    if len(strong) < 4:
        return None, set()

    # Keep only anchors that recur on the same rows. This prevents a nearby
    # note-number column from being mistaken for a value column.
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(strong))}
    for i, (left_edge, left_words) in enumerate(strong):
        for j in range(i + 1, len(strong)):
            right_edge, right_words = strong[j]
            if right_edge - left_edge < width * .04:
                continue
            co_rows = sum(any(abs((left["bbox"][1] + left["bbox"][3]) / 2 -
                                  (right["bbox"][1] + right["bbox"][3]) / 2) <= 18
                              for right in right_words) for left in left_words)
            if co_rows >= 5:
                adjacency[i].add(j)
                adjacency[j].add(i)
    components: list[list[int]] = []
    unseen = set(adjacency)
    while unseen:
        pending, component = [unseen.pop()], []
        while pending:
            current = pending.pop()
            component.append(current)
            neighbours = adjacency[current] & unseen
            unseen.difference_update(neighbours)
            pending.extend(neighbours)
        components.append(component)
    selected = max(components, key=lambda part: (len(part),
                    sum(len(strong[index][1]) for index in part)))
    if len(selected) != 4:
        return None, set()
    columns_x = [strong[index][0] for index in sorted(selected, key=lambda i: strong[i][0])]
    column_centers = [statistics.median(
        (word["bbox"][0] + word["bbox"][2]) / 2 for word in strong[index][1])
        for index in sorted(selected, key=lambda i: strong[i][0])]
    amount_word_ids = {id(word) for word in amount_words}
    positioned_value_ids = amount_word_ids | {
        id(word) for word in word_items
        if numeric.fullmatch(word["text"])
        and any(abs(word["bbox"][2] - anchor) <= 18 for anchor in columns_x)
    }
    row_groups: list[list[dict[str, Any]]] = []
    for word in sorted((word for word in word_items
                        if id(word) in positioned_value_ids or
                        (numeric.fullmatch(word["text"]) and word["text"] in ("-", "–", "—"))),
                       key=lambda item: (sum(item["bbox"][1::2]) / 2, item["bbox"][0])):
        center_y = (word["bbox"][1] + word["bbox"][3]) / 2
        group = next((items for items in reversed(row_groups)
                      if abs(center_y - sum((item["bbox"][1] + item["bbox"][3]) / 2
                                            for item in items) / len(items)) <= 18), None)
        if group is None:
            row_groups.append([word])
        else:
            group.append(word)

    candidates: list[dict[str, Any]] = []
    for group in row_groups:
        values: list[dict[str, Any] | None] = [None] * 4
        for word in group:
            column = min(range(4), key=lambda index: abs(word["bbox"][2] - columns_x[index]))
            if abs(word["bbox"][2] - columns_x[column]) <= 18:
                if values[column] is not None:
                    break
                values[column] = word
        if sum(value is not None for value in values) < 3:
            continue
        row_y = sum((word["bbox"][1] + word["bbox"][3]) / 2 for word in group) / len(group)
        candidates.append({"y": row_y, "values": values})
    if len(candidates) < 5:
        return None, set()

    # Avoid joining separate tables: select the densest vertically continuous
    # run of statement rows using the page's observed row spacing.
    runs: list[list[dict[str, Any]]] = []
    for candidate in candidates:
        if runs and candidate["y"] - runs[-1][-1]["y"] <= 95:
            runs[-1].append(candidate)
        else:
            runs.append([candidate])
    matched = max(runs, key=len)
    if len(matched) < 5:
        return None, set()

    # Assign each label token to only its nearest value row. On this scan the
    # left text baseline is about 20-30 px above the four right-aligned values.
    labels_by_row: list[list[dict[str, Any]]] = [[] for _ in matched]
    for word in word_items:
        if (word["bbox"][2] >= columns_x[0] - 35 or id(word) in positioned_value_ids or
                (numeric.fullmatch(word["text"])
                 and len(re.sub(r"\D", "", word["text"])) >= 4)):
            continue
        center_y = (word["bbox"][1] + word["bbox"][3]) / 2
        nearest = min(range(len(matched)), key=lambda index: abs(center_y - matched[index]["y"]))
        if abs(center_y - matched[nearest]["y"]) <= 38:
            labels_by_row[nearest].append(word)

    first_data_y = matched[0]["y"]
    code_header = next((word for word in word_items
                        if _plain(word["text"]) == "ma"
                        and first_data_y - 180 <= word["bbox"][1] < first_data_y), None)
    note_header = next((word for word in word_items
                        if _plain(word["text"]) == "thuyet"
                        and first_data_y - 180 <= word["bbox"][1] < first_data_y), None)
    code_center = ((code_header["bbox"][0] + code_header["bbox"][2]) / 2
                   if code_header else None)
    note_center = ((note_header["bbox"][0] + note_header["bbox"][2]) / 2
                   if note_header else None)
    headers: dict[int, list[tuple[float, float, str]]] = {index: [] for index in range(4)}
    for word in word_items:
        top = word["bbox"][1]
        if not first_data_y - 180 <= top < first_data_y:
            continue
        if not re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]20\d{2}|20\d{2}", word["text"]):
            continue
        center = (word["bbox"][0] + word["bbox"][2]) / 2
        column = min(range(4), key=lambda index: abs(center - column_centers[index]))
        headers[column].append((top, center, word["text"]))

    header_words = [word for word in word_items
                    if first_data_y - 180 <= word["bbox"][1] < first_data_y
                    and word["bbox"][0] >= columns_x[0] - 260
                    and (any(char.isalpha() for char in word["text"])
                         or word["text"] == "4")]
    header_lines: list[tuple[float, list[dict[str, Any]]]] = []
    for word in sorted(header_words, key=lambda item: (item["bbox"][1], item["bbox"][0])):
        top = word["bbox"][1]
        existing = next((line for line in header_lines if abs(line[0] - top) <= 14), None)
        if existing:
            existing[1].append(word)
        else:
            header_lines.append((top, [word]))
    for top, line_words in header_lines:
        phrase = " ".join(word["text"] for word in sorted(line_words,
                                                            key=lambda item: item["bbox"][0]))
        normalized = unicodedata.normalize("NFD", phrase).casefold()
        normalized = "".join(char for char in normalized
                             if not unicodedata.combining(char)).replace("đ", "d")
        if "quy" in normalized and "luy ke" in normalized:
            ordered = sorted(line_words, key=lambda item: item["bbox"][0])
            split_at = next((position for position, word in enumerate(ordered)
                             if _plain(word["text"]).startswith("luy")), len(ordered))
            quarter = " ".join(word["text"] for word in ordered[:split_at])
            cumulative = " ".join(word["text"] for word in ordered[split_at:])
            for target in (0, 1):
                headers[target].append((top, float(columns_x[target]), quarter))
            for target in (2, 3):
                headers[target].append((top, float(columns_x[target]), cumulative))
            continue
        elif "quy" in normalized:
            targets = (0, 1)
        elif "luy ke" in normalized:
            targets = (2, 3)
        else:
            for word in line_words:
                center = (word["bbox"][0] + word["bbox"][2]) / 2
                target = min(range(4), key=lambda index: abs(center - column_centers[index]))
                center = (word["bbox"][0] + word["bbox"][2]) / 2
                headers[target].append((top, center, word["text"]))
            continue
        for target in targets:
            headers[target].append((top, float(columns_x[target]), phrase))

    rows: list[Row] = []
    used: set[int] = set()
    for row_index, candidate in enumerate(matched):
        all_labels = sorted(labels_by_row[row_index], key=lambda item: item["bbox"][0])
        numbers = [word for word in all_labels
                   if re.fullmatch(r"\d{1,3}[a-z]?", word["text"], re.I)]
        code_candidates = ([word for word in numbers
                            if code_center is not None and
                            abs((word["bbox"][0] + word["bbox"][2]) / 2 - code_center) <= 75]
                           if code_center is not None else [])
        note_candidates = ([word for word in numbers
                            if note_center is not None and
                            abs((word["bbox"][0] + word["bbox"][2]) / 2 - note_center) <= 75]
                           if note_center is not None else [])
        code = code_candidates[0]["text"] if len(code_candidates) == 1 else None
        note = note_candidates[0]["text"] if len(note_candidates) == 1 else None
        if code_center is None:
            code = numbers[-2]["text"] if len(numbers) >= 2 else numbers[-1]["text"] if numbers else None
            note = numbers[-1]["text"] if len(numbers) >= 2 else None
        labels = [word for word in all_labels if word not in numbers
                  and not re.fullmatch(r"\d{1,3}[._]?", word["text"])]
        if not any(any(char.isalpha() for char in word["text"]) for word in labels):
            # An OCR-detected value row without a legible printed label is
            # retained, but explicitly marked for human review below.
            label_text = ""
        else:
            label_text = " ".join(word["text"] for word in labels).strip()
        row_words = [*all_labels, *(value for value in candidate["values"] if value)]
        cells: dict[str, Cell] = {}
        for index, value in enumerate(candidate["values"]):
            cells[f"c{index + 1}"] = {
                "raw": value["text"] if value else None,
                "bbox": value["bbox"] if value else None,
                "needs_review": True,
                "review_reason": "TESSERACT_SINGLE_SOURCE" if value else "OCR_VALUE_MISSING",
            }
            if value:
                used.add(id(value))
        used.update(id(word) for word in all_labels)
        rows.append({"id": f"r{len(rows) + 1}", "code": code,
                     "label_raw": label_text,
                     "note": note,
                     "bbox": _union_boxes([word["bbox"] for word in row_words]),
                     "cells": cells})

    columns: list[Column] = []
    for index in range(4):
        line_groups: list[list[tuple[float, float, str]]] = []
        for item in sorted(set(headers[index]), key=lambda value: (value[0], value[1])):
            if line_groups and abs(item[0] - line_groups[-1][0][0]) <= 14:
                line_groups[-1].append(item)
            else:
                line_groups.append([item])
        columns.append({"key": f"c{index + 1}",
                        "header_lines": [" ".join(value[2] for value in group)
                                         for group in line_groups],
                        "bbox": None})
    return ({"id": f"p{number}-t1", "type": "table",
             "bbox": _union_boxes([row["bbox"] for row in rows]),
             "unit_text": None, "columns": columns, "rows": rows}, used)


def _recover_missing_tesseract_cells(table: TableBlock,
                                     alternate_words: list[dict[str, Any]]) -> int:
    """Fill only blank OCR cells when the primary TSV has an aligned token.

    The value stays flagged for human review because both readings come from
    Tesseract layout passes rather than independent OCR engines.
    """
    numeric = re.compile(r"\(?-?\d[\d.,/]*\)?$|^[-–—]$")
    column_edges: dict[str, list[float]] = defaultdict(list)
    for row in table["rows"]:
        for key, cell in row["cells"].items():
            if cell.get("bbox") is not None:
                column_edges[key].append(cell["bbox"][2])
    targets = {key: statistics.median(edges) for key, edges in column_edges.items() if edges}
    recovered = 0
    claimed: set[int] = set()
    for row in table["rows"]:
        present = [cell for cell in row["cells"].values() if cell.get("bbox") is not None]
        if not present:
            continue
        row_y = statistics.median((cell["bbox"][1] + cell["bbox"][3]) / 2
                                  for cell in present)
        for key, cell in row["cells"].items():
            if cell.get("raw") is not None or key not in targets:
                continue
            matches = [word for word in alternate_words
                       if id(word) not in claimed and numeric.fullmatch(word["text"])
                       and abs(word["bbox"][2] - targets[key]) <= 18
                       and abs((word["bbox"][1] + word["bbox"][3]) / 2 - row_y) <= 20]
            if len(matches) != 1:
                continue
            word = matches[0]
            claimed.add(id(word))
            cell.update(raw=word["text"], bbox=word["bbox"], needs_review=True,
                        review_reason="TESSERACT_PSM3_RECOVERED_NEEDS_REVIEW")
            recovered += 1
    return recovered


def _tess_statement_table(word_items: list[dict[str, Any]], number: int,
                          width: int) -> tuple[TableBlock | None, set[int]]:
    """Find repeated aligned amount columns on a scanned statement."""
    four_column_table, four_column_used = _tess_four_column_statement_table(
        word_items, number, width)
    if four_column_table is not None:
        return four_column_table, four_column_used
    numeric = re.compile(r"\(?-?\d[\d.,]*\)?$")
    lines: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for word in word_items:
        lines[(word["block"], word["paragraph"], word["line"])].append(word)
    physical: list[list[dict[str, Any]]] = []
    for line in sorted(lines.values(), key=lambda items: min(word["bbox"][1] for word in items)):
        top = min(word["bbox"][1] for word in line)
        bottom = max(word["bbox"][3] for word in line)
        previous_top = min(word["bbox"][1] for word in physical[-1]) if physical else 0
        previous_bottom = max(word["bbox"][3] for word in physical[-1]) if physical else 0
        # A printed row may have slightly different OCR baselines across wide
        # columns. Merge only intersecting word boxes so adjacent rows remain
        # separate even when the baseline tolerance must be wide.
        if physical and top <= previous_bottom and previous_top <= bottom:
            physical[-1].extend(line)
        else:
            physical.append(list(line))
    anchors: list[tuple[float, set[int]]] = []
    for index, line in enumerate(physical):
        for word in line:
            if (not numeric.fullmatch(word["text"]) or
                    len(re.sub(r"\D", "", word["text"])) < 4 or
                    word["bbox"][2] < width * .55):
                continue
            edge = word["bbox"][2]
            cluster = next((item for item in anchors if abs(item[0] - edge) <= 18), None)
            if cluster is None:
                anchors.append((edge, {index}))
            else:
                cluster[1].add(index)
    strong = sorted((item for item in anchors if len(item[1]) >= 5), key=lambda item: item[0])
    if len(strong) < 2:
        return None, set()
    # Group numeric edges that repeatedly occur on the same printed rows.
    # This can yield two comparative columns or four quarter/year columns.
    adjacency: dict[int, set[int]] = {index: set() for index in range(len(strong))}
    for left_index, left_anchor in enumerate(strong):
        for right_index in range(left_index + 1, len(strong)):
            if (strong[right_index][0] - left_anchor[0] >= width * .04 and
                    len(left_anchor[1] & strong[right_index][1]) >= 5):
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)
    components: list[list[int]] = []
    unseen = set(adjacency)
    while unseen:
        pending = [unseen.pop()]
        component: list[int] = []
        while pending:
            current = pending.pop()
            component.append(current)
            neighbours = adjacency[current] & unseen
            unseen.difference_update(neighbours)
            pending.extend(neighbours)
        components.append(component)
    selected = max(components, key=lambda component: (len(component),
                    sum(len(strong[index][1]) for index in component)))
    value_anchors = [strong[index] for index in sorted(selected, key=lambda i: strong[i][0])]
    if len(value_anchors) < 2 or len(value_anchors) > 4:
        return None, set()
    candidates: list[tuple[int, list[dict[str, Any]], list[dict[str, Any]]]] = []
    for index, line in enumerate(physical):
        values = [[word for word in line if numeric.fullmatch(word["text"])
                   and abs(word["bbox"][2] - anchor[0]) <= 18]
                  for anchor in value_anchors]
        if any(len(value) != 1 for value in values):
            continue
        value_words = [value[0] for value in values]
        labels = [word for word in line if word not in value_words
                  and word["bbox"][2] < value_words[0]["bbox"][0] - 8]
        if not any(any(char.isalpha() for char in word["text"]) for word in labels):
            continue
        candidates.append((index, labels, value_words))
    groups: list[list[tuple[int, list[dict[str, Any]], list[dict[str, Any]]]]] = []
    for candidate in candidates:
        if groups and candidate[0] - groups[-1][-1][0] <= 3:
            groups[-1].append(candidate)
        else:
            groups.append([candidate])
    matched = max(groups, key=len, default=[])
    if len(matched) < 5:
        return None, set()
    # Retain the printed headings above the detected numeric columns. Tesseract
    # emits words and geometry, not table structure, so only attach a heading
    # when it is horizontally close to one of the repeated value-column edges.
    first_data_y = min(word["bbox"][1] for word in matched[0][1] + matched[0][2])
    heading_phrases: dict[int, list[tuple[float, str]]] = {
        index: [] for index in range(len(value_anchors))}
    # Dates are often printed as a single OCR token, with their x position
    # centered over an amount column rather than aligned to its right edge.
    for word in word_items:
        top = word["bbox"][1]
        if (not first_data_y - 300 <= top < first_data_y or
                not re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]20\d{2}|20\d{2}",
                                 word["text"])):
            continue
        center = (word["bbox"][0] + word["bbox"][2]) / 2
        column = min(range(len(value_anchors)),
                     key=lambda index: abs(center - value_anchors[index][0]))
        if abs(center - value_anchors[column][0]) <= width * .3:
            heading_phrases[column].append((top, word["text"]))
    for line in physical:
        line_y = min(word["bbox"][1] for word in line)
        if not (0 <= first_data_y - line_y <= 300):
            continue
        ordered = sorted(line, key=lambda word: word["bbox"][0])
        if not any(any(char.isalpha() for char in word["text"]) or
                   re.search(r"\d", word["text"]) for word in ordered):
            continue
        for column, anchor_item in enumerate(value_anchors):
            anchor = anchor_item[0]
            candidates = [word for word in ordered if word["bbox"][0] >= width * .5 and
                          abs((word["bbox"][0] + word["bbox"][2]) / 2 - anchor) <= width * .16]
            if not candidates:
                continue
            phrase = " ".join(word["text"] for word in candidates)
            normalized = unicodedata.normalize("NFD", phrase).casefold()
            normalized = "".join(char for char in normalized
                                  if not unicodedata.combining(char)).replace("đ", "d")
            if len(re.findall(r"20\d{2}", phrase)) > 1:
                continue  # This line spans both comparison columns.
            # Do not mistake earlier amounts for headers. Keep only printed
            # date/year or relative-period wording that can resolve a period.
            if not (re.search(r"20\d{2}", phrase) or
                    re.search(r"\b(?:so cuoi|so dau|ky nay|ky truoc|nam nay|nam truoc)\b",
                              normalized) or "thang" in normalized):
                continue
            heading_phrases[column].append((line_y, phrase))
    rows: list[Row] = []
    used: set[int] = set()
    for _, labels, values in matched:
        labels = sorted(labels, key=lambda word: word["bbox"][0])
        all_labels = list(labels)
        code = None
        if labels and re.fullmatch(r"\d{1,3}[a-z]?", labels[0]["text"], re.I):
            code = labels.pop(0)["text"]
        note = None
        if labels and re.fullmatch(r"\d{1,3}(?:\([a-z]\))?", labels[-1]["text"], re.I):
            note = labels.pop()["text"]
        row_words = [*all_labels, *values]
        used.update(id(word) for word in row_words)
        cells = {f"c{index + 1}": {"raw": value["text"], "bbox": value["bbox"],
                                    "needs_review": True,
                                    "review_reason": "TESSERACT_SINGLE_SOURCE"}
                 for index, value in enumerate(values)}
        rows.append({"id": f"r{len(rows) + 1}", "code": code,
                     "label_raw": " ".join(word["text"] for word in labels),
                     "note": note, "bbox": _union_boxes([word["bbox"] for word in row_words]),
                     "cells": cells})
    table_box = _union_boxes([row["bbox"] for row in rows])
    if table_box is None:
        return None, set()
    columns: list[Column] = [
        {"key": f"c{index + 1}",
         "header_lines": [text for _y, text in sorted(set(heading_phrases[index]))],
         "bbox": None}
        for index in range(len(value_anchors))
    ]
    return ({"id": f"p{number}-t1", "type": "table", "bbox": table_box,
             "unit_text": None, "columns": columns, "rows": rows}, used)


def _ai_box(box: list[float] | None, width: int, height: int) -> list[float] | None:
    """Convert AI's [y0,x0,y1,x1] / 1000 to the upright image's pixel space."""
    if box is None:
        return None
    y0, x0, y1, x1 = box
    return [round(x0 * width / 1000, 2), round(y0 * height / 1000, 2),
            round(x1 * width / 1000, 2), round(y1 * height / 1000, 2)]


def _union_boxes(boxes: list[list[float] | None]) -> list[float] | None:
    present = [box for box in boxes if box is not None]
    if not present:
        return None
    return [min(box[0] for box in present), min(box[1] for box in present),
            max(box[2] for box in present), max(box[3] for box in present)]


def _tess_vote(box: list[float] | None, words: list[dict[str, Any]],
               claimed: set[int]) -> dict[str, Any] | None:
    """Read only TSV words whose centers fall inside the AI cell box."""
    if box is None:
        return None
    selected = [word for word in words if id(word) not in claimed
                and box[0] - 2 <= (word["bbox"][0] + word["bbox"][2]) / 2 <= box[2] + 2
                and box[1] - 2 <= (word["bbox"][1] + word["bbox"][3]) / 2 <= box[3] + 2]
    if not selected:
        return None
    claimed.update(id(word) for word in selected)
    selected.sort(key=lambda word: (word["bbox"][1], word["bbox"][0]))
    return {"raw": " ".join(word["text"] for word in selected),
            "conf": round(sum(word["conf"] for word in selected) / len(selected), 2)}


def _same_cell_reading(left: str, right: str) -> bool:
    """Ignore whitespace only; punctuation and signs can change a financial value."""
    return "".join(left.split()).casefold() == "".join(right.split()).casefold()


def _ai_ir_blocks(ai_blocks: list[dict[str, Any]], word_items: list[dict[str, Any]],
                  number: int, width: int, height: int, provider: str,
                  flag_unverified: bool = False) -> tuple[list[dict[str, Any]], int, int]:
    """A3/A4/A5: convert AI blocks to IR and attach positional TSV cell votes."""
    engine = "OPENROUTER" if provider == "openrouter" else "GEMINI"
    result: list[dict[str, Any]] = []
    tess_votes = disagreements = 0
    claimed_words: set[int] = set()
    for ai in ai_blocks:
        if ai["type"] != "table":
            result.append({"type": ai["type"], "text": ai["text"] or "",
                           "bbox": _ai_box(ai["box_2d"], width, height)})
            continue
        # Some models include printed label/code/note columns despite the
        # prompt. Those fields already belong to each row, not to the set of
        # financial periods. Remove only a recognizable leading metadata
        # prefix and retain its note when the row field is absent.
        metadata: dict[str, str] = {}
        roles = {"chi tieu": "label", "ma so": "code",
                 "ma chi tieu": "code", "thuyet minh": "note"}
        for col in ai["columns"]:
            role = roles.get(_plain(" ".join(col["header_lines"])).strip())
            if role is None or role in metadata:
                break
            metadata[role] = col["key"]
        value_columns = ai["columns"][len(metadata):]
        remap = {col["key"]: f"c{index + 1}"
                 for index, col in enumerate(value_columns)}
        columns: list[Column] = [{"key": remap[col["key"]],
                                  "header_lines": col["header_lines"],
                                  "bbox": _ai_box(col["box_2d"], width, height)}
                                 for col in value_columns]
        rows: list[Row] = []
        for ai_row in ai["rows"]:
            metadata_cells = {role: next((cell["raw"] for cell in ai_row["cells"]
                                          if cell["column_key"] == key), None)
                              for role, key in metadata.items()}
            meta_conflict = any(
                metadata_cells.get(role) and ai_row[field] and
                not _same_cell_reading(metadata_cells[role], ai_row[field])
                for role, field in (("label", "label_raw"), ("code", "code"),
                                    ("note", "note")))
            cells: dict[str, Cell] = {}
            for ai_cell in ai_row["cells"]:
                key = remap.get(ai_cell["column_key"])
                if key is None:
                    continue
                box = _ai_box(ai_cell["box_2d"], width, height)
                raw = ai_cell["raw"] or None
                votes: dict[str, Any] = {engine: {"raw": raw, "conf": None}}
                tess = _tess_vote(box, word_items, claimed_words)
                vote_conflict = False
                if tess:
                    votes["TESSERACT"] = tess
                    tess_votes += 1
                    if raw and tess["raw"] and not _same_cell_reading(raw, tess["raw"]):
                        # Keep the AI transcript as evidence; the conflict
                        # blocks arithmetic until a person reviews the cell.
                        vote_conflict = True
                        disagreements += 1
                    elif raw is None and tess["conf"] >= 85:
                        raw = tess["raw"]
                unresolved = (raw is None or not tess or box is None or
                              meta_conflict or vote_conflict)
                cell: Cell = {"raw": raw, "bbox": box, "votes": votes}
                if flag_unverified:
                    cell.update(needs_review=unresolved,
                                review_reason=("OCR_READ_DISAGREEMENT_OR_UNVERIFIED"
                                               if unresolved else None))
                cells[key] = cell
            row_box = (_ai_box(ai_row["box_2d"], width, height)
                       or _union_boxes([cell["bbox"] for cell in cells.values()]))
            rows.append({"id": f"r{len(rows) + 1}",
                         "code": ai_row["code"] or metadata_cells.get("code"),
                         "label_raw": ai_row["label_raw"] or metadata_cells.get("label") or "",
                         "note": ai_row["note"] or metadata_cells.get("note"),
                         "bbox": row_box, "cells": cells})
        table_box = (_ai_box(ai["box_2d"], width, height)
                     or _union_boxes([column["bbox"] for column in columns]
                                     + [row["bbox"] for row in rows]))
        result.append({"id": f"p{number}-t{1 + sum(block['type'] == 'table' for block in result)}",
                       "type": "table", "title": ai["title"], "bbox": table_box,
                       "unit_text": ai["unit_text"], "columns": columns, "rows": rows})
    return result, tess_votes, disagreements


def _page_class(blocks: list[dict[str, Any]]) -> str | None:
    """Phân loại sơ bộ từ tiêu đề; nhánh BCTC có phân loại riêng ở financialContent."""
    headings = " ".join(block["text"] for block in blocks if block["type"] == "heading")
    value = _plain(headings)
    if "muc luc" in value:
        return "toc"
    if "thong tin ve doanh nghiep" in value:
        return "company_information"
    return "narrative" if any(block["type"] == "paragraph" for block in blocks) else None


def _record_text_for_classification(record: dict[str, Any]) -> str:
    """Get OCR text and structured OCR headings without inventing page text."""
    parts = [str(record.get("text") or "")]
    ai_blocks = record.get("aiBlocks")
    if isinstance(ai_blocks, list):
        for block in ai_blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "table":
                parts.append(str(block.get("text") or ""))
                continue
            parts.append(str(block.get("title") or ""))
            parts.extend(str(value) for column in block.get("columns", [])
                         for value in column.get("header_lines", []))
            parts.extend(str(row.get("code") or "") + " " +
                         str(row.get("label_raw") or "")
                         for row in block.get("rows", []))
    return "\n".join(part for part in parts if part.strip())


def _printed_page(page: pdfplumber.page.Page) -> str | None:
    candidates = [word for word in page.extract_words(extra_attrs=["size"])
                  if word["top"] > page.height * 0.9 and
                  re.fullmatch(r"(?:[0-9]{1,4}|[ivxlcdm]{1,8})", word["text"], re.I) and
                  8 <= word["size"] <= 45]
    if not candidates:
        return None
    selected = max(candidates, key=lambda word: (word["size"], word["top"]))
    return selected["text"]


# 4. Nguồn gốc trang: ghi engine, model/công cụ, hash ảnh và cách render
# để người đọc IR truy ngược được chữ đến đúng PDF/ảnh OCR.
def _image_path(work_dir: Path, number: int) -> Path:
    name = page_name(number)
    upright = work_dir / f"{name}.up.png"
    image = upright if upright.is_file() else work_dir / f"{name}.png"
    if not image.is_file():
        raise FileNotFoundError(f"Thiếu ảnh OCR trang {number}: {image}")
    return image


def _png_size(image: Path) -> tuple[int, int]:
    with image.open("rb") as source:
        header = source.read(24)
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Ảnh OCR không phải PNG: {image}")
    return struct.unpack(">II", header[16:24])


def _source(record: dict[str, Any], pdf: Path, digest: str,
            page: pdfplumber.page.Page, work_dir: Path) -> dict[str, Any]:
    """Chuyển route trong pages.jsonl thành source hợp lệ của IR v1."""
    route = record["route"]
    source: dict[str, Any] = {"engine": "TEXT_LAYER", "tool": f"pdfplumber {pdfplumber.__version__}",
                              "document_sha256": digest, "file_name": pdf.name}
    if route == "text_layer":
        return source
    image = _image_path(work_dir, record["page"])
    width, height = _png_size(image)
    rotation = int(record.get("rotation", 0))
    real_width, real_height = (height, width) if rotation in (90, 270) else (width, height)
    dpi = round(((real_width / page.width) + (real_height / page.height)) * 36, 2)
    source.update(image_sha256=hash_file(image), render={"dpi": dpi, "rotation": rotation})
    if route in ("tesseract+gemini", "tesseract+openrouter"):
        source.update(engine="OPENROUTER" if route == "tesseract+openrouter" else "GEMINI",
                      tool=record["gemini"]["model"],
                      prompt_version=record["gemini"].get(
                          "prompt_version", PROMPT_VERSION if isinstance(record.get("aiBlocks"), list)
                          else "api-v1"))
    else:
        source.update(engine="TESSERACT", tool="tesseract vie")
    return source


def _tokens(text: str) -> list[str]:
    return [token for token in (_plain(word).strip(".,:;()[]*") for word in text.split())
            if token]


def _represented_words(blocks: list[dict[str, Any]]) -> Counter[str]:
    """Đếm chữ trong cả khối thường lẫn ô bảng để audit kiểm mất chữ."""
    words: Counter[str] = Counter()
    for block in blocks:
        if block["type"] != "table":
            words.update(_tokens(block["text"]))
            continue
        words.update(_tokens(block.get("title") or ""))
        words.update(_tokens(block.get("unit_text") or ""))
        for column in block["columns"]:
            words.update(_tokens(" ".join(column["header_lines"])))
        for row in block["rows"]:
            for key in ("code", "label_raw", "note"):
                words.update(_tokens(str(row.get(key) or "")))
            for cell in row["cells"].values():
                words.update(_tokens(str(cell.get("raw") or "")))
    return words


def _preserve_unrepresented_source_words(page: pdfplumber.page.Page,
                                         blocks: list[dict[str, Any]]) -> None:
    """Keep visible PDF words omitted by a table crop in the page IR."""
    source_words = [word for word in page.extract_words(
        x_tolerance=2, y_tolerance=3, extra_attrs=["size"])
        if 0 <= word["top"] < page.height]
    missing = Counter(_tokens(" ".join(word["text"] for word in source_words)))
    missing.subtract(_represented_words(blocks))
    used_ids = {str(block.get("id")) for block in blocks}
    sequence = 1
    for word in source_words:
        needed: list[str] = []
        tokens = _tokens(word["text"])
        for token in tokens:
            if missing[token] > 0:
                needed.append(token)
                missing[token] -= 1
        if not needed:
            continue
        # Most pdfplumber words yield one token. When a word yields several,
        # keep only the missing tokens rather than duplicating represented text.
        text = word["text"] if len(needed) == len(tokens) else " ".join(needed)
        while f"p{page.page_number}-b{sequence}" in used_ids:
            sequence += 1
        block_id = f"p{page.page_number}-b{sequence}"
        used_ids.add(block_id)
        blocks.append({"id": block_id, "type": "paragraph", "text": text,
                       "bbox": _box([word])})
        sequence += 1


def _clamp_box(box: list[float] | None, width: float, height: float) -> list[float] | None:
    if box is None:
        return None
    x0, y0, x1, y1 = box
    if x0 >= width or y0 >= height or x1 <= 0 or y1 <= 0:
        return None
    return [round(max(0, x0), 2), round(max(0, y0), 2),
            round(min(width, x1), 2), round(min(height, y1), 2)]


# 5. Ngoại lệ đã rà soát trên đúng PDF mẫu: gắn KPI và sửa thứ tự đọc
# của vài trang nhiều cột. Điều kiện SHA-256 ngăn áp nhầm sang PDF khác.
def _promote_reviewed_kpis(blocks: list[dict[str, Any]],
                           reviews: list[dict[str, Any]]) -> None:
    """Mark the exact printed numeral as KPI; keep its caption in review data."""
    for review in reviews:
        if review["review_status"] != "verified":
            continue
        x0, y0, x1, y1 = review["bbox"]
        matches = [block for block in blocks
                   if block.get("text", "").strip() == review["value_raw"]
                   and block["bbox"] is not None
                   and block["bbox"][0] >= x0 - 1 and block["bbox"][1] >= y0 - 1
                   and block["bbox"][2] <= x1 + 1 and block["bbox"][3] <= y1 + 1]
        if len(matches) != 1:
            raise ValueError(f"Trang KPI: không định vị duy nhất số {review['value_raw']}")
        matches[0]["type"] = "kpi"
        review["block_id"] = matches[0]["id"]
        review["value_bbox"] = matches[0]["bbox"]


def _order_reviewed_multicolumn_page(blocks: list[dict[str, Any]],
                                     page_number: int,
                                     override: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Apply an explicitly selected reading-order override."""
    spec = override.get("reading_order", {}).get(str(page_number)) if override else None
    if spec is None:
        return blocks
    furniture = [block for block in blocks if block["type"] == "furniture"]
    content = [block for block in blocks if block["type"] != "furniture"]
    boundaries, top_cutoff = spec["boundaries"], spec["top_cutoff"]
    top = [block for block in content if block["bbox"] and block["bbox"][1] < top_cutoff]
    panels = [block for block in content if block not in top]
    top.sort(key=lambda block: (block["bbox"][1], block["bbox"][0]))
    panels.sort(key=lambda block: (
        sum(block["bbox"][0] >= edge for edge in boundaries),
        block["bbox"][1], block["bbox"][0]))
    return top + panels + furniture


def make_page_ir(record: dict[str, Any], pdf: Path, digest: str,
                 page: pdfplumber.page.Page, work_dir: Path,
                 tables_override: list[dict[str, Any]] | None = None,
                 page_class_override: str | None = None,
                 layout_exclude_boxes: list[list[float]] | None = None,
                 annual_override: dict[str, Any] | None = None) -> PageIR:
    """Dựng một trang IR: chọn lớp chữ/OCR, ghép bảng, gán loại và nguồn."""
    number = record["page"]
    merged_votes = 0
    ocr_tool: str | None = None
    header_blocks: list[dict[str, Any]] = []
    tables = (reviewed_annual_tables(page, annual_override, header_blocks)
              if record["route"] == "text_layer" else []) if tables_override is None else tables_override
    if record["route"] == "text_layer":
        # PDF có chữ sẵn: bbox tính theo point của trang PDF.
        blocks = _layout_blocks(page, layout_exclude_boxes if layout_exclude_boxes is not None
                                else [table["bbox"] for table in tables])
        page_width, page_height, unit = page.width, page.height, "pt"
    else:
        # Trang scan: ưu tiên IR có cấu trúc do AI trả về, tọa độ đổi về pixel.
        word_items = record.get("tesseract", {}).get("wordItems")
        ai_blocks = record.get("aiBlocks")
        if isinstance(ai_blocks, list) and ai_blocks:
            page_width, page_height = _png_size(_image_path(work_dir, number))
            blocks, merged_votes, _ = _ai_ir_blocks(
                ai_blocks, word_items or [], number, page_width, page_height,
                record.get("gemini", {}).get("provider", "gemini"),
                flag_unverified=page_class_override in (
                    "balance_sheet", "income_statement", "cash_flow"))
            unit = "px"
        elif word_items and " ".join(record["text"].split()) == " ".join(
                item["text"] for item in word_items).strip():
            # Never assign Tesseract coordinates to a corrected AI transcript.
            page_width, page_height = _png_size(_image_path(work_dir, number))
            used_words: set[int] = set()
            if record["route"] == "tesseract" and page_class_override in (
                    "balance_sheet", "income_statement", "cash_flow"):
                tess_table, used_words = _tess_statement_table(word_items, number, page_width)
                # PSM 3 is the normal fast pass, but wide multi-period tables
                # can be transcribed column-by-column. Try PSM 4 only when a
                # detected four-column table is suspiciously incomplete, and
                # keep the pass that yields more recoverable rows.
                if (page_class_override == "income_statement" and tess_table is not None
                        and len(tess_table["columns"]) == 4
                        and len(tess_table["rows"]) < 15):
                    try:
                        from tesseract import tess_env, tesseract
                        alternate = tesseract(_image_path(work_dir, number),
                                              tess_env(None), psm=4)
                        alternate_table, alternate_used = _tess_statement_table(
                            alternate["wordItems"], number, page_width)
                        if (alternate_table is not None and
                                len(alternate_table["rows"]) > len(tess_table["rows"])):
                            _recover_missing_tesseract_cells(alternate_table, word_items)
                            word_items = alternate["wordItems"]
                            tess_table, used_words = alternate_table, alternate_used
                            ocr_tool = "tesseract vie; statement table passes --psm 3 + --psm 4"
                    except (OSError, RuntimeError):
                        # The existing PSM 3 result remains usable when the
                        # optional layout retry cannot run on this machine.
                        pass
                if tess_table is not None:
                    tables.append(tess_table)
            blocks = _ocr_blocks([word for word in word_items if id(word) not in used_words])
            unit = "px"
        else:
            blocks = _text_blocks(
                record["text"], number,
                needs_review=page_class_override in (
                    "balance_sheet", "income_statement", "cash_flow"))
            page_width, page_height, unit = page.width, page.height, "pt"
    if record["route"] == "text_layer":
        blocks = _order_reviewed_multicolumn_page(blocks, number, annual_override)
    content = []
    remaining_headers = header_blocks.copy()
    for table in sorted(tables, key=lambda block: (
            block["bbox"][0] >= page.width * 0.55,
            block["bbox"][1], block["bbox"][0])):
        x0, y0, x1, y1 = table["bbox"]
        headers = [block for block in remaining_headers
                   if x0 <= block["bbox"][0] <= x1 and y0 <= block["bbox"][1] <= y1]
        content.extend(sorted(headers, key=lambda block: (block["bbox"][1], block["bbox"][0])))
        content.append(table)
        remaining_headers = [block for block in remaining_headers if block not in headers]
    content.extend(remaining_headers)
    # Đặt bảng và tiêu đề liên quan trước furniture để giữ thứ tự đọc.
    furniture_at = next((index for index, block in enumerate(blocks)
                         if block["type"] == "furniture"), len(blocks))
    blocks[furniture_at:furniture_at] = content
    for index, block in enumerate(blocks, 1):
        if block["type"] != "table":
            block["id"] = f"p{number}-b{index}"
            block["bbox"] = _clamp_box(block["bbox"], page_width, page_height)
            if unit == "px" and block["bbox"] is None and not record.get("aiBlocks"):
                raise ValueError(f"Tesseract bbox ngoài ảnh trang {number}")
            if block["type"] == "heading" and _plain(block["text"]).startswith("mau so"):
                block["type"] = "form_code"
    page_class = page_class_override or _page_class(blocks)
    source = _source(record, pdf, digest, page, work_dir)
    if ocr_tool:
        source["tool"] = ocr_tool
    if merged_votes:
        source["engine"] = "MERGED"
        source["tool"] = f"{record['gemini']['model']} + tesseract vie"
    ir: PageIR = {
        "ir_version": "1", "page": number, "printed_page": _printed_page(page),
        "page_class": cast(PageClass | None, page_class),
        "page_size": {"width": page_width, "height": page_height, "unit": unit},
        "source": cast(Source, source),
        "blocks": cast(list[Block], blocks),
    }
    return ir


# 6. Lọc menu/header/footer lặp: so cùng chữ ở gần cùng vị trí tương đối
# trên ít nhất 50% các trang có lớp chữ. Không xóa chữ khỏi IR; đổi type
# thành furniture để bước dùng nội dung có thể bỏ qua.
def _furniture_key(block: dict[str, Any], page: dict[str, Any]) -> tuple[str, int, int] | None:
    """Khóa so khớp gồm chữ và ô vị trí 2% chiều rộng/cao trang."""
    bbox = block.get("bbox")
    if block.get("type") not in ("heading", "paragraph", "furniture") or bbox is None:
        return None
    width, height = page["page_size"]["width"], page["page_size"]["height"]
    x0, y0, _, y1 = bbox
    if not (x0 < width * .22 or y0 < height * .1 or y1 > height * .9):
        return None
    text = " ".join(unicodedata.normalize("NFC", block["text"]).casefold().split())
    if len(text) < 3:
        return None
    return text, round(x0 / width * 50), round(y0 / height * 50)


def audit_and_promote(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Xác nhận furniture lặp và trả thống kê, kể cả chỗ chồng lên bảng."""
    pages = {page["page"]: page for page in documents if page["source"]["engine"] == "TEXT_LAYER"}
    threshold = math.ceil(len(pages) * .5)
    appearances: dict[tuple[str, int, int], set[int]] = defaultdict(set)
    for page in pages.values():
        for block in page["blocks"]:
            key = _furniture_key(block, page)
            if key is not None:
                appearances[key].add(page["page"])
    repeated = {key: seen for key, seen in appearances.items()
                if len(seen) >= threshold and threshold > 0}
    promoted = 0
    sidebar_associated = 0
    page_numbers = 0
    demoted: list[dict[str, Any]] = []
    furniture_table_overlaps: list[dict[str, Any]] = []
    for page in documents:
        if page["source"]["engine"] != "TEXT_LAYER":
            continue
        repeated_menu_items = sum(bool(re.match(r"^0[1-7]\s", key[0]))
                                  for block in page["blocks"]
                                  if (key := _furniture_key(block, page)) in repeated)
        numbered_menu_items = sum(bool(re.match(r"^0[1-7]\s", key[0]))
                                  for block in page["blocks"]
                                  if (key := _furniture_key(block, page)) is not None
                                  and key[1] <= 11)
        has_repeated_sidebar = repeated_menu_items >= 3 or (
            bool(repeated) and numbered_menu_items >= 4)
        for block in page["blocks"]:
            key = _furniture_key(block, page)
            if key in repeated:
                if block["type"] != "furniture":
                    block["type"] = "furniture"
                    promoted += 1
                continue
            bbox = block.get("bbox")
            sidebar_item = (has_repeated_sidebar and bbox is not None
                            and bbox[0] < page["page_size"]["width"] * .22
                            and page["page_size"]["height"] * .08 < bbox[1]
                            < page["page_size"]["height"] * .75)
            if sidebar_item and block["type"] in ("heading", "paragraph", "furniture"):
                if block["type"] != "furniture":
                    block["type"] = "furniture"
                    promoted += 1
                sidebar_associated += 1
            elif block["type"] == "furniture":
                text = " ".join(block["text"].split())
                # Printed page numbers change on every page; their position is checked separately.
                if bbox and bbox[1] > page["page_size"]["height"] * .85 \
                        and re.fullmatch(r"\d{1,4}|[ivxlcdm]{1,8}", text, re.I):
                    page_numbers += 1
                else:
                    block["type"] = "paragraph"
                    demoted.append({"page": page["page"], "block_id": block["id"],
                                    "text": text[:120],
                                    "matching_pages": len(appearances.get(key, set()))})
        table_boxes = [block["bbox"] for block in page["blocks"]
                       if block["type"] == "table" and block.get("bbox")]
        for block in page["blocks"]:
            if block["type"] != "furniture" or not block.get("bbox"):
                continue
            x0, y0, x1, y1 = block["bbox"]
            if any(min(x1, box[2]) > max(x0, box[0])
                   and min(y1, box[3]) > max(y0, box[1]) for box in table_boxes):
                furniture_table_overlaps.append({"page": page["page"], "block_id": block["id"]})
    return {"scope": "all_text_layer_pages_from_pages_jsonl", "pages_checked": len(pages),
            "minimum_repeated_pages": threshold, "position_grid": "2% of page width and height",
            "repeated_groups": [{"text": key[0], "x_bin": key[1], "y_bin": key[2],
                                 "pages": len(seen)} for key, seen in sorted(repeated.items())],
            "promoted_blocks": promoted, "sidebar_associated_blocks": sidebar_associated,
            "page_number_blocks": page_numbers, "demoted_unverified_blocks": len(demoted),
            "demoted_examples": demoted[:30],
            "furniture_table_overlaps": furniture_table_overlaps}


# 7. Điều phối cả tài liệu: đọc pages.jsonl, dựng/validate từng trang,
# tách hai nhánh, lọc furniture chung rồi ghi file trang và index.
def build_document_ir(pdf: Path, pages_jsonl: Path, output_dir: Path,
                      template_path: Path | None = None,
                      overrides_path: Path | None = None) -> dict[str, Any]:
    """Ghi content/ cho thường niên và table/ cho phần BCTC kiểm toán."""
    pdf, pages_jsonl = pdf.resolve(), pages_jsonl.resolve()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    records = [json.loads(line) for line in pages_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError(f"Không có trang OCR trong {pages_jsonl}")
    numbers = [record["page"] for record in records]
    if len(numbers) != len(set(numbers)):
        raise ValueError("pages.jsonl có số trang bị trùng")
    digest = hash_file(pdf)
    annual_override = load_annual_override(overrides_path, digest)
    documents: list[dict[str, Any]] = []
    financial_documents: list[dict[str, Any]] = []
    furniture_reference_pages: list[dict[str, Any]] = []
    observed_sections: list[tuple[int, str | None]] = []
    page_topics: dict[int, list[str]] = {}
    kpi_review: list[dict[str, Any]] = []
    work_dir = pages_jsonl.parent / "work"
    with pdfplumber.open(pdf) as source_pdf:
        for record in records:
            number = record["page"]
            if not isinstance(number, int) or not 1 <= number <= len(source_pdf.pages):
                raise ValueError(f"Số trang OCR không hợp lệ: {number}")
            source_page = source_pdf.pages[number - 1]
            section_evidence = section_from_sidebar(source_page)
            section = section_evidence[0] if section_evidence else None
            main_text = (source_page.crop((source_page.width * .22, 0, source_page.width,
                                           source_page.height * .9)).extract_text() or ""
                         if record["route"] == "text_layer"
                         else _record_text_for_classification(record))
            header_text = source_page.crop((0, 0, source_page.width,
                                            source_page.height * .2)).extract_text() or ""
            financial_class = financial_page_class(number, section, digest,
                                                    main_text, header_text)
            if financial_class is None and section_evidence is None and record["route"] == "text_layer":
                # Standalone statements may print their title in the left margin.
                full_text = source_page.extract_text() or ""
                financial_class = financial_page_class(number, section, digest,
                                                        full_text, header_text)
            if financial_class is not None:
                # Nhánh BCTC: tách bảng chính khi đủ dấu cột/mã dòng.
                financial_tables, exclude_boxes = (statement_tables(source_page, digest, financial_class)
                    if record["route"] == "text_layer" else ([], None))
                financial_ir = make_page_ir(
                    record, pdf, digest, source_page, work_dir,
                    tables_override=financial_tables,
                    page_class_override=financial_class,
                    layout_exclude_boxes=exclude_boxes)
                if record["route"] == "text_layer":
                    _preserve_unrepresented_source_words(source_page, financial_ir["blocks"])
                flag_bad_financial_cells(financial_ir)
                errors = validate_page(financial_ir, validator)
                if errors:
                    raise ValueError(f"IR BCTC trang {number} sai schema: {'; '.join(errors[:5])}")
                financial_documents.append(financial_ir)
            topics = annual_topics(number, section, annual_override)
            if not topics and financial_class is None:
                header_lines = header_text.splitlines()
                topics = annual_topics_from_header(header_lines[0] if header_lines else "")
                if topics == ["unclassified"] and len(header_lines) > 1:
                    detail = annual_topics_from_header(header_lines[1])
                    if detail and detail != ["unclassified"]:
                        topics = detail
            if not topics and financial_class is None and record["route"] == "text_layer":
                topics = annual_table_topics(source_page)
            if not topics:
                if financial_class is None and record["route"] == "text_layer":
                    furniture_reference_pages.append(make_page_ir(
                        record, pdf, digest, source_page, work_dir, tables_override=[]))
                continue
            # Nhánh thường niên: chỉ chọn trang thuộc chủ đề mục tiêu;
            # KPI chưa kiểm chứng vẫn ở danh sách review, không tự đưa vào IR.
            page_topics[number] = topics
            observed_sections.append((number, section))
            page_kpis = reviewed_kpis(source_page, annual_override) if section and section != "financial" \
                and record["route"] == "text_layer" else []
            page_kpis = [item for item in page_kpis if annual_kpi(item)]
            ir = make_page_ir(record, pdf, digest, source_page, work_dir,
                              annual_override=annual_override)
            if record["route"] == "text_layer":
                _preserve_unrepresented_source_words(source_page, ir["blocks"])
            _promote_reviewed_kpis(ir["blocks"], page_kpis)
            kpi_review.extend({"page": number, "section": section, **candidate}
                              for candidate in page_kpis)
            errors = validate_page(ir, validator)
            if errors:
                raise ValueError(f"IR trang {number} sai schema: {'; '.join(errors[:5])}")
            documents.append(ir)
    if not documents and not financial_documents:
        raise ValueError("Không tìm thấy trang báo cáo thường niên hoặc BCTC thuộc phạm vi đã chọn")
    # Đo sự lặp trên cả hai nhánh trước khi lưu, tránh coi menu là nội dung.
    furniture_audit = audit_and_promote(documents + financial_documents + furniture_reference_pages)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(output_dir / "furniture_audit.json", furniture_audit)
    cell_review = [
        {"page": ir["page"], "table_id": block["id"], "row_id": row["id"],
         "column": key, "bbox": cell["bbox"], "votes": cell.get("votes"),
         "reason": cell.get("review_reason") or "unresolved_cell_votes"}
        for ir in documents + financial_documents
        for block in ir["blocks"] if block["type"] == "table"
        for row in block["rows"] for key, cell in row["cells"].items()
        if cell.get("needs_review") or (cell.get("raw") is None and cell.get("votes"))
    ]
    save_json(output_dir / "ocr_cell_review.json",
              {"document_sha256": digest, "items": cell_review})
    content_dir = output_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    # Chạy lại cùng PDF: bỏ file trang cũ không còn nằm trong phạm vi IR.
    expected_content = {f"{page_name(ir['page'])}.ir.json" for ir in documents}
    for stale in content_dir.glob("p-*.ir.json"):
        if stale.name not in expected_content:
            stale.unlink()
    for ir in documents:
        (content_dir / f"{page_name(ir['page'])}.ir.json").write_text(
            _readable_json(ir) + "\n", encoding="utf-8", newline="\n")
    financial_summary = None
    if financial_documents:
        table_dir = output_dir / "table"
        table_dir.mkdir(parents=True, exist_ok=True)
        expected_table = {f"{page_name(ir['page'])}.ir.json" for ir in financial_documents}
        for stale in table_dir.glob("p-*.ir.json"):
            if stale.name not in expected_table:
                stale.unlink()
        for ir in financial_documents:
            (table_dir / f"{page_name(ir['page'])}.ir.json").write_text(
                _readable_json(ir) + "\n", encoding="utf-8", newline="\n")
        financial_summary = financial_index(financial_documents, digest, template_path)
        save_json(table_dir / "index.json", financial_summary)
    # Index giúp tìm trang/chủ đề/KPI mà không phải mở mọi p-NNN.ir.json.
    summary = {"pdf": str(pdf), "scope": "annual_report_content", "pages": len(documents),
               "routes": dict(Counter(ir["source"]["engine"] for ir in documents)),
               "blockTypes": dict(Counter(block["type"] for ir in documents for block in ir["blocks"])),
               "sectionIndex": "sections.json", "kpiReview": "kpi_review.json",
               "kpiVerified": sum(item["review_status"] == "verified" for item in kpi_review),
               "kpiCandidates": sum(item["review_status"] == "candidate" for item in kpi_review),
               "pageRanges": compact_page_ranges([ir["page"] for ir in documents]),
               "filePattern": "p-{page:03d}.ir.json"}
    sections = section_index(observed_sections, digest)
    sections.update(annual_content_index(documents, page_topics, annual_override))
    save_json(content_dir / "sections.json", sections)
    save_json(content_dir / "kpi_review.json",
              {"document_sha256": digest,
               "description": "Verified captions are linked to value-only KPI blocks by block_id; "
                              "unverified candidates are not added to IR.",
               "items": kpi_review})
    save_json(content_dir / "index.json", summary)
    manifest: dict[str, Any] = {
        "pdf": str(pdf), "document_sha256": digest,
        "overrides_applied": [annual_override["id"]] if annual_override else [],
        "content": {"directory": "content", "index": "content/index.json",
                    "pages": len(documents)},
    }
    result = dict(summary)
    if financial_summary is not None:
        financial_entry = {
            "directory": "table", "index": "table/index.json",
            "pages": financial_summary["pages"],
            "structuredTablePages": len(expand_page_ranges(financial_summary["structured_table_ranges"])),
            "notesTextOnlyPages": len(expand_page_ranges(financial_summary["notes_text_only_ranges"])),
        }
        manifest["table"] = financial_entry
        result["financialStatements"] = financial_entry
    save_json(output_dir / "index.json", manifest)
    return result


# 8. CLI độc lập; main.py cũng có thể gọi thẳng build_document_ir() sau OCR.
def main(argv: list[str] | None = None) -> int:
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr.encoding.lower() != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages-jsonl", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--template", type=Path,
                        help="Template luật BCTC; mặc định templates/financial-template-lines.json")
    parser.add_argument("--overrides", type=Path,
                        help="File override đã rà soát cho đúng PDF; mặc định không dùng")
    args = parser.parse_args(argv)
    pdf = args.pdf.resolve()
    pages_jsonl = args.pages_jsonl or Path("ocr_router_out") / pdf.stem / "pages.jsonl"
    output_dir = args.out or pages_jsonl.parent / "annual_ir"
    try:
        summary = build_document_ir(pdf, pages_jsonl, output_dir, args.template, args.overrides)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"✖ {exc}\n")
    print(f"OK: {summary['pages']} trang IR thường niên; blocks: {summary['blockTypes']}")
    if "financialStatements" in summary:
        financial = summary["financialStatements"]
        print(f"BCTC: {financial['pages']} trang trong table/; "
              f"{financial['structuredTablePages']} trang có bảng cấu trúc, "
              f"{financial['notesTextOnlyPages']} trang thuyết minh chỉ có text")
    print(output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
