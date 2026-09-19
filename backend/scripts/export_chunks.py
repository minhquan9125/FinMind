"""Export chunks + BAAI/bge-m3 embeddings for the 8 pre-scraped tickers to
plain JSON files, without needing PostgreSQL/Docker running.

Reuses the exact same pipeline the API uses (json_ingest.financial_json_to_pages
-> chunking.build_chunks -> text_analysis.term_frequencies -> EmbeddingService)
so the chunks in these files are identical to what POST /api/documents/import-
symbol/{symbol} would store in document_chunks - just written to a file
instead of a database, for a teammate who wants the data without setting up
Postgres/pgvector.

Usage (from backend/):
    python scripts/export_chunks.py [SYMBOL ...]
    (no args -> exports all of TARGET_SYMBOLS below)

Output: data/chunks/{SYMBOL}.chunks.json (one file per symbol), each an
object: {symbol, model, embedding_dim, generated_at, chunk_count, chunks: [...]}.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parent.parent
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from src.chunking import build_chunks  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.embeddings import get_embedding_service  # noqa: E402
from src.json_ingest import financial_json_to_pages  # noqa: E402
from src.text_analysis import term_frequencies  # noqa: E402

# Same list as TARGET_SYMBOLS in data_pipeline/src/scrapers/direct_vn_collector.py
TARGET_SYMBOLS = ["FPT", "VNM", "HPG", "VCB", "MWG", "VIC", "TCB", "SSI"]

REPO_ROOT = BACKEND_SRC.parent
NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
OUTPUT_DIR = REPO_ROOT / "data" / "chunks"


def export_symbol(symbol: str) -> None:
    source_path = NORMALIZED_DIR / f"{symbol}.json"
    if not source_path.exists():
        print(f"  [!] Skip {symbol}: no file at {source_path}")
        return

    settings = get_settings()
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    pages = financial_json_to_pages(symbol, payload)
    raw_chunks = build_chunks(pages, settings.chunk_words, settings.chunk_stride)
    if not raw_chunks:
        print(f"  [!] Skip {symbol}: no chunks produced")
        return

    chunk_texts = [c.text for c in raw_chunks]
    tf_list, _df, _ttf = term_frequencies(chunk_texts)

    print(f"  Embedding {len(chunk_texts)} chunks with {settings.embedding_model} (this is the slow step)...")
    start = time.monotonic()
    embedder = get_embedding_service()
    embeddings = embedder.embed_texts(chunk_texts)
    elapsed = time.monotonic() - start
    print(f"  Done embedding in {elapsed:.1f}s")

    chunks_out = []
    for index, (chunk, tf, vector) in enumerate(zip(raw_chunks, tf_list, embeddings)):
        chunks_out.append(
            {
                "chunk_index": index,
                "page": chunk.page,
                "text": chunk.text,
                "word_count": len(chunk.text.split(" ")),
                "token_count": sum(tf.values()),
                "unique_count": len(tf),
                "embedding": vector,
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{symbol}.chunks.json"
    out_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "model": settings.embedding_model,
                "embedding_dim": settings.embedding_dim,
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "chunk_count": len(chunks_out),
                "chunks": chunks_out,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  -> Saved {len(chunks_out)} chunks to {out_path.relative_to(REPO_ROOT)}")


def main(symbols: list[str]) -> None:
    print(f"Exporting chunks for: {', '.join(symbols)}")
    for symbol in symbols:
        print(f"\n[{symbol}]")
        export_symbol(symbol)


if __name__ == "__main__":
    main([s.upper() for s in sys.argv[1:]] or TARGET_SYMBOLS)
