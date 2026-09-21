"""Dense embedding service (ADR04).

The project proposal (Section 9, Table 18 and ADR04) specifies BAAI/bge-m3 as
the embedding model because it supports Vietnamese and mixed-language
retrieval. This wraps sentence-transformers so the rest of the backend only
depends on embed_texts()/embed_query() and never touches the model directly -
that keeps the retriever swappable per ADR03 (versioned adapters/contracts)
without touching callers.

The model is loaded lazily (on first use, not at import time) because it is
~2.2GB and requires network access to Hugging Face on first run. Unit tests
should inject a fake EmbeddingService instead of loading the real model.
"""

from functools import lru_cache

import numpy as np

from .config import get_settings


class EmbeddingService:
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load(self):
        if self._model is None:
            # Imported lazily so the package can be imported (e.g. for tests
            # that stub out embeddings) without requiring sentence-transformers
            # or a downloaded model to be present.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,  # L2-normalize so cosine == dot product
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(model_name=settings.embedding_model, device=settings.embedding_device)
