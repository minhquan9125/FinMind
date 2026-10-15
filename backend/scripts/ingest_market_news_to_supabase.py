"""Load OHLCV bars and news from data_pipeline into Supabase.

Reads
  data_pipeline/ScrapersOHLCV/data/stocks/<SYMBOL>/data.json   -> public.price_bars + price_indicators
                                                                   (chi so VNINDEX/VN30/... -> market_index_bars)
  data_pipeline/ScrapersOHLCV/data/stocks/<SYMBOL>/live.json   -> public.market_live_snapshots
  data_pipeline/scrapers/data/**/<date>.json                    -> public.news_articles

Each source file is also kept as one row in raw_payloads, with an ingestion_jobs
row, so every price bar / article can be traced back to its file.

Dry-run by default (no database connection). Pass --apply to write. Run
supabase/migrations/20261008000000_add_news_articles.sql and 20261008000100_add_market_extras.sql first.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OHLCV_DIR = PROJECT_ROOT / "data_pipeline" / "ScrapersOHLCV" / "data" / "stocks"
NEWS_DIR = PROJECT_ROOT / "data_pipeline" / "scrapers" / "data"
# Same namespace and id recipe as ingest_to_supabase.py so rows line up.
NAMESPACE = uuid.UUID("b77dbd7f-5d89-479d-90a3-421e5f0981ea")
# vnstock/KBS quotes prices in thousand VND (57.3 = 57,300 VND); same price_scale as ingest_to_supabase.py.
PRICE_SCALE = 1000
# False: every distinct file content gets its own job/payload row (history, used by backfill).
# True: one job/payload row per file path, overwritten in place (used by the crawler sink).
STABLE_PAYLOAD_IDS = False
INDEX_SYMBOLS = {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX", "HNX", "UPCOM"}


def stable_id(kind: str, *parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, ":".join((kind, *(str(p) for p in parts))))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value.replace("'", '"'))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def decimal_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


# ---------------------------------------------------------------- OHLCV

def build_price_plan(path: Path, data: dict[str, Any], live: dict[str, Any] | None = None) -> dict[str, Any]:
    """Turn one stocks/<SYMBOL>/data.json payload into a write plan (no I/O)."""
    symbol = path.parent.name.upper()
    indicators = {
        str(i.get("trade_date"))[:10]: (decimal_or_none(i.get("sma20")), decimal_or_none(i.get("sma50")), decimal_or_none(i.get("rsi14")))
        for i in data.get("indicators") or [] if isinstance(i, dict)
    }
    bars = []
    for bar in data.get("bars") or []:
        try:
            trade_date = date.fromisoformat(str(bar["trade_date"])[:10])
            volume = int(bar["volume"]) if bar.get("volume") is not None else None
        except (KeyError, ValueError, TypeError):
            continue
        bars.append((trade_date, decimal_or_none(bar.get("open")), decimal_or_none(bar.get("high")),
                     decimal_or_none(bar.get("low")), decimal_or_none(bar.get("close")), volume,
                     bar.get("exchange")))
    prov = data.get("provenance") or {}
    return {
        "symbol": symbol, "path": path, "bars": bars,
        "source": f"{prov.get('library', 'vnstock')}_{prov.get('provider', 'kbs')}".lower(),
        "name": prov.get("name") or symbol,
        "exchange": next((b[6] for b in bars if b[6]), None),
        "payload": data.get("bars") or [],
        "is_index": symbol in INDEX_SYMBOLS or prov.get("instrument_type") == "index",
        "indicators": indicators, "live": live, "live_path": path.parent / "live.json",
    }


def collect_prices(symbols: set[str] | None) -> list[dict[str, Any]]:
    """One plan per data.json; stocks go to price_bars, indices to market_index_bars."""
    plans = []
    for path in sorted(OHLCV_DIR.glob("*/data.json")):
        if symbols and path.parent.name.upper() not in symbols:
            continue
        live_path = path.parent / "live.json"
        plans.append(build_price_plan(path, load_json(path), load_json(live_path) if live_path.exists() else None))
    return plans


# ----------------------------------------------------------------- news

def merge_file_articles(path: Path, data: Any, merged: dict[tuple[str, str], dict[str, Any]],
                        symbols: set[str] | None = None) -> dict[str, Any] | None:
    """Add one news file's articles into `merged` (keyed by source+url); return its file plan."""
    articles = data.get("articles") if isinstance(data, dict) else None
    if not isinstance(articles, list):
        return None
    file_source = str(data.get("source") or path.parent.name)
    kept = 0
    for art in articles:
        if not isinstance(art, dict) or not art.get("url") or not art.get("title"):
            continue
        source = str(art.get("source") or file_source)
        art_symbols = {str(s).upper() for s in as_list(art.get("matched_symbols")) + as_list(art.get("symbols"))}
        if symbols and not (art_symbols & symbols):
            continue
        key = (source, str(art["url"]))
        kept += 1
        row = merged.get(key)
        if row is None:
            merged[key] = {"key": key, "art": art, "symbols": art_symbols, "path": path}
        else:
            row["symbols"] |= art_symbols
    return {"path": path, "source": file_source, "count": kept, "payload": articles}


