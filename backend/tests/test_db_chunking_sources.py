import asyncio
from datetime import date

from src.documents.db_chunking import (
    chunk_document,
    chunk_documents,
    company_documents,
    index_documents,
    price_documents,
)
from src.documents.db_source import (
    fetch_company_documents,
    fetch_index_documents,
    fetch_news_documents,
    fetch_price_documents,
)


def price_rows(days=40):
    rows = []
    for i in range(days):
        d = date(2026, 9, 1 + i) if i < 30 else date(2026, 10, i - 29)
        rows.append({
            "price_id": f"p{i}", "symbol": "FPT", "company_name": "Công ty FPT", "trade_date": d,
            "open": 57.0 + i, "high": 58.0 + i, "low": 56.0 + i, "close": 57.5 + i, "volume": 1_000_000 + i,
            "price_scale": 1000, "sma20": 57.1 if i > 19 else None, "sma50": None, "rsi14": 50.5 if i > 13 else None,
        })
    return rows


def test_price_document_has_month_summary_then_daily_rows():
    doc = price_documents(price_rows())[0]
    assert doc.source_table == "price_bars" and doc.doc_type == "PRICE_HISTORY"
    assert [s.label for s in doc.sections] == ["Lịch sử giá cổ phiếu · tháng 2026-09", "Lịch sử giá cổ phiếu · tháng 2026-10"]
    first = doc.sections[0].rows
    assert first[0].text.startswith("Tổng kết tháng 2026-09: mở cửa 57,000 đồng, đóng cửa")
    assert "30 phiên giao dịch" in first[0].text
    assert first[1].text.startswith("2026-09-01: mở 57,000 đồng; cao 58,000 đồng; thấp 56,000 đồng; đóng 57,500 đồng; khối lượng 1,000,000")


def test_price_rows_include_indicators_only_when_present():
    rows = price_documents(price_rows())[0].sections[0].rows
    early = rows[2].text  # day 2: no indicators yet
    late = rows[-1].text  # last day of month: sma20 and rsi14 present
    assert "SMA20" not in early and "RSI14" not in early
    assert "SMA20 57.10" in late and "RSI14 50.50" in late


def test_price_chunks_repeat_unit_header_and_cover_every_day():
    doc = price_documents(price_rows())[0]
    chunks = chunk_document(doc, max_words=60)
    assert len(chunks) > 4
    assert all("đồng/cổ phiếu" in c.text.split("\n")[0] for c in chunks)
    keys =[k for c in chunks for k in c.locator["row_keys"]]
    expected = [r.key for s in doc.sections for r in s.rows]
    assert keys == expected  # no row lost, none duplicated, order preserved


def test_index_documents_use_points():
    rows = [{"index_symbol": "VNINDEX", "index_name": "VN-Index", "trade_date": date(2026, 10, d),
             "open": 1750.1, "high": 1760.5, "low": 1740.2, "close": 1755.0, "volume": 500_000_000,
             "sma20": None, "sma50": None, "rsi14": None} for d in (1, 2, 3)]
    doc = index_documents(rows)[0]
    assert doc.source_table == "market_index_bars" and doc.symbol is None
    text = doc.sections[0].rows[1].text
    assert "1,750.10 điểm" in text and "khối lượng 500,000,000" in text


def test_company_profile_is_one_chunk_with_facts():
    rows = [{"company_id": "c1", "symbol": "FPT", "company_name": "Công ty Cổ phần FPT", "industry_type": "NON_BANK",
             "sector": "Công nghệ thông tin", "exchange": "HOSE", "is_active": True},
            {"company_id": "c2", "symbol": None, "company_name": "Bỏ qua", "industry_type": None,
             "sector": None, "exchange": None, "is_active": None}]
    docs = company_documents(rows)
    assert len(docs) == 1  # a row without a symbol is not a company profile
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert "Sàn niêm yết: HOSE" in chunks[0].text and "đang hoạt động" in chunks[0].text


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows


def test_fetch_helpers_for_new_sources():
    prices = asyncio.run(fetch_price_documents(FakeConn(price_rows(5)), ["fpt"]))
    assert len(prices) == 1

    idx = asyncio.run(fetch_index_documents(FakeConn([
        {"index_symbol": "VN30", "index_name": "VN30", "trade_date": date(2026, 10, 1), "open": 1, "high": 2, "low": 1,
         "close": 2, "volume": 3, "sma20": None, "sma50": None, "rsi14": None}])))
    assert idx[0].source_id == "VN30"

    comp_conn = FakeConn([{"company_id": "c1", "symbol": "VCB", "company_name": "Vietcombank", "industry_type": None,
                           "sector": None, "exchange": "HOSE", "is_active": True}])
    comps = asyncio.run(fetch_company_documents(comp_conn, None))
    assert comps[0].symbol == "VCB" and comp_conn.calls[0][1] == (None,)


def test_news_limit_zero_means_all():
    conn = FakeConn([])
    asyncio.run(fetch_news_documents(conn, None, 0))
    assert conn.calls[0][1] == (None, None)  # LIMIT NULL reads every article


def test_company_fact_keys_are_column_names_of_the_companies_table():
    from src.documents.db_chunking import company_documents
    doc = company_documents([{"company_id": "c1", "symbol": "FPT", "company_name": "FPT Corp",
                              "industry_type": "IT", "sector": "Công nghệ", "exchange": "HOSE", "is_active": True}])[0]
    keys = [row.key for row in doc.sections[0].rows]
    assert keys == ["FPT:symbol", "FPT:company_name", "FPT:exchange", "FPT:industry_type", "FPT:sector", "FPT:is_active"]


def test_news_day_uses_vietnam_time_not_utc():
    from datetime import datetime, timezone
    from src.documents.db_chunking import chunk_document, news_documents
    row = {"article_id": "a9", "source": "cafef", "title": "Tin", "content": "Nội dung.",
           "published_at": datetime(2026, 10, 1, 20, 30, tzinfo=timezone.utc), "symbols": [], "url": "u"}
    chunk = chunk_document(news_documents([row])[0])[0]
    assert "2026-10-02" in chunk.text and chunk.locator["published_at"] == "2026-10-02"
