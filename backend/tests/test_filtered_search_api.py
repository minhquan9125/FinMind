from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    async def fake_search(pool, index, vector, top_k, company_symbol=None, period=None, doc_type=None):
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


def test_filtered_search_rejects_blank_query():
    response = client.post("/api/search/filtered", json={"query": "   "})
    assert response.status_code == 400
