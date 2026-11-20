"""Company catalog and key BCTC facts per period, for the company and compare pages. Read-only."""
from __future__ import annotations

from decimal import Decimal

# Fact key shown on the page -> metric code. Revenue is operating income for banks.
_CODES = {'totalAssets': 'TOTAL_ASSETS', 'liabilities': 'TOTAL_LIABILITIES', 'equity': 'OWNERS_EQUITY',
          'netProfit': 'PROFIT_AFTER_TAX', 'roe': 'ROE', 'roa': 'ROA'}
_ALL_CODES = [*_CODES.values(), 'NET_REVENUE', 'TOTAL_OPERATING_INCOME']

_CATALOG_SQL = """
SELECT c.symbol, c.company_name, c.sector, c.exchange, c.industry_type,
       (SELECT p.period_code FROM financial_reports r JOIN reporting_periods p USING (period_id)
        WHERE r.company_id = c.company_id
        ORDER BY p.end_date DESC, (p.period_type = 'YEAR') DESC LIMIT 1) AS latest_period
FROM companies c WHERE c.is_active IS NOT FALSE ORDER BY c.symbol
"""

_FACTS_SQL = """
WITH latest AS (
  SELECT r.*, max(r.report_version) OVER (PARTITION BY r.period_id, r.statement_scope) AS top_version
  FROM financial_reports r WHERE r.company_id = $1
)
SELECT p.period_code, p.period_type, p.fiscal_year, p.quarter, p.end_date, l.published_at,
       m.code, o.value, o.unit, v.status AS v_status
FROM latest l
JOIN reporting_periods p USING (period_id)
JOIN observations o ON o.report_id = l.report_id
JOIN metrics m ON m.metric_id = o.metric_id
LEFT JOIN LATERAL (SELECT status FROM financial_report_verifications v WHERE v.report_id = l.report_id
                   ORDER BY v.verified_at DESC, v.verification_id DESC LIMIT 1) v ON true
WHERE l.report_version = l.top_version AND m.code = ANY($2::text[])
"""

_DOCS_SQL = """
SELECT DISTINCT ON (d.document_id) d.document_id, p.period_code, p.end_date, d.title, d.source_url, v.status
FROM financial_report_verifications v
JOIN financial_reports r ON r.report_id = v.report_id
JOIN reporting_periods p ON p.period_id = r.period_id
JOIN documents d ON d.document_id = v.document_id
WHERE r.company_id = $1
ORDER BY d.document_id, v.verified_at DESC, v.verification_id DESC
"""

_SOURCES_SQL = """
SELECT DISTINCT s.name FROM financial_reports r JOIN ingestion_jobs j ON j.job_id = r.job_id
JOIN sources s ON s.source_id = j.source_id WHERE r.company_id = $1 ORDER BY 1
"""


def period_label(period_type, fiscal_year, quarter, code):
    if period_type == 'YEAR':
        return f'Năm {fiscal_year}'
    if period_type == 'QUARTER' and quarter:
        return f'Quý {quarter}/{fiscal_year}'
    return code


def period_status(statuses):
    """One verification state for a period from its facts' report states (None = never checked)."""
    known = {s for s in statuses if s}
    if not known:
        return None
    if 'MISMATCH' in known:
        return 'MISMATCH'
    return 'VERIFIED' if known == {'VERIFIED'} and None not in statuses else 'PARTIAL'


def _number(value):
    return float(value) if isinstance(value, Decimal) else value


def build_periods(rows, industry_type):
    """Group fact rows by period, newest first, and add revenue growth against the same period a year earlier."""
    revenue_code = 'TOTAL_OPERATING_INCOME' if industry_type == 'BANK' else 'NET_REVENUE'
    codes = {**{code: key for key, code in _CODES.items()}, revenue_code: 'revenue'}
    periods = {}
    for row in rows:
        key = codes.get(row['code'])
        if key is None:
            continue
        period = periods.setdefault(row['period_code'], dict(
            period=row['period_code'],
            label=period_label(row['period_type'], row['fiscal_year'], row['quarter'], row['period_code']),
            type=row['period_type'], year=row['fiscal_year'], quarter=row['quarter'],
            endDate=row['end_date'].isoformat() if row['end_date'] else None, publishedAt=None,
            facts={}, _statuses=[]))
        if row['published_at'] and (period['publishedAt'] is None or row['published_at'].isoformat() > period['publishedAt']):
            period['publishedAt'] = row['published_at'].isoformat()
        period['facts'][key] = dict(value=_number(row['value']), unit=row['unit'], status=row['v_status'])
        if key not in ('roe', 'roa'):  # ratios come from the data API and are never checked against the PDF
            period['_statuses'].append(row['v_status'])
    for period in periods.values():
        period['status'] = period_status(period.pop('_statuses'))
        prev_code = (f"{period['year'] - 1}-YEAR" if period['type'] == 'YEAR'
                     else f"{period['year'] - 1}-Q{period['quarter']}" if period['quarter'] else None)
        now, before = period['facts'].get('revenue'), periods.get(prev_code, {}).get('facts', {}).get('revenue')
        # growth only between values in the same unit, never across a unit change
        if now and before and before['value'] and now['unit'] == before['unit']:
            period['facts']['revenueYoy'] = dict(
                value=(now['value'] - before['value']) / abs(before['value']), unit='RATIO', status=None)
    return sorted(periods.values(), key=lambda p: (p['endDate'] or '', p['type'] == 'YEAR'), reverse=True)


def _company(row):
    return dict(ticker=row['symbol'], name=row['company_name'], sector=row['sector'],
                exchange=row['exchange'], industryType=row['industry_type'])


async def list_companies(conn):
    return [dict(_company(r), latestPeriod=r['latest_period']) for r in await conn.fetch(_CATALOG_SQL)]


async def company_detail(conn, symbol):
    row = await conn.fetchrow(
        'SELECT company_id, symbol, company_name, sector, exchange, industry_type FROM companies '
        'WHERE symbol = $1 AND is_active IS NOT FALSE', symbol)
    if row is None:
        return None
    periods = build_periods(await conn.fetch(_FACTS_SQL, row['company_id'], _ALL_CODES), row['industry_type'])
    docs = sorted(await conn.fetch(_DOCS_SQL, row['company_id']),
                  key=lambda d: (d['end_date'] or d['period_code'], d['title'] or ''), reverse=True)
    reports = [dict(id=str(d['document_id']), title=d['title'], period=d['period_code'],
                    url=d['source_url'], status=d['status']) for d in docs]
    sources = [r['name'] for r in await conn.fetch(_SOURCES_SQL, row['company_id'])]
    return dict(_company(row), periods=periods, reports=reports, sources=sources)
