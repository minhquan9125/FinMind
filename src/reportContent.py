"""Evidence-based section and KPI extraction for annual-report pages.

This module does not change the one-page Document IR schema. A report section
spans pages, so its page ranges are written to a separate document index.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

import pdfplumber


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


FPT_2024_SHA256 = "fc9f2c52317e6690ac723266d7d892328cf2c362b3f23e7f88c4fca403c94b52"
FPT_2025_SHA256 = "9449a7251d126b635988974dbc72c2773c7fff39f4e5e858b5f7d3928b4e0e6c"

# Chỉ mục nội dung thường niên. Số trang FPT được kiểm tra trên đúng PDF mẫu;
# PDF khác chỉ dùng nhãn chương đọc được trên chính tài liệu đó.
ANNUAL_TOPICS = {
    "leadership": "Thông điệp ban lãnh đạo",
    "company": "Doanh nghiệp, ngành nghề và cơ cấu tổ chức",
    "shareholders": "Cổ đông, cổ phần và thay đổi vốn",
    "strategy": "Chiến lược phát triển",
    "performance": "Kết quả hoạt động và kế hoạch",
    "governance": "Quản trị công ty",
    "people_esg": "Nhân sự và ESG",
}

FPT_ANNUAL_RANGES = {
    "company": [(20, 20), (24, 28)],
    "shareholders": [(29, 32)],
    "strategy": [(41, 49)],
    "performance": [(50, 67)],
    "governance": [(33, 40), (68, 95)],
    "people_esg": [(57, 57), (96, 141)],
}

STOCK_TRANSACTION_HEADERS = {
    "c2": ["Số cổ phiếu sở hữu đầu kỳ", "Số cổ phiếu"],
    "c3": ["Số cổ phiếu sở hữu đầu kỳ", "Tỷ lệ"],
    "c4": ["Số cổ phiếu sở hữu cuối kỳ", "Số cổ phiếu"],
    "c5": ["Số cổ phiếu sở hữu cuối kỳ", "Tỷ lệ"],
}
INSIDER_CONTRACT_HEADERS = {
    "c6": ["Nội dung và tổng giá trị giao dịch", "Giao dịch"],
    "c7": ["Nội dung và tổng giá trị giao dịch", "Tổng giá trị"],
}

# Coordinates in PDF points, reviewed on the exact FPT sample. A spec defines
# printed column boundaries, the row-start column and the expected row count.
FPT_ANNUAL_TABLES = [
    dict(page=29, topic="shareholders", title="THÔNG TIN VỀ CỔ PHIẾU", box=(429, 185, 1115, 670),
         cuts=(429, 840, 1115), fields="label c1", body=200, anchor=(435, 450, r".+"), rows=10),
    dict(page=29, topic="shareholders", title="CƠ CẤU CỔ ĐÔNG THEO CÁC MỨC CỔ PHIẾU SỞ HỮU",
         box=(1166, 155, 1865, 500), cuts=(1166, 1330, 1440, 1580, 1715, 1865),
         fields="label c1 c2 c3 c4", body=270, anchor=(1170, 1190, r"(?:\d[\d.]*|Tổng)"), rows=5),
    dict(page=29, topic="shareholders", title="CƠ CẤU CỔ ĐÔNG THEO ĐỐI TƯỢNG SỞ HỮU",
         box=(1166, 615, 1865, 995), cuts=(1166, 1330, 1440, 1580, 1715, 1865),
         fields="label c1 c2 c3 c4", body=710, anchor=(1170, 1190, r"(?:Nhà|Cổ|Tổng)"), rows=5),
    dict(page=30, topic="shareholders", title="CƠ CẤU CỔ ĐÔNG THEO QUỐC TỊCH",
         box=(429, 100, 1115, 440), cuts=(429, 550, 670, 800, 980, 1115),
         fields="label c1 c2 c3 c4", body=178, anchor=(438, 455, r"(?:Việt|Cá|Tổ|Nước|Tổng)"), rows=7),
    dict(page=30, topic="shareholders", title="TOP 10 CỔ ĐÔNG LỚN",
         box=(1166, 105, 1865, 495), cuts=(1166, 1238, 1610, 1780, 1865),
         fields="code label c1 c2", body=140, anchor=(1185, 1210, r"\d{1,2}"), rows=10),
    dict(page=30, topic="shareholders", title="TÌNH HÌNH THAY ĐỔI VỐN ĐIỀU LỆ",
         box=(429, 590, 1865, 1015), cuts=(429, 510, 640, 830, 1865),
         fields="code c1 c2 label", body=650, anchor=(443, 465, r"\d{1,2}"), rows=10,
         logical="fpt-2024-charter-capital", unit="Đơn vị: VNĐ"),
    dict(page=31, topic="shareholders", title="TÌNH HÌNH THAY ĐỔI VỐN ĐIỀU LỆ (tiếp theo)",
         box=(429, 105, 1865, 1020), cuts=(429, 510, 640, 830, 1865),
         fields="code c1 c2 label", body=165, anchor=(440, 465, r"\d{1,2}"), rows=21,
         logical="fpt-2024-charter-capital", continued=True, unit="Đơn vị: VNĐ"),
    dict(page=32, topic="shareholders", title="TÌNH HÌNH THAY ĐỔI VỐN ĐIỀU LỆ (tiếp theo)",
         box=(429, 105, 1865, 635), cuts=(429, 510, 640, 830, 1865),
         fields="code c1 c2 label", body=165, anchor=(440, 465, r"\d{1,2}"), rows=10,
         logical="fpt-2024-charter-capital", continued=True, unit="Đơn vị: VNĐ"),
    dict(page=57, topic="people_esg", title="NHÂN SỰ BÌNH QUÂN CỦA LĨNH VỰC DỊCH VỤ CNTT CHO THỊ TRƯỜNG NƯỚC NGOÀI",
         box=(1166, 115, 1865, 330), cuts=(1166, 1580, 1700, 1785, 1865),
         fields="label c1 c2 c3", body=178, anchor=(1175, 1195, r"(?:Tổng|Doanh)"), rows=3),
    dict(page=77, topic="governance", title="DANH SÁCH THÀNH VIÊN HĐQT NHIỆM KỲ 2022-2027 VÀ SỐ CUỘC HỌP THAM DỰ TRONG NĂM 2024",
         box=(429, 105, 1865, 860), cuts=(429, 750, 1290, 1510, 1690, 1865),
         fields="label c1 c2 c3 c4", body=165, anchor=(430, 450, r"(?:Ông|Bà)"), rows=7),
    dict(page=83, topic="governance", title="GIAO DỊCH CỔ PHIẾU CỦA CỔ ĐÔNG LỚN VÀ CỔ ĐÔNG NỘI BỘ",
         box=(429, 105, 1865, 1000), cuts=(429, 480, 710, 900, 1025, 1110, 1240, 1320, 1865),
         fields="code label c1 c2 c3 c4 c5 c6", body=205, anchor=(445, 470, r"\d{1,2}"), rows=10,
         headers=STOCK_TRANSACTION_HEADERS),
    dict(page=84, topic="governance", title="HỢP ĐỒNG HOẶC GIAO DỊCH VỚI CỔ ĐÔNG NỘI BỘ",
         box=(429, 185, 1865, 1000), cuts=(429, 470, 605, 725, 855, 1055, 1110, 1455, 1700, 1865),
         fields="code label c1 c2 c3 c4 c5 c6 c7", body=290,
         anchor=(438, 460, r"\d{1,2}"), rows=4,
         logical="fpt-2024-insider-contracts", unit="Đơn vị: VNĐ",
         headers=INSIDER_CONTRACT_HEADERS),
    dict(page=85, topic="governance", title="HỢP ĐỒNG HOẶC GIAO DỊCH VỚI CỔ ĐÔNG NỘI BỘ (tiếp theo)",
         box=(429, 105, 1865, 900), cuts=(429, 470, 605, 725, 855, 1055, 1110, 1455, 1700, 1865),
         fields="code label c1 c2 c3 c4 c5 c6 c7", body=215,
         anchor=(438, 460, r"\d{1,2}"), rows=3,
         logical="fpt-2024-insider-contracts", continued=True, unit="Đơn vị: VNĐ",
         headers=INSIDER_CONTRACT_HEADERS),
    dict(page=86, topic="governance", title="HỢP ĐỒNG HOẶC GIAO DỊCH VỚI CỔ ĐÔNG NỘI BỘ (tiếp theo)",
         box=(429, 105, 1865, 925), cuts=(429, 470, 605, 725, 855, 1055, 1110, 1455, 1700, 1865),
         fields="code label c1 c2 c3 c4 c5 c6 c7", body=215,
         anchor=(438, 460, r"\d{1,2}"), rows=3,
         logical="fpt-2024-insider-contracts", continued=True, unit="Đơn vị: VNĐ",
         headers=INSIDER_CONTRACT_HEADERS),
    dict(page=95, topic="governance", title="CHI TIẾT THÙ LAO CỦA BKS NĂM 2024",
         box=(1166, 290, 1865, 495), cuts=(1166, 1235, 1440, 1700, 1865),
         fields="code label c1 c2", body=330, anchor=(1185, 1260, r"(?:[1-3]|Tổng)"), rows=4,
         unit="Đơn vị: VNĐ"),
]


def annual_topics(number: int, section: str | None, digest: str) -> list[str]:
    if digest == FPT_2024_SHA256:
        return [topic for topic, ranges in FPT_ANNUAL_RANGES.items()
                if any(first <= number <= last for first, last in ranges)]
    return {
        "leadership": ["leadership"], "highlights": ["performance"],
        "overview": ["company"], "strategy": ["strategy"],
        "business": ["performance"], "governance": ["governance"],
        "esg": ["people_esg"],
    }.get(section, [])


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


def reviewed_annual_tables(page: pdfplumber.page.Page, digest: str,
                           header_blocks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Reconstruct only the annual tables whose geometry was reviewed on this PDF."""
    if digest != FPT_2024_SHA256:
        return []
    specs = [spec for spec in FPT_ANNUAL_TABLES if spec["page"] == page.page_number]
    if not specs:
        return []
    words = page.extract_words(x_tolerance=2, y_tolerance=3)
    tables = []
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
        columns = []
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
        rows = []
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
            cells = {field: {"raw": "\n".join(_printed_lines(part)), "bbox": _word_box(part)}
                     for field, part in parts.items()
                     if re.fullmatch(r"c[1-9]\d*", field) and part}
            rows.append({"id": f"r{position + 1}", "code": code,
                         "label_raw": label, "note": None, "bbox": _word_box(row_words),
                         "cells": cells})
        if not rows or not columns:
            raise ValueError(f"Trang {page.page_number}: bảng {spec['title']} rỗng")
        table = {"id": f"p{page.page_number}-t{sequence}", "type": "table",
                 "title": spec["title"], "continued": spec.get("continued", False),
                 "bbox": _word_box(candidate_words), "unit_text": spec.get("unit"),
                 "columns": columns, "rows": rows}
        if spec.get("logical"):
            table["logical_table_id"] = spec["logical"]
        tables.append(table)
    return tables


