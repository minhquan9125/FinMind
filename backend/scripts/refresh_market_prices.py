"""Daily same-source price refresh: ENTRADE stock bars and KBS VNINDEX/HNXINDEX/UPCOMINDEX, append-only.

  python -m backend.scripts.refresh_market_prices            # dry run: capture, compare, plan
  python -m backend.scripts.refresh_market_prices --apply    # append the planned sessions

Only sessions that have closed are appended, and only days after the latest stored
one. Every stored bar in the compared window must still equal what the source
returns; any difference stops the run and nothing is written. Stored bars, source
approval and daily activity are never changed.

Stop the backend first: the KBS SDK allows one collector process at a time.
Each run keeps its raw captures and receipts under outputs/market-refresh/<time>/.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from backend.scripts import ingest_market_news_to_supabase as ingest
from backend.scripts.reconcile_market_prices import _clean, append_missing, build_receipt
from backend.src.core.config import get_settings
from backend.src.market_data.activity import VN
from backend.src.market_data.history import normalize_index_history
from backend.src.market_data.sdk import BatchSDKClient, CollectorLock

ROOT = ingest.PROJECT_ROOT
ENDPOINT = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
OHLC = ("open", "high", "low", "close")
BASIS = ("source_name", "source_id", "price_scale", "is_adjusted")
WINDOW_DAYS = 120  # stored days re-checked against the source on every run
# shortcut: a fixed clock, not the exchange calendar; a holiday simply returns no new bar.
# Upgrade to the trading calendar if early-close sessions must be appended the same afternoon.
SESSION_FINAL_AT = time(15, 30)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def closed_through(now: datetime) -> date:
    """Latest day whose daily bar is final; today's bar is provisional until after the close."""
    local = now.astimezone(VN)
    return local.date() if local.time() >= SESSION_FINAL_AT else local.date() - timedelta(days=1)


def entrade_rows(symbol, raw: bytes, basis: dict, stored_days: set, since: date, through: date, url: str) -> list:
    """Candidate rows on the stored basis. A bad row the database already left out stays out;
    a bad row for a stored or new day stops the run."""
    payload = json.loads(raw, parse_float=Decimal)
    arrays = [payload[key] for key in ("t", "o", "h", "l", "c", "v")]
    if not all(isinstance(a, list) for a in arrays) or len({len(a) for a in arrays}) != 1 or not arrays[0]:
        raise ValueError(f"{symbol}: source returned no usable series")
    by_day = {}
    for stamp, *values in zip(*arrays, strict=True):
        if type(stamp) is not int:
            raise ValueError(f"{symbol}: invalid source timestamp")
        day = datetime.fromtimestamp(stamp, VN).date()
        # Same rule as the original loader: the latest provider timestamp wins within one day.
        if since <= day <= through and (day not in by_day or stamp > by_day[day][0]):
            by_day[day] = (stamp, *values)
    digest, last_stored, rows = hashlib.sha256(raw).hexdigest(), max(stored_days), []
    for day, (stamp, o, h, l, c, v) in sorted(by_day.items()):
        try:
            if type(v) not in (int, Decimal) or Decimal(v) != Decimal(v).to_integral_value():
                raise ValueError("volume is not a whole number")
            prices = []
            for value in (o, h, l, c):
                if type(value) not in (int, str, Decimal):
                    raise ValueError("price is not a number")
                prices.append(format(Decimal(value).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP), ".4f"))
            row = {"symbol": symbol, "trade_date": day.isoformat(), **basis, **dict(zip(OHLC, prices, strict=True)),
                   "volume": int(v), "source_timestamp": stamp, "origin_url": url, "origin_response_sha256": digest}
            _clean(row)
            rows.append(row)
        except (ValueError, ArithmeticError) as exc:
            if day in stored_days or day > last_stored:
                raise ValueError(f"{symbol} {day}: {exc}") from None
    return rows


