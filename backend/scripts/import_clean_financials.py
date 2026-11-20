"""Import FinancialCleaner JSON into ERD tables; default is offline dry-run."""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'data_pipeline/FinancialCleaner'))
from cleaner import codec
from cleaner.core import SECTIONS, validate_symbol
from cleaner.mapping import load_mapping
from ingest_to_supabase import parse_period, stable_id, verify_schema

SECTION = {'balance_sheet': 'BALANCE_SHEET', 'income_statement': 'INCOME_STATEMENT',
           'cash_flow_statement': 'CASH_FLOW', 'ratios': 'RATIO'}


def read_input(path):
    raw = path.read_bytes()
    data = codec.loads(raw.decode('utf-8-sig'))
    symbol = validate_symbol(data['mã_chứng_khoán'])
    if symbol != path.parent.name:
        raise ValueError('Symbol does not match input folder')
    maps, _, _ = load_mapping(data['ngành'])
    seen = set()
    values = []
    for section, vietnamese in SECTIONS.items():
        for row in data['báo_cáo_tài_chính'][vietnamese]:
            period = row['kỳ_báo_cáo']
            year, quarter, kind, *_ = parse_period(period)
            if year != row['năm'] or quarter != row['quý'] or kind != {'Quý': 'QUARTER', 'Năm': 'YEAR'}[row['loại_kỳ']]:
                raise ValueError(f'Invalid period: {symbol}/{period}')
            for metric in row['chỉ_tiêu']:
                code, raw_key = metric['mã_chuẩn'], metric['trường_gốc']
                if maps[section].get(raw_key) != code or len(code) > 100:
                    raise ValueError(f'Metric mapping mismatch: {symbol}/{code}')
                identity = (period, section, code)
                if identity in seen:
                    raise ValueError(f'Duplicate metric: {identity}')
                seen.add(identity)
                original = metric['giá_trị']
                if isinstance(original, bool):
                    raise ValueError('Boolean financial value')
                value = Decimal(str(original))
                if not value.is_finite():
                    raise ValueError('Nonfinite financial value')
                values.append((period, section, metric, value))
    if not values:
        raise ValueError(f'Empty input: {symbol}')
    return {'path': path, 'data': data, 'values': values, 'digest': hashlib.sha256(raw).hexdigest(),
            'symbol': symbol, 'raw': raw.decode('utf-8-sig')}


async def ensure_company(conn, data):
    """Reuse company identity and fill only NULL/blank profile fields from clean source."""
    symbol = data['mã_chứng_khoán']
    companies = await conn.fetch('SELECT company_id FROM companies WHERE symbol=$1', symbol)
    if len(companies) > 1:
        raise ValueError(f'Duplicate company: {symbol}')
    company_id = companies[0]['company_id'] if companies else stable_id('company', symbol)
    profile = (data['tên_doanh_nghiệp'], data['ngành'], data['tên_ngành'], data['sàn'])
    if not companies:
        await conn.execute('INSERT INTO companies(company_id,symbol,company_name,industry_type,sector,exchange,is_active) VALUES($1,$2,$3,$4,$5,$6,true)',
                           company_id, symbol, *profile)
    else:
        await conn.execute('''UPDATE public.companies SET
            company_name=CASE WHEN NULLIF(btrim(company_name),'') IS NULL THEN NULLIF(btrim($2),'') ELSE company_name END,
            industry_type=CASE WHEN NULLIF(btrim(industry_type),'') IS NULL THEN NULLIF(btrim($3),'') ELSE industry_type END,
            sector=CASE WHEN NULLIF(btrim(sector),'') IS NULL THEN NULLIF(btrim($4),'') ELSE sector END,
            exchange=CASE WHEN NULLIF(btrim(exchange),'') IS NULL THEN NULLIF(btrim($5),'') ELSE exchange END
            WHERE company_id=$1 AND (
                (NULLIF(btrim(company_name),'') IS NULL AND NULLIF(btrim($2),'') IS NOT NULL) OR
                (NULLIF(btrim(industry_type),'') IS NULL AND NULLIF(btrim($3),'') IS NOT NULL) OR
                (NULLIF(btrim(sector),'') IS NULL AND NULLIF(btrim($4),'') IS NOT NULL) OR
                (NULLIF(btrim(exchange),'') IS NULL AND NULLIF(btrim($5),'') IS NOT NULL))''', company_id, *profile)
    return company_id


