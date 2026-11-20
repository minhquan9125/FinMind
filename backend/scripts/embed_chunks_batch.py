"""Embed a JSON chunk fixture and write vectors plus per-chunk status to JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.config import get_settings  # noqa: E402
from src.documents.batch_embeddings import embed_chunks  # noqa: E402
from src.documents.embeddings import EmbeddingService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "chunks_thu.json")
    parser.add_argument("--output", type=Path, default=ROOT / "backend/.tmp/embedding-batch-results.json")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None, help="process only the first N chunks")
    args = parser.parse_args()

    chunks = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        parser.error("input JSON must be a list of chunks")
    if args.limit is not None:
        chunks = chunks[:args.limit]

    settings = get_settings()
    batch_size = settings.embedding_batch_size if args.batch_size is None else args.batch_size
    embedder = EmbeddingService(
        model_name=settings.embedding_model,
        revision=settings.embedding_model_revision,
        device=settings.embedding_device,
        batch_size=batch_size,  # one value for both the model's inner batches and the outer batches
    )
    result = embed_chunks(chunks, embedder, batch_size=batch_size, max_retries=args.max_retries)
    output = {
        "model_ref": settings.embedding_model_ref,
        "embedding_dim": settings.embedding_dim,
        "batch_size": batch_size,
        "max_retries": args.max_retries,
        "input_count": len(chunks),
        "succeeded_count": len(result.succeeded),
        "failed_count": len(result.failed),
        "skipped_count": len(result.skipped),
        "succeeded": result.succeeded,
        "failed": result.failed,
        "skipped": result.skipped,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    # Keep the summary printable on Windows shells using legacy code pages.
    print(f"Input: {len(chunks)} | succeeded: {len(result.succeeded)} | failed: {len(result.failed)}"
          f" | skipped (duplicate id): {len(result.skipped)}")
    print(f"JSON output: {args.output}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
