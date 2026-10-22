"""Read-only, provisional WBS20/WBS25 audit of proposed Golden40 v6.

This measures retrieval and filter behavior on the selected index. It does not
score Recall/MRR or approve draft answers: reviewed gold labels are absent.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from golden_v6 import DEFAULT_GOLDEN, load_golden_v6
from src.core.db import connect, disconnect, get_pool
from src.documents import repository
from src.documents.embeddings import get_embedding_service

V2_INDEX_ID = "434ef5e0-6516-578d-8d18-721d21347e01"

# Every value below is visible in the revised question itself. The month filter
# avoids UTC publication-date ambiguity; no gold IDs or answers are used.
QUESTION_SCOPE = {
    1: ("TCB", "2026-10"), 2: ("CTG", "2026-10"),
    3: ("FPT", "2026-09"), 4: ("FPT", "2026-09"),
    5: (None, "2026-09"), 6: ("MBB", "2026-09"),
    7: ("TCB", "2026-10"), 8: ("VCB", "2026-08"),
    9: ("FPT", "2026-09"), 10: ("FPT", "2026-10"),
    **{number: ("FPT", "2026-Q2") for number in range(31, 39)},
}


def selected_questions(questions, ids):
    if not ids:
        return questions
    wanted = {part.strip().upper() for part in ids.split(",")}
    known = {item["id"] for item in questions}
    unknown = wanted - known
    if unknown:
        raise ValueError(f"Unknown Golden IDs: {', '.join(sorted(unknown))}")
    return [item for item in questions if item["id"] in wanted]


def classify_status(question):
    number = question["number"]
    if number in QUESTION_SCOPE:
        return "provisional_retrieval"
    if 21 <= number <= 29:
        return "blocked_pdf_not_in_v2"
    if question["kind"] == "refusal":
        return "requires_answer_generation_and_reviewed_scope"
    return "separate_structured_query_not_vector_recall"


async def search(pool, index_id, vector, top_k, company, period, doc_type):
    """Read ranked IDs first; one stale source must not hide the other hits."""
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            start = time.perf_counter()
            rows = await conn.fetch(
                """
                SELECT t.chunk_id::text,t.document_id::text,t.chunk_index,
                       t.content_hash,t.locator_json,i.chunker_version,
                       d.title,d.doc_type,
                       coalesce(c.symbol,t.locator_json->>'symbol') AS company_symbol,
                       coalesce(p.period_code,t.locator_json->>'period_code',
                                t.locator_json->>'published_at',
                                t.locator_json->>'section') AS period,
                       1-(t.embedding <=> $5::vector) AS score
                FROM public.text_chunks t
                JOIN public.index_versions i USING(index_version_id)
                JOIN public.documents d USING(document_id)
                LEFT JOIN public.companies c USING(company_id)
                LEFT JOIN public.reporting_periods p USING(period_id)
                WHERE t.index_version_id=$1::uuid AND t.superseded_at IS NULL
                  AND ($2::text IS NULL OR upper(coalesce(c.symbol,
                       t.locator_json->>'symbol',t.locator_json->>'source_id'))=upper($2)
                       OR (t.locator_json->>'source_table'='news_articles' AND EXISTS (
                           SELECT 1 FROM public.news_articles n
                           WHERE n.article_id::text=t.locator_json->>'source_id'
                             AND upper($2)=ANY(n.symbols))))
                  AND ($3::text IS NULL OR coalesce(p.period_code,
                       t.locator_json->>'period_code',
                       t.locator_json->>'published_at',t.locator_json->>'section',
                       d.title) ILIKE '%' || $3 || '%')
                  AND ($4::text IS NULL OR upper(d.doc_type)=upper($4))
                ORDER BY t.embedding <=> $5::vector LIMIT $6
                """,
                index_id, company, period, doc_type, vector, top_k,
            )
            retrieval_ms = round((time.perf_counter() - start) * 1000, 3)
            hits = []
            for row in rows:
                hit = dict(row)
                try:
                    hit = (await repository.resolve_result_rows(conn, [row]))[0]
                    hit["resolution_error"] = None
                except Exception as exc:
                    hit["resolution_error"] = f"{type(exc).__name__}: {exc}"
                    hit["text"] = None
                    locator = hit["locator_json"]
                    hit["locator_json"] = json.loads(locator) if isinstance(locator, str) else locator
                hits.append(hit)
            return hits, retrieval_ms


async def run(args):
    questions = selected_questions(load_golden_v6(args.golden), args.ids)
    if args.validate_only:
        print(json.dumps({"questions": len(questions), "kinds": {
            kind: sum(item["kind"] == kind for item in questions)
            for kind in sorted({item["kind"] for item in questions})
        }}, ensure_ascii=False))
        return
    if args.out is None:
        raise ValueError("--out is required unless --validate-only is set")

    await connect()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                index = await conn.fetchrow(
                    "SELECT index_version_id::text,chunker_version,embedding_model,status "
                    "FROM public.index_versions WHERE index_version_id=$1::uuid",
                    args.index_version_id,
                )
                if index is None:
                    raise ValueError("Selected index_version_id does not exist")
                active_chunks = await conn.fetchval(
                    "SELECT count(*) FROM public.text_chunks "
                    "WHERE index_version_id=$1::uuid AND superseded_at IS NULL",
                    args.index_version_id,
                )
                if not active_chunks:
                    raise ValueError("Selected index has no active chunks")
                corpus = await conn.fetchrow(
                    "SELECT version_label,status FROM public.corpus_versions "
                    "WHERE index_version_id=$1::uuid", args.index_version_id,
                )

        embedder = get_embedding_service() if any(
            item["number"] in QUESTION_SCOPE for item in questions
        ) else None
        results = []
        for question in questions:
            item = dict(question, status=classify_status(question),
                        gold_approved=False, recall_at_5=None, recall_at_10=None)
            if question["number"] not in QUESTION_SCOPE:
                results.append(item)
                continue

            number = question["number"]
            company, period = QUESTION_SCOPE[number]
            doc_type = "NEWS" if number <= 10 else "FINANCIAL_STATEMENT"
            item["scope"] = {"company_symbol": company, "period": period,
                             "doc_type": doc_type}
            try:
                started = time.perf_counter()
                vector = embedder.embed_query(question["question"])
                item["embedding_ms"] = round((time.perf_counter() - started) * 1000, 3)
                unfiltered, unfiltered_ms = await search(
                    pool, args.index_version_id, vector, args.top_k,
                    None, None, None,
                )
                scoped, scoped_ms = await search(
                    pool, args.index_version_id, vector, args.top_k,
                    company, period, doc_type,
                )
                bad_company, _ = await search(
                    pool, args.index_version_id, vector, args.top_k,
                    "NO_SUCH_COMPANY", period, doc_type,
                )
                bad_period, _ = await search(
                    pool, args.index_version_id, vector, args.top_k,
                    company, "1900-01", doc_type,
                )
                item.update(
                    unfiltered_ms=unfiltered_ms, scoped_ms=scoped_ms,
                    unfiltered_count=len(unfiltered), scoped_count=len(scoped),
                    unfiltered_source_errors=sum(bool(hit["resolution_error"]) for hit in unfiltered),
                    scoped_source_errors=sum(bool(hit["resolution_error"]) for hit in scoped),
                    wrong_company_empty=not bad_company,
                    wrong_period_empty=not bad_period,
                    scoped_hits=[{
                        "chunk_id": hit["chunk_id"],
                        "document_id": hit["document_id"],
                        "score": round(float(hit["score"]), 6),
                        "doc_type": hit["doc_type"],
                        "title": hit["title"],
                        "content_hash": hit["content_hash"].strip(),
                        "locator": hit["locator_json"],
                        "text_excerpt": hit["text"][:350] if hit["text"] else None,
                        "source_resolution_error": hit["resolution_error"],
                    } for hit in scoped],
                )
                if scoped and item["scoped_source_errors"] == len(scoped):
                    item["status"] = "blocked_source_reconstruction"
                elif item["scoped_source_errors"]:
                    item["status"] = "provisional_retrieval_with_source_errors"
                elif not scoped:
                    item["status"] = "no_scoped_hits"
            except Exception as exc:
                item["status"] = "retrieval_error"
                item["error"] = f"{type(exc).__name__}: {exc}"
            results.append(item)
            print(question["id"], item["status"], "hits=", item.get("scoped_count"),
                  "error=", item.get("error"), flush=True)

        report = {
            "schema_version": "finmind-golden40-v6-provisional-audit-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "golden_file": str(args.golden),
            "index": dict(index),
            "active_chunks": active_chunks,
            "registered_corpus": dict(corpus) if corpus else None,
            "top_k": args.top_k,
            "database_mode": "read-only",
            "official_quality_score": None,
            "reason": "Golden v6 is a draft without reviewed evidence groups or approved answers",
            "questions": results,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"Report: {args.out}; questions={len(results)}; "
              f"retrieval_errors={sum(row['status'] == 'retrieval_error' for row in results)}")
    finally:
        await disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--index-version-id", default=V2_INDEX_ID)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--ids", help="Comma-separated question IDs, e.g. Q01,Q31")
    parser.add_argument("--validate-only", action="store_true")
    asyncio.run(run(parser.parse_args()))
