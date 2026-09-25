"""API-level smoke tests for the JSON-based document endpoints
(POST /api/documents/json and POST /api/documents/import-symbol/{symbol}).

Same approach as test_api_search.py: fake embedder + monkeypatched
repository.* so no real database or BAAI/bge-m3 model is required.
"""

import io
import json

from fastapi.testclient import TestClient

from src import repository
from src.config import Settings, get_settings
from src.embeddings import get_embedding_service
from src.main import app


class FakeEmbedder:
    def embed_texts(self, texts):
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 4


app.dependency_overrides[get_embedding_service] = lambda: FakeEmbedder()
client = TestClient(app)


def _patch_storage(monkeypatch):
    async def fake_create_document(pool, filename, page_count):
        return "doc-1"

    async def fake_insert_chunks(pool, document_id, rows):
        fake_insert_chunks.rows = rows

    monkeypatch.setattr(repository, "create_document", fake_create_document)
    monkeypatch.setattr(repository, "insert_chunks", fake_insert_chunks)
    monkeypatch.setattr("src.routers.documents.get_pool", lambda: object())
    return fake_insert_chunks


def test_upload_json_document_normalized_financial_payload(monkeypatch):
    _patch_storage(monkeypatch)
    payload = {
        "symbol": "SSI",
        "price_history": [
            {"date": "2024-01-02", "open": 30.0, "high": 31.0, "low": 29.5, "close": 30.5, "volume": 1000},
        ],
        "financial_data": {
            "ratios": [{"period_label": "2024-Q1", "period_type": "QUARTER", "pe": 11.5}],
            "income_statement": [],
            "balance_sheet": [],
            "cash_flow_statement": [],
        },
    }
    files = {"file": ("SSI.json", io.BytesIO(json.dumps(payload).encode("utf-8")), "application/json")}
    response = client.post("/api/documents/json", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "doc-1"
    assert body["chunk_count"] >= 1


def test_upload_json_document_generic_list_payload(monkeypatch):
    _patch_storage(monkeypatch)
    payload = [{"name": "a", "value": 1}, {"name": "b", "value": 2}]
    files = {"file": ("rows.json", io.BytesIO(json.dumps(payload).encode("utf-8")), "application/json")}
    response = client.post("/api/documents/json", files=files)
    assert response.status_code == 200
    assert response.json()["chunk_count"] == 2


def test_upload_json_document_rejects_invalid_json(monkeypatch):
    _patch_storage(monkeypatch)
    files = {"file": ("bad.json", io.BytesIO(b"{not valid json"), "application/json")}
    response = client.post("/api/documents/json", files=files)
    assert response.status_code == 400


def test_upload_json_document_rejects_non_json_filename(monkeypatch):
    _patch_storage(monkeypatch)
    files = {"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")}
    response = client.post("/api/documents/json", files=files)
    assert response.status_code == 400


def test_import_symbol_reads_normalized_file(tmp_path, monkeypatch):
    _patch_storage(monkeypatch)
    payload = {
        "symbol": "SSI",
        "price_history": [
            {"date": "2024-01-02", "open": 30.0, "high": 31.0, "low": 29.5, "close": 30.5, "volume": 1000},
        ],
        "financial_data": {"ratios": [{"period_label": "2024-Q1", "period_type": "QUARTER", "pe": 11.5}]},
    }
    (tmp_path / "SSI.json").write_text(json.dumps(payload), encoding="utf-8")

    fake_settings = Settings(financial_data_dir=str(tmp_path))
    app.dependency_overrides[get_settings] = lambda: fake_settings
    try:
        response = client.post("/api/documents/import-symbol/ssi")
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 200
    assert response.json()["filename"] == "SSI.json"


def test_import_symbol_404_when_file_missing(tmp_path, monkeypatch):
    _patch_storage(monkeypatch)
    fake_settings = Settings(financial_data_dir=str(tmp_path))
    app.dependency_overrides[get_settings] = lambda: fake_settings
    try:
        response = client.post("/api/documents/import-symbol/ZZZ")
    finally:
        del app.dependency_overrides[get_settings]

    assert response.status_code == 404