def build_news_plan(path: Path, data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    plan = merge_file_articles(path, data, merged)
    return ([plan] if plan else []), list(merged.values())


def collect_news(symbols: set[str] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (per-file plans, merged unique articles keyed by source+url)."""
    files = []
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(NEWS_DIR.rglob("*.json")):
        plan = merge_file_articles(path, load_json(path), merged, symbols)
        if plan:
            files.append(plan)
    return files, list(merged.values())


# -------------------------------------------------------------- database

async def ensure_source(conn: Any, name: str, source_type: str, note: str) -> uuid.UUID:
    source_id = stable_id("source", name)
    await conn.execute(
        """INSERT INTO public.sources (source_id, name, source_type, approval_status, scope_note, is_enabled)
           VALUES ($1, $2, $3, 'PENDING', $4, false) ON CONFLICT (source_id) DO NOTHING""",
        source_id, name, source_type, note,
    )
    return source_id


async def store_payload(conn: Any, path: Path, source: str, source_type: str, note: str,
                        payload: Any, count: int) -> uuid.UUID:
    raw = canonical_json(payload)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    version = "latest" if STABLE_PAYLOAD_IDS else digest
    job_id = stable_id("job", rel(path), version)
    payload_id = stable_id("payload", rel(path), version)
    source_id = await ensure_source(conn, source, source_type, note)
    now = datetime.now(timezone.utc)
    await conn.execute(
        """INSERT INTO public.ingestion_jobs
             (job_id, source_id, trigger_type, status, schema_version, started_at, finished_at,
              records_ok, records_quarantined)
           VALUES ($1, $2, 'BATCH', 'SUCCEEDED', '1.0', $3, $3, $4, 0)
           ON CONFLICT (job_id) DO UPDATE SET status = EXCLUDED.status,
             finished_at = EXCLUDED.finished_at, records_ok = EXCLUDED.records_ok""",
        job_id, source_id, now, count,
    )
    await conn.execute(
        """INSERT INTO public.raw_payloads (payload_id, job_id, source_uri, sha256, payload, stored_at)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6)
           ON CONFLICT (payload_id) DO UPDATE SET source_uri = EXCLUDED.source_uri,
             payload = EXCLUDED.payload, stored_at = EXCLUDED.stored_at""",
        payload_id, job_id, rel(path), digest, raw, now,
    )
    return payload_id


async def apply_prices(conn: Any, plans: list[dict[str, Any]], overwrite: bool) -> None:
    conflict = (
        "DO UPDATE SET payload_id=EXCLUDED.payload_id, open=EXCLUDED.open, high=EXCLUDED.high, "
        "low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume, price_scale=EXCLUDED.price_scale"
        if overwrite else "DO NOTHING"
    )
    for plan in plans:
        if plan["is_index"]:
            await apply_index(conn, plan)
            continue
        async with conn.transaction():
            symbol = plan["symbol"]
            company_id = await conn.fetchval(
                "SELECT company_id FROM public.companies WHERE symbol = $1 ORDER BY company_id LIMIT 1", symbol)
            if company_id is None:
                company_id = stable_id("company", symbol)
                await conn.execute(
                    """INSERT INTO public.companies (company_id, symbol, company_name, industry_type, sector, exchange, is_active)
                       VALUES ($1, $2, $3, $4, NULL, $5, true) ON CONFLICT (company_id) DO NOTHING""",
                    company_id, symbol, plan["name"], "INDEX" if plan["is_index"] else None, plan["exchange"],
                )
            payload_id = await store_payload(
                conn, plan["path"], plan["source"], "MARKET_DATA", "Daily OHLCV bars (ScrapersOHLCV)",
                plan["payload"], len(plan["bars"]))
            rows = [
                (stable_id("price", symbol, d, False), company_id, payload_id, d, False, PRICE_SCALE,
                 o, h, l, c, v)
                for d, o, h, l, c, v, _ in plan["bars"]
            ]
            if rows:
                await conn.executemany(
                    f"""INSERT INTO public.price_bars
                          (price_id, company_id, payload_id, trade_date, is_adjusted, price_scale,
                           open, high, low, close, volume)
                        VALUES ($1,$2,$3,$4,$5,$6,$7::numeric,$8::numeric,$9::numeric,$10::numeric,$11)
                        ON CONFLICT (price_id) {conflict}""", rows)
                inds = [(r[0], *plan["indicators"][str(r[3])]) for r in rows if str(r[3]) in plan["indicators"]]
                if inds:
                    await conn.executemany(
                        """INSERT INTO public.price_indicators (price_id, sma20, sma50, rsi14)
                           VALUES ($1, $2::numeric, $3::numeric, $4::numeric)
                           ON CONFLICT (price_id) DO UPDATE SET sma20=EXCLUDED.sma20, sma50=EXCLUDED.sma50,
                             rsi14=EXCLUDED.rsi14, updated_at=now()""", inds)
            await apply_live(conn, plan)
        print(f"  price_bars {symbol}: {len(plan['bars'])} (+chi bao, live: {'co' if plan['live'] else 'khong'})")


async def apply_live(conn: Any, plan: dict[str, Any]) -> None:
    if not plan["live"]:
        return
    payload_id = await store_payload(
        conn, plan["live_path"], plan["source"], "MARKET_DATA", "Live quote snapshot (ScrapersOHLCV)",
        plan["live"], len(plan["live"].get("rows") or []))
    await conn.execute(
        """INSERT INTO public.market_live_snapshots (symbol, instrument_type, fetched_at, data, payload_id)
           VALUES ($1, $2, $3, $4::jsonb, $5)
           ON CONFLICT (symbol) DO UPDATE SET instrument_type=EXCLUDED.instrument_type,
             fetched_at=EXCLUDED.fetched_at, data=EXCLUDED.data, payload_id=EXCLUDED.payload_id, updated_at=now()""",
        plan["symbol"], "index" if plan["is_index"] else "stock", parse_dt(plan["live"].get("fetched_at")),
        canonical_json(plan["live"]), payload_id)


async def apply_index(conn: Any, plan: dict[str, Any]) -> None:
    async with conn.transaction():
        payload_id = await store_payload(
            conn, plan["path"], plan["source"], "MARKET_DATA", "Index daily bars (ScrapersOHLCV)",
            plan["payload"], len(plan["bars"]))
        rows = [
            (plan["symbol"], plan["name"], plan["exchange"], d, o, h, l, c, v, *plan["indicators"].get(str(d), (None, None, None)), payload_id)
            for d, o, h, l, c, v, _ in plan["bars"]
        ]
        if rows:
            await conn.executemany(
                """INSERT INTO public.market_index_bars
                     (index_symbol, index_name, exchange, trade_date, open, high, low, close, volume,
                      sma20, sma50, rsi14, payload_id)
                   VALUES ($1,$2,$3,$4,$5::numeric,$6::numeric,$7::numeric,$8::numeric,$9,$10::numeric,$11::numeric,$12::numeric,$13)
                   ON CONFLICT (index_symbol, trade_date) DO UPDATE SET index_name=EXCLUDED.index_name,
                     open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                     volume=EXCLUDED.volume, sma20=EXCLUDED.sma20, sma50=EXCLUDED.sma50,
                     rsi14=EXCLUDED.rsi14, payload_id=EXCLUDED.payload_id""", rows)
        await apply_live(conn, plan)
    print(f"  market_index_bars {plan['symbol']}: {len(plan['bars'])} (live: {'co' if plan['live'] else 'khong'})")


async def apply_news(conn: Any, files: list[dict[str, Any]], articles: list[dict[str, Any]]) -> None:
    payload_by_file: dict[Path, uuid.UUID] = {}
    async with conn.transaction():
        for f in files:
            if f["count"]:
                payload_by_file[f["path"]] = await store_payload(
                    conn, f["path"], f["source"], "NEWS", "News articles (scrapers)", f["payload"], f["count"])
        rows = []
        for item in articles:
            art = item["art"]
            source, url = item["key"]
            rows.append((
                stable_id("news", source, url), source, art.get("id"), url, art["title"],
                art.get("description"), art.get("content"), parse_dt(art.get("published_at")),
                parse_dt(art.get("crawled_at")), sorted(item["symbols"]),
                json.dumps(as_list(art.get("attachments")), ensure_ascii=False),
                art.get("marker"),
                json.dumps(art["cross_check"], ensure_ascii=False) if isinstance(art.get("cross_check"), dict) else None,
                payload_by_file.get(item["path"]),
            ))
        await conn.executemany(
            """INSERT INTO public.news_articles
                 (article_id, source, external_id, url, title, description, content, published_at,
                  crawled_at, symbols, attachments, marker, cross_check, payload_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13::jsonb,$14)
               ON CONFLICT (article_id) DO UPDATE SET title=EXCLUDED.title, description=EXCLUDED.description,
                 content=EXCLUDED.content, published_at=EXCLUDED.published_at, symbols=EXCLUDED.symbols,
                 attachments=EXCLUDED.attachments, marker=EXCLUDED.marker, cross_check=EXCLUDED.cross_check,
                 payload_id=EXCLUDED.payload_id""", rows)
    print(f"  news_articles: {len(articles)}")


async def run(args: argparse.Namespace) -> int:
    symbols = {s.upper() for s in args.symbol} or None
    do_prices, do_news = args.only in (None, "prices"), args.only in (None, "news")
    price_plans = collect_prices(symbols) if do_prices else []
    news_files, articles = collect_news(symbols) if do_news else ([], [])

    print("Plan:")
    for p in price_plans:
        table = "market_index_bars" if p["is_index"] else "price_bars"
        print(f"  {table:<17} {p['symbol']:<8} {len(p['bars']):>4} bars, {len(p['indicators']):>3} chi bao, live: {'co' if p['live'] else 'khong'}")
    if do_news:
        print(f"  news_articles: {len(articles)} bai duy nhat tu {sum(1 for f in news_files if f['count'])} file")

    if not args.apply:
        print("Dry run: khong ket noi database, khong ghi gi. Them --apply de nap that.")
        return 0

    import asyncpg
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL chua duoc dat trong .env")
    conn = await asyncpg.connect(url, ssl="require" if "supabase" in url else None, statement_cache_size=0)
    try:
        needed = (["news_articles"] if do_news else []) + (
            ["price_indicators", "market_index_bars", "market_live_snapshots"] if do_prices else [])
        for table in needed:
            if not await conn.fetchval("SELECT to_regclass($1)", f"public.{table}"):
                raise RuntimeError(f"Chua co bang {table}. Chay cac file trong supabase/migrations/2026100800*.sql truoc.")
        print("Applying:")
        if do_prices:
            await apply_prices(conn, price_plans, overwrite=not args.no_overwrite)
        if do_news:
            await apply_news(conn, news_files, articles)
    finally:
        await conn.close()
    print("Xong.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="ghi that vao database (mac dinh chi chay thu)")
    parser.add_argument("--only", choices=["prices", "news"], help="chi nap gia hoac chi nap tin")
    parser.add_argument("--symbol", nargs="*", default=[], help="gioi han theo ma, vd: --symbol VCB FPT")
    parser.add_argument("--no-overwrite", action="store_true", help="khong ghi de nen gia da ton tai")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except (ValueError, RuntimeError) as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
