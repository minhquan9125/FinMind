"""Run period regression cases against PostgreSQL using SELECT-only expressions."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

import asyncpg

from backend.src.core.config import get_settings
from backend.src.documents.retrieval_period import PERIOD_SQL, EXACT_PERIOD_SQL, FILTER_PERIOD_SQL


# doc_type, title, structured period, locator, period, exact period, query, matched
CASES = [
    ('ANNUAL_REPORT', 'FPT — Báo cáo thường niên 2024', None, {'section': 'PDF_PAGE_161'}, '2024', '2024', '2024', True),
    ('ANNUAL_REPORT', 'FPT — Báo cáo thường niên 2025', None, {'section': 'PDF_PAGE_161'}, '2025', '2025', '2024', False),
    ('ANNUAL_REPORT', 'FPT — Annual Report 2024', None, {'section': 'PDF_PAGE_2024'}, '2024', '2024', '2024', True),
    ('ANNUAL_REPORT', 'Untitled', None, {'section': 'PDF_PAGE_2024'}, None, None, '2024', False),
    ('ANNUAL_REPORT', 'FPT — Báo cáo thường niên 2024', None, {'published_at': '2025-04-01', 'section': 'PDF_PAGE_2'}, '2024', '2024', '2025', False),
    ('ANNUAL_REPORT', 'Untitled', '2023', {'section': 'PDF_PAGE_2024'}, '2023', '2023', '2024', False),
    ('ANNUAL_REPORT', 'Untitled', None, {'period_code': '2024', 'section': 'PDF_PAGE_1'}, '2024', '2024', '2024', True),
    ('ANNUAL_REPORT', 'FPT — Báo cáo thường niên 2024', None, {'section': 'PDF_PAGE_1'}, '2024', '2024', '2024-Q2', False),
    ('ANNUAL_REPORT', 'FPT — Báo cáo thường niên 2024 (updated 2025)', None, {'section': 'PDF_PAGE_1'}, None, None, '2025', False),
    ('FINANCIAL_STATEMENT', 'Financial report', '2025-Q2', {}, '2025-Q2', '2025-Q2', '2025', True),
    ('FINANCIAL_STATEMENT', 'Financial report', '2025-Q2', {}, '2025-Q2', '2025-Q2', '2025-Q1', False),
    ('NEWS', 'News', None, {'published_at': '2026-10-22T08:00:00+07:00'}, '2026-10-22T08:00:00+07:00', None, '2026-10', True),
    ('PRICE_HISTORY', 'Prices', None, {'section': '2026-05'}, '2026-05', None, '2026-05', True),
    ('FINANCIAL_STATEMENT', 'Legacy financial report 2024', None, {}, None, None, '2024', True),
]


async def verify(connection):
    results = []
    sql = f'''SELECT {PERIOD_SQL} AS period, {EXACT_PERIOD_SQL} AS exact_period,
                     coalesce({FILTER_PERIOD_SQL} ILIKE '%' || $5::text || '%', false) AS matched
              FROM (SELECT $1::text AS doc_type, $2::text AS title) d
              CROSS JOIN (SELECT $3::text AS period_code) p
              CROSS JOIN (SELECT $4::jsonb AS locator_json) t'''
    for number, (kind, title, structured, locator, period, exact, query, matched) in enumerate(CASES, 1):
        row = await connection.fetchrow(sql, kind, title, structured, json.dumps(locator), query)
        expected = dict(period=period, exact_period=exact, matched=matched)
        results.append(dict(case=number, actual=dict(row), expected=expected, passed=dict(row)==expected))
    return dict(checked_at=datetime.now(timezone.utc).isoformat(), mode='READ_ONLY',
                passed=all(r['passed'] for r in results), cases=results)


async def main(output):
    connection = await asyncpg.connect(get_settings().database_url, timeout=10, statement_cache_size=0,
                                      server_settings={'default_transaction_read_only': 'on', 'statement_timeout': '20000'})
    try:
        async with connection.transaction(readonly=True, isolation='repeatable_read'):
            report = await verify(connection)
    finally:
        await connection.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'passed': report['passed'], 'cases': len(report['cases']), 'output': str(output)}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args().output))
