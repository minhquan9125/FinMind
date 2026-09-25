"""Convert JSON payloads into Page objects for the Vector RAG pipeline.

Two shapes are handled:
- The normalized financial JSON produced by data_pipeline/src/scrapers/
  direct_vn_collector.py (data/normalized/{SYMBOL}.json): one page per
  price-month summary or per reporting period.
- Arbitrary JSON uploads (POST /api/documents/json): a best-effort, schema-
  agnostic flattening so any record-shaped JSON can still be chunked.

Output feeds straight into chunking.build_chunks(), so the same 130-word/
100-stride windowing and embedding pipeline used for PDFs applies here too -
no separate ranking or storage path is needed.

Income statement / balance sheet / cash flow rows use the data provider's
internal field codes (isaNN, bsaNN, cfaNN, ...) with no human-readable legend
available in this repo, so those three sections are serialized as raw
"code: value" pairs. Semantic search quality for them will be weaker than for
prices/ratios (which do have readable field names) until a code->label
dictionary is added.
"""

from __future__ import annotations

import json

from .chunking import Page

RATIO_LABELS: dict[str, str] = {
    "marketCap": "Vốn hóa thị trường",
    "dividendYield": "Tỷ suất cổ tức",
    "pe": "P/E",
    "pb": "P/B",
    "ps": "P/S",
    "priceToCashFlow": "Giá trên dòng tiền",
    "evToEbitda": "EV/EBITDA",
    "cashRatio": "Tỷ số tiền mặt",
    "quickRatio": "Tỷ số thanh toán nhanh",
    "currentRatio": "Tỷ số thanh toán hiện hành",
    "ownersEquity": "Vốn chủ sở hữu",
    "debtPerEquity": "Nợ trên vốn chủ sở hữu (lần)",
    "debtToEquity": "Nợ trên vốn chủ sở hữu",
    "roe": "ROE",
    "roa": "ROA",
    "grossMargin": "Biên lợi nhuận gộp",
    "ebitMargin": "Biên EBIT",
    "preTaxProfitMargin": "Biên lợi nhuận trước thuế",
    "afterTaxProfitMargin": "Biên lợi nhuận sau thuế",
    "assetTurnover": "Vòng quay tài sản",
    "roic": "ROIC",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "financialLeverage": "Đòn bẩy tài chính",
    "equity": "Vốn chủ sở hữu",
    "npl": "Tỷ lệ nợ xấu",
    "car": "Hệ số an toàn vốn (CAR)",
}

_RATIO_META_KEYS = {
    "period_label", "period_type", "year", "quarter", "ratioTTMId", "ratioType",
    "organCode", "yearReport", "ratioYearId",
}

FINANCIAL_META_KEYS = {
    "period_label", "period_type", "year", "quarter", "organCode", "ticker",
    "createDate", "updateDate", "yearReport", "lengthReport", "publicDate",
}

SECTION_PAGE = {
    "prices": 0,
    "ratios": 1,
    "income_statement": 2,
    "balance_sheet": 3,
    "cash_flow_statement": 4,
}

SECTION_LABELS_VI = {
    "income_statement": "Báo cáo kết quả kinh doanh",
    "balance_sheet": "Bảng cân đối kế toán",
    "cash_flow_statement": "Báo cáo lưu chuyển tiền tệ",
}


def _fmt(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        # Plain comma-grouped integer for large amounts (VND figures easily
        # exceed 1e12) instead of e.g. "6.093e+13", which is unreadable and
        # won't match a user's literal-number search query; small ratios
        # (pe, roe, ...) keep up to 4 significant decimal digits.
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:.4g}"
    return str(value)


def _price_month_pages(symbol: str, price_history: list[dict]) -> list[Page]:
    if not price_history:
        return []
    months: dict[str, list[dict]] = {}
    for bar in price_history:
        key = (bar.get("date") or "")[:7]  # YYYY-MM
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
        label = row.get("period_label", "?")
        parts = [f"Chỉ số tài chính {symbol} kỳ {label}:"]
        for key, value in row.items():
            if key in _RATIO_META_KEYS or value is None:
                continue
            parts.append(f"{RATIO_LABELS.get(key, key)} {_fmt(value)};")
        pages.append(Page(page=SECTION_PAGE["ratios"], text=" ".join(parts)))
    return pages


def _statement_pages(symbol: str, section: str, rows: list[dict]) -> list[Page]:
    label_vi = SECTION_LABELS_VI[section]
    pages = []
    for row in rows:
        label = row.get("period_label", "?")
        parts = [f"{label_vi} {symbol} kỳ {label}:"]
        for key, value in row.items():
            if key in FINANCIAL_META_KEYS or value is None:
                continue
            parts.append(f"{key}: {_fmt(value)} |")
        pages.append(Page(page=SECTION_PAGE[section], text=" ".join(parts)))
    return pages


def is_normalized_financial_payload(data) -> bool:
    """True for the schema produced by data_pipeline (data/normalized/*.json)."""
    return isinstance(data, dict) and "price_history" in data and "financial_data" in data


def financial_json_to_pages(symbol: str, payload: dict) -> list[Page]:
    """One page per price-month summary or per reporting period, so
    build_chunks() can window/split them exactly like PDF pages."""
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
    """Best-effort chunking for a JSON upload that is not the FinMind
    normalized financial schema: one page per record in the first list-of-
    objects found (top-level list, or a top-level field holding one), or a
    single page for the whole payload as a last resort."""
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
