"""Evidence-based section and KPI extraction for annual-report pages.

This module does not change the one-page Document IR schema. A report section
spans pages, so its page ranges are written to a separate document index.
"""

from __future__ import annotations

import json
import re
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import pdfplumber

from ir_types import Cell, Column, Row, TableBlock


SECTION_TITLES = {
    "leadership": "Thông điệp ban lãnh đạo",
    "highlights": "Dấu ấn trong năm",
    "overview": "Dấu ấn và tổng quan doanh nghiệp",
    "strategy": "Chiến lược phát triển",
    "business": "Phân tích hoạt động kinh doanh",
    "governance": "Quản trị công ty",
    "esg": "Báo cáo ESG",
    "financial": "Báo cáo tài chính",
}

SECTION_PHRASES = {
    "thong diep ban lanh dao": "leadership",
    "thong diep lanh dao": "leadership",
    "dau an 2024": "overview",
    "dau an 2025": "highlights",
    "tong quan ve fpt": "overview",
    "chien luoc phat trien": "strategy",
    "phan tich hoat dong kinh doanh": "business",
    "quan tri cong ty": "governance",
    "bao cao esg": "esg",
    "bao cao tai chinh": "financial",
}


def _plain(text: str) -> str:
    value = unicodedata.normalize("NFD", text).casefold().replace("đ", "d")
    return "".join(char for char in value if not unicodedata.combining(char))


def _is_active_blue(color: Any) -> bool:
    return (isinstance(color, tuple) and len(color) == 3
            and 0 <= color[0] < 0.08 and 0.25 < color[1] < 0.45
            and 0.5 < color[2] < 0.76)


def section_from_sidebar(page: pdfplumber.page.Page) -> tuple[str, str] | None:
    """Read the active blue navigation item; return no label when ambiguous."""
    lines: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for char in page.chars:
        if char["x0"] < page.width * 0.21 and page.height * 0.14 < char["top"] < page.height * 0.58 \
                and _is_active_blue(char.get("non_stroking_color")):
            lines[round(char["top"] / 4) * 4].append(char)
    matches = []
    for chars in lines.values():
        text = "".join(char["text"] for char in sorted(chars, key=lambda item: item["x0"]))
        normalized = _plain(text)
        for phrase, section in SECTION_PHRASES.items():
            if phrase in normalized:
                matches.append((section, text))
                break
    return matches[0] if len(matches) == 1 else None


def detect_layout_profile(page: pdfplumber.page.Page) -> tuple[str, tuple[str, str] | None]:
    """Use the FPT sidebar layout only when its active label is visible."""
    section = section_from_sidebar(page)
    return ("fpt_sidebar", section) if section else ("no_sidebar", None)


def section_index(pages: list[tuple[int, str | None]], digest: str) -> dict[str, Any]:
    """Compress observed section labels into page ranges without filling gaps."""
    ranges: list[dict[str, Any]] = []
    unclassified: list[int] = []
    for number, section in sorted(pages):
        if section is None:
            unclassified.append(number)
            continue
        if ranges and ranges[-1]["id"] == section and ranges[-1]["last_page"] + 1 == number:
            ranges[-1]["last_page"] = number
        else:
            ranges.append({"id": section, "title": SECTION_TITLES[section],
                           "first_page": number, "last_page": number,
                           "evidence": "active sidebar label"})
    return {"document_sha256": digest, "sections": ranges,
            "unclassified_pages": unclassified}


def kpi_candidates(page: pdfplumber.page.Page) -> list[dict[str, Any]]:
    """Find large printed values with a nearby label; candidates need review."""
    words = page.extract_words(extra_attrs=["size"])
    candidates: list[dict[str, Any]] = []
    for value in words:
        if not (value["x0"] > page.width * 0.22
                and page.height * 0.14 < value["top"] < page.height * 0.88
                and value["size"] >= 36 and re.search(r"\d", value["text"])):
            continue
        if re.fullmatch(r"\d{1,2}", value["text"]) or ":" in value["text"]:
            continue
        possible = [word for word in words if value["x0"] - 35 <= word["x0"] < value["x0"] + 340
                    and value["top"] - 90 <= word["top"] < value["top"] - 8
                    and word["size"] < value["size"]
                    and any(char.isalpha() for char in word["text"])]
        rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for word in possible:
            rows[round(word["top"] / 4) * 4].append(word)
        labels = []
        for line_y, row in rows.items():
            label = " ".join(word["text"] for word in sorted(row, key=lambda item: item["x0"]))
            if 2 <= len(label.split()) <= 12 and not re.fullmatch(r"(?:VND|VNĐ|TỶ|TRIỆU|%|NĂM|TỶ VND|TỶ VNĐ)", label, re.I):
                labels.append((line_y, label, row))
        if not labels:
            continue
        line_y, label, label_words = max(labels, key=lambda item: item[0])
        if value["top"] - line_y > 85:
            continue
        items = label_words + [value]
        bbox = [round(min(item["x0"] for item in items), 2),
                round(min(item["top"] for item in items), 2),
                round(max(item["x1"] for item in items), 2),
                round(max(item["bottom"] for item in items), 2)]
        candidates.append({"label": label, "value_raw": value["text"], "bbox": bbox})
    return candidates


