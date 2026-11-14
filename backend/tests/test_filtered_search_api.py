from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import search
from src.documents import repository
from src.documents.embeddings import get_embedding_service


class FakeEmbedder:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3, 0.4]


app = FastAPI()
app.include_router(search.router)
app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
client = TestClient(app)


def test_filtered_search_returns_scoped_results(monkeypatch):
    async def fake_search(pool, index, vector, top_k, company_symbol=None, period=None, doc_type=None, on_ranked=None):
        assert company_symbol == "FPT"
        assert period == "2026-05"
        assert doc_type == "PRICE_HISTORY"
        assert vector == [0.1, 0.2, 0.3, 0.4]
        return [{
            "chunk_id": "chunk-1", "document_id": "doc-1", "chunk_index": 1,
            "title": "Lịch sử giá FPT", "doc_type": "PRICE_HISTORY",
            "company_symbol": "FPT", "period": "2026-05",
            "locator_json": '{"source_table":"price_bars"}',
            "text": "FPT price data", "score": 0.91,
        }]

    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT price in May 2026", "company_symbol": "FPT",
        "period": "2026-05", "doc_type": "PRICE_HISTORY",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["locator"] == {"source_table": "price_bars"}
    assert body["results"][0]["score"] == 0.91
    assert body["index_version_id"]


def test_filtered_search_wrong_scope_returns_empty(monkeypatch):
    async def fake_search(*args, **kwargs):
        return []

    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "Question with no matching company", "company_symbol": "NOPE",
    })

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_filtered_search_can_select_v2_for_read_only_trial(monkeypatch):
    async def fake_search(pool, index, vector, top_k, company_symbol=None, period=None, doc_type=None, on_ranked=None):
        assert index == search.V2_TRIAL_INDEX_ID
        assert company_symbol == "FPT"
        assert period == "2026-Q2"
        assert doc_type == "FINANCIAL_STATEMENT"
        return []

    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT quý 2 có bao nhiêu tiền?",
        "index_version_id": search.V2_TRIAL_INDEX_ID,
        "company_symbol": "FPT",
        "period": "2026-Q2",
        "doc_type": "FINANCIAL_STATEMENT",
    })

    assert response.status_code == 200
    assert response.json()["index_version_id"] == search.V2_TRIAL_INDEX_ID


def test_filtered_search_rejects_unapproved_index(monkeypatch):
    response = client.post("/api/search/filtered", json={
        "query": "FPT quý 2",
        "index_version_id": "00000000-0000-0000-0000-000000000000",
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported index_version_id."


def test_filtered_search_rejects_blank_query():
    response = client.post("/api/search/filtered", json={"query": "   "})
    assert response.status_code == 400


def test_preview_requires_explicit_corpus():
    response = client.post("/api/search/filtered", json={
        "query": "FPT", "preview_source_changed": True,
    })
    assert response.status_code == 400


def test_preview_flag_reaches_search_and_marks_response(monkeypatch):
    async def fake_corpus(pool, selected):
        return {"index_version_id": search.V2_TRIAL_INDEX_ID,
                "corpus_status": "FROZEN", "index_status": "ACTIVE",
                "embedding_model": "BAAI/bge-m3@5617a9f61b02"}

    async def fake_search(pool, index, vector, top_k, **kwargs):
        assert kwargs["preview_source_changed"] is True
        return [{"chunk_id": "chunk-1", "document_id": "doc-1", "chunk_index": 0,
                 "title": "FPT", "doc_type": "FINANCIAL_STATEMENT",
                 "company_symbol": "FPT", "period": "2026-Q2",
                 "locator_json": {}, "text": "Current unverified text", "score": 0.7,
                 "source_verified": False, "source_warning": "SOURCE_CHANGED"}]

    monkeypatch.setattr(repository, "get_corpus_index", fake_corpus)
    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT", "corpus_version_id": "232fbd29-355f-5a77-ba28-a06b8d5ceb40",
        "preview_source_changed": True,
    })
    assert response.status_code == 200
    assert response.json()["results"][0]["source_verified"] is False
    assert response.json()["results"][0]["source_warning"] == "SOURCE_CHANGED"


def test_filtered_search_uses_frozen_corpus_index_and_scope(monkeypatch):
    corpus_id = "232fbd29-355f-5a77-ba28-a06b8d5ceb40"

    async def fake_corpus(pool, selected):
        assert str(selected) == corpus_id
        return {"index_version_id": search.V2_TRIAL_INDEX_ID,
                "corpus_status": "FROZEN", "index_status": "ACTIVE",
                "embedding_model": "BAAI/bge-m3@5617a9f61b02"}

    async def fake_search(pool, index, vector, top_k, **kwargs):
        assert index == search.V2_TRIAL_INDEX_ID
        assert str(kwargs["corpus_version_id"]) == corpus_id
        return []

    monkeypatch.setattr(repository, "get_corpus_index", fake_corpus)
    monkeypatch.setattr(repository, "vector_search_filtered", fake_search)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT tổng tài sản", "corpus_version_id": corpus_id,
    })
    assert response.status_code == 200
    assert response.json()["corpus_version_id"] == corpus_id
    assert response.json()["index_version_id"] == search.V2_TRIAL_INDEX_ID


def test_filtered_search_rejects_two_version_selectors():
    response = client.post("/api/search/filtered", json={
        "query": "FPT", "corpus_version_id": "232fbd29-355f-5a77-ba28-a06b8d5ceb40",
        "index_version_id": search.V2_TRIAL_INDEX_ID,
    })
    assert response.status_code == 400


def test_filtered_search_rejects_missing_corpus(monkeypatch):
    async def fake_corpus(pool, selected):
        return None

    monkeypatch.setattr(repository, "get_corpus_index", fake_corpus)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT", "corpus_version_id": "232fbd29-355f-5a77-ba28-a06b8d5ceb40",
    })
    assert response.status_code == 404


@pytest.mark.parametrize("corpus_status,index_status,model,expected", [
    ("BUILDING", "ACTIVE", "BAAI/bge-m3@5617a9f61b02", "Corpus or its index is not ready for search."),
    ("FROZEN", "BUILDING", "BAAI/bge-m3@5617a9f61b02", "Corpus or its index is not ready for search."),
    ("FROZEN", "ACTIVE", "another-model", "Corpus embedding model differs from the configured model."),
])
def test_filtered_search_rejects_unready_or_incompatible_corpus(
    monkeypatch, corpus_status, index_status, model, expected,
):
    async def fake_corpus(pool, selected):
        return {"index_version_id": search.V2_TRIAL_INDEX_ID,
                "corpus_status": corpus_status, "index_status": index_status,
                "embedding_model": model}

    monkeypatch.setattr(repository, "get_corpus_index", fake_corpus)
    monkeypatch.setattr(search, "get_pool", lambda: object())
    response = client.post("/api/search/filtered", json={
        "query": "FPT", "corpus_version_id": "232fbd29-355f-5a77-ba28-a06b8d5ceb40",
    })
    assert response.status_code == 409
    assert response.json()["detail"] == expected
