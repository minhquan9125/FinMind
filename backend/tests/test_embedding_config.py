from types import SimpleNamespace
import sys

import numpy as np

from src.core.config import Settings
from src.documents.embeddings import EmbeddingService


def test_embedding_model_ref_includes_pinned_revision():
    settings = Settings()

    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_model_revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert settings.embedding_model_ref == (
        "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181"
    )
    assert settings.embedding_dim == 1024
    assert settings.embedding_batch_size == 8


def test_embedding_service_uses_revision_and_batch_size(monkeypatch):
    calls = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name, **kwargs):
            calls["constructor"] = (model_name, kwargs)

        def encode(self, texts, **kwargs):
            calls["encode"] = (texts, kwargs)
            return np.ones((len(texts), 4), dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    service = EmbeddingService(
        model_name="BAAI/bge-m3",
        revision="revision-sha",
        device="cpu",
        batch_size=3,
    )

    vectors = service.embed_texts(["text one", "text two"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 4
    assert calls["constructor"] == (
        "BAAI/bge-m3",
        {"revision": "revision-sha", "device": "cpu"},
    )
    assert calls["encode"][1]["batch_size"] == 3
    assert calls["encode"][1]["normalize_embeddings"] is True
