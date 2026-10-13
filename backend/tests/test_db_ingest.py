import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from src.documents.db_chunking import chunk_document, financial_documents, news_documents
from src.documents.db_ingest import (
    EMBEDDING_DIM,
    embed_all,
    index_version_id_for,
    ingest_documents,
    stored_chunk_id,
)


class FakeConn:
    def __init__(self):
        self.executed = []
        self.many = []

    async def execute(self, sql, *args):
        self.executed.append((sql, args))

    async def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))

    async def fetchval(self, sql, *args):
        return None

    @asynccontextmanager
    async def transaction(self):
        yield


class FakeEmbedder:
    def __init__(self, dim=EMBEDDING_DIM, fail_on=None):
        self.dim = dim
        self.fail_on = fail_on

    def embed_texts(self, texts):
        if self.fail_on and any(self.fail_on in t for t in texts):
            raise RuntimeError("boom")
        return [[0.1] * self.dim for _ in texts]


def fin_doc(report="r1", n=30):
    rows = [{
        "report_id": report, "symbol": "FPT", "company_name": "FPT", "period_code": "2026-Q2",
        "statement_scope": "CONSOLIDATED", "section": "INCOME_STATEMENT", "code": f"M{i:03d}",
        "canonical_name": f"Chỉ tiêu {i}", "observation_id": f"o{report}-{i}",
        "value": (i + 1) * 1_000_000, "unit": "VND",
    } for i in range(n)]
    return financial_documents(rows)[0]


def run(coro):
    return asyncio.run(coro)


def written_rows(conn):
    return [row for _, rows in conn.many for row in rows]


def test_writes_documents_and_chunks_with_vectors():
    conn = FakeConn()
    docs = [fin_doc("r1"), fin_doc("r2")]
    result = run(ingest_documents(conn, docs, FakeEmbedder(), "BAAI/bge-m3"))
    assert result.documents_ok == 2 and result.documents_failed == 0
    expected = sum(len(chunk_document(d)) for d in docs)
    assert result.chunks_written == expected
    rows = written_rows(conn)
    assert len(rows) == expected
    assert all(len(row[10]) == EMBEDDING_DIM for row in rows)  # embedding column


def test_rerun_produces_identical_ids():
    first, second = FakeConn(), FakeConn()
    run(ingest_documents(first, [fin_doc()], FakeEmbedder(), "m"))
    run(ingest_documents(second, [fin_doc()], FakeEmbedder(), "m"))
    ids_first = [row[0] for row in written_rows(first)]
    ids_second = [row[0] for row in written_rows(second)]
    assert ids_first == ids_second
    assert len(set(ids_first)) == len(ids_first)


def test_same_chunk_under_other_index_version_gets_other_id():
    chunk = chunk_document(fin_doc())[0]
    a = stored_chunk_id(index_version_id_for(130, "m1"), chunk)
    b = stored_chunk_id(index_version_id_for(130, "m2"), chunk)
    assert a != b


def test_document_failing_to_embed_is_skipped_not_half_written():
    conn = FakeConn()
    good, bad = fin_doc("r1"), fin_doc("r2")
    bad.sections[0].header += " BAD"
    result = run(ingest_documents(conn, [good, bad], FakeEmbedder(fail_on="BAD"), "m"))
    assert result.documents_ok == 1
    assert result.documents_failed == 1
    assert result.errors[0]["source_id"] == "r2"
    inserted = [args for sql, args in conn.executed if "INSERT INTO documents" in sql]
    assert len(inserted) == 1  # the failed document never reached the database


def test_wrong_vector_size_is_rejected():
    with pytest.raises(ValueError):
        embed_all(FakeEmbedder(dim=384), chunk_document(fin_doc()))


def test_stale_chunks_are_deleted():
    conn = FakeConn()
    run(ingest_documents(conn, [fin_doc()], FakeEmbedder(), "m"))
    deletes = [args for sql, args in conn.executed if sql.strip().startswith("DELETE FROM text_chunks")]
    assert len(deletes) == 1
    assert deletes[0][2] == len(chunk_document(fin_doc()))


def test_news_documents_are_written_with_url():
    doc = news_documents([{
        "article_id": "a1", "source": "cafef", "title": "Tiêu đề", "content": "Đoạn một.\n\nĐoạn hai.",
        "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc), "symbols": ["FPT"], "url": "https://x/y",
    }])[0]
    conn = FakeConn()
    result = run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    assert result.documents_ok == 1
    insert = [args for sql, args in conn.executed if "INSERT INTO documents" in sql][0]
    assert "https://x/y" in insert