def plan_index(stored: list, offered: list, through: date, symbol: str = "VNINDEX", ambiguous=()) -> list:
    """Offered index bars after the latest stored day. Stored days must match the source exactly."""
    if not stored or {row["source_name"] for row in stored} != {"vnstock_kbs"}:
        raise ValueError(f"{symbol}: stored series is empty or not from vnstock_kbs")
    by_day = {bar["date"]: bar for bar in offered}
    overlap = 0
    for row in stored:
        bar = by_day.get(row["trade_date"].isoformat())
        if bar is None:
            continue
        if any(Decimal(bar[f]) != row[f] for f in OHLC) or bar["volume"] != row["volume"]:
            raise ValueError(f"{symbol} {row['trade_date']}: stored bar differs from the source")
        overlap += 1
    if not overlap:
        raise ValueError(f"{symbol}: no overlapping day anchors the source series")
    last = stored[-1]["trade_date"]
    # Append-only cannot fill a hole later, so an ambiguous source day stops the append before it.
    holes = [date.fromisoformat(day) for day in ambiguous if date.fromisoformat(day) > last]
    stop = min(holes + [through + timedelta(days=1)])
    return [bar for bar in offered if last < date.fromisoformat(bar["date"]) < stop]


def plan_index_or_block(stored: list, offered: list, through: date,
                        symbol: str = "VNINDEX", ambiguous=()) -> tuple[list, str | None]:
    """Daily index plan; a source that now disagrees with a stored day blocks that index only,
    so the stock bars and the other indexes of the same run are still appended."""
    try:
        return plan_index(stored, offered, through, symbol, ambiguous), None
    except ValueError as exc:
        return [], str(exc)


async def plan_daily_index(index_history, index: str, stored: list, through: date, folder: Path, *,
                           sleep=asyncio.sleep) -> tuple[list, dict]:
    """Fetch, keep and plan one index. Any failure blocks (or, SDK busy, defers) that index only.
    The returned info also carries the raw payload and its file under "_raw"/"_path" for the writer."""
    info = {"source": "vnstock_kbs", "new_dates": [], "blocked": None}
    try:
        raw = await fetch_index(index_history, index, sleep=sleep)
    except Exception as exc:  # never a DSN: the SDK and its parsing only
        if is_busy(exc):
            return [], {**info, "deferred": "sdk_busy"}
        return [], {**info, "blocked": f"{type(exc).__name__}: {exc}"}
    path = folder / f"{index}-raw.json"
    try:
        _save(path, raw)
        clean, ambiguous = drop_ambiguous_days(raw)
        bars = normalize_index_history(index, clean, max_age_days=BACKFILL_DAYS)["bars"]
        rows, blocked = plan_index_or_block(stored, bars, through, index, ambiguous)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        return [], {**info, "blocked": f"{type(exc).__name__}: {exc}"}
    return rows, {**info, "new_dates": [bar["date"] for bar in rows], "ambiguous_days_skipped": ambiguous,
                  "blocked": blocked, "_raw": raw, "_path": path}


BACKFILL_INDEXES = ("VNINDEX", "HNXINDEX", "UPCOMINDEX")
DAILY_INDEXES = BACKFILL_INDEXES


def is_busy(exc: BaseException) -> bool:
    """The shared SDK's BusyError, whichever import path raised it: the backend runs as `src.*`,
    this script imports `backend.src.*`, and the two are different classes."""
    return isinstance(exc, RuntimeError) and type(exc).__name__ == "BusyError" and hasattr(exc, "wait_seconds")


async def fetch_index(index_history, symbol: str, *, sleep=asyncio.sleep, attempts: int = 3) -> dict:
    """One SDK history call; waits out the shared quota spacing (BusyError) instead of failing the run."""
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(index_history, symbol)
        except RuntimeError as exc:
            if not is_busy(exc) or attempt == attempts - 1:
                raise
            await sleep(exc.wait_seconds + 1)
INDEX_META = {"VNINDEX": ("VN-Index", "HOSE"), "HNXINDEX": ("HNX-Index", "HNX"), "UPCOMINDEX": ("UPCOM-Index", "UPCOM")}
BACKFILL_DAYS = 400