ANNUAL_TOPICS = {
    "leadership": "Thông điệp ban lãnh đạo",
    "company": "Doanh nghiệp, ngành nghề và cơ cấu tổ chức",
    "shareholders": "Cổ đông, cổ phần và thay đổi vốn",
    "strategy": "Chiến lược phát triển",
    "performance": "Kết quả hoạt động và kế hoạch",
    "governance": "Quản trị công ty",
    "people_esg": "Nhân sự và ESG",
    "unclassified": "Nội dung thường niên chưa phân loại chủ đề",
}


def load_annual_override(path: Path | None, digest: str) -> dict[str, Any] | None:
    """Load a reviewed PDF-specific override only when explicitly requested."""
    if path is None:
        return None
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("document_sha256") != digest:
        raise ValueError(f"Override không khớp SHA-256 của PDF: {path}")
    if not isinstance(value.get("id"), str) or not isinstance(value.get("annual_tables"), list):
        raise ValueError(f"Override thường niên không hợp lệ: {path}")
    return value


def annual_topics(number: int, section: str | None,
                  override: dict[str, Any] | None = None) -> list[str]:
    if override and override.get("annual_topic_ranges"):
        return [topic for topic, ranges in override["annual_topic_ranges"].items()
                if any(first <= number <= last for first, last in ranges)]
    return {
        "leadership": ["leadership"], "highlights": ["performance"],
        "overview": ["company"], "strategy": ["strategy"],
        "business": ["performance"], "governance": ["governance"],
        "esg": ["people_esg"],
    }.get(section, [])


def annual_topics_from_header(header: str) -> list[str]:
    """Classify annual narrative from the printed section title on this page.

    This is a conservative fallback for reports without FPT's colored sidebar.
    A title is evidence for a topic; PDF page numbers and document hashes are not.
    """
    value = _plain(" ".join(header.split())).replace("d0i", "doi")
    if "quan tri doanh nghiep" in value or "quan tri cong ty" in value:
        return ["governance"]
    if "phat trien ben vung" in value or "bao cao esg" in value:
        return ["people_esg"]
    if "chuyen doi so" in value or "chien luoc phat trien" in value:
        return ["strategy"]
    if "hanh trinh chuyen doi" in value:
        return ["strategy"]
    if "nen tang vung vang" in value:
        return ["unclassified"]
    if "thanh tuu cua" in value or "bao cao toan canh" in value:
        return ["performance"]
    if ("cau chuyen cua" in value or "co cau co dong" in value or
            "ve chung toi" in value or "chung toi la ai" in value):
        return ["company"]
    if "tam nhin cua" in value or "bao cao cua tong giam doc" in value:
        return ["leadership"]
    return []


def annual_kpi(item: dict[str, Any]) -> bool:
    """Financial ratios and amounts already belong to the BCTC extraction."""
    if item.get("review_status") != "verified":
        return False
    label = _plain(item.get("label", ""))
    return not any(term in label for term in (
        "doanh thu", "loi nhuan", "lntt", "von hoa", "roe", "roa", "eps",
        "co tuc", "thu nhap tren co phieu", "ngan sach nha nuoc"))


def _word_box(words: list[dict[str, Any]]) -> list[float]:
    return [round(min(word["x0"] for word in words), 2),
            round(min(word["top"] for word in words), 2),
            round(max(word["x1"] for word in words), 2),
            round(max(word["bottom"] for word in words), 2)]


def _printed_lines(words: list[dict[str, Any]]) -> list[str]:
    """Preserve reading order inside one printed cell, including line wraps."""
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 4:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [" ".join(word["text"] for word in sorted(line, key=lambda item: item["x0"]))
            for line in lines]


def _words_in_band(words: list[dict[str, Any]], left: float, right: float,
                   top: float, bottom: float) -> list[dict[str, Any]]:
    return [word for word in words if left <= word["x0"] < right
            and top <= word["top"] < bottom]


