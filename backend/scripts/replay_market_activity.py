"""Replay stored quote envelopes into public.daily_market_activity.

  python -m backend.scripts.replay_market_activity --input <file-or-folder> [--apply]

Dry-run by default: no database, no configuration, no provider call. Reads real
live/audit/durable quote files inside the repository, validates them with the
shared normalizer and, with --apply, stores them through the shared importer in
one transaction. Old snapshots keep their observed session state; nothing here
turns an intraday quote into an end-of-day figure or invents missing days.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from backend.scripts import ingest_market_news_to_supabase as ingest
from backend.src.market_data.activity import classify_activity_session, normalize_activity
from backend.src.market_data.universe import BACKGROUND_SYMBOLS

SOURCE = "vnstock_kbs"
MAX_FILES = 2000
MAX_BYTES = 1024 * 1024
SAVED = ("inserted", "updated", "unchanged")


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _json_files(target: Path) -> list[Path]:
    """Sorted, bounded, link-free *.json files under a path inside the repository."""
    root = ingest.PROJECT_ROOT
    absolute = Path(os.path.abspath(target))
    if not absolute.exists() or not absolute.resolve().is_relative_to(root):
        raise ValueError("--input must be an existing path inside the repository")
    for item in (absolute, *absolute.parents):
        if item == root:
            break
        if _is_link(item):
            raise ValueError("--input must not pass through a link")
    base = absolute.resolve()
    if base.is_file():
        return [base]
    files: list[Path] = []
    for folder, folders, names in os.walk(base):
        folders[:] = sorted(name for name in folders if not _is_link(Path(folder, name)))
        files += [Path(folder, name) for name in sorted(names)
                  if name.endswith(".json") and not name.endswith(".ack.json")]
        if len(files) > MAX_FILES:
            raise ValueError(f"More than {MAX_FILES} JSON files; narrow --input")
    return files


def _envelope(path: Path) -> tuple[str, object]:
    """('ok', envelope) or (outcome, reason) for files that carry no usable quote."""
    try:
        if _is_link(path):
            return "rejected", "link"
        if path.stat().st_size > MAX_BYTES:
            return "rejected", "larger_than_1MiB"
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "rejected", "unreadable_json"
    if not (isinstance(data, dict) and isinstance(data.get("fetched_at"), str)
            and isinstance(data.get("rows"), list)):
        return "skipped", "not_a_quote_envelope"
    if data.get('instrument_type') == 'index' or data.get('symbol') in ingest.INDEX_SYMBOLS:
        return 'skipped', 'benchmark_is_not_stock_activity'
    return "ok", data


async def apply_plans(plans: list[dict]) -> list[str]:
    """Store every plan in one transaction: all observations land or none."""
    conn = await ingest.connect_database()
    try:
        async with conn.transaction():
            return [(await ingest.apply_live(conn, plan))["activity_status"] for plan in plans]
    finally:
        await conn.close()


async def replay(target: Path, apply: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    summary = {"input": str(target), "apply": apply, "observed": 0, "inserted": 0, "updated": 0,
               "unchanged": 0, "rejected": 0, "skipped": 0, "failed": 0, "dates": [],
               "missing": [], "observations": [], "issues": []}
    plans = []

    def issue(outcome, path, reason, symbol=None):
        summary[outcome] += 1
        summary["issues"].append({"file": ingest.rel(path), "symbol": symbol,
                                  "outcome": outcome, "reason": reason})

    for path in _json_files(Path(target)):
        outcome, data = _envelope(path)
        if outcome != "ok":
            issue(outcome, path, data)
            continue
        rows = [row for row in data["rows"] if isinstance(row, dict)]
        if not rows:
            issue("rejected", path, "no_quote_rows")
        for symbol in dict.fromkeys(str(row.get("symbol")) for row in rows):
            if symbol in ingest.INDEX_SYMBOLS:
                issue("skipped", path, "benchmark_is_not_stock_activity", symbol)
                continue
            if symbol not in ingest.PROJECT_SYMBOLS.union(BACKGROUND_SYMBOLS):
                issue("rejected", path, "untracked_symbol", symbol[:16])
                continue
            # One quote per stored observation, the shape the durable archive already uses.
            single = {**data, "rows": [row for row in rows if row.get("symbol") == symbol]}
            session = classify_activity_session(single, ingest.PROJECT_ROOT)
            try:
                record = normalize_activity(single, symbol=symbol, source_name=SOURCE,
                                            now=now, session_status=session)
            except ValueError as exc:
                issue("rejected", path, str(exc), symbol)
                continue
            summary["observed"] += 1
            summary["observations"].append({
                "file": ingest.rel(path), "symbol": symbol,
                "trade_date": record["trade_date"].isoformat(),
                "fetched_at": record["fetched_at"].isoformat(),
                "observation_status": record["observation_status"],
                "quality_status": record["quality_status"], "warnings": record["warnings"],
                "volume": record["volume"],
                "foreign_buy_volume": record["foreign_buy_volume"],
                "foreign_sell_volume": record["foreign_sell_volume"],
                "total_value_vnd": None if record["total_value_vnd"] is None else str(record["total_value_vnd"]),
            })
            plans.append({"symbol": symbol, "source": SOURCE, "is_index": False, "live": single,
                          "live_path": path, "activity_session_status": session})

    # Oldest first, so a later snapshot of the same day replaces an earlier one.
    order = sorted(range(len(plans)), key=lambda i: datetime.fromisoformat(summary["observations"][i]["fetched_at"]))
    plans = [plans[i] for i in order]
    summary["observations"] = [summary["observations"][i] for i in order]
    summary["dates"] = sorted({item["trade_date"] for item in summary["observations"]})
    summary["missing"] = sorted(set(BACKGROUND_SYMBOLS) - {item["symbol"] for item in summary["observations"]})

    if apply and plans:
        try:
            statuses = await apply_plans(plans)
        except Exception as exc:  # rolled back as a whole; report the class, never a DSN
            summary["failed"] = len(plans)
            summary["error"] = type(exc).__name__
        else:
            for observation, status in zip(summary["observations"], statuses, strict=True):
                observation["database_status"] = status
                summary[status if status in SAVED else "rejected"] += 1
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="quote file or folder inside the repository")
    parser.add_argument("--apply", action="store_true", help="write to the configured database (default: dry run)")
    args = parser.parse_args(argv)
    try:
        summary = asyncio.run(replay(args.input, apply=args.apply))
    except ValueError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed"] or summary["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
