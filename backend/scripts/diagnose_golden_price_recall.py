"""Compare HNSW and exact vector search for Golden price questions.

Uses the current db-v1 vectors and never writes to the database. This checks
whether raising top_k or bypassing HNSW finds the exact source price rows.
"""

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.config import get_settings
from src.core.db import connect, disconnect, get_pool
from src.documents import repository
from src.documents.embeddings import get_embedding_service

from audit_golden_q01_q20 import PRICE_DATES, SCOPE, load_golden


SQL = """
SELECT t.locator_json, d.title
FROM public.text_chunks t
JOIN public.documents d USING(document_id)
LEFT JOIN public.companies c USING(company_id)
LEFT JOIN public.reporting_periods p USING(period_id)
WHERE t.index_version_id = $1
  AND t.superseded_at IS NULL
  AND ($2::text IS NULL OR upper(coalesce(c.symbol,
       t.locator_json->>'symbol', t.locator_json->>'source_id')) = upper($2))
  AND ($3::text IS NULL OR coalesce(p.period_code,
       t.locator_json->>'published_at', t.locator_json->>'section',
       d.title) ILIKE '%' || $3 || '%')
  AND d.doc_type = 'PRICE_HISTORY'
ORDER BY t.embedding <=> $4::vector
LIMIT $5
"""


async def search(conn, index_version_id, company, period, vector, top_k, *, exact):
    async with conn.transaction(readonly=True):
        if exact:
            await conn.execute("SET LOCAL enable_indexscan = off")
            await conn.execute("SET LOCAL enable_bitmapscan = off")
        rows = await conn.fetch(SQL, index_version_id, company, period, vector, top_k)
        return [json.loads(row["locator_json"])
                if isinstance(row["locator_json"], str)
                else row["locator_json"] for row in rows]


async def run(args):
    settings = get_settings()
    index_version_id = repository.index_for_document(
        {"file_type": "DB"}, settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model_ref,
    )
    questions = load_golden(ROOT / "Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md")
    await connect()
    try:
        embedder = get_embedding_service()
        cases = []
        async with get_pool().acquire() as conn:
            for number in (11, 12, 13, 16, 20):
                company, period, _ = SCOPE[number]
                vector = embedder.embed_query(questions[number]["question"])
                needed = {}
                async with conn.transaction(readonly=True):
                    for symbol, day in PRICE_DATES[number]:
                        price_id = await conn.fetchval(
                            """
                            SELECT p.price_id::text FROM public.price_bars p
                            JOIN public.companies c USING(company_id)
                            WHERE c.symbol = $1 AND p.trade_date = $2
                            """, symbol, date.fromisoformat(day),
                        )
                        needed[f"{symbol}:{day}"] = price_id
                measurements = []
                for exact in (False, True):
                    for top_k in (5, 20):
                        locators = await search(
                            conn, index_version_id, company, period, vector,
                            top_k, exact=exact,
                        )
                        keys = {key for locator in locators
                                for key in locator.get("row_keys", [])}
                        found = [name for name, price_id in needed.items()
                                 if price_id in keys]
                        measurements.append({
                            "mode": "exact" if exact else "hnsw",
                            "top_k": top_k,
                            "returned_chunks": len(locators),
                            "found_rows": found,
                            "all_rows_found": len(found) == len(needed),
                        })
                cases.append({"id": f"Q{number:02d}", "required_rows": list(needed),
                              "measurements": measurements})
        report = {
            "schema_version": "finmind-price-recall-diagnosis-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "index_version_id": index_version_id,
            "transaction_mode": "read-only",
            "cases": cases,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        for case in cases:
            print(case["id"], [(item["mode"], item["top_k"], item["found_rows"])
                                for item in case["measurements"]])
        print(f"Report: {args.out}")
    finally:
        await disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
