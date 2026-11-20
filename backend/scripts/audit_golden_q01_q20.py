"""Audit Vietnamese Golden Q01-Q20 against the current db-v1 vector index.

This reads the questions from the approved Markdown file and the expected
source identities from the same file. Database work uses read-only
transactions; the report is written locally with --out.
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from src.core.config import get_settings
from src.core.db import connect, disconnect, get_pool
from src.documents import repository
from src.documents.embeddings import get_embedding_service


# A period filter is used only when the question concerns one publication or
# one price month. Cross-period and whole-dataset questions stay unfiltered.
SCOPE = {
    1: ("MSN", "2026-09", "NEWS"),
    2: ("CTR", "2026-07", "NEWS"),
    3: ("FPT", "2026-09", "NEWS"),
    4: ("FPT", "2026-09", "NEWS"),
    5: (None, "2026-09", "NEWS"),
    6: ("MBB", "2026-09", "NEWS"),
    7: ("CTR", "2026-08", "NEWS"),
    8: (None, "2026-10", "NEWS"),
    9: ("CTR", "2026-09", "NEWS"),
    10: (None, None, "NEWS"),
    11: ("VCB", None, "PRICE_HISTORY"),
    12: (None, None, "PRICE_HISTORY"),
    13: ("FPT", None, "PRICE_HISTORY"),
    14: ("CTR", None, "PRICE_HISTORY"),
    15: ("VCB", "2026-05", "PRICE_HISTORY"),
    16: (None, None, "PRICE_HISTORY"),
    17: ("MSN", "2026-07", "PRICE_HISTORY"),
    18: (None, None, "PRICE_HISTORY"),
    19: ("VCB", "2026-04", "PRICE_HISTORY"),
    20: ("MBB", None, "PRICE_HISTORY"),
}

# These source dates come from Golden, not from retrieval output. For a question
# that compares two dates, both price rows must be among the returned chunks.
PRICE_DATES = {
    11: [("VCB", "2026-04-09"), ("VCB", "2026-10-06")],
    12: [("MBB", "2026-05-20")],
    13: [("FPT", "2026-04-10"), ("FPT", "2026-07-27")],
    15: [("VCB", "2026-05-20")],
    16: [("NLG", "2026-04-10"), ("NLG", "2026-10-07")],
    17: [("MSN", "2026-07-27")],
    19: [("VCB", "2026-04-23")],
    20: [("MBB", "2026-09-30"), ("MBB", "2026-10-06")],
}

AGGREGATE_QUESTIONS = {10, 12, 13, 14, 16, 18}


def load_golden(path):
    content = path.read_text(encoding="utf-8")
    if content.startswith("# Golden40 v6"):
        raise ValueError(
            "Golden40 v6 uses revised questions and unapproved gold. "
            "Run scripts/audit_golden_v6.py instead; this legacy audit is v5-only."
        )
    blocks = {
        int(number): body
        for number, body in re.findall(
            r"(?ms)^### Q(\d{2})\s*\n(.*?)(?=^### Q\d{2}|^## |\Z)", content
        )
    }
    questions = {}
    for number in range(1, 21):
        body = blocks[number]
        question = re.search(r"(?m)^- \*\*Câu hỏi:\*\* (.+)$", body)
        if question is None:
            raise ValueError(f"Golden Q{number:02d} has no question")
        title = None
        if number <= 9:
            source_line = next(
                line for line in body.splitlines()
                if "news_articles.json" in line and "title" in line
            )
            title = re.search(r'\*"([^"]+)"', source_line).group(1)
        questions[number] = {"question": question.group(1), "title_fragment": title}
    return questions


async def expected_news(conn, title_fragment, index_version_id):
    rows = await conn.fetch(
        """
        SELECT n.article_id::text AS article_id, n.title,
               count(t.chunk_id) AS active_chunks
        FROM public.news_articles n
        LEFT JOIN public.documents d ON d.external_id = n.article_id::text
        LEFT JOIN public.text_chunks t ON t.document_id = d.document_id
          AND t.index_version_id = $2 AND t.superseded_at IS NULL
        WHERE n.title ILIKE '%' || $1 || '%'
        GROUP BY n.article_id, n.title
        """,
        title_fragment, index_version_id,
    )
    return [dict(row) for row in rows]


async def expected_prices(conn, dates, index_version_id):
    expected = []
    for symbol, trade_date in dates:
        row = await conn.fetchrow(
            """
            SELECT p.price_id::text AS price_id
            FROM public.price_bars p JOIN public.companies c USING(company_id)
            WHERE c.symbol = $1 AND p.trade_date = $2
            """,
            symbol, date.fromisoformat(trade_date),
        )
        price_id = row["price_id"] if row else None
        active = False
        if price_id:
            active = await conn.fetchval(
                """
                SELECT EXISTS (
                  SELECT 1 FROM public.text_chunks t
                  JOIN public.documents d USING(document_id)
                  WHERE t.index_version_id = $1 AND t.superseded_at IS NULL
                    AND d.doc_type = 'PRICE_HISTORY'
                    AND t.locator_json->'row_keys' ? $2
                )
                """,
                index_version_id, price_id,
            )
        expected.append({
            "symbol": symbol, "trade_date": trade_date,
            "price_id": price_id, "in_active_index": active,
        })
    return expected


async def run(args):
    questions = load_golden(args.golden)
    settings = get_settings()
    index_version_id = repository.index_for_document(
        {"file_type": "DB"}, settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model_ref,
    )
    await connect()
    try:
        pool = get_pool()
        embedder = get_embedding_service()
        results = []
        for number in range(1, 21):
            company, period, doc_type = SCOPE[number]
            question = questions[number]
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    news = (await expected_news(conn, question["title_fragment"], index_version_id)
                            if number <= 9 else [])
                    prices = (await expected_prices(conn, PRICE_DATES[number], index_version_id)
                              if number in PRICE_DATES else [])

            vector = embedder.embed_query(question["question"])
            try:
                hits = await repository.vector_search_filtered(
                    pool, index_version_id, vector, args.top_k,
                    company_symbol=company, period=period, doc_type=doc_type,
                )
                error = None
            except Exception as exc:
                hits = []
                error = f"{type(exc).__name__}: {exc}"

            returned_keys = {
                key for hit in hits
                for key in hit["locator_json"].get("row_keys", [])
            }
            returned_articles = {
                hit["locator_json"].get("source_id") for hit in hits
            }
            if number <= 9:
                expected_ids = {article["article_id"] for article in news}
                source_in_index = len(news) == 1 and news[0]["active_chunks"] > 0
                retrieved_source = bool(expected_ids & returned_articles)
            elif number in PRICE_DATES:
                source_in_index = all(row["in_active_index"] for row in prices)
                retrieved_source = all(
                    row["price_id"] in returned_keys for row in prices
                )
            else:
                source_in_index = None
                retrieved_source = None

            results.append({
                "id": f"Q{number:02d}",
                "question": question["question"],
                "scope": {"company_symbol": company, "period": period,
                          "doc_type": doc_type},
                "requires_aggregation": number in AGGREGATE_QUESTIONS,
                "source_in_active_index": source_in_index,
                "expected_news": news,
                "expected_price_rows": prices,
                "returned_expected_source": retrieved_source,
                "error": error,
                "hits": [{
                    "chunk_id": hit["chunk_id"], "title": hit["title"],
                    "score": round(float(hit["score"]), 6),
                    "source_id": hit["locator_json"].get("source_id"),
                    "row_keys": hit["locator_json"].get("row_keys", []),
                    "text_excerpt": hit["text"][:350],
                } for hit in hits],
            })

        report = {
            "schema_version": "finmind-golden-q01-q20-audit-v1",
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "golden_file": str(args.golden.relative_to(ROOT)),
            "index_version_id": index_version_id,
            "top_k": args.top_k,
            "transaction_mode": "read-only",
            "questions": results,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for result in results:
            print(
                result["id"],
                "source_in_index=", result["source_in_active_index"],
                "retrieved=", result["returned_expected_source"],
                "hits=", len(result["hits"]),
                "aggregate=", result["requires_aggregation"],
                "error=", result["error"],
            )
        print(f"Report: {args.out}")
    finally:
        await disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path,
                        default=ROOT / "Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=5)
    asyncio.run(run(parser.parse_args()))
