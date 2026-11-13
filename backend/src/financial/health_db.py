"""Read BCTC observations from the DB for the health calculator, merged with the current verification."""
from decimal import Decimal
import json
from uuid import UUID

_PERIOD_BASIS = {'ANNUAL': 'YEAR', 'STANDALONE_QUARTER': 'QUARTER', 'YEAR_TO_DATE': 'YTD'}

_SQL = """
WITH latest AS (
  SELECT r.*, max(r.report_version) OVER (PARTITION BY r.company_id, r.period_id, r.statement_scope) AS top_version
  FROM financial_reports r JOIN companies c ON c.company_id = r.company_id WHERE c.symbol = ANY($1::text[])
)
SELECT c.symbol, c.industry_type, m.section, m.code, p.period_code, o.value, o.unit, o.scale, o.currency,
       o.locator_json::text AS locator_text, l.published_at, o.observation_id, l.payload_id,
       s.name AS source_name, rp.source_uri, rp.sha256, s.approval_status, l.report_id, l.report_version,
       l.restated_from_id, v.status AS v_status, v.unit AS v_unit, v.unit_status, v.statement_scope AS v_scope,
       v.period_basis, v.period_start, v.period_end, v.fiscal_year_end, v.fiscal_label_convention,
       v.comparison_basis
FROM latest l
JOIN companies c ON c.company_id = l.company_id
JOIN reporting_periods p ON p.period_id = l.period_id
JOIN observations o ON o.report_id = l.report_id
JOIN metrics m ON m.metric_id = o.metric_id
LEFT JOIN raw_payloads rp ON rp.payload_id = l.payload_id
LEFT JOIN ingestion_jobs j ON j.job_id = l.job_id
LEFT JOIN sources s ON s.source_id = j.source_id
LEFT JOIN LATERAL (SELECT * FROM financial_report_verifications v WHERE v.report_id = l.report_id
                   ORDER BY v.verified_at DESC, v.verification_id DESC LIMIT 1) v ON true
WHERE l.report_version = l.top_version
ORDER BY c.symbol, p.period_code, m.code
"""


def _loads(text):
    return json.loads(text, parse_float=Decimal, parse_int=Decimal)


def _payload_value(payload, locator, period_code):
    """Exact Decimal from the raw payload, or None when the shape or row is not found."""
    rows = payload.get(locator.get('source_section')) if isinstance(payload, dict) else None
    for row in rows if isinstance(rows, list) else []:
        if (isinstance(row, dict) and row.get('period_label') == period_code
                and row.get('ratioType') == locator.get('ratio_type')):
            value = row.get(locator.get('source_field'))
            return value if isinstance(value, Decimal) else None
    return None


def _merge(row, locator):
    """Copy each verification field into the locator only when its own check passed."""
    if row['v_status'] is None or row['v_status'] == 'MISMATCH':
        return
    # the unit check covers money only, never ratio units
    if row['unit_status'] == 'VERIFIED' and row['section'] != 'RATIO':
        locator['unit_status'] = 'VERIFIED'
    if row['v_scope'] not in (None, 'UNKNOWN'):
        locator['statement_scope'] = row['v_scope']
    if row['section'] == 'BALANCE_SHEET':
        locator['period_basis'] = 'INSTANT'
    elif row['period_basis'] in _PERIOD_BASIS:
        locator['period_basis'] = _PERIOD_BASIS[row['period_basis']]
    # A restated prior period is not comparable: leave the basis unknown so the pair is never compared.
    if row['comparison_basis'] not in (None, 'UNKNOWN', 'RESTATED'):
        locator['comparison_basis'] = row['comparison_basis']
    if row['fiscal_label_convention'] not in (None, 'UNKNOWN'):
        locator['fiscal_label_convention'] = row['fiscal_label_convention']
        if row['fiscal_year_end']:
            locator['fiscal_year_end'] = row['fiscal_year_end']
    for key in ('period_start', 'period_end'):
        if row[key] is not None:
            locator[key] = row[key].isoformat()
    if row['section'] == 'BALANCE_SHEET' and row['period_end'] is not None:
        locator['period_start'] = locator['period_end']  # a balance sheet is a single day (INSTANT)


