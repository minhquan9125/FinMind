"""Create embeddings for chunks in batches while keeping per-chunk failures."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Protocol, Sequence

EMBEDDING_DIM = 1024


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class BatchEmbeddingResult:
    succeeded: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)


def _validate_vector(vector: Any) -> str | None:
    if not isinstance(vector, (list, tuple)):
        return "embedding is not a vector"
    if len(vector) != EMBEDDING_DIM:
        return f"expected {EMBEDDING_DIM} dimensions, got {len(vector)}"
    try:
        if not all(math.isfinite(float(value)) for value in vector):
            return "embedding contains a non-finite value"
    except (TypeError, ValueError):
        return "embedding contains a non-numeric value"
    return None


def embed_chunks(
    chunks: Sequence[dict[str, Any]],
    embedder: Embedder,
    *,
    batch_size: int = 8,
    max_retries: int = 2,
) -> BatchEmbeddingResult:
    """Embed chunks; isolate a failed batch and retry only failing chunks.

    A chunk-level exception gets one initial attempt plus ``max_retries`` more.
    Invalid input and invalid vector output are deterministic errors and are
    reported immediately without retrying.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    result = BatchEmbeddingResult()
    valid: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id", ""))
        if not chunk_id:
            result.failed.append({"chunk_id": None, "attempts": 0, "retryable": False,
                                 "error": "missing chunk_id"})
            continue
        if chunk_id in seen_ids:
            result.failed.append({"chunk_id": chunk_id, "attempts": 0, "retryable": False,
                                 "error": "duplicate chunk_id; duplicate input ignored"})
            continue
        seen_ids.add(chunk_id)
        text = chunk.get("text")
        if not isinstance(text, str) or not text.strip():
            result.failed.append({"chunk_id": chunk_id, "attempts": 0, "retryable": False,
                                 "error": "chunk text is empty or invalid"})
            continue
        valid.append(chunk)

    for start in range(0, len(valid), batch_size):
        batch = valid[start:start + batch_size]
        try:
            vectors = embedder.embed_texts([chunk["text"] for chunk in batch])
            if len(vectors) != len(batch):
                raise ValueError(f"expected {len(batch)} vectors, got {len(vectors)}")
            vector_errors = [_validate_vector(vector) for vector in vectors]
            if any(vector_errors):
                raise ValueError("one or more vectors had invalid shape or values")
        except Exception:  # isolate the bad chunk without losing batch successes
            for chunk in batch:
                _embed_one(chunk, embedder, result, max_retries)
        else:
            for chunk, vector in zip(batch, vectors):
                result.succeeded.append({"chunk": chunk, "embedding": vector, "attempts": 1})

    return result


def _embed_one(
    chunk: dict[str, Any], embedder: Embedder, result: BatchEmbeddingResult, max_retries: int
) -> None:
    chunk_id = str(chunk["chunk_id"])
    last_error = "embedding failed"
    for attempt in range(1, max_retries + 2):
        try:
            vectors = embedder.embed_texts([chunk["text"]])
            if len(vectors) != 1:
                result.failed.append({"chunk_id": chunk_id, "attempts": attempt, "retryable": False,
                                     "error": f"expected 1 vector, got {len(vectors)}"})
                return
            vector_error = _validate_vector(vectors[0])
            if vector_error:
                result.failed.append({"chunk_id": chunk_id, "attempts": attempt, "retryable": False,
                                     "error": vector_error})
                return
            result.succeeded.append({"chunk": chunk, "embedding": vectors[0], "attempts": attempt})
            return
        except Exception as exc:  # retry model/runtime exceptions only
            last_error = f"{type(exc).__name__}: {exc}"

    result.failed.append({"chunk_id": chunk_id, "attempts": max_retries + 1, "retryable": True,
                         "error": last_error})
