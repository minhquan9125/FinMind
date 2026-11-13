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
    FINANCIAL_VERIFIED_RENDERER_VERSION,
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

# Same ordering as financial.health_db: newest verified_at, verification_id DESC breaks ties.
_LATEST = "ORDER BY v.verified_at DESC, v.verification_id DESC"


def _verified_sql(pick: str) -> str:
    sql = FINANCIAL_SQL.replace(
        "o.observation_id, o.value, o.unit\n",
        "o.observation_id, o.value, o.unit,\n"
        "       v.verification_id, v.status AS v_status, v.statement_scope AS v_scope, v.unit AS v_unit,\n"
        "       v.unit_status AS v_unit_status, v.evidence AS v_evidence, d.title AS doc_title, d.source_url AS doc_url\n")
    return sql.replace(
        "WHERE (",
        "LEFT JOIN LATERAL (SELECT * FROM public.financial_report_verifications v WHERE v.report_id = fr.report_id"
        f"{pick} LIMIT 1) v ON true\nLEFT JOIN public.documents d ON d.document_id = v.document_id\nWHERE (")


FINANCIAL_VERIFIED_SQL = _verified_sql(" " + _LATEST)
# Pinned to one verification so an old chunk rebuilds to the same text after a newer verification appears.
FINANCIAL_PINNED_SQL = _verified_sql(" AND v.verification_id = $2::uuid")

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


async def fetch_financial_documents(conn: Any, symbols: Sequence[str] | None = None, *,
                                    renderer_version: str | None = None) -> list[SourceDocument]:
    verified = renderer_version == FINANCIAL_VERIFIED_RENDERER_VERSION
    rows = await conn.fetch(FINANCIAL_VERIFIED_SQL if verified else FINANCIAL_SQL, _symbols(symbols))
    options = {} if renderer_version is None else {'renderer_version': renderer_version}
    return financial_documents((dict(r) for r in rows), **options)


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


async def fetch_locator_document(conn: Any, table: str, source_id: str, max_words: int = 130, *, financial_renderer_version: str = 'db-v1',
                                 verification_id: str | None = None) -> SourceDocument | None:
    """SELECT one source document only; no text_chunks reads, writes or embedding."""
    if table == 'news_articles':
        rows = await conn.fetch(
            'SELECT article_id,source,title,content,published_at,symbols,url '
            'FROM public.news_articles WHERE article_id::text=$1', source_id)
        docs = news_documents((dict(r) for r in rows), max_words=max_words)
    elif table == 'financial_reports':
        where = '($1::text[] IS NULL OR c.symbol = ANY($1::text[]))'
        if financial_renderer_version == FINANCIAL_VERIFIED_RENDERER_VERSION:
            # verification_id None (chunk built unverified, or unpinned caller) matches no row: renders unverified by design.
            sql = FINANCIAL_PINNED_SQL.replace(where, 'fr.report_id::text=$1')
            fetched = await conn.fetch(sql, source_id, verification_id)
        else:
            fetched = await conn.fetch(FINANCIAL_SQL.replace(where, 'fr.report_id::text=$1'), source_id)
        docs = financial_documents((dict(r) for r in fetched), renderer_version=financial_renderer_version)
    elif table == 'companies':
        sql = COMPANIES_SQL.replace('($1::text[] IS NULL OR symbol = ANY($1::text[]))', 'company_id::text=$1')
        docs = company_documents(dict(r) for r in await conn.fetch(sql, source_id))
    elif table == 'price_bars':
        docs = await fetch_price_documents(conn, [source_id])
    elif table == 'market_index_bars':
        docs = await fetch_index_documents(conn, [source_id])
    else:
        raise ValueError('Unsupported locator source_table')
    return next((doc for doc in docs if str(doc.source_id) == source_id), None)
