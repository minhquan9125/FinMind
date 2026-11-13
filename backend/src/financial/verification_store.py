"""Append-only DB writes for the BCTC metadata job. Callers own the transaction (one per company)."""
import asyncio
import calendar
import hashlib
from datetime import date, datetime
from decimal import Context, Decimal, InvalidOperation
import json
from uuid import UUID, uuid4

from backend.src.financial.verification import same_conclusion

# Metadata lives only in financial_report_verifications, never in observations.locator_json.
_META_KEYS = ('unit_status', 'period_basis', 'statement_scope', 'comparison_basis')
_VERIFICATION_COLUMNS = ('document_id', 'statement_scope', 'audit_status', 'unit', 'unit_status', 'period_basis',
                         'comparison_basis', 'fiscal_label_convention', 'period_start', 'period_end',
                         'fiscal_year_end', 'status')


def same_value(old: Decimal, new: Decimal) -> bool:
    """Equal, or old rounded to new's decimal places equals new: the old importer stored float noise
    (0.41943289929999999499... for the payload's 0.4194328993)."""
    if old == new:
        return True
    exponent = Decimal(new).as_tuple().exponent
    if not isinstance(exponent, int):  # NaN / Infinity
        return False
    try:
        return Decimal(old).quantize(Decimal(1).scaleb(exponent), context=Context(prec=200)) == new
    except InvalidOperation:
        return False


def values_differ(old: dict, new: dict) -> bool:
    """A new version only when a metric holding a value on both sides changed; one-sided metrics alone do not."""
    return any(not same_value(old[k], new[k]) for k in old.keys() & new.keys()
               if old[k] is not None and new[k] is not None)


async def ensure_source(conn, name: str, *, source_type: str, base_url: str) -> UUID:
    found = await conn.fetchval('SELECT source_id FROM sources WHERE name=$1 ORDER BY source_id LIMIT 1', name)
    if found:
        return found
    source_id = uuid4()
    await conn.execute("INSERT INTO sources(source_id,name,source_type,base_url,approval_status,is_enabled) "
                       "VALUES($1,$2,$3,$4,'PENDING',true)", source_id, name, source_type, base_url)
    return source_id


async def start_job(conn, source_id, *, trigger_type: str = 'BATCH') -> UUID:
    job_id = uuid4()
    await conn.execute("INSERT INTO ingestion_jobs(job_id,source_id,trigger_type,status,started_at) "
                       "VALUES($1,$2,$3,'RUNNING',now())", job_id, source_id, trigger_type)
    return job_id


async def finish_job(conn, job_id, *, ok: int, quarantined: int, status: str) -> None:
    """Callers pass status 'SUCCEEDED' or 'FAILED'."""
    await conn.execute('UPDATE ingestion_jobs SET status=$2,records_ok=$3,records_quarantined=$4,finished_at=now() '
                       'WHERE job_id=$1', job_id, status, ok, quarantined)


async def store_payload(conn, job_id, *, source_uri: str, payload_text: str) -> UUID:
    sha = await asyncio.to_thread(lambda: hashlib.sha256(payload_text.encode('utf-8')).hexdigest())
    found = await conn.fetchval('SELECT payload_id FROM raw_payloads WHERE source_uri=$1 AND sha256=$2 LIMIT 1',
                                source_uri, sha)
    if found:
        return found
    payload_id = uuid4()
    await conn.execute('INSERT INTO raw_payloads(payload_id,job_id,source_uri,sha256,payload,stored_at) '
                       'VALUES($1,$2,$3,$4,$5::jsonb,now())', payload_id, job_id, source_uri, sha, payload_text)
    return payload_id


async def ensure_document(conn, entry: dict, *, company_id, period_id, job_id, sha256: str, page_count: int,
                          file_size: int) -> UUID:
    await conn.execute(
        "INSERT INTO documents(document_id,company_id,period_id,job_id,doc_type,file_type,title,source_url,"
        "external_id,page_count,file_size,published_at,sha256,parse_status,language,created_at) "
        "VALUES($1,$2,$3,$4,'FINANCIAL_STATEMENT','PDF',$5,$6,$7,$8,$9,$10,$11,'PARSED','vi',now()) "
        "ON CONFLICT (sha256) DO NOTHING",
        uuid4(), company_id, period_id, job_id, entry.get('title'), entry.get('url'), entry.get('external_id'),
        page_count, file_size, _as_timestamptz(entry.get('last_update')), sha256)
    return await conn.fetchval('SELECT document_id FROM documents WHERE sha256=$1', sha256)


async def current_verification(conn, report_id) -> dict | None:
    row = await conn.fetchrow('SELECT * FROM financial_report_verifications WHERE report_id=$1 '
                              'ORDER BY verified_at DESC LIMIT 1', report_id)
    if row is None:
        return None
    out = dict(row)
    checks = json.loads(out['checks']) if isinstance(out['checks'], str) else dict(out['checks'])
    out['reason_codes'] = checks.pop('reason_codes', [])
    out['checks'] = checks
    if isinstance(out['evidence'], str):
        out['evidence'] = json.loads(out['evidence'])
    return out


