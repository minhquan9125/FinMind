import asyncio
import json
import uuid
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
    write_chunks,
)


class FakeConn:
    def __init__(self, current=None, existing_ids=None):
        self.executed = []
        self.many = []
        self.current = current or []  # rows of currently valid chunks already in the database
        self.existing_ids = existing_ids or []  # chunk_ids that exist (retired or not)

    async def execute(self, sql, *args):
        self.executed.append((sql, args))

    async def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))

    async def fetchval(self, sql, *args):
        return None

    async def fetch(self, sql, *args):
        if "superseded_at IS NULL" in sql and "chunk_index" in sql:
            return list(self.current)
        if "WHERE chunk_id = ANY" in sql:
            wanted = set(args[0])
            return [{"chunk_id": cid} for cid in self.existing_ids if cid in wanted]
        return []

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
    assert all(json.loads(row[11])["source_table"] == "financial_reports" for row in rows)
    assert all(json.loads(row[11])["row_keys"] for row in rows)


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


def _current_rows(doc, version_id, count=None, change=None):
    """What the database would already hold for this document (all chunks current)."""
    chunks = chunk_document(doc)
    rows = []
    for c in chunks[: count if count is not None else len(chunks)]:
        changed = change == c.chunk_index
        # a row whose text differs was stored under a different (old) chunk_id
        chunk_id = uuid.uuid4() if changed else uuid.UUID(stored_chunk_id(version_id, c))
        rows.append({"chunk_id": chunk_id, "chunk_index": c.chunk_index,
                     "content_hash": "f" * 64 if changed else c.content_hash})
    return rows


def test_unchanged_document_writes_nothing():
    doc = fin_doc()
    version = index_version_id_for(130, "m")
    conn = FakeConn(current=_current_rows(doc, version))
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    assert conn.many == []  # nothing inserted
    assert not any("UPDATE text_chunks" in sql for sql, _ in conn.executed)


def test_changed_chunk_is_retired_and_a_new_chunk_is_inserted():
    doc = fin_doc()
    version = index_version_id_for(130, "m")
    conn = FakeConn(current=_current_rows(doc, version, change=1))
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    old_id = conn.current[1]["chunk_id"]
    retire = [args for sql, args in conn.executed if "SET superseded_at = $2" in sql]
    assert len(retire) == 1 and retire[0][0] == [old_id]  # the old chunk, by id
    inserted = [row for sql, rows in conn.many if "INSERT INTO text_chunks" in sql for row in rows]
    assert len(inserted) == 1 and inserted[0][3] == 1  # only position 1 is rewritten
    assert inserted[0][0] != old_id  # the old chunk_id is never reused for new content
    links = [rows for sql, rows in conn.many if "superseded_by_chunk_id = $2" in sql]
    assert links == [[(old_id, inserted[0][0])]]


def test_no_statement_ever_changes_an_existing_chunk_id():
    doc = fin_doc()
    version = index_version_id_for(130, "m")
    conn = FakeConn(current=_current_rows(doc, version, change=0))
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    all_sql = [sql for sql, _ in conn.executed] + [sql for sql, _ in conn.many]
    assert not any("SET chunk_id" in sql or "chunk_id = EXCLUDED.chunk_id" in sql for sql in all_sql)
    assert not any("DELETE FROM text_chunks" in sql for sql in all_sql)


def test_chunks_that_no_longer_exist_are_retired_not_deleted():
    doc = fin_doc()
    version = index_version_id_for(130, "m")
    total = len(chunk_document(doc))
    rows = _current_rows(doc, version)
    extra = {"chunk_id": uuid.uuid4(), "chunk_index": total + 2, "content_hash": "a" * 64}
    conn = FakeConn(current=rows + [extra])
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    retire = [args for sql, args in conn.executed if "SET superseded_at = $2" in sql]
    assert retire and extra["chunk_id"] in retire[0][0]
    assert not any("DELETE FROM text_chunks" in sql for sql, _ in conn.executed)


def test_old_text_coming_back_revives_the_retired_chunk():
    doc = fin_doc()
    version = index_version_id_for(130, "m")
    chunks = chunk_document(doc)
    # position 0 currently holds other text; the retired row with the original id still exists
    original_id = uuid.UUID(stored_chunk_id(version, chunks[0]))
    current = _current_rows(doc, version, change=0)
    conn = FakeConn(current=current, existing_ids=[original_id])
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    revive = [args for sql, args in conn.executed if "SET superseded_at = NULL" in sql]
    assert revive and revive[0][0] == [original_id]
    inserted = [row for sql, rows in conn.many if "INSERT INTO text_chunks" in sql for row in rows]
    assert inserted == []  # revived, not inserted a second time


def test_write_chunks_rejects_missing_vectors_before_database_changes():
    conn = FakeConn()
    doc = fin_doc()
    chunks = chunk_document(doc)
    with pytest.raises(ValueError, match="expected .* vectors"):
        run(write_chunks(conn, doc, chunks, [], index_version_id_for(130, "m")))
    assert conn.executed == []
    assert conn.many == []


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


def _news_doc(title="FPT: Nghị quyết HĐQT về cổ tức"):
    return news_documents([{
        "article_id": "a2", "source": "cafef", "title": title, "content": "Đoạn một.\n\nĐoạn hai.",
        "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc), "symbols": ["FPT"], "url": "https://x/z",
    }])[0]


def test_news_chunk_locator_carries_type_but_chunk_id_ignores_it():
    chunks = chunk_document(_news_doc())
    loc = chunks[0].locator
    assert loc["news_type"] == "CONG_BO_THONG_TIN" and loc["news_priority"] == 1
    assert "CONG_BO_THONG_TIN" not in chunks[0].text  # type lives in the locator, not in the text
    other = chunk_document(_news_doc("FPT: Nghị quyết HĐQT về cổ tức"))
    assert [c.chunk_id for c in chunks] == [c.chunk_id for c in other]


@pytest.mark.parametrize("title,expected", [
    ("FPT: Nghị quyết HĐQT thông qua phương án phát hành", "CONG_BO_THONG_TIN"),
    ("FPT báo lợi nhuận quý 3 tăng 20%", "KET_QUA_KINH_DOANH"),
    ("FPT hợp tác chiến lược với đối tác Nhật", "CHIEN_LUOC_DOANH_NGHIEP"),
    ("Khối ngoại mua ròng phiên hôm nay", "DIEN_BIEN_GIA"),
    ("Góc nhìn thị trường tuần tới", "BINH_LUAN_KHAC"),
    ("", "BINH_LUAN_KHAC"),
])
def test_classify_news(title, expected):
    from src.documents.db_chunking import classify_news
    assert classify_news(title) == expected


def test_unchanged_text_but_new_locator_refreshes_locator_only():
    doc = _news_doc()
    version = index_version_id_for(130, "m")
    rows = _current_rows(doc, version)
    for row in rows:
        row["locator_json"] = '{"source_table": "news_articles"}'  # old locator without the type
    conn = FakeConn(current=rows)
    run(ingest_documents(conn, [doc], FakeEmbedder(), "m"))
    updates = [r for sql, r in conn.many if "SET locator_json" in sql]
    assert len(updates) == 1 and len(updates[0]) == len(rows)
    assert all(json.loads(loc)["news_type"] == "CONG_BO_THONG_TIN" for _, loc in updates[0])
    assert not any("INSERT INTO text_chunks" in sql for sql, _ in conn.many)  # no re-embedding, no new chunk
    assert not any("SET superseded_at" in sql for sql, _ in conn.executed)
