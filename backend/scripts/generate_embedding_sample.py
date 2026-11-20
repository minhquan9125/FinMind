"""Generate a small, reproducible BAAI/bge-m3 sample from chunks_thu.json."""

import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import sentence_transformers
import torch
import transformers

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
INPUT_PATH = REPO_ROOT / "chunks_thu.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "embedding" / "bge-m3-sample-v1.json"


def select_sample_chunks(chunks: list[dict], limit: int = 3) -> list[dict]:
    """Choose a deterministic sample spanning different source documents."""
    selected = []
    seen_documents = set()
    for chunk in chunks:
        text = chunk.get("text", "").strip()
        document_id = chunk.get("document_id")
        if not text or not document_id or document_id in seen_documents:
            continue
        selected.append(chunk)
        seen_documents.add(document_id)
        if len(selected) == limit:
            break
    if not selected:
        raise ValueError(f"No usable chunks found in {INPUT_PATH}")
    return selected


def main() -> None:
    from backend.src.core.config import get_settings
    from backend.src.documents.embeddings import get_embedding_service

    chunks = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    sample = select_sample_chunks(chunks)
    texts = [chunk["text"].strip() for chunk in sample]

    vectors = get_embedding_service().embed_texts(texts)

    settings = get_settings()
    if len(vectors) != len(sample):
        raise ValueError(f"Expected {len(sample)} vectors, received {len(vectors)}")
    if any(len(vector) != settings.embedding_dim for vector in vectors):
        raise ValueError(f"Expected vectors with {settings.embedding_dim} dimensions")

    samples = []
    for chunk, text, vector in zip(sample, texts, vectors):
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isfinite(norm) or not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
            raise ValueError(f"Expected a normalized vector, got L2 norm {norm}")
        samples.append(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text": text,
                "dimension": len(vector),
                "l2_norm": norm,
                "vector": vector,
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "artifact_version": "s3-g02-sample-v1",
        "source_file": "chunks_thu.json",
        "model_id": settings.embedding_model,
        "model_revision": settings.embedding_model_revision,
        "model_ref": settings.embedding_model_ref,
        "device": settings.embedding_device,
        "batch_size": settings.embedding_batch_size,
        "dimension": settings.embedding_dim,
        "normalized": True,
        "input_count": len(samples),
        "runtime": {
            "python": platform.python_version(),
            "sentence_transformers": sentence_transformers.__version__,
            "transformers": transformers.__version__,
            "torch": torch.__version__,
        },
        "samples": samples,
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(samples)} vectors to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"Model: {settings.embedding_model_ref}")
    print(f"Shape: {len(samples)} x {settings.embedding_dim}; batch size: {settings.embedding_batch_size}")


if __name__ == "__main__":
    main()
