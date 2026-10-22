"""Run the fixed WBS20 retrieval set against the configured pgvector database.

The search transaction is read-only. Embedding is reported separately from
database retrieval time. Re-run the same command before and after creating the
HNSW index to compare results.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.config import get_settings
from src.core.db import connect, disconnect, get_pool
from src.documents import repository
from src.documents.embeddings import get_embedding_service


async def run(args):
    questions_path = args.questions
    questions = json.loads(questions_path.read_text(encoding="utf-8"))["questions"]
    settings = get_settings()
    index_version_id = repository.index_for_document(
        {"file_type": "DB"}, settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model_ref,
    )
    await connect()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                pgvector = await conn.fetchval(
                    "SELECT extversion FROM pg_extension WHERE extname='vector'"
                )
                hnsw = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' "
                    "AND tablename='text_chunks' AND indexdef ILIKE '%USING hnsw%')"
                )
        embedder = get_embedding_service()
        results = []
        for question in questions:
            start = time.perf_counter()
            vector = embedder.embed_query(question["query"])
            embedding_ms = (time.perf_counter() - start) * 1000
            timings = []
            hits = []
            for attempt in range(args.runs + 1):
                start = time.perf_counter()
                found = await repository.vector_search_filtered(
                    pool, index_version_id, vector, args.top_k,
                    company_symbol=question.get("company_symbol"),
                    period=question.get("period"),
                    doc_type=question.get("doc_type"),
                )
                elapsed = (time.perf_counter() - start) * 1000
                if attempt:
                    timings.append(elapsed)
                hits = found
            expected = question.get("expected_title_contains", "").casefold()
            expected_row_key = question.get("expected_row_key")
            if question.get("expected_empty"):
                expected_found = not hits
            else:
                expected_found = any(
                    (expected and expected in row["title"].casefold())
                    or (expected_row_key and expected_row_key in row["locator_json"].get("row_keys", []))
                    for row in hits
                )
            wanted_period = question.get("period")
            in_scope = all(
                (not question.get("doc_type") or row["doc_type"] == question["doc_type"])
                and (not question.get("company_symbol") or row["company_symbol"] == question["company_symbol"])
                and (not wanted_period or wanted_period in (row["period"] or ""))
                for row in hits
            )
            results.append({
                "id": question["id"],
                "source_question_id": question["source_question_id"],
                "language": question["language"],
                "embedding_ms": round(embedding_ms, 3),
                "retrieval_ms": [round(value, 3) for value in timings],
                "retrieval_mean_ms": round(statistics.mean(timings), 3),
                "expected_source_found": expected_found,
                "scope_correct": in_scope,
                "hits": [{
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "doc_type": row["doc_type"],
                    "company_symbol": row["company_symbol"],
                    "period": row["period"],
                    "score": round(float(row["score"]), 6),
                    "locator": row["locator_json"],
                    "text_excerpt": row["text"][:500],
                } for row in hits],
            })
        report = {
            "schema_version": "finmind-wbs20-benchmark-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "index_version_id": index_version_id,
            "embedding_model": settings.embedding_model_ref,
            "embedding_dimension": settings.embedding_dim,
            "pgvector_version": pgvector,
            "hnsw_present": hnsw,
            "top_k": args.top_k,
            "timed_runs_per_question": args.runs,
            "transaction_mode": "read-only",
            "question_count": len(results),
            "questions": results,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = {
            "file": str(args.out),
            "questions": len(results),
            "hnsw_present": hnsw,
            "mean_retrieval_ms": round(statistics.mean(
                row["retrieval_mean_ms"] for row in results), 3),
            "expected_source_found": sum(row["expected_source_found"] for row in results),
            "scope_correct": sum(row["scope_correct"] for row in results),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        await disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path,
                        default=ROOT / "backend/scripts/fixtures/wbs20_filtered_questions.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--runs", type=int, default=3,
                        help="Timed DB runs per question after one untimed warm-up")
    asyncio.run(run(parser.parse_args()))