def drop_ambiguous_days(raw: dict) -> tuple[dict, list]:
    """The source sometimes returns two different bars for one day; neither is guessed at."""
    days = [str(row.get("time", ""))[:10] for row in raw["rows"]]
    repeated = sorted({day for day in days if days.count(day) > 1})
    return {**raw, "rows": [row for row, day in zip(raw["rows"], days) if day not in repeated]}, repeated


def plan_index_backfill(symbol: str, stored: list, offered: list, through: date | None = None,
                        anchor: int = 20) -> dict:
    """Offered bars older than the first stored day, plus closed days (<= through) after the last one.

    Each edge is extended only when its `anchor` nearest stored days all agree with the source and at
    least one of them overlaps it. A stored day the source now reports differently is listed in
    `mismatched_days` and left untouched. An index with nothing stored is an explicit initial load.
    Holes inside the stored range are left alone."""
    offered = [bar for bar in offered if through is None or date.fromisoformat(bar["date"]) <= through]
    if not stored:
        return {"rows": list(offered), "initial_load": True, "matched_overlap": 0,
                "mismatched_days": [], "blocked_edges": []}
    if {row["source_name"] for row in stored} != {"vnstock_kbs"}:
        raise ValueError(f"{symbol}: stored series is not from vnstock_kbs")
    by_day = {bar["date"]: bar for bar in offered}
    matched, mismatched = 0, []
    for row in stored:
        bar = by_day.get(row["trade_date"].isoformat())
        if bar is None:
            continue
        if any(Decimal(bar[f]) != row[f] for f in OHLC) or bar["volume"] != row["volume"]:
            mismatched.append(row["trade_date"].isoformat())
        else:
            matched += 1
    if not matched:
        raise ValueError(f"{symbol}: no overlapping day anchors the source series")

    def anchored(edge):
        days = [row["trade_date"].isoformat() for row in edge]
        return not set(days) & set(mismatched) and any(day in by_day for day in days)

    first, last = stored[0]["trade_date"], stored[-1]["trade_date"]
    older = [bar for bar in offered if date.fromisoformat(bar["date"]) < first]
    newer = [bar for bar in offered if date.fromisoformat(bar["date"]) > last]
    blocked = []
    if older and not anchored(stored[:anchor]):
        blocked.append("before")
        older = []
    if newer and not anchored(stored[-anchor:]):
        blocked.append("after")
        newer = []
    if blocked and not older and not newer:
        raise ValueError(f"{symbol} {mismatched[0] if mismatched else ''}: stored bar differs from the source")
    return {"rows": sorted(older + newer, key=lambda bar: bar["date"]), "initial_load": False,
            "matched_overlap": matched, "mismatched_days": mismatched, "blocked_edges": blocked}


async def _stored_index_series(conn, symbol: str) -> list:
    return [dict(r) for r in await conn.fetch(
        """SELECT t.trade_date, t.open, t.high, t.low, t.close, t.volume, s.name AS source_name
           FROM public.market_index_bars t
           LEFT JOIN public.raw_payloads r USING (payload_id) LEFT JOIN public.ingestion_jobs j USING (job_id)
           LEFT JOIN public.sources s USING (source_id)
           WHERE t.index_symbol = $1 ORDER BY t.trade_date""", symbol)]


