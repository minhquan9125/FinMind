"""Import FinancialCleaner JSON into ERD tables; default is offline dry-run."""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
import hashlib
import json
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
from src.financial.import_plan import load_rules, load_workbook_approved_overrides, make_plan, require_frozen_configuration, release_values

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


async def apply_one(conn, item, financial_plan=None):
    data, symbol, digest = item['data'], item['symbol'], item['digest']
    source_name = data['nguồn_dữ_liệu'].get('nguồn_tài_chính') or 'UNKNOWN'
    source_id = stable_id('source', source_name)
    await conn.execute("INSERT INTO sources(source_id,name,source_type,approval_status,scope_note,is_enabled) VALUES($1,$2,'FINANCIAL_DATA','PENDING',$3,false) ON CONFLICT(source_id) DO NOTHING",
                       source_id, source_name, 'FinancialCleaner JSON; native units and reporting basis unverified')
    version = financial_plan['mapping_manifest_sha256'] if financial_plan else None
    version_args = (version,) if version else ()
    job_id, payload_id = stable_id('clean-job', symbol, digest, *version_args), stable_id('clean-payload', symbol, digest, *version_args)
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
        report_id = stable_id('clean-report', symbol, period, digest, *version_args)
        reports[period] = report_id
        await conn.execute("INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,statement_scope,audit_status,report_version) VALUES($1,$2,$3,$4,$5,'UNKNOWN','UNKNOWN',1) ON CONFLICT(report_id) DO NOTHING",
                           report_id, company_id, period_id, payload_id, job_id)
    observation_rows = []
    metric_rows = {}
    decisions = ({(e['period'],e['section'],e['code']):e for e in financial_plan['entries']}
                 if financial_plan else {})
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
        decision = decisions.get((period,section,code))
        unit, scale, currency = 'SOURCE_NATIVE', 1, None
        if financial_plan:
            if decision is None or Decimal(decision['source_value']) != value:
                raise ValueError('Import plan differs from current observation')
            locator['financial_mapping'] = decision.get('financial_mapping') or {
                'schema_version':'financial-mapping-locator-v1',
                'config_version_id':financial_plan['config_version_id'],
                'mapping_manifest_sha256':version,'status':'UNVERIFIED','reason':decision['reason']}
            if decision['status'] in ('VERIFIED_SNAPSHOT','WORKBOOK_APPROVED'):
                unit,scale,currency=decision['unit'],decision['scale'],decision['currency']
                locator.update(unit_status=decision['status'],period_basis='POINT_IN_TIME')
        observation_rows.append((stable_id('observation', reports[period], metric_id), reports[period], metric_id,
                                 value, codec.dumps(locator),unit,scale,currency))
    await conn.executemany("INSERT INTO metrics(metric_id,code,canonical_name,section,default_unit,industry_scope,mapping_status) VALUES($1,$2,$3,$4,'SOURCE_NATIVE',$5,'MAPPED') ON CONFLICT(metric_id) DO NOTHING", list(metric_rows.values()))
    await conn.executemany("INSERT INTO observations(observation_id,report_id,metric_id,value,locator_json,unit,scale,currency) VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8) ON CONFLICT(observation_id) DO NOTHING", observation_rows)
    # Exact value and locator comparison catches precision loss and ID conflicts.
    stored = await conn.fetch('SELECT observation_id,value,locator_json,unit,scale,currency FROM observations WHERE report_id=ANY($1::uuid[])', list(reports.values()))
    actual = {r['observation_id']: (r['value'], codec.loads(r['locator_json']),r['unit'],r['scale'],r['currency']) for r in stored}
    expected = {r[0]: (r[3], codec.loads(r[4]),r[5],r[6],r[7]) for r in observation_rows}
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
    rules_path=getattr(args,'financial_rules',None)
    bundle=load_rules(Path(rules_path)) if rules_path else None
    workbook_overrides = load_workbook_approved_overrides(Path(args.workbook_overrides)) if args.workbook_overrides else None
    plans=[make_plan(item,bundle,workbook_overrides) for item in items] if bundle else None
    if plans:
        output=Path(getattr(args,'plan_out',None) or ROOT/'outputs/financial-import-plan/plan.json')
        if not output.is_absolute():
            output=ROOT/output
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({'database_writes':False,'plans':plans},ensure_ascii=False,indent=2),encoding='utf-8')
        draft={'status':'DRAFT_NOT_REGISTERED_OR_FROZEN','config_version_id':plans[0]['config_version_id'],
               'version_label':'financial-bs-v1','system_configs':release_values(bundle)}
        output.with_name('configuration-draft.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2),encoding='utf-8')
        release_manifest={
            'schema_version':'financial-controlled-release-v1',
            'status':'DRAFT_NOT_REGISTERED_OR_FROZEN',
            'database_writes':False,
            'production_enabled':False,
            'source_family':'clean',
            'mapping_manifest_sha256':plans[0]['mapping_manifest_sha256'],
            'workbook_overrides':bool(workbook_overrides),
            'workbook_override_status':'WORKBOOK_APPROVED' if workbook_overrides else None,
            'plan_path':str(output.relative_to(ROOT)).replace('\\','/'),
            'configuration_path':str(output.with_name('configuration-draft.json').relative_to(ROOT)).replace('\\','/'),
            'corpus_mutation':'FORBIDDEN_CORPUS_V2_IS_FROZEN',
        }
        output.with_name('controlled-release-manifest.json').write_text(
            json.dumps(release_manifest,ensure_ascii=False,indent=2),encoding='utf-8'
        )
        total=sum(len(p['entries']) for p in plans)
        verified=sum(p['counts'].get('VERIFIED_SNAPSHOT',0) for p in plans)
        lines=['# Kế hoạch nhập theo bộ quy tắc tài chính', '',
               f'Đã kiểm tra {len(plans)} công ty, {total} giá trị. Đủ bằng chứng: {verified}; giữ nguồn chưa xác minh: {total-verified}.',
               'Không kết nối hoặc ghi database khi chạy mặc định. Không sửa số liệu đầu vào.', '',
               '| Công ty | Đủ bằng chứng | Chưa có quy tắc | Có quy tắc nhưng kỳ chưa được đối chiếu |',
               '|---|---:|---:|---:|']
        for p in plans:
            lines.append(f"| {p['symbol']} | {p['counts'].get('VERIFIED_SNAPSHOT',0)} | {p['reasons'].get('NO_REVIEWED_RULE',0)} | {p['reasons'].get('PERIOD_NOT_IN_VERIFIED_SAMPLES',0)} |")
        lines += ['', 'Chi tiết từng giá trị và các lý do khác (file thay đổi, số thay đổi, sai nguồn) nằm trong plan.json.',
                  'configuration-draft.json chứa bản nháp đủ bốn nhóm cấu hình; chưa đăng ký, đóng băng hoặc kích hoạt trên Supabase.',
                  'Các số chưa xác minh vẫn giữ nguyên với SOURCE_NATIVE; không bỏ dữ liệu, không thay bằng 0, không tự suy đơn vị.',
                  'Nhánh nhập mới tạo ID report/job/payload theo cả hash nguồn và hash mapping, rồi gắn config/rule/evidence vào locator.',
                  'Dữ liệu cũ giữ nguyên. Vì bản mới tồn tại song song bản cũ, reader phải chọn phiên bản/config rõ ràng trước khi triển khai ghi chung; không cộng cả hai bản.',
                  'report.statement_scope vẫn UNKNOWN cho báo cáo chứa nhiều loại số chưa kiểm chứng; scope và ngày chốt đã xác minh nằm ở locator của từng số.',
                  'Mã metric và tên hiện có không đổi toàn cục; canonical_metric_code và hash định nghĩa nằm trong financial_mapping.',
                  'Để ghi cần cấu hình cùng ID đã đóng băng, đủ bốn nhóm system_configs khớp và chính sách VERIFIED_SNAPSHOT_IMPORT rõ ràng. Chưa thực hiện bước này.',
                  'Kiểm thử nhập lặp và xung đột dùng DB mô phỏng, không phải xác nhận đã chạy ghi/rollback trên Supabase thật.']
        output.with_name('Ke_hoach_nhap.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        for p in plans:print('FINANCIAL_RULE_PLAN',p['symbol'],p['counts'],p['reasons'],flush=True)
    for item in items:
        print('PLAN', item['symbol'], 'periods', len({v[0] for v in item['values']}), 'observations', len(item['values']), flush=True)
    if not (args.apply or args.rollback):
        print('DRY_RUN_ONLY; verified and workbook-approved decisions are limited to listed snapshots; other observations remain native/unverified')
        return
    import asyncpg
    from src.core.config import get_settings
    conn = await asyncpg.connect(get_settings().database_url, ssl='require', statement_cache_size=0, timeout=25)
    tx = conn.transaction(isolation='repeatable_read')
    await tx.start()
    try:
        if plans:
            if args.companies_only or args.allow_schema_widening:
                raise ValueError('Financial rule import cannot change profiles only or widen the shared schema')
            await require_frozen_configuration(conn,plans,bundle)
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
        for i,item in enumerate(items):
            counts = await apply_one(conn, item,plans[i] if plans else None)
            print('VERIFIED', item['symbol'], 'reports', counts[0], 'observations', counts[1], flush=True)
        # Repeat the exact input in the same transaction to prove idempotent IDs/counts.
        before = await conn.fetchrow('SELECT (SELECT count(*) FROM observations) AS o,(SELECT count(*) FROM financial_reports) AS r')
        for i,item in enumerate(items):
            await apply_one(conn, item,plans[i] if plans else None)
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
    parser.add_argument('--financial-rules', help='Reviewed source-rule package; writes also require a matching frozen DB configuration')
    parser.add_argument('--plan-out', help='Write the offline financial decision plan to this JSON file')
    parser.add_argument('--workbook-overrides', help='Approved workbook unit mappings for the controlled offline release')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        print('IMPORT_FAILED', type(exc).__name__, str(exc), file=sys.stderr)
        sys.exit(1)
