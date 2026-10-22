import asyncio
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import search
from src.documents.price_queries import PriceQueryError, classify, query_price


def test_explicit_date_takes_priority_over_high_low_words():
    operation, dates = classify(
        "Ngày 20/05/2026, giá mở cửa, cao nhất, thấp nhất và đóng cửa của VCB là bao nhiêu?"
    )
    assert operation == "daily_bar"
    assert dates == [date(2026, 5, 20)]


def test_comparison_and_aggregate_questions_are_distinct():
    assert classify("So sánh close MBB 30/09/2026 và 06/10/2026")[0] == "compare_closes"
    assert classify("Mã nào có volume lớn nhất trong toàn bộ dữ liệu giá?")[0] == "max_volume"
    assert classify("Khối lượng giao dịch trung bình của CTR là bao nhiêu?")[0] == "average_volume"
    assert classify("Có bao nhiêu phiên giá cho mỗi mã và tổng bao nhiêu records?")[0] == "count_bars"


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.transaction_args = None
        self.fetch_args = None

    def transaction(self, **kwargs):
        self.transaction_args = kwargs
        return FakeTransaction()

    async def fetch(self, sql, *args):
        if "FROM public.companies" in sql and "price_bars" not in sql:
            return [{"symbol": "MBB"}]
        self.fetch_args = args
        return [
            {"price_id": "first", "symbol": "MBB", "trade_date": date(2026, 9, 30),
             "price_scale": 1000, "open": Decimal("19.6"), "high": Decimal("19.8"),
             "low": Decimal("19.5"), "close": Decimal("19.65"), "volume": 100},
            {"price_id": "last", "symbol": "MBB", "trade_date": date(2026, 10, 6),
             "price_scale": 1000, "open": Decimal("19.1"), "high": Decimal("19.2"),
             "low": Decimal("18.8"), "close": Decimal("19.20"), "volume": 200},
        ]


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


def test_price_comparison_reads_source_rows_and_preserves_ids():
    conn = FakeConnection()
    result = asyncio.run(query_price(
        FakePool(conn), "So sánh giá đóng cửa MBB 30/09/2026 và 06/10/2026", "MBB"
    ))
    assert conn.transaction_args == {"readonly": True, "isolation": "repeatable_read"}
    assert conn.fetch_args[0] == "MBB"
    assert result["data"]["change_percent"] == "-2.29"
    assert [item["price_id"] for item in result["sources"]] == ["first", "last"]


def test_invalid_question_is_explicit():
    with pytest.raises(PriceQueryError):
        classify("Cho tôi giá cổ phiếu")


def test_price_api_returns_structured_result(monkeypatch):
    async def fake_query(pool, question, company_symbol, period):
        assert question == "Giá MBB ngày 06/10/2026?"
        assert company_symbol == "MBB"
        return {"question": question, "operation": "daily_bar",
                "scope": {"company_symbol": "MBB", "period": period},
                "data": {"close": "19.20"},
                "sources": [{"price_id": "bar-id"}]}

    monkeypatch.setattr(search, "query_price", fake_query)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    app = FastAPI()
    app.include_router(search.router)
    response = TestClient(app).post("/api/search/price", json={
        "question": "Giá MBB ngày 06/10/2026?", "company_symbol": "MBB",
    })
    assert response.status_code == 200
    assert response.json()["sources"][0]["price_id"] == "bar-id"


def test_price_api_rejects_unsupported_question(monkeypatch):
    async def fake_query(*args):
        raise PriceQueryError("Chưa hỗ trợ dạng câu hỏi giá này.")

    monkeypatch.setattr(search, "query_price", fake_query)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    app = FastAPI()
    app.include_router(search.router)
    response = TestClient(app).post("/api/search/price", json={"question": "Giá cổ phiếu?"})
    assert response.status_code == 400
    assert "Chưa hỗ trợ" in response.json()["detail"]