async def apply_one(conn, item):
    data, symbol, digest = item['data'], item['symbol'], item['digest']
    source_name = data['nguồn_dữ_liệu'].get('nguồn_tài_chính') or 'UNKNOWN'
    source_id = stable_id('source', source_name)
    await conn.execute("INSERT INTO sources(source_id,name,source_type,approval_status,scope_note,is_enabled) VALUES($1,$2,'FINANCIAL_DATA','PENDING',$3,false) ON CONFLICT(source_id) DO NOTHING",
                       source_id, source_name, 'FinancialCleaner JSON; native units and reporting basis unverified')
    job_id, payload_id = stable_id('clean-job', symbol, digest), stable_id('clean-payload', symbol, digest)
    await conn.execute("INSERT INTO ingestion_jobs(job_id,source_id,trigger_type,status,schema_version,started_at,finished_at,records_ok,records_quarantined) VALUES($1,$2,'BATCH','SUCCEEDED','clean-v1',now(),now(),$3,0) ON CONFLICT(job_id) DO NOTHING",
                       job_id, source_id, len(item['values']))
    await conn.execute('INSERT INTO raw_payloads(payload_id,job_id,source_uri,sha256,payload,stored_at) VALUES($1,$2,$3,$4,$5::jsonb,now()) ON CONFLICT(payload_id) DO NOTHING',
                       payload_id, job_id, item['path'].relative_to(ROOT).as_posix(), digest, item['raw'])
    company_id = await ensure_company(conn, data)
    reports = {}
    for period in sorted({v[0] for v in item['values']}):
        year, quarter, kind, start, end = parse_period(period)
        periods = await conn.fetch('SELECT period_id FROM reporting_periods WHERE period_code=$1', period)
        if len(periods) > 1:
            raise ValueError(f'Duplicate period: {period}')
        period_id = periods[0]['period_id'] if periods else stable_id('period', period)
        if not periods:
            await conn.execute('INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,start_date,end_date) VALUES($1,$2,$3,$4,$5,$6,$7)',
                               period_id, period, year, quarter, kind, start, end)
        # Immutable report version per exact source file. No overwrite of older reports.
        report_id = stable_id('clean-report', symbol, period, digest)
        reports[period] = report_id
        await conn.execute("INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,statement_scope,audit_status,report_version) VALUES($1,$2,$3,$4,$5,'UNKNOWN','UNKNOWN',1) ON CONFLICT(report_id) DO NOTHING",
                           report_id, company_id, period_id, payload_id, job_id)
    observation_rows = []
    metric_rows = {}
    for period, section, metric, value in item['values']:
        code = metric['mã_chuẩn']
        metric_id = stable_id('metric', data['ngành'], SECTION[section], code)
        # Cleaner explicitly preserves source units, but does not certify VND/%/YTD.
        metric_rows[metric_id] = (metric_id, code, metric['tên_chỉ_tiêu'], SECTION[section], data['ngành'])
        locator = {'source_file': item['path'].relative_to(ROOT).as_posix(), 'file_sha256': digest,
                   'source_sha256': data['nguồn_dữ_liệu'].get('sha256_nguồn'),
                   'mapping_sha256': data['nguồn_dữ_liệu'].get('sha256_mapping'),
                   'source_section': section, 'source_field': metric['trường_gốc'], 'period_code': period,
                   'metric_code': code, 'period_basis': 'UNVERIFIED', 'unit_status': 'UNVERIFIED'}
        observation_rows.append((stable_id('observation', reports[period], metric_id), reports[period], metric_id, value, codec.dumps(locator)))
    await conn.executemany("INSERT INTO metrics(metric_id,code,canonical_name,section,default_unit,industry_scope,mapping_status) VALUES($1,$2,$3,$4,'SOURCE_NATIVE',$5,'MAPPED') ON CONFLICT(metric_id) DO NOTHING", list(metric_rows.values()))
    await conn.executemany("INSERT INTO observations(observation_id,report_id,metric_id,value,unit,scale,currency,locator_json) VALUES($1,$2,$3,$4,'SOURCE_NATIVE',1,NULL,$5::jsonb) ON CONFLICT(observation_id) DO NOTHING", observation_rows)
    # Exact value and locator comparison catches precision loss and ID conflicts.
    stored = await conn.fetch('SELECT observation_id,value,locator_json FROM observations WHERE report_id=ANY($1::uuid[])', list(reports.values()))
    actual = {r['observation_id']: (r['value'], codec.loads(r['locator_json'])) for r in stored}
    expected = {r[0]: (r[3], codec.loads(r[4])) for r in observation_rows}
    if actual != expected:
        raise ValueError(f'Exact DB verification failed: {symbol}')
    return len(reports), len(observation_rows)


