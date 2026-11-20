"""Dense embedding service (ADR04).

The project proposal (Section 9, Table 18 and ADR04) specifies BAAI/bge-m3 as
the embedding model because it supports Vietnamese and mixed-language
retrieval. This wraps sentence-transformers so the rest of the backend only
depends on embed_texts()/embed_query() and never touches the model directly -
that keeps the retriever swappable per ADR03 (versioned adapters/contracts)
without touching callers.

The model loads on first use, not at import time. The research app warms this
shared service during startup by default. It is ~2.2GB and requires access to
Hugging Face if no local weights exist. Tests should inject a fake service.
"""

from functools import lru_cache
from collections import OrderedDict
import os
from pathlib import Path
import threading

import numpy as np

from ..core.config import get_settings

PROJECT_MODEL_CACHE = Path(__file__).resolve().parents[1] / 'vector_retrieval' / '.cache' / 'huggingface'


class EmbeddingService:
    def __init__(
        self,
        model_name: str,
        *,
        revision: str,
        device: str = "cpu",
        batch_size: int = 8,
    ):
        self.model_name = model_name
        self.revision = revision
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._load_lock = threading.Lock()
        self._encode_lock = threading.Lock()
        self._query_vectors = OrderedDict()

    @property
    def is_ready(self):
        return self._model is not None

    def prepare(self):
        """Load local weights once; safe to run in a shared background task."""
        self._load()

    def _load(self):
        with self._load_lock:
            return self._load_once()

    def _load_once(self):
        if self._model is None:
            # Imported lazily so the package can be imported (e.g. for tests
            # that stub out embeddings) without requiring sentence-transformers
            # or a downloaded model to be present.
            from sentence_transformers import SentenceTransformer

            options = {}
            snapshot = PROJECT_MODEL_CACHE / ('models--' + self.model_name.replace('/', '--')) / 'snapshots' / self.revision
            if (not os.getenv('HF_HUB_CACHE') and (snapshot / 'config.json').is_file()
                    and any((snapshot / name).is_file() for name in ('pytorch_model.bin', 'model.safetensors'))):
                options = {'cache_folder': str(PROJECT_MODEL_CACHE), 'local_files_only': True}
            self._model = SentenceTransformer(
                self.model_name,
                revision=self.revision,
                device=self.device,
                **options,
            )
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Classification, routing and retrieval share this service. Protect
        # tokenizer/model state for every caller, not just the dense retriever.
        with self._encode_lock:
            key=texts[0] if len(texts)==1 and isinstance(texts[0],str) else None
            if key is not None and key in self._query_vectors:
                self._query_vectors.move_to_end(key)
                return [list(self._query_vectors[key])]
            model = self._load()
            vectors = model.encode(
                texts,
                normalize_embeddings=True,  # L2-normalize so cosine == dot product
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=self.batch_size,
            )
            result=np.asarray(vectors,dtype=np.float32).tolist()
            # Reuse only vectors for this exact text and fixed model revision;
            # never cache answers, retrieved documents or conversation state.
            if key is not None and len(result)==1:
                self._query_vectors[key]=tuple(result[0])
                if len(self._query_vectors)>256:self._query_vectors.popitem(last=False)
            return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(
        model_name=settings.embedding_model,
        revision=settings.embedding_model_revision,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