async def run_index_backfill(apply: bool, *, now: datetime | None = None, index_history=None) -> int:
    """Prepend older sessions of VNINDEX/HNXINDEX/UPCOMINDEX; all three in one transaction."""
    import asyncpg
    now = now or datetime.now(VN)
    folder = ROOT / "outputs/market-refresh" / (datetime.now(VN).strftime("%Y%m%d-%H%M%S-%f") + "-index-backfill")
    folder.mkdir(parents=True)
    report = {"started_at": now.isoformat(), "apply": apply, "committed": False, "indexes": {}}
    lock, client, conn = CollectorLock(ROOT / ".agent-state/market-live/collector.lock"), None, None
    try:
        if index_history is None:
            try:
                lock.acquire()
            except RuntimeError:
                raise RuntimeError("Backend dang chay va giu bo lay gia. Dung backend roi chay lai.") from None
            client = BatchSDKClient(ROOT, timeout=120)
            index_history = lambda symbol: client.history(symbol, days=BACKFILL_DAYS)
        conn = await asyncpg.connect(get_settings().database_url, timeout=10, command_timeout=60, statement_cache_size=0)
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            stored = {symbol: await _stored_index_series(conn, symbol) for symbol in BACKFILL_INDEXES}
        plans = {}
        for symbol in BACKFILL_INDEXES:
            raw = await asyncio.to_thread(index_history, symbol)
            path = folder / f"{symbol}-raw.json"
            _save(path, raw)
            clean, ambiguous = drop_ambiguous_days(raw)
            offered = normalize_index_history(symbol, clean, max_age_days=BACKFILL_DAYS)["bars"]
            try:
                plan = plan_index_backfill(symbol, stored[symbol], offered, through=closed_through(now))
            except ValueError as exc:
                # A source that disagrees with one stored index blocks that index only; nothing of it is written.
                report["indexes"][symbol] = {"stored_before": len(stored[symbol]), "blocked": str(exc),
                                             "ambiguous_days_skipped": ambiguous}
                continue
            plans[symbol] = (plan, raw, path)
            report["indexes"][symbol] = {"stored_before": len(stored[symbol]), "offered": len(offered),
                                         "ambiguous_days_skipped": ambiguous,
                                         "new_dates": [bar["date"] for bar in plan["rows"]],
                                         "initial_load": plan["initial_load"], "matched_overlap": plan["matched_overlap"],
                                         "mismatched_days": plan["mismatched_days"], "blocked_edges": plan["blocked_edges"],
                                         "total_after": len(stored[symbol]) + len(plan["rows"])}
        report["planned_rows"] = sum(len(plan["rows"]) for plan, _, _ in plans.values())
        if apply and report["planned_rows"]:
            async with conn.transaction():
                await conn.execute("SET LOCAL lock_timeout = '5s'")
                await conn.execute("LOCK TABLE public.market_index_bars IN SHARE ROW EXCLUSIVE MODE")
                for symbol, (plan, raw, path) in plans.items():
                    if not plan["rows"]:
                        continue
                    # Nothing changed since the read-only snapshot, or nothing is written.
                    if await _stored_index_series(conn, symbol) != stored[symbol]:
                        raise ValueError(f"{symbol}: stored series changed since it was read")
                    # Indicators run over the merged chain in date order, so a prepended row only sees older
                    # closes and a caught-up row sees the stored ones; stored rows keep their own values.
                    chain = [{"trade_date": r["trade_date"].isoformat(), "close": str(r["close"])} for r in stored[symbol]]
                    chain += [{"trade_date": bar["date"], "close": bar["close"]} for bar in plan["rows"]]
                    stats = {s["trade_date"]: s for s in _indicators(sorted(chain, key=lambda r: r["trade_date"]))}
                    payload_id = await ingest.store_payload(
                        conn, path, "vnstock_kbs", "MARKET_DATA", f"{symbol} history backfill in index points",
                        raw, len(raw["rows"]), immutable=True)
                    name, exchange = INDEX_META[symbol]
                    await conn.executemany(
                        """INSERT INTO public.market_index_bars (index_symbol, index_name, exchange, trade_date,
                             open, high, low, close, volume, payload_id, sma20, sma50, rsi14)
                           VALUES ($1, $2, $3, $4, $5::numeric, $6::numeric, $7::numeric, $8::numeric, $9, $10,
                                   $11::numeric, $12::numeric, $13::numeric)""",
                        [(symbol, name, exchange, date.fromisoformat(bar["date"]), *(bar[f] for f in OHLC), bar["volume"],
                          payload_id, *(stats[bar["date"]][k] for k in ("sma20", "sma50", "rsi14"))) for bar in plan["rows"]])
            report["committed"] = True
    except Exception as exc:  # the report carries the reason, never a DSN
        report["failure_class"] = type(exc).__name__
        if isinstance(exc, (ValueError, RuntimeError)):
            report["failure"] = str(exc)
    finally:
        if conn is not None:
            await conn.close()
        if client is not None:
            await asyncio.to_thread(client.close)
        lock.close()
        _save(folder / "report.json", report)

    blocked = [symbol for symbol, item in report["indexes"].items() if "blocked" in item]
    for symbol, item in report["indexes"].items():
        if symbol in blocked:
            reason = item["blocked"].encode("ascii", "backslashreplace").decode()
            print(f"{symbol}: BI CHAN, khong ghi: {reason}")
            continue
        print(f"{symbol}: dang co {item['stored_before']}, them {len(item['new_dates'])}, sau khi them {item['total_after']}"
              + (" (nap lan dau)" if item["initial_load"] else "")
              + (f"; lech nguon, khong sua: {', '.join(item['mismatched_days'])}" if item["mismatched_days"] else "")
              + (f"; khong noi them phia: {', '.join(item['blocked_edges'])}" if item["blocked_edges"] else ""))
    if "failure_class" in report:
        reason = report.get("failure", "xem report.json").encode("ascii", "backslashreplace").decode()
        print(f"LOI ({report['failure_class']}): {reason}", file=sys.stderr)
    elif report["committed"]:
        print(f"Da ghi {report['planned_rows']} dong.")
    elif report.get("planned_rows"):
        print(f"Xem truoc: {report['planned_rows']} dong se duoc ghi. Chay lai voi --apply de ghi.")
    else:
        print("Khong co phien cu nao can bu.")
    print(f"Bien ban: {folder / 'report.json'}")
    return 1 if "failure_class" in report or blocked else 0


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")


