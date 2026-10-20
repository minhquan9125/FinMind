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

from src.documents import repository
from src.documents.embeddings import get_embedding_service
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
    monkeypatch.setattr("src.api.routers.search.get_pool", lambda: object())

    response = client.post(
        "/api/search", json={"document_id": "missing-doc", "query": "revenue"}
    )
    assert response.status_code == 404


def test_search_returns_results_for_known_document(monkeypatch):
    async def fake_get_document(pool, document_id):
        return {"id": document_id}

    async def fake_vector_search(pool, document_id, index_version_id, query_embedding, top_k):
        return [
            {"chunk_index": 0, "page": 1, "text": "Revenue increased this quarter.", "score": 0.83},
        ]

    monkeypatch.setattr(repository, "get_document", fake_get_document)
    monkeypatch.setattr(repository, "vector_search", fake_vector_search)
    monkeypatch.setattr("src.api.routers.search.get_pool", lambda: object())

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
    monkeypatch.setattr("src.api.routers.search.get_pool", lambda: object())

    response = client.post("/api/search", json={"document_id": "doc-1", "query": "   "})
    assert response.status_code == 400


def test_search_source_failure_returns_reason_without_results(monkeypatch):
    from src.documents.chunk_reconstruction import ReconstructionError
    async def get_document(*args): return {'id': 'doc', 'file_type': 'DB'}
    async def fail(*args): raise ReconstructionError('SOURCE_CHANGED', 'source changed')
    monkeypatch.setattr(repository, 'get_document', get_document)
    monkeypatch.setattr(repository, 'vector_search', fail)
    monkeypatch.setattr('src.api.routers.search.get_pool', lambda: object())
    response = client.post('/api/search', json={'document_id': 'doc', 'query': 'FPT'})
    assert response.status_code == 409
    assert response.json()['reason_code'] == 'SOURCE_CHANGED'
    assert 'results' not in response.json()


def test_search_db_source_allows_null_page_and_uses_db_index(monkeypatch):
    from src.documents.db_ingest import index_version_id_for
    from src.core.config import get_settings
    async def get_document(*args): return {'id': 'doc', 'file_type': 'DB'}
    async def search(pool, document, index, vector, top_k):
        settings = get_settings()
        assert index == index_version_id_for(settings.chunk_words, settings.embedding_model_ref)
        return [{'chunk_index': 0, 'page': None, 'text': 'FPT source content', 'score': 1.0}]
    monkeypatch.setattr(repository, 'get_document', get_document)
    monkeypatch.setattr(repository, 'vector_search', search)
    monkeypatch.setattr('src.api.routers.search.get_pool', lambda: object())
    response = client.post('/api/search', json={'document_id': 'doc', 'query': 'FPT'})
    assert response.status_code == 200
    assert response.json()['results'][0]['page'] is None