async def append_verification(conn, report_id, job_id, conclusion: dict) -> UUID | None:
    await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1))', f'financial_report_verifications:{report_id}')
    current = await current_verification(conn, report_id)
    # compare only the conclusion's keys; the row also carries report_id etc.
    if current and same_conclusion({k: current.get(k) for k in conclusion}, conclusion):
        return None
    checks = {**conclusion.get('checks', {}), 'reason_codes': conclusion.get('reason_codes', [])}
    vid = uuid4()
    values = [conclusion.get(c) for c in _VERIFICATION_COLUMNS]
    # clock_timestamp, not now(): two verifications in one transaction must still order.
    await conn.execute(
        'INSERT INTO financial_report_verifications(verification_id,report_id,job_id,checks,evidence,supersedes_id,'
        'verified_at,' + ','.join(_VERIFICATION_COLUMNS) + ') VALUES($1,$2,$3,$4::jsonb,$5::jsonb,$6,clock_timestamp(),'
        + ','.join(f'${i}' for i in range(7, 7 + len(_VERIFICATION_COLUMNS))) + ')',
        vid, report_id, job_id, json.dumps(checks, default=str), json.dumps(conclusion.get('evidence', []), default=str),
        current['verification_id'] if current else None, *values)
    return vid


def _period_dates(code: str) -> tuple[date, date]:
    year = int(code[:4])
    if code.endswith('YEAR'):
        return date(year, 1, 1), date(year, 12, 31)
    q = int(code[-1])
    end_month = q * 3
    return date(year, end_month - 2, 1), date(year, end_month, calendar.monthrange(year, end_month)[1])


def _as_timestamptz(value):
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
        raise ValueError('last_update must be a tz-aware datetime or None')
    return value


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return value


async def _period_id(conn, rec: dict) -> UUID:
    found = await conn.fetchval('SELECT period_id FROM reporting_periods WHERE period_code=$1', rec['period_code'])
    if found:
        return found
    start, end = _period_dates(rec['period_code'])
    period_id = uuid4()
    await conn.execute('INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,'
                       'start_date,end_date) VALUES($1,$2,$3,$4,$5,$6,$7) '
                       'ON CONFLICT (period_code) DO NOTHING', period_id, rec['period_code'],
                       rec['fiscal_year'], rec['quarter'], rec['period_type'], start, end)
    return await conn.fetchval('SELECT period_id FROM reporting_periods WHERE period_code=$1', rec['period_code'])


def metric_key(rec: dict) -> tuple:
    return rec['code'], rec['section'], rec.get('industry_type')


async def append_reports(conn, records: list[dict], *, job_id, payload_id) -> dict:
    groups: dict[tuple, list[dict]] = {}
    for rec in records:
        groups.setdefault((rec['symbol'], rec['period_code'], rec['section']), []).append(rec)
    result = dict(new_reports=0, new_versions=0, unchanged=0)
    metrics: dict[tuple, UUID] = {}
    for (symbol, _code, section), recs in groups.items():
        company_id = await conn.fetchval('SELECT company_id FROM companies WHERE symbol=$1', symbol)
        if company_id is None:
            raise ValueError(f'unknown company symbol {symbol!r}')
        for rec in recs:
            key = metric_key(rec)
            if key not in metrics:
                # metrics is keyed by (code, section, industry_scope): one code can exist per section and industry.
                found = await conn.fetch('SELECT metric_id FROM metrics WHERE code=$1 AND section=$2 '
                                         'AND industry_scope=$3 LIMIT 2', *key)
                if len(found) != 1:
                    raise ValueError(f'{"ambiguous" if found else "unknown"} metric {key!r}')
                metrics[key] = found[0]['metric_id']
        if len({r['code'] for r in recs}) != len(recs):
            raise ValueError(f'duplicate metric code in {symbol} {_code} {section}')
        period_id = await _period_id(conn, recs[0])
        await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1))',
                           f'financial_reports:{company_id}:{_code}:{section}')
        new = {r['code']: Decimal(r['value']) if not isinstance(r['value'], Decimal) else r['value'] for r in recs}
        latest = await conn.fetchrow('SELECT report_id,report_version FROM financial_reports WHERE company_id=$1 '
                                     'AND period_id=$2 AND statement_scope=$3 ORDER BY report_version DESC LIMIT 1',
                                     company_id, period_id, section)
        if latest:
            old = {r['code']: r['value'] for r in await conn.fetch(
                'SELECT m.code,o.value FROM observations o JOIN metrics m ON m.metric_id=o.metric_id '
                'WHERE o.report_id=$1', latest['report_id'])}
            if not values_differ(old, new):
                result['unchanged'] += 1
                continue
            result['new_versions'] += 1
        else:
            result['new_reports'] += 1
        report_id = uuid4()
        await conn.execute(
            "INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,statement_scope,"
            "audit_status,report_version,restated_from_id,published_at) VALUES($1,$2,$3,$4,$5,$6,'UNKNOWN',$7,$8,$9)",
            report_id, company_id, period_id, payload_id, job_id, section,
            latest['report_version'] + 1 if latest else 1, latest['report_id'] if latest else None,
            _as_date(recs[0].get('published_at')))
        await conn.executemany(
            'INSERT INTO observations(observation_id,report_id,metric_id,value,unit,scale,currency,locator_json) '
            'VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb)',
            [(uuid4(), report_id, metrics[metric_key(r)], new[r['code']], r.get('unit'), r.get('scale'), r.get('currency'),
              json.dumps({k: v for k, v in (r.get('locator_json') or {}).items() if k not in _META_KEYS},
                         default=str)) for r in recs])
    return result


async def quarantine(conn, job_id, *, payload_id, reason_code: str, reasons: dict) -> None:
    await conn.execute("INSERT INTO quarantine_records(record_id,job_id,payload_id,entity_type,reason_code,status,"
                       "reasons) VALUES($1,$2,$3,'FINANCIAL_REPORT',$4,'PENDING',$5::jsonb)",
                       uuid4(), job_id, payload_id, reason_code, json.dumps(reasons, default=str))
