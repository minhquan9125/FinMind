"""WBS30 traces are useful for debugging without retaining question text."""

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import search
from src.documents import repository, retrieval_trace
from src.documents.chunk_reconstruction import ReconstructionError
from src.documents.embeddings import get_embedding_service


class FakeEmbedder:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3, 0.4]


app = FastAPI()
app.include_router(search.router)
app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
client = TestClient(app)


def sample_row():
    return {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()),
        "chunk_index": 0, "title": "Sensitive source title",
        "doc_type": "NEWS", "company_symbol": "FPT", "period": "2026-09",
        "locator_json": {}, "text": "Sensitive chunk content", "score": 0.81234567,
    }


def test_trace_success_and_empty(monkeypatch):
    traces = []
    row = sample_row()

    async def fake_search(*args, **kwargs):
        kwargs["on_ranked"]([{"chunk_id": row["chunk_id"], "score": row["score"]}]
                            if kwargs.get("company_symbol") == "FPT" else [])
        return [row] if kwargs.get("company_symbol") == "FPT" else []

    monkeypatch.setattr(search, "write_retrieval_trace", traces.append)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    for symbol in ("FPT", "NOPE"):
        response = client.post("/api/search/filtered", json={
            "query": "private question", "company_symbol": symbol,
        })
        assert response.status_code == 200

    assert len(traces) == 2
    assert traces[0]["status"] == "success"
    assert traces[0]["rows"][0]["score"] == row["score"]
    assert traces[0]["ranked_hits"][0]["chunk_id"] == row["chunk_id"]
    assert traces[1]["status"] == "empty"
    assert traces[1]["rows"] == []
    assert traces[1]["ranked_hits"] == []
    assert all(t["embedding_ms"] is not None and t["retrieval_ms"] is not None for t in traces)
    assert all(t["error_code"] is None for t in traces)


def test_trace_source_changed_error_without_raw_exception(monkeypatch):
    traces = []
    ranked = {"chunk_id": str(uuid.uuid4()), "score": 0.71}

    async def fake_search(*args, **kwargs):
        kwargs["on_ranked"]([ranked])
        raise ReconstructionError("SOURCE_CHANGED", "private database detail")

    monkeypatch.setattr(search, "write_retrieval_trace", traces.append)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    with pytest.raises(ReconstructionError):
        client.post("/api/search/filtered", json={"query": "private question"})
    assert len(traces) == 1
    assert traces[0]["status"] == "error"
    assert traces[0]["error_code"] == "SOURCE_CHANGED"
    assert traces[0]["rows"] is None
    assert traces[0]["ranked_hits"] == [ranked]
    assert traces[0]["retrieval_ms"] is not None
    assert "private" not in str(traces[0])


def test_trace_embedding_error_has_no_retrieval_timing(monkeypatch):
    traces = []

    def fail_embedding(self, text):
        raise RuntimeError("secret model token")

    monkeypatch.setattr(search, "write_retrieval_trace", traces.append)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    monkeypatch.setattr(FakeEmbedder, "embed_query", fail_embedding)
    with pytest.raises(RuntimeError):
        client.post("/api/search/filtered", json={"query": "private question"})
    assert len(traces) == 1
    assert traces[0]["error_code"] == "EMBEDDING_ERROR"
    assert traces[0]["embedding_ms"] is not None
    assert traces[0]["retrieval_ms"] is None
    assert "secret" not in str(traces[0])


def test_local_jsonl_omits_question_text_source_and_exception(monkeypatch):
    target = retrieval_trace.TRACE_FILE.parent / f"retrieval-trace-test-{uuid.uuid4()}.jsonl"
    monkeypatch.setattr(retrieval_trace, "TRACE_FILE", target)
    trace = {
        "trace_id": str(uuid.uuid4()), "timestamp": "2026-10-22T00:00:00+00:00",
        "status": "success", "index_version_id": str(uuid.uuid4()),
        "corpus_version_id": None, "company_symbol": "FPT' secret",
        "period": "2026-Q2", "doc_type": "NEWS", "top_k": 5,
        "preview_source_changed": False, "embedding_ms": 2.1,
        "retrieval_ms": 3.2, "total_ms": 5.3,
        "rows": [sample_row()], "error_code": None,
        "query": "private question", "exception": "database password",
    }
    trace["ranked_hits"] = [{"chunk_id": trace["rows"][0]["chunk_id"],
                              "score": trace["rows"][0]["score"]}]
    try:
        retrieval_trace.write_retrieval_trace(trace)
        trace["status"] = "empty"
        trace["rows"] = []
        trace["ranked_hits"] = []
        retrieval_trace.write_retrieval_trace(trace)
        trace["status"] = "error"
        trace["rows"] = None
        trace["ranked_hits"] = [{"chunk_id": str(uuid.uuid4()), "score": 0.71}]
        trace["error_code"] = "SOURCE_CHANGED"
        retrieval_trace.write_retrieval_trace(trace)
        content = target.read_text(encoding="utf-8")
        events = [json.loads(line) for line in content.splitlines()]
        assert len(events) == 3
        assert events[0]["hit_count"] == 1
        assert events[0]["returned_hit_count"] == 1
        assert events[0]["hits"][0]["score"] == 0.812346
        assert events[0]["filters"]["company_symbol"] == "[redacted]"
        assert events[1]["status"] == "empty"
        assert events[1]["hit_count"] == 0
        assert events[1]["returned_hit_count"] == 0
        assert events[2]["status"] == "error"
        assert events[2]["hit_count"] == 1
        assert events[2]["returned_hit_count"] is None
        assert events[2]["hits"][0]["score"] == 0.71
        assert events[2]["error_code"] == "SOURCE_CHANGED"
        assert all(secret not in content for secret in (
            "private question", "Sensitive source title", "Sensitive chunk content",
            "database password", "FPT' secret",
        ))
    finally:
        target.unlink(missing_ok=True)