async def fetch_health_records(conn, symbols: list[str]) -> list[dict]:
    payloads: dict = {}
    records = []
    for row in await conn.fetch(_SQL, list(symbols)):
        locator = _loads(row['locator_text']) if row['locator_text'] else {}
        pid = row['payload_id']
        if pid not in payloads:  # each payload is parsed once per call
            text = await conn.fetchval('SELECT payload::text FROM raw_payloads WHERE payload_id=$1', pid) if pid else None
            payloads[pid] = _loads(text) if text else None
        value = _payload_value(payloads[pid], locator, row['period_code'])
        _merge(row, locator)
        unit, currency = row['unit'], row['currency']
        if locator.get('unit_status') == 'VERIFIED' and row['section'] != 'RATIO' and row['unit'] != 'VND_PER_SHARE':
            unit = row['v_unit'] or 'VND'
            currency = 'VND'  # imports leave currency NULL; the verified unit is Vietnamese dong
        records.append(dict(
            symbol=row['symbol'], industry_type=row['industry_type'], section=row['section'], code=row['code'],
            period_code=row['period_code'], value=row['value'] if value is None else value, unit=unit,
            scale=row['scale'], currency=currency, locator_json=locator, published_at=row['published_at'],
            # ids as text: the calculator's provenance check requires strings, and asyncpg returns UUID objects
            observation_id=_id(row['observation_id']), payload_id=_id(pid), source_name=row['source_name'],
            source_uri=row['source_uri'], sha256=row['sha256'], approval_status=row['approval_status'],
            report_id=_id(row['report_id']), report_version=row['report_version'],
            restated_from_id=_id(row['restated_from_id'])))
    return records


def _id(value):
    return None if value is None else str(value)


async def citation_for(conn, observation_id) -> dict | None:
    observation_id = UUID(str(observation_id))
    row = await conn.fetchrow(
        'SELECT m.code, v.status, v.evidence, d.title, d.source_url FROM observations o '
        'JOIN metrics m ON m.metric_id=o.metric_id '
        'JOIN LATERAL (SELECT * FROM financial_report_verifications v WHERE v.report_id=o.report_id '
        'ORDER BY v.verified_at DESC, v.verification_id DESC LIMIT 1) v ON true '
        'JOIN documents d ON d.document_id=v.document_id WHERE o.observation_id=$1', observation_id)
    if row is None or row['status'] == 'MISMATCH':
        return None
    evidence = row['evidence']
    evidence = json.loads(evidence) if isinstance(evidence, str) else evidence or []
    page = next((e.get('page') for e in evidence if isinstance(e, dict) and e.get('metric') == row['code']), None)
    if page is None:  # no page means this number was not found in the PDF: do not cite it
        return None
    return dict(title=row['title'], url=row['source_url'], page=page)


# ---- chat evidence (MARKET_ANALYSIS): verified BCTC health for one symbol, with citation links ----
CACHE_SECONDS = 600  # rows for every symbol are re-read at most every 10 minutes, not on each chat question
_CACHE: dict = {'at': None, 'rows': None}


async def _health_rows(conn) -> list[dict]:
    import time
    from .health_store import canonical_rows
    now = time.monotonic()
    if _CACHE['rows'] is None or now - _CACHE['at'] > CACHE_SECONDS:
        symbols = [r['symbol'] for r in await conn.fetch(
            'SELECT DISTINCT c.symbol FROM companies c JOIN financial_reports r USING (company_id) ORDER BY 1')]
        _CACHE.update(rows=canonical_rows(await fetch_health_records(conn, symbols)), at=now)
    return _CACHE['rows']


async def get_financial_health(pool, symbol: str) -> dict | None:
    """Compact health for chat (see health_passage.compact_health) or None when the symbol has no BCTC.
    Read-only; picks the latest period with at least one verified signal, else the latest period."""
    from .health import _period, analyze_company
    from .health_passage import compact_health
    from .peers import compare_peers
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            rows = await _health_rows(conn)
            periods = sorted({r['period'] for r in rows if r['symbol'] == symbol},
                             key=lambda p: (_period(p)[0], _period(p)[1] or 5), reverse=True)
            if not periods:
                return None
            target = None
            for period in periods:
                candidate = analyze_company(rows, symbol=symbol, period=period)
                target = target or candidate
                if candidate['status'] != 'insufficient_data':
                    target = candidate
                    break
            analyses = []
            for other in sorted({r['symbol'] for r in rows if r['period'] == target['period']}):
                try:
                    analyses.append(target if other == symbol else
                                    analyze_company(rows, symbol=other, period=target['period']))
                except ValueError:  # an ambiguous peer is left out of the comparison, not fatal
                    continue
            try:
                peers = compare_peers(analyses, symbol=symbol)
            except ValueError:
                peers = {}
            citations = []
            for row in target['evidence']:
                if row.get('observation_id') and row.get('period') == target['period']:
                    cite = await citation_for(conn, row['observation_id'])
                    if cite and cite not in citations:
                        citations.append(cite)
    health = compact_health(target, peers, citations)
    period = health['period']
    health['period'] = period if '-Q' in period else f'{period}-YEAR'
    return health

