"""Chunk text that already lives in Supabase instead of PDF files.

Sources supported:

* financial statements: rows of ``observations`` joined with ``metrics``,
  ``financial_reports``, ``reporting_periods`` and ``companies``;
* news: rows of ``news_articles``;
* stock prices: ``price_bars`` (+ ``price_indicators``), one document per symbol;
* market indices: ``market_index_bars``, one document per index;
* company profiles: ``companies``.

Design rules (agreed in the chunk contract):

* a chunk never splits a table row or a sentence-sized unit;
* every chunk repeats the section header, so a number is never separated from
  its company, period, statement scope and unit;
* ``chunk_id`` is deterministic: same source and same content give the same
  id on every run, a changed value gives a new id;
* every chunk carries a ``locator`` that points back to the exact source rows
  (``observation_id`` for financial facts, ``article_id``/``url`` for news).

This module is pure: it does not touch the database. See ``db_source.py`` for
the SQL that feeds it and ``scripts/chunk_from_supabase.py`` for the CLI.
The PDF path in ``chunking.py`` is left unchanged.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

# Same namespace as backend/scripts/ingest_*.py so ids line up across tools.
NAMESPACE = uuid.UUID("b77dbd7f-5d89-479d-90a3-421e5f0981ea")
CHUNKER_VERSION = "db-v1"
DEFAULT_MAX_WORDS = 130  # same order of magnitude as the PDF window (130 words)

SECTION_ORDER = ("INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW", "RATIO")
SECTION_LABEL_VI = {
    "INCOME_STATEMENT": "Báo cáo Kết quả hoạt động kinh doanh",
    "BALANCE_SHEET": "Bảng Cân đối kế toán",
    "CASH_FLOW": "Báo cáo Lưu chuyển tiền tệ",
    "RATIO": "Chỉ số tài chính",
}
FLOW_SECTIONS = {"INCOME_STATEMENT", "CASH_FLOW"}


# --------------------------------------------------------------------- types

@dataclass(frozen=True)
class SourceRow:
    """One indivisible line of source text."""

    key: str  # observation_id, or "p<number>" for a news paragraph
    text: str


@dataclass
class SourceSection:
    label: str
    header: str  # repeated at the top of every chunk of this section
    rows: list[SourceRow]


@dataclass
class SourceDocument:
    source_table: str  # financial_reports | news_articles
    source_id: str
    doc_type: str  # FINANCIAL_STATEMENT | NEWS
    title: str
    symbol: str | None
    language: str
    sections: list[SourceSection]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def document_id(self) -> str:
        return str(uuid.uuid5(NAMESPACE, f"document:{self.source_table}:{self.source_id}"))


@dataclass
class DbChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    section_index: int
    section_label: str
    text: str
    token_count: int
    char_start: int  # offsets inside the section body (rows joined by "\n")
    char_end: int
    content_hash: str
    locator: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "section_index": self.section_index,
            "section_label": self.section_label,
            "text": self.text,
            "token_count": self.token_count,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "content_hash": self.content_hash,
            "locator": self.locator,
        }


# ----------------------------------------------------------------- chunking

def _words(text: str) -> int:
    return len(text.split())


def section_body(section: SourceSection) -> str:
    return "\n".join(row.text for row in section.rows)


def chunk_section(doc: SourceDocument, section_index: int, first_chunk_index: int,
                  max_words: int = DEFAULT_MAX_WORDS) -> list[DbChunk]:
    """Pack consecutive rows of one section into chunks of at most ``max_words``.

    The header counts towards the budget and is repeated in every chunk. A row
    is never split: a row longer than the budget becomes a chunk on its own.
    """
    section = doc.sections[section_index]
    if not section.rows:
        return []
    budget = max(max_words - _words(section.header), 1)
    document_id = doc.document_id

    groups: list[list[tuple[SourceRow, int]]] = []  # (row, char offset in body)
    current: list[tuple[SourceRow, int]] = []
    current_words = 0
    offset = 0
    for row in section.rows:
        row_words = _words(row.text)
        if current and current_words + row_words > budget:
            groups.append(current)
            current, current_words = [], 0
        current.append((row, offset))
        current_words += row_words
        offset += len(row.text) + 1  # + "\n"
    if current:
        groups.append(current)

    chunks: list[DbChunk] = []
    for position, group in enumerate(groups):
        body = "\n".join(row.text for row, _ in group)
        text = f"{section.header}\n{body}" if section.header else body
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunk_index = first_chunk_index + position
        chunk_id = str(uuid.uuid5(
            NAMESPACE, f"chunk:{document_id}:{CHUNKER_VERSION}:{section_index}:{position}:{content_hash}"))
        start = group[0][1]
        end = group[-1][1] + len(group[-1][0].text)
        chunks.append(DbChunk(
            chunk_id=chunk_id, document_id=document_id, chunk_index=chunk_index,
            section_index=section_index, section_label=section.label, text=text,
            token_count=_words(text), char_start=start, char_end=end, content_hash=content_hash,
            locator={
                "source_table": doc.source_table,
                "source_id": doc.source_id,
                "doc_type": doc.doc_type,
                "symbol": doc.symbol,
                "section": section.label,
                "row_keys": [row.key for row, _ in group],
                **{k: v for k, v in doc.meta.items() if k in ("url", "published_at", "period_code")},
            },
        ))
    return chunks


def chunk_document(doc: SourceDocument, max_words: int = DEFAULT_MAX_WORDS) -> list[DbChunk]:
    chunks: list[DbChunk] = []
    for index in range(len(doc.sections)):
        chunks.extend(chunk_section(doc, index, len(chunks), max_words))
    return chunks


def chunk_documents(docs: Iterable[SourceDocument], max_words: int = DEFAULT_MAX_WORDS) -> list[DbChunk]:
    out: list[DbChunk] = []
    for doc in docs:
        out.extend(chunk_document(doc, max_words))
    return out


# ------------------------------------------------------------ text helpers

def period_text(period_code: str | None, section: str) -> str:
    """'2026-Q2' -> 'quý 2/2026 ...'; flow vs point-in-time is stated explicitly."""
    code = (period_code or "").strip()
    quarter = re.fullmatch(r"(\d{4})-Q([1-4])", code)
    if quarter:
        base = f"quý {quarter.group(2)}/{quarter.group(1)}"
        if section == "BALANCE_SHEET":
            return f"tại cuối {base}"
        if section in FLOW_SECTIONS:
            return f"{base} (riêng quý)"
        return base
    year = re.fullmatch(r"(\d{4})(?:-YEAR)?", code)
    if year:
        base = f"năm {year.group(1)}"
        return f"{base} (cả năm)" if section in FLOW_SECTIONS else base
    return code or "không rõ kỳ"


def format_value(value: Any, unit: str | None) -> str:
    """Render a value with its unit; amounts stored in VND are shown in millions."""
    if value is None:
        return "không có dữ liệu"
    number = float(value)
    unit = (unit or "").upper()
    if unit == "VND":
        return f"{number / 1_000_000:,.2f} triệu VND"
    if unit == "VND_PER_SHARE":
        return f"{number:,.2f} VND/cổ phiếu"
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.4g}"


# ------------------------------------------- rows -> SourceDocument builders

def financial_documents(rows: Iterable[dict[str, Any]]) -> list[SourceDocument]:
    """Group observation rows into one document per financial report.

    Expected keys per row: report_id, symbol, company_name, period_code,
    statement_scope, section, code, canonical_name, observation_id, value, unit.
    """
    reports: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        reports.setdefault(str(row["report_id"]), []).append(row)

    docs: list[SourceDocument] = []
    for report_id, items in reports.items():
        first = items[0]
        symbol = first.get("symbol")
        scope = first.get("statement_scope") or "không rõ phạm vi"
        company = first.get("company_name") or symbol or ""
        period_code = first.get("period_code")
        by_section: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_section.setdefault(str(item.get("section") or "OTHER"), []).append(item)

        sections: list[SourceSection] = []
        ordered = [s for s in SECTION_ORDER if s in by_section] + sorted(s for s in by_section if s not in SECTION_ORDER)
        for section in ordered:
            label_vi = SECTION_LABEL_VI.get(section, section)
            header = (f"{company} ({symbol}) | {label_vi} | {period_text(period_code, section)} | "
                      f"Phạm vi: {scope} | Đơn vị: triệu VND, trừ EPS (VND/cổ phiếu) và chỉ số tỷ lệ")
            lines = []
            for item in sorted(by_section[section], key=lambda r: str(r.get("code") or "")):
                name = item.get("canonical_name") or item.get("code") or ""
                text = f"{name} ({item.get('code')}): {format_value(item.get('value'), item.get('unit'))}"
                lines.append(SourceRow(key=str(item.get("observation_id")), text=text))
            sections.append(SourceSection(label=f"{label_vi} · {period_text(period_code, section)}",
                                          header=header, rows=lines))
        docs.append(SourceDocument(
            source_table="financial_reports", source_id=report_id, doc_type="FINANCIAL_STATEMENT",
            title=f"Báo cáo tài chính {symbol} {period_text(period_code, 'RATIO')} ({scope})",
            symbol=symbol, language="vi", sections=sections,
            meta={"period_code": period_code},
        ))
    return docs


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def _split_long(text: str, max_words: int) -> list[str]:
    """Split one paragraph that is longer than the budget: sentences first, words last."""
    units: list[str] = []
    buffer: list[str] = []
    count = 0
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        words = sentence.split()
        if not words:
            continue
        if len(words) > max_words:  # a single sentence longer than the budget
            if buffer:
                units.append(" ".join(buffer))
                buffer, count = [], 0
            for start in range(0, len(words), max_words):
                units.append(" ".join(words[start:start + max_words]))
            continue
        if buffer and count + len(words) > max_words:
            units.append(" ".join(buffer))
            buffer, count = [], 0
        buffer.append(sentence.strip())
        count += len(words)
    if buffer:
        units.append(" ".join(buffer))
    return units


def news_documents(rows: Iterable[dict[str, Any]], max_words: int = DEFAULT_MAX_WORDS) -> list[SourceDocument]:
    """One document per news article. Expected keys: article_id, source, title,
    content, published_at, symbols, url."""
    docs: list[SourceDocument] = []
    for row in rows:
        content = (row.get("content") or "").strip()
        if not content:
            continue
        published = row.get("published_at")
        day = published.date().isoformat() if isinstance(published, datetime) else (
            published.isoformat() if isinstance(published, date) else "không rõ ngày")
        title = (row.get("title") or "").strip()
        header = f"Tin {row.get('source') or ''} | {day} | {title}"
        budget = max(max_words - _words(header), 1)

        units: list[str] = []
        for paragraph in re.split(r"\n\s*\n|\n", content):
            paragraph = " ".join(paragraph.split())
            if not paragraph:
                continue
            units.extend(_split_long(paragraph, budget) if _words(paragraph) > budget else [paragraph])
        rows_out = [SourceRow(key=f"p{index}", text=text) for index, text in enumerate(units, 1)]
        symbols = row.get("symbols") or []
        docs.append(SourceDocument(
            source_table="news_articles", source_id=str(row["article_id"]), doc_type="NEWS",
            title=title, symbol=symbols[0] if symbols else None, language="vi",
            sections=[SourceSection(label="Nội dung", header=header, rows=rows_out)],
            meta={"url": row.get("url"), "published_at": day},
        ))
    return docs


# ------------------------------------------------------- prices and indices

def _month(day: Any) -> str:
    return day.strftime("%Y-%m") if hasattr(day, "strftime") else str(day)[:7]


def _day(day: Any) -> str:
    return day.isoformat() if hasattr(day, "isoformat") else str(day)[:10]


def _f(value: Any) -> float | None:
    return None if value is None else float(value)


def _bars_documents(rows: Iterable[dict[str, Any]], *, source_table: str, doc_type: str, key: str,
                    name_key: str, label: str, unit_note: str, price_fmt, key_fn) -> list[SourceDocument]:
    """Shared builder: one document per instrument, one section per month.

    Each month starts with a summary row, then one row per trading day, so both
    "xu hướng cả tháng" and "giá đóng cửa ngày X" questions can be answered.
    """
    by_instrument: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_instrument.setdefault(str(row[key]), []).append(row)

    docs: list[SourceDocument] = []
    for code, bars in by_instrument.items():
        bars = sorted(bars, key=lambda r: _day(r["trade_date"]))
        name = bars[0].get(name_key) or code
        by_month: dict[str, list[dict[str, Any]]] = {}
        for bar in bars:
            by_month.setdefault(_month(bar["trade_date"]), []).append(bar)

        sections: list[SourceSection] = []
        for month, items in by_month.items():
            highs = [_f(b.get("high")) for b in items if b.get("high") is not None]
            lows = [_f(b.get("low")) for b in items if b.get("low") is not None]
            volumes = [int(b["volume"]) for b in items if b.get("volume") is not None]
            top = price_fmt({**items[0], "high": max(highs)}, "high") if highs else "không có"
            bottom = price_fmt({**items[0], "low": min(lows)}, "low") if lows else "không có"
            summary = (
                f"Tổng kết tháng {month}: mở cửa {price_fmt(items[0], 'open')}, "
                f"đóng cửa {price_fmt(items[-1], 'close')}, cao nhất {top}, thấp nhất {bottom}, "
                f"tổng khối lượng {sum(volumes):,}, {len(items)} phiên giao dịch."
            )
            lines = [SourceRow(key=f"{code}:{month}:summary", text=summary)]
            for bar in items:
                volume = f"; khối lượng {int(bar['volume']):,}" if bar.get("volume") is not None else ""
                parts = [
                    f"{_day(bar['trade_date'])}: mở {price_fmt(bar, 'open')}; cao {price_fmt(bar, 'high')}; "
                    f"thấp {price_fmt(bar, 'low')}; đóng {price_fmt(bar, 'close')}{volume}"
                ]
                for field_name, label_text in (("sma20", "SMA20"), ("sma50", "SMA50"), ("rsi14", "RSI14")):
                    if bar.get(field_name) is not None:
                        parts.append(f"{label_text} {float(bar[field_name]):.2f}")
                lines.append(SourceRow(key=key_fn(code, bar), text="; ".join(parts)))
            header = f"{name} ({code}) | {label} | tháng {month} | {unit_note}"
            sections.append(SourceSection(label=f"{label} · tháng {month}", header=header, rows=lines))
        docs.append(SourceDocument(
            source_table=source_table, source_id=code, doc_type=doc_type,
            title=f"{label} {code}", symbol=code if doc_type == "PRICE_HISTORY" else None,
            language="vi", sections=sections, meta={},
        ))
    return docs


def price_documents(rows: Iterable[dict[str, Any]]) -> list[SourceDocument]:
    """price_bars rows: symbol, company_name, trade_date, open, high, low, close, volume,
    price_scale (raw value x scale = VND), optional price_id, sma20, sma50, rsi14."""
    def fmt(bar: dict[str, Any], field_name: str) -> str:
        value = bar.get(field_name)
        if value is None:
            return "không có"
        scale = bar.get("price_scale") or 1
        return f"{float(value) * scale:,.0f} đồng"

    return _bars_documents(
        rows, source_table="price_bars", doc_type="PRICE_HISTORY", key="symbol", name_key="company_name",
        label="Lịch sử giá cổ phiếu", unit_note="Giá: đồng/cổ phiếu, khối lượng: cổ phiếu, giá gốc chưa xác nhận điều chỉnh",
        price_fmt=fmt,
        key_fn=lambda code, bar: str(bar.get("price_id") or f"{code}:{_day(bar['trade_date'])}"),
    )


def index_documents(rows: Iterable[dict[str, Any]]) -> list[SourceDocument]:
    """market_index_bars rows: index_symbol, index_name, trade_date, open, high, low, close,
    volume, optional sma20, sma50, rsi14."""
    def fmt(bar: dict[str, Any], field_name: str) -> str:
        value = bar.get(field_name)
        return "không có" if value is None else f"{float(value):,.2f} điểm"

    return _bars_documents(
        rows, source_table="market_index_bars", doc_type="MARKET_INDEX", key="index_symbol",
        name_key="index_name", label="Lịch sử chỉ số", unit_note="Đơn vị: điểm, khối lượng: cổ phiếu",
        price_fmt=fmt, key_fn=lambda code, bar: f"{code}:{_day(bar['trade_date'])}",
    )


# ----------------------------------------------------------- company profile

def company_documents(rows: Iterable[dict[str, Any]]) -> list[SourceDocument]:
    """companies rows: company_id, symbol, company_name, industry_type, sector, exchange, is_active."""
    docs: list[SourceDocument] = []
    for row in rows:
        symbol = row.get("symbol")
        if not symbol:
            continue
        facts = [
            ("Mã chứng khoán", symbol),
            ("Tên doanh nghiệp", row.get("company_name")),
            ("Sàn niêm yết", row.get("exchange")),
            ("Loại hình ngành", row.get("industry_type")),
            ("Lĩnh vực", row.get("sector")),
            ("Trạng thái", None if row.get("is_active") is None else
             ("đang hoạt động" if row.get("is_active") else "ngừng hoạt động")),
        ]
        lines = [SourceRow(key=f"{symbol}:{name}", text=f"{name}: {value}") for name, value in facts if value]
        docs.append(SourceDocument(
            source_table="companies", source_id=str(row.get("company_id") or symbol),
            doc_type="COMPANY_PROFILE", title=f"Hồ sơ doanh nghiệp {symbol}", symbol=symbol, language="vi",
            sections=[SourceSection(label="Hồ sơ doanh nghiệp", header=f"Hồ sơ doanh nghiệp {symbol}", rows=lines)],
            meta={},
        ))
    return docs
