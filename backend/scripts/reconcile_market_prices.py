"""Price-basis gate: compare a candidate daily series with the stored one before appending.

  python -m backend.scripts.reconcile_market_prices --existing <file> --candidate <file>
  python -m backend.scripts.reconcile_market_prices --existing <file> --candidate <file> \
      --apply --receipt <saved dry-run output>

Each file is a JSON list of rows (symbol, trade_date, open, high, low, close,
volume, price_scale, is_adjusted, source_name[, source_id]) or one envelope
{symbol, source_name, price_scale, is_adjusted, bars: [...]}.

Dry-run by default: prints a receipt, touches no database, configuration or
network. --apply appends only the candidate days that come after the stored
series, and only when the saved receipt still matches both files and the
database still equals the reviewed export. It never overwrites a stored price.
Close numbers from another source or basis are never treated as compatible.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys

from backend.scripts import ingest_market_news_to_supabase as ingest
from backend.src.market_data.analysis import _decimal, _row_day, _volume

OHLC = ("open", "high", "low", "close")
BASIS = ("source_name", "source_id", "price_scale", "is_adjusted")


def _rows(series):
    """Rows of a list, or of an envelope whose metadata applies to every bar."""
    if isinstance(series, dict) and isinstance(series.get("bars"), list):
        shared = {key: series[key] for key in ("symbol", *BASIS) if key in series}
        rows = []
        for bar in series["bars"]:
            if not isinstance(bar, dict):
                raise ValueError("row must be an object")
            if any(key in bar and (type(bar[key]), bar[key]) != (type(value), value)
                   for key, value in shared.items()):
                raise ValueError("row conflicts with envelope metadata")
            rows.append({**bar, **shared})
    elif isinstance(series, list):
        rows = series
    else:
        raise ValueError("expected a list of rows or an envelope with bars")
    if not rows:
        raise ValueError("empty series")
    return rows


def _clean(row):
    if not isinstance(row, dict):
        raise ValueError("row must be an object")
    symbol, source, source_id = row.get("symbol"), row.get("source_name"), row.get("source_id")
    if type(symbol) is not str or not re.fullmatch("[A-Z]{3}", symbol):
        raise ValueError("invalid stock symbol")
    item = {"symbol": symbol, "trade_date": _row_day(row), "raw": row,
            **{field: _decimal(row.get(field), positive=True) for field in OHLC}}
    if not item["low"] <= min(item["open"], item["close"]) <= max(item["open"], item["close"]) <= item["high"]:
        raise ValueError("invalid OHLC relationships")
    if row.get("volume") is None:
        raise ValueError("volume is required")
    item["volume"] = _volume(row["volume"])
    if type(row.get("price_scale")) is not int or row["price_scale"] <= 0:
        raise ValueError("a positive integer price_scale is required")
    if type(row.get("is_adjusted")) is not bool:
        raise ValueError("explicit boolean is_adjusted is required")
    if type(source) is not str or not source or type(source_id) not in (str, type(None)):
        raise ValueError("source_name is required; source_id must be text when present")
    item.update({key: row.get(key) for key in BASIS})
    return item


def _index(series, side, differences):
    """{(symbol, day): validated row}; every problem is recorded, never skipped silently."""
    try:
        rows = _rows(series)
    except ValueError as exc:
        differences.append({"side": side, "error": str(exc)})
        return {}
    cleaned = {}
    for position, row in enumerate(rows):
        try:
            item = _clean(row)
            key = (item["symbol"], item["trade_date"])
            if key in cleaned:
                raise ValueError("duplicate symbol and trade_date")
            cleaned[key] = item
        except (ValueError, TypeError) as exc:
            differences.append({"side": side, "index": position, "error": str(exc)})
    return cleaned


def compare_price_series(existing, candidate) -> dict:
    differences: list[dict] = []
    old = _index(existing, "existing", differences)
    new = _index(candidate, "candidate", differences)
    basis = {side: sorted({json.dumps({key: row[key] for key in BASIS}, sort_keys=True) for row in rows.values()})
             for side, rows in (("existing", old), ("candidate", new))}
    if len({*basis["existing"], *basis["candidate"]}) != 1:
        differences.append({"field": "basis", **basis})

    different = 0
    for key in sorted(old.keys() & new.keys()):
        fields = [field for field in (*OHLC, "volume") if old[key][field] != new[key][field]]
        different += bool(fields)
        differences += [{"symbol": key[0], "trade_date": key[1].isoformat(), "field": field,
                         "existing": str(old[key]["raw"][field]), "candidate": str(new[key]["raw"][field])}
                        for field in fields]
    missing = sorted(new.keys() - old.keys())
    existing_only = sorted(old.keys() - new.keys())

    for symbol in sorted({symbol for symbol, _ in new}):
        stored = [day for s, day in old if s == symbol]
        offered = [day for s, day in new if s == symbol]
        if not any((symbol, day) in new for day in stored):
            differences.append({"symbol": symbol, "error": "no overlapping day anchors this symbol"})
            continue
        # Only later days may be appended; an earlier candidate-only day would be a correction.
        differences += [{"symbol": symbol, "trade_date": day.isoformat(),
                         "error": "candidate day is not after the latest stored day"}
                        for s, day in missing if s == symbol and day < max(stored)]
        differences += [{"symbol": symbol, "trade_date": day.isoformat(),
                         "error": "stored day is absent from the candidate range"}
                        for s, day in existing_only if s == symbol and min(offered) < day < max(offered)]

    return {
        "status": "unresolved" if differences else "compatible",
        "counts": {"existing": len(old), "candidate": len(new),
                   "matched": len(old.keys() & new.keys()) - different, "different": different,
                   "missing": len(missing), "existing_only": len(existing_only)},
        "missing": [{"symbol": symbol, "trade_date": day.isoformat()} for symbol, day in missing],
        "differences": differences,
    }


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _receipt(existing_bytes, candidate_bytes) -> dict:
    return {
        "existing_sha256": hashlib.sha256(existing_bytes).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        "comparison": compare_price_series(json.loads(existing_bytes), json.loads(candidate_bytes)),
    }


def build_receipt(existing_path, candidate_path) -> dict:
    return _receipt(Path(existing_path).read_bytes(), Path(candidate_path).read_bytes())


def verify_receipt(receipt, existing_path, candidate_path) -> None:
    if receipt != build_receipt(existing_path, candidate_path):
        raise ValueError("Receipt does not match the current input files")


async def append_missing(conn, existing_path, candidate_path, receipt) -> dict:
    """Append the receipt's missing days in one transaction, or change nothing."""
    existing_bytes, candidate_bytes = Path(existing_path).read_bytes(), Path(candidate_path).read_bytes()
    if receipt != _receipt(existing_bytes, candidate_bytes):
        raise ValueError('Receipt does not match the current input files')
    if receipt['comparison']['status'] != 'compatible':
        raise ValueError('Price basis is unresolved; nothing was written')
    # Parse the same bytes that were hashed, so a file replacement cannot bypass approval.
    old = _index(json.loads(existing_bytes), 'existing', [])
    new = _index(json.loads(candidate_bytes), 'candidate', [])
    missing = sorted((item["symbol"], _row_day(item)) for item in receipt["comparison"]["missing"])
    inserted = 0
    async with conn.transaction():
        # Legacy importers do not share our advisory lock; serialize their writes through verification and INSERT.
        await conn.execute('LOCK TABLE public.price_bars IN SHARE ROW EXCLUSIVE MODE')
        for symbol in sorted({symbol for symbol, _ in missing}):
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", f"price-append:{symbol}")
            companies = await conn.fetch("SELECT company_id FROM public.companies WHERE symbol=$1", symbol)
            if len(companies) != 1:
                raise ValueError(f"{symbol}: unknown or ambiguous company")
            company_id = companies[0]["company_id"]
            reviewed = {day: row for (s, day), row in old.items() if s == symbol}
            stored = await conn.fetch(
                """SELECT b.trade_date,b.open,b.high,b.low,b.close,b.volume,b.price_scale,b.is_adjusted,
                          s.name AS source_name, s.source_id::text AS source_id
                   FROM public.price_bars b
                   LEFT JOIN public.raw_payloads r ON r.payload_id=b.payload_id
                   LEFT JOIN public.ingestion_jobs j ON j.job_id=r.job_id
                   LEFT JOIN public.sources s ON s.source_id=j.source_id
                   WHERE b.company_id=$1 AND b.trade_date>=$2""", company_id, min(reviewed))
            fields = (*OHLC, "volume", "price_scale", "is_adjusted", "source_name")
            # From its first day on, the database must equal the reviewed export: no newer
            # stored day, no second basis, no changed price since the dry run.
            if (len(stored) != len(reviewed)
                    or any(row["trade_date"] not in reviewed
                           or any(row[f] != reviewed[row["trade_date"]][f] for f in fields)
                           or reviewed[row["trade_date"]]["source_id"] not in (None, row["source_id"])
                           for row in stored)):
                raise ValueError(f"{symbol}: database differs from the reviewed existing export")
            rows = [new[(symbol, day)] for s, day in missing if s == symbol]
            payload_id = await ingest.store_payload(
                conn, Path(candidate_path).resolve(), rows[0]["source_name"], "MARKET_DATA",
                "Reconciled daily OHLCV append", [row["raw"] for row in rows], len(rows), immutable=True)
            # Plain INSERT: a conflicting stored bar aborts the transaction instead of being rewritten.
            await conn.executemany(
                """INSERT INTO public.price_bars
                     (price_id, company_id, payload_id, trade_date, is_adjusted, price_scale,
                      open, high, low, close, volume)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                [(ingest.stable_id("price", symbol, row["trade_date"], row["is_adjusted"]), company_id,
                  payload_id, row["trade_date"], row["is_adjusted"], row["price_scale"],
                  *(row[field] for field in OHLC), row["volume"]) for row in rows])
            inserted += len(rows)
    return {"inserted": inserted, "symbols": sorted({symbol for symbol, _ in missing})}


def _apply_runtime(existing_path, candidate_path, receipt) -> dict:
    async def run():
        conn = await ingest.connect_database()
        try:
            return await append_missing(conn, existing_path, candidate_path, receipt)
        finally:
            await conn.close()
    try:
        return asyncio.run(run())
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:  # report the class, never a DSN
        raise RuntimeError(f"Database append failed and was rolled back: {type(exc).__name__}") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--existing", type=Path, required=True, help="export of the stored series")
    parser.add_argument("--candidate", type=Path, required=True, help="series offered for appending")
    parser.add_argument("--apply", action="store_true", help="append missing days (default: dry run)")
    parser.add_argument("--receipt", type=Path, help="saved dry-run output; required with --apply")
    args = parser.parse_args(argv)
    try:
        receipt = build_receipt(args.existing, args.candidate)
        compatible = receipt["comparison"]["status"] == "compatible"
        if not args.apply:
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0 if compatible else 1
        if not args.receipt:
            raise ValueError("--apply requires --receipt with the reviewed dry-run output")
        if _load(args.receipt) != receipt:
            raise ValueError("Receipt does not match the current input files")
        if not compatible:
            raise ValueError("Price basis is unresolved; nothing was written")
        print(json.dumps(_apply_runtime(args.existing, args.candidate, receipt), ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
