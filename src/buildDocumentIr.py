"""Build schema-valid IR for annual content and audited financial pages.

Usage:
    python src/buildDocumentIr.py "report.pdf"
    python src/buildDocumentIr.py "report.pdf" --pages-jsonl "ocr_router_out/report/pages.jsonl"

Annual content is written under annual_ir/content/; financial pages under
annual_ir/table/. The root index links both sections.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import struct
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pdfplumber
from jsonschema import Draft202012Validator

from ir_types import Block, Cell, Column, PageClass, PageIR, Row, Source, TableBlock
from model import PROMPT_VERSION
from financialContent import (compact_page_ranges, expand_page_ranges,
                              financial_index, financial_page_class,
                              statement_tables)
from render import page_name
from reportContent import (FPT_2024_SHA256, annual_content_index, annual_kpi,
                           annual_topics, reviewed_annual_tables, reviewed_kpis, section_from_sidebar,
                           section_index)
from util import hash_file, save_json
from validate_ir import SCHEMA, validate_page


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
            lines = [item for item in columns[anchor] if low < item["top"] < high]
            for block in _group_fragments(lines, body_size, "paragraph"):
                if "\n" not in block["text"] and _heading({**block, "size": body_size * 1.15}, body_size):
                    block["type"] = "heading"
                blocks.append(block)
    blocks.extend(_group_fragments(furniture, body_size, "furniture"))
    return blocks


def _markdown_table(lines: list[str], number: int, sequence: int) -> TableBlock | None:
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
        cells: dict[str, Cell] = {f"c{index}": {"raw": parts[i], "bbox": None}
                                  for index, i in enumerate(value_indices, 1) if parts[i]}
        rows.append({"id": f"r{len(rows) + 1}", "code": parts[code_index] or None if code_index is not None else None,
                     "label_raw": parts[label_index], "note": parts[note_index] or None if note_index is not None else None,
                     "bbox": None, "cells": cells})
    table: TableBlock = {"id": f"p{number}-t{sequence}", "type": "table", "bbox": None,
                         "unit_text": None, "columns": columns, "rows": rows}
    return table


def _text_blocks(text: str, number: int) -> list[dict[str, Any]]:
    """Fallback for raster OCR: preserve text without claiming false geometry."""
    blocks: list[dict[str, Any]] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        table = _markdown_table(lines, number, 1 + sum(block["type"] == "table" for block in blocks))
        if table is not None:
            blocks.append(table)
            continue
        joined = "\n".join(lines)
        letters = [char for char in joined if char.isalpha()]
        uppercase = bool(letters) and sum(char.isupper() for char in letters) / len(letters) > 0.85
        block_type = "heading" if uppercase and len(joined) < 140 else "paragraph"
        if joined.startswith("[stamp]"):
            block_type = "stamp"
        blocks.append({"type": block_type, "text": joined, "bbox": None})
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


def _page_class(blocks: list[dict[str, Any]]) -> str | None:
    headings = " ".join(block["text"] for block in blocks if block["type"] == "heading")
    value = _plain(headings)
    if "muc luc" in value:
        return "toc"
    if "thong tin ve doanh nghiep" in value:
        return "company_information"
    return "narrative" if any(block["type"] == "paragraph" for block in blocks) else None


def _printed_page(page: pdfplumber.page.Page) -> str | None:
    candidates = [word for word in page.extract_words(extra_attrs=["size"])
                  if word["top"] > page.height * 0.9 and
                  re.fullmatch(r"(?:[0-9]{1,4}|[ivxlcdm]{1,8})", word["text"], re.I) and
                  8 <= word["size"] <= 45]
    if not candidates:
        return None
    selected = max(candidates, key=lambda word: (word["size"], word["top"]))
    return selected["text"]


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
    if route == "tesseract+gemini":
        source.update(engine="GEMINI", tool=record["gemini"]["model"],
                      prompt_version=PROMPT_VERSION)
    else:
        source.update(engine="TESSERACT", tool="tesseract vie")
    return source


def _tokens(text: str) -> list[str]:
    return [token for token in (_plain(word).strip(".,:;()[]*") for word in text.split())
            if token]


def _represented_words(blocks: list[dict[str, Any]]) -> Counter[str]:
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


def _clamp_box(box: list[float] | None, width: float, height: float) -> list[float] | None:
    if box is None:
        return None
    x0, y0, x1, y1 = box
    if x0 >= width or y0 >= height or x1 <= 0 or y1 <= 0:
        return None
    return [round(max(0, x0), 2), round(max(0, y0), 2),
            round(min(width, x1), 2), round(min(height, y1), 2)]


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
                                     page_number: int, digest: str) -> list[dict[str, Any]]:
    """Read the independent panels on three visually inspected FPT pages."""
    if digest != FPT_2024_SHA256 or page_number not in (45, 98, 133):
        return blocks
    furniture = [block for block in blocks if block["type"] == "furniture"]
    content = [block for block in blocks if block["type"] != "furniture"]
    if page_number == 45:
        boundaries, top_cutoff = (1100,), 0
    elif page_number == 98:
        boundaries, top_cutoff = (640, 1040, 1440), 180
    else:
        boundaries, top_cutoff = (900,), 160
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
                 layout_exclude_boxes: list[list[float]] | None = None) -> PageIR:
    number = record["page"]
    header_blocks: list[dict[str, Any]] = []
    tables = (reviewed_annual_tables(page, digest, header_blocks)
              if record["route"] == "text_layer" else []) if tables_override is None else tables_override
    if record["route"] == "text_layer":
        blocks = _layout_blocks(page, layout_exclude_boxes if layout_exclude_boxes is not None
                                else [table["bbox"] for table in tables])
        page_width, page_height, unit = page.width, page.height, "pt"
    else:
        word_items = record.get("tesseract", {}).get("wordItems")
        # Gemini may correct OCR text. Never assign Tesseract positions to
        # different Gemini words; old pages.jsonl also lacks word geometry.
        ocr_text = " ".join(item["text"] for item in word_items) if word_items else ""
        same_text = " ".join(record["text"].split()) == " ".join(ocr_text.split())
        if word_items and same_text:
            blocks = _ocr_blocks(word_items)
            page_width, page_height = _png_size(_image_path(work_dir, number))
            unit = "px"
        else:
            blocks = _text_blocks(record["text"], number)
            page_width, page_height, unit = page.width, page.height, "pt"
    if record["route"] == "text_layer":
        blocks = _order_reviewed_multicolumn_page(blocks, number, digest)
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
    furniture_at = next((index for index, block in enumerate(blocks)
                         if block["type"] == "furniture"), len(blocks))
    blocks[furniture_at:furniture_at] = content
    for index, block in enumerate(blocks, 1):
        if block["type"] != "table":
            block["id"] = f"p{number}-b{index}"
            block["bbox"] = _clamp_box(block["bbox"], page_width, page_height)
            if unit == "px" and block["bbox"] is None:
                raise ValueError(f"Tesseract bbox ngoài ảnh trang {number}")
            if block["type"] == "heading" and _plain(block["text"]).startswith("mau so"):
                block["type"] = "form_code"
    page_class = page_class_override or _page_class(blocks)
    ir: PageIR = {
        "ir_version": "1", "page": number, "printed_page": _printed_page(page),
        "page_class": cast(PageClass | None, page_class),
        "page_size": {"width": page_width, "height": page_height, "unit": unit},
        "source": cast(Source, _source(record, pdf, digest, page, work_dir)),
        "blocks": cast(list[Block], blocks),
    }
    return ir


def build_document_ir(pdf: Path, pages_jsonl: Path, output_dir: Path) -> dict[str, Any]:
    """Write annual pages and audited financial pages to separate IR folders."""
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
    documents: list[dict[str, Any]] = []
    financial_documents: list[dict[str, Any]] = []
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
                         if record["route"] == "text_layer" else record["text"])
            financial_class = financial_page_class(number, section, digest, main_text)
            if financial_class is not None:
                financial_tables, exclude_boxes = (statement_tables(source_page, digest, financial_class)
                    if record["route"] == "text_layer" else ([], None))
                financial_ir = make_page_ir(
                    record, pdf, digest, source_page, work_dir,
                    tables_override=financial_tables,
                    page_class_override=financial_class,
                    layout_exclude_boxes=exclude_boxes)
                errors = validate_page(financial_ir, validator)
                if errors:
                    raise ValueError(f"IR BCTC trang {number} sai schema: {'; '.join(errors[:5])}")
                financial_documents.append(financial_ir)
            topics = annual_topics(number, section, digest)
            if not topics:
                continue
            page_topics[number] = topics
            observed_sections.append((number, section))
            page_kpis = reviewed_kpis(source_page, digest) if section and section != "financial" \
                and record["route"] == "text_layer" else []
            page_kpis = [item for item in page_kpis if annual_kpi(item)]
            ir = make_page_ir(record, pdf, digest, source_page, work_dir)
            _promote_reviewed_kpis(ir["blocks"], page_kpis)
            kpi_review.extend({"page": number, "section": section, **candidate}
                              for candidate in page_kpis)
            errors = validate_page(ir, validator)
            if errors:
                raise ValueError(f"IR trang {number} sai schema: {'; '.join(errors[:5])}")
            documents.append(ir)
    if not documents and not financial_documents:
        raise ValueError("Không tìm thấy trang báo cáo thường niên hoặc BCTC thuộc phạm vi đã chọn")
    output_dir.mkdir(parents=True, exist_ok=True)
    content_dir = output_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    expected_content = {f"{page_name(ir['page'])}.ir.json" for ir in documents}
    for stale in content_dir.glob("p-*.ir.json"):
        if stale.name not in expected_content:
            stale.unlink()
    for ir in documents:
        (content_dir / f"{page_name(ir['page'])}.ir.json").write_text(
            _readable_json(ir) + "\n", encoding="utf-8")
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
                _readable_json(ir) + "\n", encoding="utf-8")
        financial_summary = financial_index(financial_documents, digest)
        save_json(table_dir / "index.json", financial_summary)
    summary = {"pdf": str(pdf), "scope": "annual_report_content", "pages": len(documents),
               "routes": dict(Counter(ir["source"]["engine"] for ir in documents)),
               "blockTypes": dict(Counter(block["type"] for ir in documents for block in ir["blocks"])),
               "sectionIndex": "sections.json", "kpiReview": "kpi_review.json",
               "kpiVerified": sum(item["review_status"] == "verified" for item in kpi_review),
               "kpiCandidates": sum(item["review_status"] == "candidate" for item in kpi_review),
               "pageRanges": compact_page_ranges([ir["page"] for ir in documents]),
               "filePattern": "p-{page:03d}.ir.json"}
    sections = section_index(observed_sections, digest)
    sections.update(annual_content_index(documents, page_topics, digest))
    save_json(content_dir / "sections.json", sections)
    save_json(content_dir / "kpi_review.json",
              {"document_sha256": digest,
               "description": "Verified captions are linked to value-only KPI blocks by block_id; "
                              "unverified candidates are not added to IR.",
               "items": kpi_review})
    save_json(content_dir / "index.json", summary)
    manifest: dict[str, Any] = {
        "pdf": str(pdf), "document_sha256": digest,
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


def main(argv: list[str] | None = None) -> int:
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr.encoding.lower() != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages-jsonl", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    pdf = args.pdf.resolve()
    pages_jsonl = args.pages_jsonl or Path("ocr_router_out") / pdf.stem / "pages.jsonl"
    output_dir = args.out or pages_jsonl.parent / "annual_ir"
    try:
        summary = build_document_ir(pdf, pages_jsonl, output_dir)
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