def annual_content_index(documents: list[dict[str, Any]],
                         page_topics: dict[int, list[str]], digest: str) -> dict[str, Any]:
    by_page = {document["page"]: document for document in documents}
    topics = [{"id": topic, "title": title,
               "pdf_pages": [number for number in sorted(page_topics)
                             if topic in page_topics[number]]}
              for topic, title in ANNUAL_TOPICS.items()]
    topics = [topic for topic in topics if topic["pdf_pages"]]
    tables = []
    if digest == FPT_2024_SHA256:
        for spec in FPT_ANNUAL_TABLES:
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
        # Locate likely annual tables by their visible caption. Discovery is
        # intentionally separate from promotion to structured rows/cells.
        captions = ("co cau co dong", "thong tin ve co phieu", "top 10 co dong",
                    "danh sach thanh vien hdqt", "chi tiet thu lao")
        for number, document in by_page.items():
            for block in document["blocks"]:
                if block["type"] not in ("heading", "paragraph") or not block.get("bbox"):
                    continue
                if block["bbox"][0] < document["page_size"]["width"] * .22:
                    continue
                caption = " ".join(block["text"].split()).lstrip("• ").strip()
                if len(caption) > 140 or not any(_plain(caption).startswith(term)
                                                      for term in captions):
                    continue
                tables.append({"topic": page_topics[number][0], "pdf_page": number,
                               "title": caption, "ir_file": f"p-{number:03d}.ir.json",
                               "status": "text_only", "table_block_id": None})
    return {"topics": topics, "table_targets": tables}