def _word_lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group one printed baseline while keeping adjacent PDF columns separate."""
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 4:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda word: word["x0"]) for line in lines]


def _caption_kind(title: str) -> str | None:
    title = _plain(title).lstrip("• ").strip()
    if title.startswith("thong tin ve co phieu"):
        return "stock"
    if title.startswith("co cau co dong theo"):
        return "shareholders"
    if title.startswith("top 10 co dong"):
        return "top_shareholders"
    if title.startswith("tinh hinh thay doi von dieu le"):
        return "charter_capital"
    if title.startswith("giao dich co phieu cua co dong"):
        return "stock_transactions"
    if title.startswith("hop dong hoac giao dich voi co dong"):
        return "insider_contracts"
    if title.startswith("nhan su binh quan"):
        return "personnel"
    if title.startswith("danh sach thanh vien hdqt"):
        return "board"
    if title.startswith("chi tiet thu lao"):
        if "bks" in title or "ban kiem soat" in title:
            return "bks_pay"
        if "hdqt" in title or "hoi dong quan tri" in title:
            return "board_pay"
    return None


def annual_table_captions(page: pdfplumber.page.Page,
                          words: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Find captions in either PDF column, independent of page number/year."""
    words = words if words is not None else page.extract_words(x_tolerance=2, y_tolerance=3)
    captions = []
    for line in _word_lines([word for word in words
                             if page.width * .03 < word["x0"] < page.width * .98]):
        runs: list[list[dict[str, Any]]] = []
        for word in line:
            if not runs or word["x0"] - runs[-1][-1]["x1"] > max(36, page.width * .035):
                runs.append([word])
            else:
                runs[-1].append(word)
        for run in runs:
            title = " ".join(word["text"] for word in run).lstrip("• ").strip()
            kind = _caption_kind(title)
            if kind and len(title) <= 160:
                captions.append({"kind": kind, "title": title, "words": run,
                                 "bbox": _word_box(run)})
    return captions


def annual_table_topics(page: pdfplumber.page.Page) -> list[str]:
    """Allow table pages into annual IR even when a new report has no FPT sidebar."""
    found = {("shareholders" if caption["kind"] in
              ("stock", "shareholders", "top_shareholders", "charter_capital")
              else "people_esg" if caption["kind"] == "personnel" else "governance")
             for caption in annual_table_captions(page)}
    return [topic for topic in ("shareholders", "governance", "people_esg") if topic in found]


def _dynamic_zone(page: pdfplumber.page.Page, caption: dict[str, Any],
                  captions: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    left = max(0, caption["bbox"][0] - 7)
    right = min(page.width * .98, left + page.width *
                (.75 if caption["kind"] == "board" else .37))
    top = caption["bbox"][1]
    bottom = min(page.height * .9, top + page.height *
                 (.80 if caption["kind"] == "board" else .49))
    later = [item["bbox"][1] - 3 for item in captions
             if item is not caption and top + 8 < item["bbox"][1] < bottom
             and left <= item["bbox"][0] < right - 20]
    if later:
        bottom = min(bottom, min(later))
    return left, top, right, bottom


def _dynamic_table(caption: dict[str, Any], columns: list[Column],
                   rows: list[Row], header_words: list[dict[str, Any]],
                   number: int, sequence: int) -> TableBlock | None:
    if len(rows) < 3 or not columns or any(not row["label_raw"] or
                                           len(row["cells"]) != len(columns) for row in rows):
        return None
    # The caption, headers and every cell need source positions. Missing or
    # ambiguous words remain ordinary text instead of being promoted.
    boxes = [caption["bbox"]] + ([_word_box(header_words)] if header_words else [])
    boxes.extend(row["bbox"] for row in rows)
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[2] for box in boxes)
    y1 = max(box[3] for box in boxes)
    return {"id": f"p{number}-t{sequence}", "type": "table",
            "title": caption["title"], "continued": False,
            "bbox": [x0, y0, x1, y1], "unit_text": None,
            "columns": columns, "rows": rows}


