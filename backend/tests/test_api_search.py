"""API-level smoke tests for the search endpoint.

These do not require a running PostgreSQL instance or the real BAAI/bge-m3
model: the embedding service is swapped for a deterministic fake via FastAPI
dependency overrides, and repository.* functions are monkeypatched so no
real database connection is required. This only checks request/response
wiring (routes, status codes, schema shape) - end-to-end behaviour against a
real Postgres + pgvector instance still needs `docker compose up` (see
readmerepair.md).
"""

from fastapi.testclient import TestClient

from src import repository
from src.embeddings import get_embedding_service
from src.main import app


class FakeEmbedder:
    def embed_texts(self, texts):
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 4


app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
client = TestClient(app)


def test_search_returns_404_for_unknown_document(monkeypatch):
    async def fake_get_document(pool, document_id):
        return None

    monkeypatch.setattr(repository, "get_document", fake_get_document)
    # Bypass the real asyncpg pool since get_document is faked anyway.
    monkeypatch.setattr("src.routers.search.get_pool", lambda: object())

    response = client.post(
        "/api/search", json={"document_id": "missing-doc", "query": "revenue"}
    )
    assert response.status_code == 404


def test_search_returns_results_for_known_document(monkeypatch):
    async def fake_get_document(pool, document_id):
        return {"id": document_id}

    async def fake_vector_search(pool, document_id, query_embedding, top_k):
        return [
            {"chunk_index": 0, "page": 1, "text": "Revenue increased this quarter.", "score": 0.83},
        ]

    monkeypatch.setattr(repository, "get_document", fake_get_document)
    monkeypatch.setattr(repository, "vector_search", fake_vector_search)
    monkeypatch.setattr("src.routers.search.get_pool", lambda: object())

    response = client.post(
        "/api/search", json={"document_id": "doc-1", "query": "revenue", "top_k": 3}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["score"] == 0.83
    assert "revenue" in body["results"][0]["matched_terms"]


def test_search_rejects_empty_query(monkeypatch):
    async def fake_get_document(pool, document_id):
        return {"id": document_id}

    monkeypatch.setattr(repository, "get_document", fake_get_document)
    monkeypatch.setattr("src.routers.search.get_pool", lambda: object())

    response = client.post("/api/search", json={"document_id": "doc-1", "query": "   "})
    assert response.status_code == 400