def _fetch_entrade(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "FinMind-Price-Reconciliation/1.0"})
    with build_opener(_NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("source response too large")
    return raw


def _indicators(rows: list) -> list:
    sys.dont_write_bytecode = True  # the crawler folder stays free of __pycache__
    if str(ROOT / "data_pipeline/ScrapersOHLCV") not in sys.path:
        sys.path.append(str(ROOT / "data_pipeline/ScrapersOHLCV"))
    from ohlcv.history.vnstock import indicators
    return indicators(rows)


async def _stored_stocks(conn, symbols) -> dict:
    records = await conn.fetch(
        """SELECT c.symbol, b.trade_date, b.open, b.high, b.low, b.close, b.volume, b.price_scale, b.is_adjusted,
                  s.name AS source_name, s.source_id::text AS source_id
           FROM public.price_bars b JOIN public.companies c USING (company_id)
           LEFT JOIN public.raw_payloads r USING (payload_id) LEFT JOIN public.ingestion_jobs j USING (job_id)
           LEFT JOIN public.sources s USING (source_id)
           WHERE c.symbol = ANY($1::text[]) ORDER BY c.symbol, b.trade_date""", symbols)
    stocks = {symbol: [] for symbol in symbols}
    for record in records:
        stocks[record["symbol"]].append(dict(record))
    return stocks



async def _write(conn, plans: list, index_plans: dict) -> None:
    await conn.execute("SET LOCAL lock_timeout = '5s'")
    await conn.execute("LOCK TABLE public.price_bars, public.market_index_bars IN SHARE ROW EXCLUSIVE MODE")
    for plan in plans:
        if not plan["missing"]:
            continue
        await append_missing(conn, plan["existing"], plan["candidate"], plan["receipt"])
        # Wilder RSI carries the whole history, so indicators come from every stored close.
        closes = await conn.fetch(
            """SELECT b.price_id, b.trade_date, b.close FROM public.price_bars b
               JOIN public.companies c USING (company_id) WHERE c.symbol = $1 ORDER BY b.trade_date""", plan["symbol"])
        stats = _indicators([{"trade_date": r["trade_date"].isoformat(), "close": str(r["close"])} for r in closes])
        await conn.executemany(
            """INSERT INTO public.price_indicators (price_id, sma20, sma50, rsi14)
               VALUES ($1, $2::numeric, $3::numeric, $4::numeric)""",
            [(r["price_id"], s["sma20"], s["sma50"], s["rsi14"]) for r, s in zip(closes, stats, strict=True)
             if s["trade_date"] in plan["missing"]])
    for symbol, (index_new, index_raw, index_path) in index_plans.items():
        if not index_new:
            continue
        stored = await _stored_index_series(conn, symbol)
        closes = [{"trade_date": r["trade_date"].isoformat(), "close": str(r["close"])} for r in stored]
        closes += [{"trade_date": bar["date"], "close": bar["close"]} for bar in index_new]
        stats = {s["trade_date"]: s for s in _indicators(closes)}
        payload_id = await ingest.store_payload(
            conn, index_path, "vnstock_kbs", "MARKET_DATA", f"{symbol} history in index points; provisional observations",
            index_raw, len(index_raw["rows"]), immutable=True)
        name, exchange = INDEX_META[symbol]
        await conn.executemany(
            """INSERT INTO public.market_index_bars (index_symbol, index_name, exchange, trade_date,
                 open, high, low, close, volume, payload_id, sma20, sma50, rsi14)
               VALUES ($1, $2, $3, $4, $5::numeric, $6::numeric, $7::numeric, $8::numeric, $9, $10,
                       $11::numeric, $12::numeric, $13::numeric)""",
            [(symbol, name, exchange, date.fromisoformat(bar["date"]), *(bar[f] for f in OHLC), bar["volume"], payload_id,
              *(stats[bar["date"]][k] for k in ("sma20", "sma50", "rsi14"))) for bar in index_new])


async def run(apply: bool, *, now: datetime | None = None, fetch=_fetch_entrade, index_history=None, symbols=None,
              on_report=None) -> int:
    import asyncpg
    now = now or datetime.now(VN)
    through = closed_through(now)
    symbols = sorted(ingest.PROJECT_SYMBOLS if symbols is None else set(symbols))
    if not 1<=len(symbols)<=100 or any(type(s) is not str or len(s)!=3 or not s.isascii() or not s.isalpha() or not s.isupper() for s in symbols):
        raise ValueError('Invalid refresh stock universe')
    folder = ROOT / "outputs/market-refresh" / now.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    report = {"started_at": now.isoformat(), "apply": apply, "closed_through": through.isoformat(),
              "committed": False, "stocks": {}, "indexes": {}}
    lock, client, conn = CollectorLock(ROOT / ".agent-state/market-live/collector.lock"), None, None
    try:
        if index_history is None:
            try:
                lock.acquire()
            except RuntimeError:
                raise RuntimeError("Backend dang chay va giu bo lay gia. Dung backend roi chay lai.") from None
            client = BatchSDKClient(ROOT, timeout=120)  # a cold SDK start alone takes about 30 seconds
            index_history = client.history
        conn = await asyncpg.connect(get_settings().database_url, timeout=10, command_timeout=60, statement_cache_size=0)
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            stocks = await _stored_stocks(conn, symbols)
            index_stored = {index: await _stored_index_series(conn, index) for index in DAILY_INDEXES}

        plans = []
        for symbol in symbols:
            stored = stocks[symbol]
            if not stored:
                raise ValueError(f"{symbol}: no stored bars to anchor an append")
            since = stored[-1]["trade_date"] - timedelta(days=WINDOW_DAYS)
            window = [row for row in stored if row["trade_date"] >= since]
            basis = {json.dumps({k: row[k] for k in BASIS}, sort_keys=True) for row in window}
            if len(basis) != 1:
                raise ValueError(f"{symbol}: stored window mixes sources or price bases")
            basis = json.loads(basis.pop())
            if (basis["source_name"], basis["price_scale"], basis["is_adjusted"]) != ("ENTRADE", 1000, False):
                raise ValueError(f"{symbol}: stored bars are not unadjusted ENTRADE thousand-VND bars")
            url = ENDPOINT + "?" + urlencode({
                "symbol": symbol, "from": int(datetime.combine(since, time(), VN).timestamp()),
                "to": int(now.timestamp()), "resolution": "1D"})
            raw = await asyncio.to_thread(fetch, url)
            (folder / f"{symbol}-entrade-raw.json").write_bytes(raw)
            rows = entrade_rows(symbol, raw, basis, {row["trade_date"] for row in window}, since, through, url)
            existing, candidate = folder / f"{symbol}-existing.json", folder / f"{symbol}-candidate.json"
            _save(existing, [{**row, "trade_date": row["trade_date"].isoformat(),
                              **{f: str(row[f]) for f in OHLC}} for row in window])
            _save(candidate, rows)
            receipt = build_receipt(existing, candidate)
            _save(folder / f"{symbol}-receipt.json", receipt)
            comparison = receipt["comparison"]
            missing = [item["trade_date"] for item in comparison["missing"]]
            report["stocks"][symbol] = {"status": comparison["status"], "counts": comparison["counts"],
                                        "new_dates": missing, "differences": comparison["differences"][:4]}
            if comparison["status"] != "compatible":
                raise ValueError(f"{symbol}: stored bars differ from the source; nothing was written")
            plans.append({"symbol": symbol, "existing": existing, "candidate": candidate,
                          "receipt": receipt, "missing": set(missing)})
            await asyncio.sleep(1)  # stay polite to the public endpoint

        index_plans = {}
        for index in DAILY_INDEXES:
            index_new, info = await plan_daily_index(index_history, index, index_stored[index], through, folder)
            raw, path = info.pop("_raw", None), info.pop("_path", None)
            if index_new:
                index_plans[index] = (index_new, raw, path)
            report["indexes"][index] = info

        planned = sum(len(plan["missing"]) for plan in plans) + sum(len(p[0]) for p in index_plans.values())
        report["planned_rows"] = planned
        if apply and planned:
            async with conn.transaction():
                await _write(conn, plans, index_plans)
            report["committed"] = True
    except Exception as exc:  # the report carries the reason, never a DSN
        report["failure_class"] = type(exc).__name__
        if isinstance(exc, (ValueError, RuntimeError)):
            report["failure"] = str(exc)
    finally:
        if conn is not None:
            await conn.close()
        if client is not None:
            await asyncio.to_thread(client.close)
        lock.close()
        _save(folder / "report.json", report)
        if on_report is not None:
            on_report(report)

    for symbol, item in report["stocks"].items():
        print(f"{symbol}: {item['status']}, phien moi: {', '.join(item['new_dates']) or 'khong co'}")
    for index, item in report["indexes"].items():
        print(f"{index}: phien moi: {', '.join(item['new_dates']) or 'khong co'}")
        if item.get("blocked"):
            reason = item["blocked"].encode("ascii", "backslashreplace").decode()
            print(f"CANH BAO: {index} khong noi them vi lech nguon: {reason}")
    if "failure_class" in report:
        # ASCII only: this also prints inside the backend, whose console may not encode Vietnamese.
        reason = report.get("failure", "xem report.json").encode("ascii", "backslashreplace").decode()
        print(f"LOI ({report['failure_class']}): {reason}", file=sys.stderr)
    elif report["committed"]:
        print(f"Da ghi {report['planned_rows']} dong.")
    elif report["planned_rows"]:
        print(f"Xem truoc: {report['planned_rows']} dong se duoc ghi. Chay lai voi --apply de ghi.")
    else:
        print(f"Khong co phien moi da chot (tinh den {through}).")
    print(f"Bien ban: {folder / 'report.json'}")
    # A deferred index makes the run report not-ok, so the backend retries it in 30 minutes.
    deferred = [index for index, item in report.get("indexes", {}).items() if item.get("deferred")]
    if deferred:
        print(f"HOAN: {', '.join(deferred)} chua lay duoc vi SDK dang ban; lan chay sau se lay.")
    return 1 if "failure_class" in report or deferred else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="append the planned sessions (default: dry run)")
    parser.add_argument("--backfill-index", action="store_true",
                        help="prepend older VNINDEX/HNXINDEX/UPCOMINDEX sessions instead of the daily refresh")
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # a legacy Windows console must not crash the report
    args = parser.parse_args(argv)
    return asyncio.run(run_index_backfill(args.apply) if args.backfill_index else run(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