def _dynamic_shareholders(caption: dict[str, Any], words: list[dict[str, Any]],
                          number: int, sequence: int) -> TableBlock | None:
    lines = _word_lines(words)
    header = next((line for line in lines
                   if caption["bbox"][1] + 12 <= line[0]["top"] < caption["bbox"][1] + 100
                   and sum(_plain(word["text"]) == "so" for word in line) >= 2
                   and sum(_plain(word["text"]).startswith("ty") for word in line) >= 2), None)
    if header is None:
        return None
    starts = [word for word in header if _plain(word["text"]) == "so" or
              _plain(word["text"]).startswith("ty")]
    starts = sorted(starts, key=lambda word: word["x0"])[:4]
    if len(starts) != 4 or [_plain(word["text"])[:2] for word in starts] != ["so", "ty", "so", "ty"]:
        return None
    value_left = starts[0]["x0"] - 12
    body: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []
    for line in lines:
        if line[0]["top"] < header[0]["top"] + 24:
            continue
        values = [word for word in line if word["x0"] >= value_left and
                  re.fullmatch(r"[\d.,]+%?", word["text"])]
        if len(values) == 4 and values[1]["text"].endswith("%") and values[3]["text"].endswith("%"):
            body.append((line, values))
    if not 3 <= len(body) <= 40:
        return None
    steps = [body[i + 1][0][0]["top"] - body[i][0][0]["top"] for i in range(len(body) - 1)]
    typical = statistics.median(steps) if steps else 22
    if typical <= 6 or typical > 80:
        return None
    columns: list[Column] = []
    for i, start in enumerate(starts):
        end_x = starts[i + 1]["x0"] - 10 if i < 3 else float("inf")
        header_part = [word for word in words if header[0]["top"] - 2 <= word["top"]
                       < body[0][0][0]["top"] - 10 and
                       start["x0"] - 10 <= word["x0"] < end_x]
        columns.append({"key": f"c{i+1}", "header_lines": _printed_lines(header_part),
                        "bbox": _word_box(header_part) if header_part else _word_box([start])})
    rows: list[Row] = []
    for i, (line, values) in enumerate(body):
        y0 = line[0]["top"] - 5
        y1 = (body[i+1][0][0]["top"] - 5 if i + 1 < len(body)
              else line[0]["top"] + min(typical * 1.4, 40))
        row_words = [word for word in words if y0 <= word["top"] < y1]
        labels = [word for word in row_words if word["x0"] < value_left]
        label = " ".join(_printed_lines(labels))
        if not label or any(word not in row_words for word in values):
            return None
        rows.append({"id": f"r{i+1}", "code": None, "label_raw": label,
                     "note": None, "bbox": _word_box(labels + values),
                     "cells": {f"c{j+1}": {"raw": value["text"], "bbox": _word_box([value])}
                               for j, value in enumerate(values)}})
    return _dynamic_table(caption, columns, rows, header, number, sequence)


def _dynamic_stock(caption: dict[str, Any], words: list[dict[str, Any]],
                   number: int, sequence: int) -> TableBlock | None:
    labels = ("ten co phieu", "loai co phieu", "ma chung khoan", "menh gia co phieu",
              "ngay bat dau", "tong so co phieu", "so luong co phieu", "ty le so huu")
    lines = [line for line in _word_lines(words)
             if line[0]["top"] > caption["bbox"][1] + 22]
    values_x = [word["x0"] for line in lines for word in line
                if word["x0"] > caption["bbox"][0] + 110]
    if not values_x:
        return None
    # The first word of each value is vertically aligned across printed rows.
    aligned = sorted(values_x, key=lambda x: -sum(abs(x - other) < 6 for other in values_x))
    split = aligned[0] - 8
    rows: list[Row] = []
    for line in lines:
        left = [word for word in line if word["x0"] < split]
        right = [word for word in line if word["x0"] >= split]
        label = " ".join(word["text"] for word in left)
        if not right or not any(_plain(label).startswith(prefix) for prefix in labels):
            continue
        rows.append({"id": f"r{len(rows)+1}", "code": None, "label_raw": label,
                     "note": None, "bbox": _word_box(left + right),
                     "cells": {"c1": {"raw": " ".join(word["text"] for word in right),
                                      "bbox": _word_box(right)}}})
    if not 4 <= len(rows) <= 15:
        return None
    if len({row["label_raw"] for row in rows}) != len(rows):
        return None
    gaps = [rows[i+1]["bbox"][1] - rows[i]["bbox"][1]
            for i in range(len(rows)-1)]
    if not 8 <= statistics.median(gaps) <= 50:
        return None
    column: Column = {"key": "c1", "header_lines": [], "bbox": None}
    return _dynamic_table(caption, [column], rows, [], number, sequence)


