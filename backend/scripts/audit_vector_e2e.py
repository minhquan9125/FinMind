r"""Read-only WBS34 smoke test: one frozen news document through pgvector retrieval.

Run from the repository root:
    backend\.venv\Scripts\python.exe -X utf8 backend\scripts\audit_vector_e2e.py

The sample is Golden Q03 on corpus-v4. The script never ingests or updates rows.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.config import get_settings
from src.core.db import connect, disconnect, get_pool
from src.documents import repository
from src.documents.embeddings import get_embedding_service


CORPUS_ID = "33d33730-0f0a-5274-a7f8-8d32a6be07e8"
DOCUMENT_ID = "66bc216c-5874-51a0-9dc9-f4c094287405"
SOURCE_ID = "f48b4ed9-fe8b-5f65-8d50-e3162c8b2de8"
QUESTION = (
    "Theo tin tức corpus, FPT đã phân phối bao nhiêu cổ phiếu tăng vốn "
    "từ nguồn vốn chủ sở hữu, cho bao nhiêu cổ đông và kết thúc đợt phát hành "
    "vào ngày nào (theo bài đăng ngày 29/09/2026)?"
)
EVIDENCE = ("171,4 triệu cổ phiếu", "181.748 cổ đông", "22/09/2026")


def check_chunks(rows, resolved, *, document_id, index_id, source_id, dimensions):
    """Check stored metadata against text reconstructed from the pinned source."""
    problems = []
    if not rows:
        return ["NO_ACTIVE_CHUNKS"]
    if len(rows) != len(resolved):
        problems.append("SOURCE_RECONSTRUCTION_COUNT_MISMATCH")
    positions = [row["chunk_index"] for row in rows]
    ids = [row["chunk_id"] for row in rows]
    if positions != list(range(len(rows))) or len(set(ids)) != len(ids):
        problems.append("DUPLICATE_OR_MISSING_CHUNK_POSITION")
    for row, source in zip(rows, resolved):
        locator = source["locator_json"]
        meta = locator.get("reconstruction", {})
        if row["document_id"] != document_id or row["index_version_id"] != index_id:
            problems.append("WRONG_DOCUMENT_OR_INDEX")
        if locator.get("source_table") != "news_articles" or locator.get("source_id") != source_id:
            problems.append("WRONG_SOURCE_LOCATOR")
        if meta.get("chunk_index") != row["chunk_index"] or meta.get("document_id") is None:
            problems.append("WRONG_CHUNK_LOCATOR")
        if row["dimensions"] != dimensions:
            problems.append("WRONG_VECTOR_DIMENSION")
        if hashlib.sha256(source["text"].encode("utf-8")).hexdigest() != row["content_hash"].strip():
            problems.append("CHUNK_HASH_MISMATCH")
    return sorted(set(problems))


async def run(output):
    settings = get_settings()
    report = {
        "task": "S3-WBS34",
        "sample": "Golden Q03, FPT news, 2026-09-29",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "mode": "database_read_only",
        "corpus_version_id": CORPUS_ID,
        "document_id": DOCUMENT_ID,
        "checks": {},
    }
    await connect()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                document = await conn.fetchrow(
                    """
                    SELECT cv.index_version_id::text, cv.status AS corpus_status,
                           iv.status AS index_status, iv.embedding_model,
                           cd.document_hash, d.sha256 AS current_document_hash,
                           d.title, d.doc_type
                    FROM public.corpus_versions cv
                    JOIN public.index_versions iv USING(index_version_id)
                    JOIN public.corpus_documents cd USING(corpus_version_id)
                    JOIN public.documents d USING(document_id)
                    WHERE cv.corpus_version_id=$1::uuid AND d.document_id=$2::uuid
                    """, CORPUS_ID, DOCUMENT_ID,
                )
                if document is None:
                    raise RuntimeError("Sample document is absent from frozen corpus")
                index_id = document["index_version_id"]
                report.update(index_version_id=index_id, document_title=document["title"],
                              embedding_model=document["embedding_model"])
                report["checks"]["version_and_document"] = (
                    document["corpus_status"] == "FROZEN"
                    and document["index_status"] == "ACTIVE"
                    and document["embedding_model"] == settings.embedding_model_ref
                    and document["document_hash"] == document["current_document_hash"]
                    and document["doc_type"] == "NEWS"
                )
                rows = await conn.fetch(
                    """
                    SELECT t.chunk_id::text, t.document_id::text, t.index_version_id::text,
                           t.chunk_index, t.content_hash, t.locator_json, t.embedding,
                           vector_dims(t.embedding) AS dimensions, i.chunker_version,
                           d.title, d.doc_type
                    FROM public.text_chunks t
                    JOIN public.index_versions i USING(index_version_id)
                    JOIN public.documents d USING(document_id)
                    WHERE t.document_id=$1::uuid AND t.index_version_id=$2::uuid
                      AND t.superseded_at IS NULL
                    ORDER BY t.chunk_index
                    """, DOCUMENT_ID, index_id,
                )
                resolved = await repository.resolve_result_rows(conn, rows)
                problems = check_chunks(
                    rows, resolved, document_id=DOCUMENT_ID, index_id=index_id,
                    source_id=SOURCE_ID, dimensions=settings.embedding_dim,
                )
                report["checks"]["chunk_metadata_and_source_hash"] = not problems
                report["chunk_problems"] = problems
                report["active_chunk_count"] = len(rows)
                report["chunk_ids"] = [row["chunk_id"] for row in rows]
                report["vector_dimensions"] = sorted({row["dimensions"] for row in rows})

        embedder = get_embedding_service()
        question_vector = embedder.embed_query(QUESTION)
        report["checks"]["question_vector_dimension"] = len(question_vector) == settings.embedding_dim
        scope = dict(company_symbol="FPT", period="2026-09", doc_type="NEWS",
                     corpus_version_id=CORPUS_ID)
        hits = await repository.vector_search_filtered(pool, index_id, question_vector, 5, **scope)
        target_hits = [(rank, hit) for rank, hit in enumerate(hits, 1)
                       if hit["document_id"] == DOCUMENT_ID]
        evidence_ranks = [rank for rank, hit in target_hits
                          if all(marker in hit["text"] for marker in EVIDENCE)]
        report["top_k"] = 5
        report["hit_count"] = len(hits)
        report["target_document_ranks"] = [rank for rank, _ in target_hits]
        report["evidence_ranks"] = evidence_ranks
        report["hits"] = [
            {"rank": rank, "chunk_id": hit["chunk_id"],
             "document_id": hit["document_id"], "score": round(float(hit["score"]), 6),
             "source_verified": hit.get("source_verified", True)}
            for rank, hit in enumerate(hits, 1)
        ]
        report["checks"]["expected_evidence_in_top_5"] = bool(evidence_ranks)
        report["checks"]["returned_sources_verified"] = all(
            hit.get("source_verified", True) for hit in hits
        )

        # Re-embed the verified target chunk and compare with its stored vector.
        if evidence_ranks:
            target = hits[evidence_ranks[0] - 1]
            stored = next(row for row in rows if row["chunk_id"] == target["chunk_id"])
            fresh = np.asarray(embedder.embed_query(target["text"]), dtype=np.float64)
            saved = np.asarray(stored["embedding"], dtype=np.float64)
            cosine = float(np.dot(fresh, saved) / (np.linalg.norm(fresh) * np.linalg.norm(saved)))
            report["stored_vs_reembedded_cosine"] = round(cosine, 8)
            report["checks"]["stored_vector_matches_model"] = cosine >= 0.9999
        else:
            report["checks"]["stored_vector_matches_model"] = False

        second = await repository.vector_search_filtered(pool, index_id, question_vector, 5, **scope)
        report["checks"]["repeat_search_same_chunk_ids"] = (
            [row["chunk_id"] for row in hits] == [row["chunk_id"] for row in second]
        )
        wrong_company = await repository.vector_search_filtered(
            pool, index_id, question_vector, 5, **{**scope, "company_symbol": "NO_SUCH_COMPANY"}
        )
        wrong_period = await repository.vector_search_filtered(
            pool, index_id, question_vector, 5, **{**scope, "period": "1900-01"}
        )
        report["checks"]["wrong_company_empty"] = not wrong_company
        report["checks"]["wrong_period_empty"] = not wrong_period
        positions = [row["chunk_index"] for row in rows]
        report["checks"]["no_duplicate_stored_positions"] = (
            bool(rows)
            and len(positions) == len(set(positions))
            and len(report["chunk_ids"]) == len(set(report["chunk_ids"]))
        )
        report["ingest_rerun_on_database"] = "not_run; this audit is read-only"
    finally:
        await disconnect()

    report["passed"] = all(report["checks"].values())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"],
                      "active_chunk_count": report["active_chunk_count"],
                      "evidence_ranks": report["evidence_ranks"],
                      "report": str(output)}, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "backend" / ".tmp" / "wbs34-q03-e2e.json")
    asyncio.run(run(parser.parse_args().out))
