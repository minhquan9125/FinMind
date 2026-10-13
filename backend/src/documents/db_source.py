"""Read-only SQL that feeds ``db_chunking`` from Supabase / PostgreSQL.

Every function takes an open connection (an ``asyncpg.Connection`` or anything
with an async ``fetch(sql, *args)``) and returns ``SourceDocument`` objects.
Nothing here writes to the database.
"""

from __future__ import annotations

from typing import Any, Sequence

from .db_chunking import (
    SourceDocument,
    company_documents,
    financial_documents,
    index_documents,
    news_documents,
    price_documents,
)

FINANCIAL_SQL = """
SELECT fr.report_id, c.symbol, c.company_name, rp.period_code, rp.fiscal_year, rp.quarter,
       fr.statement_scope, fr.report_version, m.section, m.code, m.canonical_name,
       o.observation_id, o.value, o.unit
FROM public.financial_reports fr
JOIN public.companies c ON c.company_id = fr.company_id
JOIN public.reporting_periods rp ON rp.period_id = fr.period_id
JOIN public.observations o ON o.report_id = fr.report_id
JOIN public.metrics m ON m.metric_id = o.metric_id
WHERE ($1::text[] IS NULL OR c.symbol = ANY($1::text[]))
ORDER BY c.symbol, rp.fiscal_year, rp.quarter NULLS FIRST, fr.report_id, m.section, m.code
"""

# LIMIT NULL means "no limit" in PostgreSQL, so limit=None reads every article.
NEWS_SQL = """
SELECT article_id, source, title, content, published_at, symbols, url
FROM public.news_articles
WHERE ($1::text[] IS NULL OR symbols && $1::text[])
ORDER BY published_at DESC NULLS LAST, article_id
LIMIT $2::int
"""

PRICES_SQL = """
SELECT p.price_id, c.symbol, c.company_name, p.trade_date, p.open, p.high, p.low, p.close,
       p.volume, p.price_scale, i.sma20, i.sma50, i.rsi14
FROM public.price_bars p
JOIN public.companies c ON c.company_id = p.company_id
LEFT JOIN public.price_indicators i ON i.price_id = p.price_id
WHERE ($1::text[] IS NULL OR c.symbol = ANY($1::text[]))
ORDER BY c.symbol, p.trade_date
"""

INDICES_SQL = """
SELECT index_symbol, index_name, exchange, trade_date, open, high, low, close, volume,
       sma20, sma50, rsi14
FROM public.market_index_bars
WHERE ($1::text[] IS NULL OR index_symbol = ANY($1::text[]))
ORDER BY index_symbol, trade_date
"""

COMPANIES_SQL = """
SELECT company_id, symbol, company_name, industry_type, sector, exchange, is_active
FROM public.companies
WHERE ($1::text[] IS NULL OR symbol = ANY($1::text[]))
ORDER BY symbol
"""


def _symbols(symbols: Sequence[str] | None) -> list[str] | None:
    return [s.strip().upper() for s in symbols] if symbols else None


async def fetch_financial_documents(conn: Any, symbols: Sequence[str] | None = None) -> list[SourceDocument]:
    rows = await conn.fetch(FINANCIAL_SQL, _symbols(symbols))
    return financial_documents(dict(r) for r in rows)


async def fetch_news_documents(conn: Any, symbols: Sequence[str] | None = None, limit: int | None = None,
                               max_words: int = 130) -> list[SourceDocument]:
    rows = await conn.fetch(NEWS_SQL, _symbols(symbols), limit or None)
    return news_documents((dict(r) for r in rows), max_words=max_words)


async def fetch_price_documents(conn: Any, symbols: Sequence[str] | None = None) -> list[SourceDocument]:
    rows = await conn.fetch(PRICES_SQL, _symbols(symbols))
    return price_documents(dict(r) for r in rows)


async def fetch_index_documents(conn: Any, symbols: Sequence[str] | None = None) -> list[SourceDocument]:
    rows = await conn.fetch(INDICES_SQL, _symbols(symbols))
    return index_documents(dict(r) for r in rows)


async def fetch_company_documents(conn: Any, symbols: Sequence[str] | None = None) -> list[SourceDocument]:
    rows = await conn.fetch(COMPANIES_SQL, _symbols(symbols))
    return company_documents(dict(r) for r in rows)