def _dynamic_top_shareholders(caption: dict[str, Any], words: list[dict[str, Any]],
                              number: int, sequence: int) -> TableBlock | None:
    header = next((line for line in _word_lines(words)
                   if any(_plain(w["text"]) == "stt" for w in line) and
                   any(_plain(w["text"]).startswith("doi") for w in line) and
                   any(_plain(w["text"]).startswith("ty") for w in line)), None)
    if header is None:
        return None
    rank_x = next(w["x0"] for w in header if _plain(w["text"]) == "stt")
    name_x = next(w["x0"] for w in header if _plain(w["text"]).startswith("doi"))
    share_x = next((w["x0"] for w in header if _plain(w["text"]) == "so"
                    and w["x0"] > name_x), None)
    pct_x = next(w["x0"] for w in header if _plain(w["text"]).startswith("ty"))
    if share_x is None or not rank_x < name_x < share_x < pct_x:
        return None
    ranks = sorted((w for w in words if header[0]["top"] + 15 < w["top"]
                    and abs(w["x0"] - rank_x) < 18
                    and re.fullmatch(r"\d{1,2}", w["text"])), key=lambda w: w["top"])
    if not 3 <= len(ranks) <= 20 or [int(w["text"]) for w in ranks] != list(range(1, len(ranks)+1)):
        return None
    steps = [ranks[i+1]["top"] - ranks[i]["top"] for i in range(len(ranks)-1)]
    typical = statistics.median(steps)
    rows: list[Row] = []
    for i, rank in enumerate(ranks):
        y0 = rank["top"] - 6
        y1 = ranks[i+1]["top"] - 6 if i+1 < len(ranks) else rank["top"] + max(typical, 35)
        band = [w for w in words if y0 <= w["top"] < y1]
        shares = [w for w in band if w["x0"] >= share_x - 20 and
                  w["x0"] < pct_x - 12 and re.fullmatch(r"[\d.,]+", w["text"])]
        percents = [w for w in band if w["x0"] >= pct_x - 15
                    and re.fullmatch(r"[\d.,]+%", w["text"])]
        names = [w for w in band if name_x - 6 <= w["x0"] < share_x - 20]
        if len(shares) != 1 or len(percents) != 1 or not names:
            return None
        rows.append({"id": f"r{i+1}", "code": rank["text"],
                     "label_raw": " ".join(_printed_lines(names)), "note": None,
                     "bbox": _word_box([rank] + names + shares + percents),
                     "cells": {"c1": {"raw": shares[0]["text"], "bbox": _word_box(shares)},
                               "c2": {"raw": percents[0]["text"], "bbox": _word_box(percents)}}})
    columns: list[Column] = [
        {"key": "c1", "header_lines": [" ".join(w["text"] for w in header
                                         if share_x <= w["x0"] < pct_x)],
         "bbox": _word_box([w for w in header if share_x <= w["x0"] < pct_x])},
        {"key": "c2", "header_lines": [" ".join(w["text"] for w in header
                                         if w["x0"] >= pct_x)],
         "bbox": _word_box([w for w in header if w["x0"] >= pct_x])}]
    return _dynamic_table(caption, columns, rows, header, number, sequence)