# Transcribed from the printed captions beside the large figures on these pages.
# The value sequence is checked on every build so a changed PDF cannot inherit
# a label from this particular edition of the report.
FPT_KPI_CAPTIONS: dict[int, list[tuple[str, str]]] = {
    24: [("37.666", "Nhân lực công nghệ"), ("10.000", "Chứng chỉ NVIDIA")],
    25: [("4.890", "Dung lượng băng thông quốc tế"),
         ("50+", "Triệu người dùng trên toàn cầu")],
    26: [("40+", "Quốc gia có hợp tác đào tạo"), ("180", "Đối tác quốc tế")],
    44: [("68,5", "Thị trường cơ sở hạ tầng AI năm 2024")],
    45: [("31,4", "Thị trường bán dẫn Việt Nam vào năm 2029"),
         ("79,3", "Trí tuệ nhân tạo đóng góp cho Việt Nam vào năm 2030")],
    98: [("100%", "Sử dụng đèn Led tại các văn phòng xây mới"),
         ("100%", "Sử dụng cốc bằng vật liệu thân thiện môi trường"),
         ("100%", "Không sử dụng chai nhựa trong văn phòng"),
         ("100%", "Túi đựng rác trong văn phòng bằng các vật liệu có thể tái chế"),
         ("66,3", "Hỗ trợ hoạt động cộng đồng"),
         ("1.769.884", "Hợp đồng ký số, chiếm khoảng 80% tổng hợp đồng ký kết"),
         ("100%", "Văn bản nội bộ được ký số"),
         ("54.687", "Việc làm ổn định"),
         ("168,1", "Học bổng Nguyễn Văn Đạo"),
         ("62.540", "Người được hỗ trợ trên phạm vi toàn quốc"),
         ("37,1%", "Nhân sự nữ"),
         ("36,0%", "Cán bộ quản lý nữ"),
         ("184,7", "Cho hoạt động đào tạo nội bộ"),
         ("118.000", "Giờ học, tiếp cận thông tin ESG"),
         ("3.489", "Nhân sự người nước ngoài (87 quốc tịch)"),
         ("1.880", "Đơn vị máu được hiến tặng"),
         ("431", "Cây cầu nâng bước em đến trường")],
    133: [("100%", "Cơ sở thuộc quyền kiểm soát vận hành của FPT được tiến hành kiểm kê khí nhà kính"),
          ("143.574", "Tổng phát thải khí nhà kính thuộc phạm vi 1 và 2"),
          ("100%", "Dữ liệu phát thải khí nhà kính phạm vi 1,2 và 3 được chuẩn hoá và triển khai đồng bộ tới CTTV"),
          ("100%", "Dữ liệu phát thải phạm vi 1 và 2 được thu thập, tính toán")],
}

