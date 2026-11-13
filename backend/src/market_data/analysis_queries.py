"""Read stored prices, daily activity and VNINDEX for the price/flow calculator.

One read-only repeatable-read transaction, parameterized and bounded to the 21
latest stock sessions. Nothing here calls a provider or refreshes data.
"""
import asyncio
from datetime import date, datetime
import re

from .activity import VN
from .analysis import analyze_series
from .trend import BENCHMARK, MAX_SESSIONS, analyze_trend

SESSIONS = 21
PROVENANCE = """LEFT JOIN public.raw_payloads r ON r.payload_id = t.payload_id
    LEFT JOIN public.ingestion_jobs j ON j.job_id = r.job_id
    LEFT JOIN public.sources s ON s.source_id = j.source_id"""
SOURCE = "s.source_id::text AS source_id, s.name AS source_name, s.approval_status"


async def get_stored_bars(pool, symbol, limit=250) -> dict | None:
    """Chart payload from the stored bars the analysis reads, so both show the same sessions.

    None when the symbol has no stored bars or they cannot be plotted as one series.
    """
    if type(symbol) is not str or not re.fullmatch("[A-Z]{3}", symbol):
        return None
    async with asyncio.timeout(5):
        async with pool.acquire() as conn:
            companies = await conn.fetch("SELECT company_id FROM public.companies WHERE symbol = $1", symbol)
            if len(companies) != 1:
                return None
            rows = await conn.fetch(
                f"""SELECT t.trade_date, t.open, t.high, t.low, t.close, t.volume, t.price_scale,
                           t.is_adjusted, s.name AS source_name, r.stored_at
                    FROM public.price_bars t {PROVENANCE}
                    WHERE t.company_id = $1 ORDER BY t.trade_date DESC LIMIT $2""",
                companies[0]["company_id"], limit)
    rows = sorted(rows, key=lambda row: row["trade_date"])
    # The chart plots thousand VND. Another scale, or two rows on one day, is not guessed at.
    if (not rows or len({row["trade_date"] for row in rows}) != len(rows)
            or any(row["price_scale"] != 1000 for row in rows)):
        return None
    bars = [{"date": row["trade_date"].isoformat(),
             **{field: format(row[field].normalize(), "f") for field in ("open", "high", "low", "close")},
             "volume": row["volume"], "status": "closed", "quality": "complete",
             "price_basis": "adjusted" if row["is_adjusted"] else "unadjusted",
             "volume_basis": "unknown", "source": row["source_name"]} for row in rows]
    stored_at = rows[-1].get("stored_at")
    return {"symbol": symbol, "interval": "1D", "source": bars[-1]["source"],
            "fetched_at": stored_at.isoformat() if stored_at else None,
            "price_unit": "thousand_vnd", "bars": bars}


async def get_price_trend(pool, symbol, as_of=None) -> dict:
    """Trend labels from up to 260 stored sessions <= as_of, read in one read-only transaction.
    ValueError: bad request or inconsistent data. LookupError: no stored prices."""
    today = datetime.now(VN).date()
    as_of = today if as_of is None else as_of
    if type(symbol) is not str or not re.fullmatch("[A-Z]{3}", symbol):
        raise ValueError("Mã cổ phiếu không hợp lệ.")
    if type(as_of) is not date or as_of > today:
        raise ValueError("Ngày phân tích không hợp lệ hoặc ở tương lai.")
    async with asyncio.timeout(10):
        async with pool.acquire() as conn, conn.transaction(readonly=True, isolation="repeatable_read"):
            companies = await conn.fetch("SELECT company_id, exchange FROM public.companies WHERE symbol = $1", symbol)
            if not companies:
                raise LookupError(symbol)
            if len(companies) > 1:
                raise RuntimeError("Ambiguous company mapping")
            company_id, exchange = companies[0]["company_id"], companies[0]["exchange"]
            prices = await conn.fetch(
                f"""SELECT t.price_id::text AS price_id, t.trade_date, t.open, t.high, t.low, t.close, t.volume,
                       t.price_scale, t.is_adjusted, t.payload_id::text AS payload_id, {SOURCE}
                    FROM public.price_bars t {PROVENANCE}
                    WHERE t.company_id = $1 AND t.trade_date <= $2
                    ORDER BY t.trade_date DESC LIMIT $3""", company_id, as_of, MAX_SESSIONS)
            if not prices:
                raise LookupError(symbol)
            days = sorted({row["trade_date"] for row in prices})
            rsi14 = await conn.fetchval(
                """SELECT i.rsi14 FROM public.price_indicators i JOIN public.price_bars b USING (price_id)
                   WHERE b.company_id = $1 AND b.trade_date = $2""", company_id, days[-1])
            index = await conn.fetch(
                """SELECT trade_date, close FROM public.market_index_bars
                   WHERE index_symbol = $1 AND trade_date = ANY($2::date[])""", BENCHMARK.get(exchange), days)
    return analyze_trend([dict(row) for row in prices], [dict(row) for row in index], exchange=exchange, rsi14=rsi14)