async def run(args):
    paths = sorted((ROOT / 'data_pipeline/FinancialCleaner/data').glob('*/tai_chinh_clean.json'))
    if args.symbol:
        wanted = set(args.symbol)
        paths = [p for p in paths if p.parent.name in wanted]
        if wanted != {p.parent.name for p in paths}:
            raise ValueError('Missing input symbols')
    items = [read_input(p) for p in paths]
    if not items:
        raise ValueError('No input files')
    for item in items:
        print('PLAN', item['symbol'], 'periods', len({v[0] for v in item['values']}), 'observations', len(item['values']), flush=True)
    if not (args.apply or args.rollback):
        print('DRY_RUN_ONLY; units/scope/period basis remain unverified')
        return
    import asyncpg
    from src.core.config import get_settings
    conn = await asyncpg.connect(get_settings().database_url, ssl='require', statement_cache_size=0, timeout=25)
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute('SELECT pg_advisory_xact_lock(167217)')
        if args.companies_only:
            for item in items:
                await ensure_company(conn, item['data'])
            if args.rollback:
                await tx.rollback()
                print('COMPANY_PROFILES_ROLLED_BACK', flush=True)
            else:
                await tx.commit()
                print('COMPANY_PROFILES_COMMITTED', flush=True)
            return
        await verify_schema(conn)
        precise = await conn.fetchval("SELECT numeric_scale IS NULL FROM information_schema.columns WHERE table_schema='public' AND table_name='observations' AND column_name='value'")
        code_width = await conn.fetchval("SELECT character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name='metrics' AND column_name='code'")
        if not precise or (code_width is not None and code_width < 100):
            if not args.allow_schema_widening:
                raise ValueError('Source exceeds value precision / metric code width; apply reviewed widening migration first')
            await conn.execute('ALTER TABLE public.observations ALTER COLUMN value TYPE numeric')
            await conn.execute('ALTER TABLE public.metrics ALTER COLUMN code TYPE varchar(100)')
        for item in items:
            counts = await apply_one(conn, item)
            print('VERIFIED', item['symbol'], 'reports', counts[0], 'observations', counts[1], flush=True)
        # Repeat the exact input in the same transaction to prove idempotent IDs/counts.
        before = await conn.fetchrow('SELECT (SELECT count(*) FROM observations) AS o,(SELECT count(*) FROM financial_reports) AS r')
        for item in items:
            await apply_one(conn, item)
        after = await conn.fetchrow('SELECT (SELECT count(*) FROM observations) AS o,(SELECT count(*) FROM financial_reports) AS r')
        if before != after:
            raise ValueError('Rerun inserted duplicates')
        print('RERUN_NO_DUPLICATES', dict(after), flush=True)
        if args.rollback:
            await tx.rollback()
            print('ROLLED_BACK', flush=True)
        else:
            await tx.commit()
            print('COMMITTED', flush=True)
    except BaseException:
        await tx.rollback()
        raise
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', nargs='+')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--rollback', action='store_true')
    parser.add_argument('--allow-schema-widening', action='store_true')
    parser.add_argument('--companies-only', action='store_true', help='Only fill missing company profile fields; no financial/schema writes')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        print('IMPORT_FAILED', type(exc).__name__, str(exc), file=sys.stderr)
        sys.exit(1)
