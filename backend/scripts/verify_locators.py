"""WBS11: check that chunk locators lead back to real source rows in Supabase.

Reads chunks from a JSON file written by chunk_from_supabase.py (--out), takes a few
chunks of every source table, and for each one looks the source rows up in the
database (read-only) and compares them with the chunk text.

Examples (from the FinMind root, DATABASE_URL in .env):
    py -X utf8 backend/scripts/chunk_from_supabase.py --out tat_ca_chunks.json
    py -X utf8 backend/scripts/verify_locators.py --chunks tat_ca_chunks.json
    py -X utf8 backend/scripts/verify_locators.py --chunks tat_ca_chunks.json --per-table 10 --report locator-report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.documents.locator_resolver import verify_chunk  # noqa: E402


def load_chunks(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["chunks"] if isinstance(data, dict) and "chunks" in data else data


def _locator(chunk: dict) -> dict:
    locator = chunk.get("locator") or chunk.get("locator_json") or {}
    return json.loads(locator) if isinstance(locator, str) else locator


def sample(chunks: list[dict], per_table: int) -> list[dict]:
    """The first and evenly spread chunks of every source table (deterministic)."""
    by_table: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_table[str(_locator(chunk).get("source_table"))].append(chunk)
    picked: list[dict] = []
    for table in sorted(by_table):
        items = by_table[table]
        step = max(1, len(items) // per_table)
        picked.extend(items[::step][:per_table])
    return picked


async def run(args: argparse.Namespace) -> int:
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Loi: DATABASE_URL chua duoc dat trong .env", file=sys.stderr)
        return 2
    chunks = sample(load_chunks(Path(args.chunks)), args.per_table)
    if not chunks:
        print("Loi: khong co chunk nao trong file.", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(url, ssl="require" if "supabase" in url else None, statement_cache_size=0)
    lines = ["| # | bang nguon | chunk_id | ket qua | van de |", "|---|---|---|---|---|"]
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # table -> [ok, total]
    try:
        for number, chunk in enumerate(chunks, 1):
            locator = _locator(chunk)
            result = await verify_chunk(conn, locator, chunk.get("text", ""))
            table = str(locator.get("source_table"))
            stats[table][1] += 1
            stats[table][0] += 1 if result.ok else 0
            problems = "; ".join(result.problems)[:150] or "-"
            lines.append(f"| {number} | {table} | {str(chunk.get('chunk_id'))[:8]} | "
                         f"{'DAT' if result.ok else 'LOI'} | {problems} |")
    finally:
        await conn.close()

    total_ok = sum(ok for ok, _ in stats.values())
    total = sum(n for _, n in stats.values())
    summary = [f"Kiem tra locator: {total_ok}/{total} chunk dat."] + \
              [f"  {table}: {ok}/{n}" for table, (ok, n) in sorted(stats.items())]
    print("\n".join(summary))
    print("\n".join(lines))
    if args.report:
        Path(args.report).write_text("# Bao cao kiem tra locator (WBS11)\n\n" + "\n".join(summary) + "\n\n"
                                     + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"Da ghi bao cao: {args.report}")
    return 0 if total_ok == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chunks", required=True, help="file JSON chunk (ket qua --out cua chunk_from_supabase.py)")
    parser.add_argument("--per-table", type=int, default=4, help="so chunk mau cho moi bang nguon")
    parser.add_argument("--report", help="ghi bao cao Markdown ra file nay")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