async def get_price_analysis(pool, symbol, as_of=None) -> dict:
    """ValueError: bad request. LookupError: no stored data. RuntimeError: stored data unusable."""
    today = datetime.now(VN).date()
    as_of = today if as_of is None else as_of
    if type(symbol) is not str or not re.fullmatch("[A-Z]{3}", symbol):
        raise ValueError("Mã cổ phiếu không hợp lệ.")
    if type(as_of) is not date or as_of > today:
        raise ValueError("Ngày phân tích không hợp lệ hoặc ở tương lai.")
    async with asyncio.timeout(15):
        async with pool.acquire() as conn, conn.transaction(readonly=True, isolation="repeatable_read"):
            companies = await conn.fetch("SELECT company_id FROM public.companies WHERE symbol = $1", symbol)
            if not companies:
                raise LookupError(symbol)
            if len(companies) > 1:
                raise RuntimeError("Ambiguous company mapping")
            company_id = companies[0]["company_id"]
            # Every stored row of the 21 latest dates: a second source or basis on one date
            # reaches the calculator and is rejected there instead of being picked silently.
            prices = await conn.fetch(
                f"""SELECT t.price_id::text AS price_id, t.trade_date, t.open, t.high, t.low, t.close, t.volume,
                       t.price_scale, t.is_adjusted, t.payload_id::text AS payload_id, {SOURCE}
                    FROM public.price_bars t {PROVENANCE}
                    WHERE t.company_id = $1 AND t.trade_date IN (
                        SELECT DISTINCT trade_date FROM public.price_bars
                        WHERE company_id = $1 AND trade_date <= $2
                        ORDER BY trade_date DESC LIMIT $3)
                    ORDER BY t.trade_date""", company_id, as_of, SESSIONS)
            if not prices:
                raise LookupError(symbol)
            activity, stored = [], await conn.fetchval("SELECT to_regclass('public.daily_market_activity')")
            if stored:
                activity = await conn.fetch(
                    f"""SELECT a.trade_date, a.volume, a.total_value_vnd, a.foreign_buy_volume,
                           a.foreign_sell_volume, a.foreign_buy_value_vnd, a.foreign_sell_value_vnd,
                           a.volume_basis, a.value_basis, a.observation_status, a.quality_status,
                           a.source_updated_at, a.fetched_at, a.payload_id::text AS payload_id,
                           a.field_payload_ids, {SOURCE}
                        FROM public.daily_market_activity a
                        LEFT JOIN public.sources s ON s.source_id = a.source_id
                        WHERE a.company_id = $1 AND a.trade_date BETWEEN $2 AND $3
                        ORDER BY a.trade_date""", company_id, prices[0]["trade_date"], as_of)
            benchmark = await conn.fetch(
                f"""SELECT t.index_symbol, t.trade_date, t.close, t.payload_id::text AS payload_id, {SOURCE}
                    FROM public.market_index_bars t {PROVENANCE}
                    WHERE t.index_symbol = 'VNINDEX' AND t.trade_date = ANY($1::date[])
                    ORDER BY t.trade_date""", [row["trade_date"] for row in prices])
    try:
        result = analyze_series([dict(row) for row in prices], [dict(row) for row in activity],
                                [dict(row) for row in benchmark],
                                symbol=symbol, requested_as_of=as_of, today=today)
    except ValueError as exc:
        raise RuntimeError("Stored price series is inconsistent") from exc
    if not stored:
        result["warnings"].append("activity_storage_unavailable")
    return result