def _dynamic_named_table(caption: dict[str, Any], words: list[dict[str, Any]],
                         number: int, sequence: int) -> TableBlock | None:
    kind = caption["kind"]
    headers = _word_lines([w for w in words if caption["bbox"][1] + 10 < w["top"]
                           < caption["bbox"][1] + 90])
    if kind == "board":
        header = next((line for line in headers if
                       any(_plain(w["text"]).startswith("thanh") for w in line) and
                       any(_plain(w["text"]).startswith("chuc") for w in line) and
                       any(_plain(w["text"]).startswith("kinh") for w in line) and
                       any(_plain(w["text"]).startswith("ngay") for w in line)), None)
        terms = ("thanh", "chuc", "kinh", "ty", "ngay", "so", "ty")
    else:
        header = next((line for line in headers if
                       any(_plain(w["text"]).startswith("thanh") for w in line) and
                       any(_plain(w["text"]).startswith("chuc") for w in line) and
                       any(_plain(w["text"]).startswith("thu") for w in line)), None)
        terms = ("thanh", "chuc", "thu")
    if header is None:
        return None
    anchors = []
    used: set[int] = set()
    for term in terms:
        match = next((w for w in header if id(w) not in used and
                      _plain(w["text"]).startswith(term) and
                      (not anchors or w["x0"] > anchors[-1]["x0"])), None)
        if match is None:
            return None
        anchors.append(match)
        used.add(id(match))
    cuts = [words[0]["x0"] - 1] + [w["x0"] - 8 for w in anchors[1:]] + [max(w["x1"] for w in words) + 1]
    people = sorted((w for w in words if w["top"] > header[0]["top"] + 25
                     and abs(w["x0"] - anchors[0]["x0"]) < 15
                     and _plain(w["text"]) in ("ong", "ba")), key=lambda w: w["top"])
    if not 3 <= len(people) <= 30:
        return None
    steps = [people[i+1]["top"] - people[i]["top"] for i in range(len(people)-1)]
    typical = statistics.median(steps)
    rows: list[Row] = []
    for i, person in enumerate(people):
        y0 = person["top"] - 6
        y1 = people[i+1]["top"] - 6 if i+1 < len(people) else person["top"] + max(typical, 24)
        band = [w for w in words if y0 <= w["top"] < y1]
        if kind == "board_pay":
            amounts = [w for w in band if w["x0"] > anchors[1]["x0"] + 65
                       and re.fullmatch(r"[\d.,]+", w["text"])]
            if len(amounts) != 1:
                return None
            amount = amounts[0]
            parts = [[w for w in band if w["x0"] < cuts[1]],
                     [w for w in band if cuts[1] <= w["x0"] < amount["x0"]],
                     [amount]]
        else:
            parts = [[w for w in band if cuts[j] <= w["x0"] < cuts[j+1]]
                     for j in range(len(cuts)-1)]
        if any(not part for part in parts):
            return None
        label = " ".join(_printed_lines(parts[0]))
        if not _plain(label).startswith(("ong ", "ba ")):
            return None
        cells = {f"c{j}": {"raw": "\n".join(_printed_lines(part)),
                          "bbox": _word_box(part)}
                 for j, part in enumerate(parts[1:], 1)}
        if kind == "board":
            if (not re.fullmatch(r"\d+/\d+", cells["c5"]["raw"]) or
                    not re.fullmatch(r"[\d.,]+%", cells["c6"]["raw"])):
                return None
        elif not re.fullmatch(r"[\d.,]+", cells["c2"]["raw"]):
            return None
        rows.append({"id": f"r{i+1}", "code": None, "label_raw": label,
                     "note": None, "bbox": _word_box(band), "cells": cells})
    columns: list[Column] = []
    for j in range(1, len(anchors)):
        header_part = [w for w in words if header[0]["top"] - 2 <= w["top"]
                       < people[0]["top"] - 10 and cuts[j] <= w["x0"] < cuts[j+1]]
        columns.append({"key": f"c{j}", "header_lines": _printed_lines(header_part),
                        "bbox": _word_box(header_part) if header_part else _word_box([anchors[j]])})
    return _dynamic_table(caption, columns, rows, header, number, sequence)


def _dynamic_bks_pay(caption: dict[str, Any], words: list[dict[str, Any]],
                     number: int, sequence: int) -> TableBlock | None:
    header = next((line for line in _word_lines(words) if
                   any(_plain(w["text"]) == "stt" for w in line) and
                   any(_plain(w["text"]) == "noi" for w in line) and
                   any(_plain(w["text"]).startswith("ngan") for w in line) and
                   any(_plain(w["text"]) == "da" for w in line)), None)
    if header is None:
        return None
    budget = next(w for w in header if _plain(w["text"]).startswith("ngan"))
    paid = next(w for w in header if _plain(w["text"]) == "da")
    body = []
    for line in _word_lines(words):
        if line[0]["top"] <= header[0]["top"] + 15:
            continue
        values = [w for w in line if w["x0"] >= budget["x0"] - 10
                  and re.fullmatch(r"[\d.]+", w["text"])]
        if (len(values) == 2 and values[0]["x0"] < paid["x0"] and
                values[1]["x0"] >= paid["x0"] - 25):
            body.append((line, values))
    if not 3 <= len(body) <= 20:
        return None
    steps = [body[i+1][0][0]["top"] - body[i][0][0]["top"] for i in range(len(body)-1)]
    typical = statistics.median(steps)
    rows: list[Row] = []
    for i, (line, values) in enumerate(body):
        y0 = line[0]["top"] - 5
        y1 = body[i+1][0][0]["top"] - 5 if i+1 < len(body) else line[0]["top"] + max(typical, 25)
        band = [w for w in words if y0 <= w["top"] < y1]
        labels = [w for w in band if w["x0"] < budget["x0"] - 10]
        if not labels:
            return None
        code = labels[0]["text"] if re.fullmatch(r"\d{1,2}", labels[0]["text"]) else None
        if code:
            labels = labels[1:]
        if not labels:
            return None
        rows.append({"id": f"r{i+1}", "code": code,
                     "label_raw": " ".join(_printed_lines(labels)), "note": None,
                     "bbox": _word_box(band),
                     "cells": {f"c{j+1}": {"raw": value["text"], "bbox": _word_box([value])}
                               for j, value in enumerate(values)}})
    columns: list[Column] = [
        {"key": "c1", "header_lines": [" ".join(w["text"] for w in header
                                         if budget["x0"] <= w["x0"] < paid["x0"])],
         "bbox": _word_box([w for w in header if budget["x0"] <= w["x0"] < paid["x0"]])},
        {"key": "c2", "header_lines": [" ".join(w["text"] for w in header
                                         if w["x0"] >= paid["x0"])],
         "bbox": _word_box([w for w in header if w["x0"] >= paid["x0"]])}]
    return _dynamic_table(caption, columns, rows, header, number, sequence)


