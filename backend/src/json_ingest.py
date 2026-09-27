"""Convert JSON payloads into Page objects and semantic text for the Vector RAG pipeline.

Integrates with `financial_mapping.py` to map raw keys (bsa, bsb, isa, isb, cfa, ratios)
into canonical uppercase observation codes (e.g., TOTAL_ASSETS, PROFIT_BEFORE_TAX, PE, ROE).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

# Ensure UTF-8 output on Windows consoles when this module is imported
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .chunking import Page

# Safe import for financial_mapping regardless of invocation path
try:
    from ..financial_mapping import META_KEYS, get_code
except (ImportError, ValueError):
    try:
        from financial_mapping import META_KEYS, get_code
    except ImportError:
        import sys
        backend_dir = Path(__file__).resolve().parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from financial_mapping import META_KEYS, get_code

# Mapping of section keys to standard Vietnamese headers
SECTION_MAP: Final[dict[str, str]] = {
    "ratios": "Chỉ số tài chính",
    "income_statement": "Báo cáo Kết quả hoạt động kinh doanh",
    "balance_sheet": "Bảng Cân đối kế toán",
    "cash_flow_statement": "Báo cáo Lưu chuyển tiền tệ",
}

SECTION_PAGE: Final[dict[str, int]] = {
    "prices": 0,
    "ratios": 1,
    "income_statement": 2,
    "balance_sheet": 3,
    "cash_flow_statement": 4,
}


def parse_period_label(label: str | None) -> str:
    """Parse period_label into a readable Vietnamese format.

    Examples:
        '2026-Q2' -> 'Quý 2/2026'
        '2025-YEAR' -> 'Năm 2025'
        '2025' -> 'Năm 2025'
    """
    if not label:
        return ""
    label_str = str(label).strip()
    if "-Q" in label_str:
        parts = label_str.split("-Q")
        if len(parts) == 2:
            return f"Quý {parts[1]}/{parts[0]}"
    if "-YEAR" in label_str:
        year = label_str.replace("-YEAR", "")
        return f"Năm {year}"
    if label_str.isdigit() and len(label_str) == 4:
        return f"Năm {label_str}"
    return label_str


def json_to_text(json_path: str | Path) -> str:
    """Read a normalized financial JSON file and convert it into semantic Vietnamese text.

    Args:
        json_path: Path to normalized JSON file (e.g. data/normalized/BID.json).

    Returns:
        Consolidated semantic text block for all financial sections.
    """
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    symbol = data.get("symbol") or path.stem.upper()
    financial_data = data.get("financial_data") or {}

    section_blocks: list[str] = []

    for section_key, section_vi in SECTION_MAP.items():
        rows = financial_data.get(section_key)
        if not rows or not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            raw_period = row.get("period_label", "")
            period = parse_period_label(raw_period)
            header = f"{symbol} - {section_vi} - {period}" if period else f"{symbol} - {section_vi}"

            lines = [header]
            for key, value in row.items():
                if key in META_KEYS:
                    continue
                # Skip non-numeric or boolean values
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                # Skip zero or null values
                if value == 0 or value is None:
                    continue

                code = get_code(key, section_key)

                # Format: monetary values in VND (>= 1,000,000) are converted to triệu VND
                if section_key == "ratios" and abs(value) < 1000:
                    val_str = f"{value:,.2f}" if abs(value) >= 0.01 else f"{value:.4g}"
                    lines.append(f"- {code}: {val_str}")
                else:
                    val_in_millions = value / 1_000_000 if abs(value) >= 1_000_000 else value
                    lines.append(f"- {code}: {val_in_millions:,.0f} triệu VND")

            if len(lines) > 1:
                section_blocks.append("\n".join(lines))

    return "\n\n".join(section_blocks)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split long text into overlapping chunks.

    Args:
        text: The source text to split.
        chunk_size: Maximum character length per chunk (default 500).
        overlap: Character overlap between consecutive chunks (default 50).

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be strictly greater than overlap")

    chunks: list[str] = []
    start = 0
    text_len = len(text)
    step = chunk_size - overlap

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start += step

    return chunks


# ==============================================================================
# Helper functions for FastAPI Document Ingestion (Preserved for compatibility)
# ==============================================================================

def _fmt(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:.4g}"
    return str(value)


def _price_month_pages(symbol: str, price_history: list[dict]) -> list[Page]:
    if not price_history:
        return []
    months: dict[str, list[dict]] = {}
    for bar in price_history:
        key = (bar.get("date") or "")[:7]
        months.setdefault(key, []).append(bar)

    lines = []
    for month in sorted(months):
        bars = months[month]
        highs = [b["high"] for b in bars if isinstance(b.get("high"), (int, float))]
        lows = [b["low"] for b in bars if isinstance(b.get("low"), (int, float))]
        volumes = [b["volume"] for b in bars if isinstance(b.get("volume"), (int, float))]
        lines.append(
            f"Cổ phiếu {symbol} tháng {month}: mở cửa {_fmt(bars[0].get('open'))}, "
            f"đóng cửa {_fmt(bars[-1].get('close'))}, "
            f"cao nhất {_fmt(max(highs) if highs else None)}, "
            f"thấp nhất {_fmt(min(lows) if lows else None)}, "
            f"tổng khối lượng giao dịch {_fmt(sum(volumes) if volumes else None)}, "
            f"{len(bars)} phiên giao dịch."
        )
    return [Page(page=SECTION_PAGE["prices"], text=" ".join(lines))]


def _ratio_pages(symbol: str, rows: list[dict]) -> list[Page]:
    pages = []
    for row in rows:
        label = parse_period_label(row.get("period_label", "?"))
        parts = [f"Chỉ số tài chính {symbol} kỳ {label}:"]
        for key, value in row.items():
            if key in META_KEYS or value is None:
                continue
            code = get_code(key, "ratios")
            display_code = {"PE": "P/E", "PB": "P/B", "PS": "P/S"}.get(code, code)
            parts.append(f"{display_code} {_fmt(value)};")
        pages.append(Page(page=SECTION_PAGE["ratios"], text=" ".join(parts)))
    return pages


def _statement_pages(symbol: str, section: str, rows: list[dict]) -> list[Page]:
    label_vi = SECTION_MAP.get(section, section)
    pages = []
    for row in rows:
        label = parse_period_label(row.get("period_label", "?"))
        parts = [f"{label_vi} {symbol} kỳ {label}:"]
        for key, value in row.items():
            if key in META_KEYS or value is None:
                continue
            code = get_code(key, section)
            parts.append(f"{code}: {_fmt(value)} |")
        pages.append(Page(page=SECTION_PAGE.get(section, 0), text=" ".join(parts)))
    return pages


def is_normalized_financial_payload(data) -> bool:
    """True for the schema produced by data_pipeline (data/normalized/*.json)."""
    return isinstance(data, dict) and "price_history" in data and "financial_data" in data


def financial_json_to_pages(symbol: str, payload: dict) -> list[Page]:
    """One page per price-month summary or per reporting period."""
    financial_data = payload.get("financial_data", {}) or {}
    pages: list[Page] = []
    pages += _price_month_pages(symbol, payload.get("price_history") or [])
    pages += _ratio_pages(symbol, financial_data.get("ratios") or [])
    pages += _statement_pages(symbol, "income_statement", financial_data.get("income_statement") or [])
    pages += _statement_pages(symbol, "balance_sheet", financial_data.get("balance_sheet") or [])
    pages += _statement_pages(symbol, "cash_flow_statement", financial_data.get("cash_flow_statement") or [])
    return pages


def _record_text(prefix: str, record: dict) -> str:
    fields = " ".join(f"{k}: {_fmt(v)} |" for k, v in record.items() if v is not None)
    return f"{prefix}: {fields}" if prefix else fields


def generic_json_to_pages(data) -> list[Page]:
    """Best-effort chunking for a generic JSON upload."""
    if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
        return [Page(page=index, text=_record_text("", item)) for index, item in enumerate(data)]

    if isinstance(data, dict):
        list_fields = {
            key: value
            for key, value in data.items()
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        }
        if list_fields:
            pages = []
            index = 0
            for field_name, rows in list_fields.items():
                for row in rows:
                    pages.append(Page(page=index, text=_record_text(f"{field_name} #{index}", row)))
                    index += 1
            return pages

    return [Page(page=0, text=json.dumps(data, ensure_ascii=False))]
