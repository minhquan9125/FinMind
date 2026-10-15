import asyncio
from contextlib import asynccontextmanager

import pytest

from src.documents.retention import (
    COUNT_SQL,
    DEFAULT_DAYS,
    DEFAULT_DOC_TYPES,
    DELETE_SQL,
    run_retention,
    validate,
)


class FakeConn:
    def __init__(self, rows=None, delete_status="DELETE 0"):
        self.rows = rows or []
        self.delete_status = delete_status
        self.fetched = []
        self.executed = []

    async def fetch(self, sql, *args):
        self.fetched.append((sql, args))
        return self.rows

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return self.delete_status

    @asynccontextmanager
    async def transaction(self):
        yield


def run(coro):
    return asyncio.run(coro)


ROWS = [{"doc_type": "MARKET_INDEX", "chunks": 4, "bytes": 20_000},
        {"doc_type": "PRICE_HISTORY", "chunks": 10, "bytes": 50_000}]


def test_default_policy_is_30_days_for_price_and_index_only():
    assert DEFAULT_DAYS == 30
    assert set(DEFAULT_DOC_TYPES) == {"PRICE_HISTORY", "MARKET_INDEX"}


def test_dry_run_counts_but_never_deletes():
    conn = FakeConn(rows=ROWS, delete_status="DELETE 14")
    report = run(run_retention(conn))
    assert report.candidates == {"MARKET_INDEX": 4, "PRICE_HISTORY": 10}
    assert report.candidate_total == 14 and report.bytes_total == 70_000
    assert report.applied is False and report.deleted == 0
    assert conn.executed == []  # nothing was deleted


def test_apply_deletes_with_days_and_types():
    conn = FakeConn(rows=ROWS, delete_status="DELETE 14")
    report = run(run_retention(conn, days=45, apply=True))
    assert report.deleted == 14 and report.applied is True
    sql, args = conn.executed[0]
    assert args == (["PRICE_HISTORY", "MARKET_INDEX"], 45)
    assert sql.strip().startswith("DELETE FROM public.text_chunks")


def test_apply_with_nothing_to_delete_runs_no_delete():
    conn = FakeConn(rows=[])
    report = run(run_retention(conn, apply=True))
    assert report.deleted == 0 and conn.executed == []


def test_sql_only_touches_superseded_old_uncited_chunks():
    for sql in (COUNT_SQL, DELETE_SQL):
        assert "t.superseded_at IS NOT NULL" in sql
        assert "interval '1 day'" in sql
        assert "NOT EXISTS (SELECT 1 FROM public.evidence e WHERE e.chunk_id = t.chunk_id)" in sql
        assert "d.doc_type = ANY($1::text[])" in sql


@pytest.mark.parametrize("protected", ["NEWS", "FINANCIAL_STATEMENT", "COMPANY_PROFILE", "news"])
def test_news_financial_and_company_chunks_cannot_be_deleted(protected):
    with pytest.raises(ValueError, match="protected"):
        validate(30, ["PRICE_HISTORY", protected])


@pytest.mark.parametrize("days", [0, -5])
def test_days_must_be_positive(days):
    with pytest.raises(ValueError, match="at least 1"):
        validate(days, ["PRICE_HISTORY"])


def test_doc_types_are_cleaned_and_required():
    assert validate(30, [" price_history ", "PRICE_HISTORY", "market_index"])[1] == ("PRICE_HISTORY", "MARKET_INDEX")
    with pytest.raises(ValueError, match="at least one"):
        validate(30, ["  "])