def dynamic_annual_tables(page: pdfplumber.page.Page) -> list[TableBlock]:
    """Promote only recognized, geometrically consistent annual tables."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    extractors = {"stock": _dynamic_stock, "shareholders": _dynamic_shareholders,
                  "top_shareholders": _dynamic_top_shareholders,
                  "board": _dynamic_named_table, "board_pay": _dynamic_named_table,
                  "bks_pay": _dynamic_bks_pay}
    captions = [caption for caption in annual_table_captions(page, words)
                if caption["kind"] in extractors]
    tables: list[TableBlock] = []
    for caption in captions:
        zone = _dynamic_zone(page, caption, captions)
        left, top, right, bottom = zone
        part = _words_in_band(words, left, right, top, bottom)
        table = extractors[caption["kind"]](caption, part, page.page_number, len(tables)+1)
        if table is not None:
            tables.append(table)
    return tables


def reviewed_annual_tables(page: pdfplumber.page.Page, override: dict[str, Any] | None,
                           header_blocks: list[dict[str, Any]] | None = None) -> list[TableBlock]:
    """Reconstruct only the annual tables whose geometry was reviewed on this PDF."""
    if override is None:
        return dynamic_annual_tables(page)
    table_specs = override["annual_tables"]
    specs = [spec for spec in table_specs if spec["page"] == page.page_number]
    if not specs:
        return []
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    tables: list[TableBlock] = []
    for sequence, spec in enumerate(specs, 1):
        x0, y0, x1, y1 = spec["box"]
        cuts = spec["cuts"]
        fields = spec["fields"].split()
        if len(fields) != len(cuts) - 1:
            raise ValueError(f"Trang {page.page_number}: số ranh giới cột không khớp {spec['title']}")
        candidate_words = _words_in_band(words, x0, x1, y0, y1)
        anchor_left, anchor_right, pattern = spec["anchor"]
        starts = sorted({word["top"] for word in candidate_words
                         if spec["body"] <= word["top"] < y1
                         and anchor_left <= word["x0"] < anchor_right
                         and re.fullmatch(pattern, word["text"])})
        if len(starts) != spec["rows"]:
            raise ValueError(f"Trang {page.page_number}: {spec['title']} có "
                             f"{len(starts)} dòng, dự kiến {spec['rows']}")
        columns: list[Column] = []
        value_headers = []
        for index, field in enumerate(fields):
            if not re.fullmatch(r"c[1-9]\d*", field):
                continue
            header_words = _words_in_band(candidate_words, cuts[index], cuts[index + 1],
                                          y0, spec["body"])
            value_headers.extend(header_words)
            columns.append({"key": field,
                            "header_lines": spec.get("headers", {}).get(field, _printed_lines(header_words)),
                            "bbox": _word_box(header_words) if header_words else None})
        if header_blocks is not None and value_headers:
            header_top = min(word["top"] for word in value_headers) - 5
            for index, field in enumerate(fields):
                if field not in ("label", "code", "note"):
                    continue
                header_words = _words_in_band(candidate_words, cuts[index], cuts[index + 1],
                                              header_top, spec["body"])
                if header_words:
                    header_blocks.append({"type": "paragraph", "text": "\n".join(_printed_lines(header_words)),
                                          "bbox": _word_box(header_words)})
        rows: list[Row] = []
        for position, start in enumerate(starts):
            # The first word of a printed row can sit a few points above its
            # numeric anchor because bold and regular fonts have different ascents.
            row_top = max(spec["body"], start - 8)
            end = starts[position + 1] - 8 if position + 1 < len(starts) else y1
            row_words = [word for word in candidate_words if row_top <= word["top"] < end]
            parts = {field: _words_in_band(row_words, cuts[index], cuts[index + 1], row_top, end)
                     for index, field in enumerate(fields)}
            label = " ".join(_printed_lines(parts.get("label", [])))
            code = " ".join(_printed_lines(parts.get("code", []))) or None
            if not label or not row_words:
                raise ValueError(f"Trang {page.page_number}: dòng {position + 1} của "
                                 f"{spec['title']} thiếu nhãn")
            cells: dict[str, Cell] = {
                field: {"raw": "\n".join(_printed_lines(part)), "bbox": _word_box(part)}
                for field, part in parts.items()
                if re.fullmatch(r"c[1-9]\d*", field) and part
            }
            if spec.get("percent_fields"):
                value_fields = [field for field in fields if re.fullmatch(r"c[1-9]\d*", field)]
                if any(field not in cells for field in value_fields):
                    raise ValueError(f"Trang {page.page_number}: {spec['title']} dòng {position + 1} thiếu ô")
                if any(not re.fullmatch(r"[\d.,]+%", cells[field]["raw"])
                       for field in spec.get("percent_fields", ())):
                    raise ValueError(f"Trang {page.page_number}: {spec['title']} dòng {position + 1} sai cột tỷ lệ")
            rows.append({"id": f"r{position + 1}", "code": code,
                         "label_raw": label, "note": None, "bbox": _word_box(row_words),
                         "cells": cells})
        if not rows or not columns:
            raise ValueError(f"Trang {page.page_number}: bảng {spec['title']} rỗng")
        table: TableBlock = {"id": f"p{page.page_number}-t{sequence}", "type": "table",
                             "title": spec["title"], "continued": spec.get("continued", False),
                             "bbox": _word_box(candidate_words), "unit_text": spec.get("unit"),
                             "columns": columns, "rows": rows}
        if spec.get("logical"):
            table["logical_table_id"] = spec["logical"]
        tables.append(table)
    return tables


def annual_content_index(documents: list[dict[str, Any]],
                         page_topics: dict[int, list[str]],
                         override: dict[str, Any] | None = None) -> dict[str, Any]:
    by_page = {document["page"]: document for document in documents}
    topics = [{"id": topic, "title": title,
               "pdf_pages": [number for number in sorted(page_topics)
                             if topic in page_topics[number]]}
              for topic, title in ANNUAL_TOPICS.items()]
    topics = [topic for topic in topics if topic["pdf_pages"]]
    tables = []
    if override is not None:
        table_specs = override["annual_tables"]
        for spec in table_specs:
            topic, number, title = spec["topic"], spec["page"], spec["title"]
            document = by_page.get(number)
            if document is None:
                continue
            content = _plain(" ".join(block.get("text", block.get("title", ""))
                                      for block in document["blocks"]))
            if _plain(title) not in content:
                raise ValueError(f"Trang {number}: thiếu tiêu đề '{title}' trong IR")
            match = next((block for block in document["blocks"] if block["type"] == "table"
                          and _plain(block.get("title") or "") == _plain(title)), None)
            tables.append({"topic": topic, "pdf_page": number, "title": title,
                           "ir_file": f"p-{number:03d}.ir.json",
                           "status": "structured" if match else "text_only",
                           "table_block_id": match["id"] if match else None})
    else:
        # A new PDF can mix confidently reconstructed tables with captions
        # whose layout is still ambiguous. Keep both states in one index.
        for number, document in by_page.items():
            seen: set[str] = set()
            for block in sorted(document["blocks"], key=lambda item: item["type"] != "table"):
                if block["type"] not in ("heading", "paragraph", "table") or not block.get("bbox"):
                    continue
                if (block["type"] != "table" and
                        block["bbox"][0] < document["page_size"]["width"] * .03):
                    continue
                caption = " ".join((block.get("title") or block.get("text") or "").split()).lstrip("• ").strip()
                if len(caption) > 160 or _caption_kind(caption) is None:
                    continue
                key = _plain(caption)
                if key in seen:
                    continue
                seen.add(key)
                tables.append({"topic": page_topics[number][0], "pdf_page": number,
                               "title": caption, "ir_file": f"p-{number:03d}.ir.json",
                               "status": "structured" if block["type"] == "table" else "text_only",
                               "needs_review": block["type"] != "table",
                               "table_block_id": block["id"] if block["type"] == "table" else None})
    return {"topics": topics, "table_targets": tables}

def reviewed_kpis(page: pdfplumber.page.Page,
                  override: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return PDF-specific reviewed values and captions, or unreviewed candidates."""
    candidates = kpi_candidates(page)
    captions = override.get("kpi_captions", {}) if override else {}
    if str(page.page_number) not in captions:
        return [{**candidate, "review_status": "candidate"} for candidate in candidates]
    expected = captions[str(page.page_number)]
    values = [item["value_raw"] for item in candidates]
    if values != [value for value, _caption in expected]:
        raise ValueError(f"Trang {page.page_number}: dãy KPI đã duyệt thay đổi: {values}")
    return [{**candidate, "label": caption, "auto_label": candidate["label"],
             "review_status": "verified", "evidence": "visual review of source PDF"}
            for candidate, (_value, caption) in zip(candidates, expected)]
