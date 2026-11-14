"""Read-only, deterministic price lookup for supported Vietnamese questions.

The price table is the source of truth for exact dates and whole-dataset
calculations. This small parser supports the question shapes in Golden Q11-Q20
without allowing model-generated SQL.
"""

import re
import unicodedata
from datetime import date
from decimal import Decimal


class PriceQueryError(ValueError):
    pass


def _plain(text):
    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _dates(question):
    found = []
    for day, month, year in re.findall(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", question):
        try:
            value = date(int(year), int(month), int(day))
        except ValueError as exc:
            raise PriceQueryError("Ngày giao dịch trong câu hỏi không hợp lệ.") from exc
        if value not in found:
            found.append(value)
    return found


def classify(question):
    """Return a supported operation and any explicit calendar dates."""
    words = _plain(question)
    dates = _dates(question)
    if "bao nhieu phien" in words or ("bao nhieu" in words and "records" in words):
        return "count_bars", dates
    if "trung binh" in words and ("volume" in words or "khoi luong" in words):
        return "average_volume", dates
    if "giam gia manh nhat" in words:
        return "strongest_decline", dates
    if len(dates) >= 2:
        return "compare_closes", dates
    if len(dates) == 1:
        return "daily_bar", dates
    if ("cao nhat" in words or "highest close" in words) and ("thap nhat" in words or "lowest close" in words):
        return "close_extremes", dates
    if ("lon nhat" in words or "ky luc" in words) and ("volume" in words or "khoi luong" in words):
        return "max_volume", dates
    raise PriceQueryError("Chưa hỗ trợ dạng câu hỏi giá này; hãy nêu mã và ngày hoặc phép thống kê cần tìm.")


def _period_bounds(period):
    if period is None:
        return None, None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
            start = date.fromisoformat(period)
            return start, date.fromordinal(start.toordinal() + 1)
        if re.fullmatch(r"\d{4}-\d{2}", period):
            year, month = map(int, period.split("-"))
            start = date(year, month, 1)
            end = date(year + (month == 12), month % 12 + 1, 1)
            return start, end
        if re.fullmatch(r"\d{4}-Q[1-4]", period, re.IGNORECASE):
            year, quarter = int(period[:4]), int(period[-1])
            month = 3 * quarter - 2
            start = date(year, month, 1)
            end = date(year + (quarter == 4), 1 if quarter == 4 else month + 3, 1)
            return start, end
        if re.fullmatch(r"\d{4}", period):
            year = int(period)
            return date(year, 1, 1), date(year + 1, 1, 1)
    except (ValueError, OverflowError) as exc:
        raise PriceQueryError("Kỳ giá không hợp lệ.") from exc
    raise PriceQueryError("Kỳ giá cần có dạng YYYY, YYYY-Qn, YYYY-MM hoặc YYYY-MM-DD.")


def _source(row):
    return {
        "source_table": "price_bars",
        "price_id": str(row["price_id"]),
        "symbol": row["symbol"],
        "trade_date": row["trade_date"].isoformat(),
        "price_scale": row["price_scale"],
        "open": str(row["open"]),
        "high": str(row["high"]),
        "low": str(row["low"]),
        "close": str(row["close"]),
        "volume": row["volume"],
    }


PRICE_ROWS = """
SELECT p.price_id, c.symbol, p.trade_date, p.price_scale,
       p.open, p.high, p.low, p.close, p.volume
FROM public.price_bars p JOIN public.companies c USING(company_id)
WHERE ($1::text IS NULL OR c.symbol = $1)
  AND ($2::date IS NULL OR p.trade_date >= $2)
  AND ($3::date IS NULL OR p.trade_date < $3)
"""


async def query_price(pool, question, company_symbol=None, period=None):
    """Return a calculated value and source price IDs, using source rows only."""
    operation, dates = classify(question)
    start, end = _period_bounds(period)
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            symbols = await conn.fetch("SELECT symbol FROM public.companies")
            available = {row["symbol"] for row in symbols}
            symbol = company_symbol.strip().upper() if company_symbol else None
            if symbol and symbol not in available:
                raise PriceQueryError(f"Không có mã công ty {symbol}.")
            if symbol is None:
                named = {ticker for ticker in available
                         if re.search(rf"\b{re.escape(ticker)}\b", question, re.IGNORECASE)}
                if len(named) > 1:
                    raise PriceQueryError("Câu hỏi có nhiều mã; hãy chọn company_symbol.")
                symbol = next(iter(named), None)

            if operation in {"daily_bar", "compare_closes", "average_volume", "close_extremes"} and not symbol:
                raise PriceQueryError("Cần mã công ty để tìm hoặc tính giá.")

            base = (symbol, start, end)
            if operation in {"daily_bar", "compare_closes"}:
                rows = await conn.fetch(
                    PRICE_ROWS + " AND p.trade_date = ANY($4::date[]) ORDER BY p.trade_date",
                    *base, dates,
                )
                if len(rows) != len(dates):
                    raise PriceQueryError("Không đủ phiên giá theo mã, ngày và kỳ đã chọn.")
                sources = [_source(row) for row in rows]
                if operation == "daily_bar":
                    row = rows[0]
                    data = {"bar": sources[0], "intraday_range": str(row["high"] - row["low"])}
                else:
                    first, last = rows[0], rows[-1]
                    change = last["close"] - first["close"]
                    change_percent = change / first["close"] * Decimal(100)
                    data = {
                        "first_close": str(first["close"]),
                        "last_close": str(last["close"]),
                        "change": str(change),
                        "change_percent": str(change_percent.quantize(Decimal("0.01"))),
                    }
            elif operation == "max_volume":
                row = await conn.fetchrow(
                    PRICE_ROWS + " ORDER BY p.volume DESC, c.symbol, p.trade_date LIMIT 1",
                    *base,
                )
                if row is None:
                    raise PriceQueryError("Không có phiên giá trong phạm vi đã chọn.")
                sources = [_source(row)]
                data = {"symbol": row["symbol"], "volume": row["volume"],
                        "trade_date": row["trade_date"].isoformat()}
            elif operation == "close_extremes":
                high = await conn.fetchrow(
                    PRICE_ROWS + " ORDER BY p.close DESC, p.trade_date LIMIT 1", *base,
                )
                low = await conn.fetchrow(
                    PRICE_ROWS + " ORDER BY p.close ASC, p.trade_date LIMIT 1", *base,
                )
                if high is None or low is None:
                    raise PriceQueryError("Không có phiên giá trong phạm vi đã chọn.")
                sources = [_source(high), _source(low)]
                data = {"highest_close": str(high["close"]),
                        "highest_date": high["trade_date"].isoformat(),
                        "lowest_close": str(low["close"]),
                        "lowest_date": low["trade_date"].isoformat()}
            elif operation == "average_volume":
                row = await conn.fetchrow(
                    """
                    SELECT count(*) AS bar_count, avg(p.volume) AS average_volume,
                           min(p.trade_date) AS first_date, max(p.trade_date) AS last_date
                    FROM public.price_bars p JOIN public.companies c USING(company_id)
                    WHERE ($1::text IS NULL OR c.symbol = $1)
                      AND ($2::date IS NULL OR p.trade_date >= $2)
                      AND ($3::date IS NULL OR p.trade_date < $3)
                    """, *base,
                )
                if row["bar_count"] == 0:
                    raise PriceQueryError("Không có phiên giá trong phạm vi đã chọn.")
                sources = []
                data = {"symbol": symbol, "bar_count": row["bar_count"],
                        "average_volume": str(row["average_volume"]),
                        "first_date": row["first_date"].isoformat(),
                        "last_date": row["last_date"].isoformat(),
                        "source_table": "price_bars"}
            elif operation == "count_bars":
                rows = await conn.fetch(
                    """
                    SELECT c.symbol, count(*) AS bar_count
                    FROM public.price_bars p JOIN public.companies c USING(company_id)
                    WHERE ($1::text IS NULL OR c.symbol = $1)
                      AND ($2::date IS NULL OR p.trade_date >= $2)
                      AND ($3::date IS NULL OR p.trade_date < $3)
                    GROUP BY c.symbol ORDER BY c.symbol
                    """, *base,
                )
                sources = []
                counts = {row["symbol"]: row["bar_count"] for row in rows}
                data = {"counts": counts, "total": sum(counts.values()),
                        "source_table": "price_bars"}
            else:  # strongest_decline
                rows = await conn.fetch(
                    """
                    SELECT c.symbol, first_bar.price_id AS first_id,
                           first_bar.trade_date AS first_date,
                           first_bar.close AS first_close,
                           last_bar.price_id AS last_id,
                           last_bar.trade_date AS last_date,
                           last_bar.close AS last_close,
                           (last_bar.close - first_bar.close)
                             / nullif(first_bar.close, 0) * 100 AS change_percent
                    FROM public.companies c
                    JOIN LATERAL (
                      SELECT price_id, trade_date, close FROM public.price_bars p
                      WHERE p.company_id = c.company_id
                        AND ($2::date IS NULL OR p.trade_date >= $2)
                        AND ($3::date IS NULL OR p.trade_date < $3)
                      ORDER BY trade_date ASC LIMIT 1
                    ) first_bar ON true
                    JOIN LATERAL (
                      SELECT price_id, trade_date, close FROM public.price_bars p
                      WHERE p.company_id = c.company_id
                        AND ($2::date IS NULL OR p.trade_date >= $2)
                        AND ($3::date IS NULL OR p.trade_date < $3)
                      ORDER BY trade_date DESC LIMIT 1
                    ) last_bar ON true
                    WHERE ($1::text IS NULL OR c.symbol = $1)
                    ORDER BY change_percent ASC, c.symbol
                    """, *base,
                )
                if not rows:
                    raise PriceQueryError("Không có phiên giá trong phạm vi đã chọn.")
                winner = rows[0]
                sources = [
                    {"source_table": "price_bars", "price_id": str(winner["first_id"]),
                     "symbol": winner["symbol"], "trade_date": winner["first_date"].isoformat(),
                     "close": str(winner["first_close"])},
                    {"source_table": "price_bars", "price_id": str(winner["last_id"]),
                     "symbol": winner["symbol"], "trade_date": winner["last_date"].isoformat(),
                     "close": str(winner["last_close"])},
                ]
                data = {
                    "symbol": winner["symbol"],
                    "change_percent": str(winner["change_percent"].quantize(Decimal("0.01"))),
                    "compared_symbols": [row["symbol"] for row in rows],
                }

            return {
                "question": question,
                "operation": operation,
                "scope": {"company_symbol": symbol, "period": period},
                "data": data,
                "sources": sources,
            }