# Reviewed on PDF page 137 of the exact FPT 2025 annual report.
FPT_2025_KPI_CAPTIONS: dict[int, list[tuple[str, str]]] = {
    137: [("43,9%", "Nhân sự dưới 30 tuổi"),
          ("53,2%", "Cán bộ quản lý dưới 40 tuổi")],
}


def reviewed_kpis(page: pdfplumber.page.Page, digest: str) -> list[dict[str, Any]]:
    """Return PDF-specific reviewed values and captions, or unreviewed candidates."""
    candidates = kpi_candidates(page)
    captions = (FPT_KPI_CAPTIONS if digest == FPT_2024_SHA256 else
                FPT_2025_KPI_CAPTIONS if digest == FPT_2025_SHA256 else {})
    if page.page_number not in captions:
        return [{**candidate, "review_status": "candidate"} for candidate in candidates]
    expected = captions[page.page_number]
    values = [item["value_raw"] for item in candidates]
    if values != [value for value, _caption in expected]:
        raise ValueError(f"Trang {page.page_number}: dãy KPI đã duyệt thay đổi: {values}")
    return [{**candidate, "label": caption, "auto_label": candidate["label"],
             "review_status": "verified", "evidence": "visual review of source PDF"}
            for candidate, (_value, caption) in zip(candidates, expected)]