# ---- company page facts: keep original health readers and their verification rules unchanged ----

def _company_money(value, scale):
    """Exact VND text, or no amount when either input cannot support exact arithmetic."""
    from decimal import DecimalException, localcontext
    if any(isinstance(number, bool) or not isinstance(number, (Decimal, int, str))
           for number in (value, scale)):
        return None
    try:
        value, scale = Decimal(value), Decimal(scale)
        if not value.is_finite() or not scale.is_finite() or scale <= 0:
            return None
        with localcontext() as context:
            context.prec = max(1, len(value.as_tuple().digits) + len(scale.as_tuple().digits))
            return format(value * scale, 'f')
    except (DecimalException, ValueError):
        return None


async def get_company_financials(pool, symbol: str) -> list[dict]:
    """At most eight periods of exact, per-observation financial facts for the company page."""
    import logging
    import re
    from ..b1_answering.evidence.grounded import _METRIC_LABELS

    sections = {
        'TOTAL_ASSETS': 'BALANCE_SHEET', 'TOTAL_LIABILITIES': 'BALANCE_SHEET',
        'TOTAL_EQUITY': 'BALANCE_SHEET', 'NET_REVENUE': 'INCOME_STATEMENT',
        'PROFIT_AFTER_TAX': 'INCOME_STATEMENT', 'CASH_FLOW_OPERATING': 'CASH_FLOW',
        'TOTAL_OPERATING_INCOME': 'INCOME_STATEMENT',
    }
    grouped = {}
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            for row in await fetch_health_records(conn, [symbol]):
                code = 'TOTAL_EQUITY' if row.get('code') == 'OWNERS_EQUITY' else row.get('code')
                if code not in sections or row.get('section') != sections[code]:
                    continue
                if code == 'TOTAL_OPERATING_INCOME' and row.get('industry_type') != 'BANK':
                    continue
                source_period = row.get('period_code')
                match = re.fullmatch(r'(\d{4})(?:-(YEAR|Q[1-4]))?', source_period or '')
                if match is None:
                    continue
                period = source_period if '-' in source_period else f'{source_period}-YEAR'
                locator = row.get('locator_json')
                locator = locator if isinstance(locator, dict) else {}
                status = 'VERIFIED' if locator.get('unit_status') == 'VERIFIED' else 'UNVERIFIED'
                value = _company_money(row.get('value'), row.get('scale'))
                signature = (Decimal(value) if value is not None else None, status,
                             locator.get('period_basis') or 'UNKNOWN',
                             locator.get('statement_scope') or 'UNKNOWN')
                facts = grouped.setdefault(period, {})
                if code in facts:
                    previous = facts[code]
                    if previous is not None and previous[1] != signature:
                        facts[code] = None
                        logging.getLogger(__name__).warning(
                            'Ambiguous financial fact omitted: %s %s %s', symbol[:10], period, code)
                    continue
                label = (_METRIC_LABELS[code] if code != 'TOTAL_OPERATING_INCOME'
                         else 'tổng thu nhập hoạt động')
                facts[code] = (dict(code=code, label=label, value_vnd=value, status=status),
                               signature, row.get('observation_id'))
            periods = []
            newest = sorted(grouped, key=lambda period: (
                int(period[:4]), 5 if period.endswith('-YEAR') else int(period[-1])), reverse=True)
            for period in newest[:8]:
                selected = [entry for entry in grouped[period].values() if entry is not None]
                first_verified = next((entry for entry in selected if entry[0]['status'] == 'VERIFIED'), None)
                source = (await citation_for(conn, first_verified[2])
                          if first_verified is not None and first_verified[2] else None)
                periods.append(dict(period=period, facts=[entry[0] for entry in selected], source=source))
    return periods