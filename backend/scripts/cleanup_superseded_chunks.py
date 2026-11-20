"""Delete old superseded price/index chunks (retention policy: 30 days).

Dry run by default: it only reports what would be deleted. Add --apply to delete.
News and financial-statement chunks are never touched, and a chunk that is still
cited in ``evidence`` is never deleted.

Examples (from the FinMind root, DATABASE_URL in .env):
    py -X utf8 backend/scripts/cleanup_superseded_chunks.py                 # report only
    py -X utf8 backend/scripts/cleanup_superseded_chunks.py --apply         # delete
    py -X utf8 backend/scripts/cleanup_superseded_chunks.py --days 60 --apply

Run it on a schedule (Windows Task Scheduler, once a day) after the migration
20261014000300_text_chunks_supersede.sql has been applied.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.documents.retention import DEFAULT_DAYS, DEFAULT_DOC_TYPES, run_retention  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Loi: DATABASE_URL chua duoc dat trong .env", file=sys.stderr)
        return 2
    conn = await asyncpg.connect(url, ssl="require" if "supabase" in url else None, statement_cache_size=0)
    try:
        has_column = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'text_chunks' AND column_name = 'superseded_at'")
        if not has_column:
            print("Loi: bang text_chunks chua co cot superseded_at. Chay migration "
                  "20261014000300_text_chunks_supersede.sql truoc.", file=sys.stderr)
            return 1
        report = await run_retention(conn, args.days, args.doc_types, apply=args.apply)
    except ValueError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2
    finally:
        await conn.close()

    print(f"Chunk da bi thay qua {report.days} ngay, loai {', '.join(report.doc_types)}, "
          "khong co trich dan (evidence) nao tro toi:")
    if not report.candidates:
        print("  khong co chunk nao can xoa.")
    for doc_type, count in report.candidates.items():
        print(f"  {doc_type}: {count} chunk")
    print(f"  tong: {report.candidate_total} chunk, khoang {report.bytes_total / 1024 / 1024:.2f} MB")
    if report.applied:
        print(f"Da xoa {report.deleted} chunk.")
    else:
        print("Chay thu: chua xoa gi. Them --apply de xoa.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="giu chunk da bi thay trong so ngay nay")
    parser.add_argument("--doc-types", nargs="+", default=list(DEFAULT_DOC_TYPES),
                        help="loai tai lieu duoc phep xoa (mac dinh gia va chi so)")
    parser.add_argument("--apply", action="store_true", help="xoa that (mac dinh chi bao cao)")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
