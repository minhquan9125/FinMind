"""Exact financial-only captures. Capture completion does not certify accounting basis."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import requests

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from backend.src.financial.exact_json import dumps, loads
from backend.src.financial import mapping
from backend.src.financial.health_store import MAP as HEALTH_MAP

SECTIONS={'INCOME_STATEMENT':'income_statement','BALANCE_SHEET':'balance_sheet',
          'CASH_FLOW':'cash_flow_statement','RATIO':'ratios'}
BASE_URL='https://iq.vietcap.com.vn/api/iq-insight-service/v1/company'
# Vietcap's internal company ID for ticker ICT is CTIN, including ratio rows without ticker.
PROVIDER_ORGAN_IDS={'ICT':'CTIN'}
UNKNOWN_FIELDS=['unit','currency','period_basis','period_start','period_end','statement_scope',
                'fiscal_year_end','fiscal_label_convention','comparison_basis','ratio_definition','audit_status']
ANALYSIS_CODES={code for codes in HEALTH_MAP.values() for code in codes}|{'NET_REVENUE','TOTAL_OPERATING_INCOME'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _integer(value):
    if isinstance(value,bool) or not isinstance(value,(int,Decimal,str)):
        raise ValueError('Invalid integral reporting metadata')
    if isinstance(value,str):
        if not re.fullmatch(r'\d+',value):
            raise ValueError('Invalid reporting integer string')
    elif isinstance(value,Decimal) and (not value.is_finite() or value!=value.to_integral_value()):
        raise ValueError('Nonintegral reporting metadata')
    return int(value)


def _numeric(value):
    return not isinstance(value,bool) and isinstance(value,(int,Decimal))


def decode_section(content, *, symbol, section):
    if section not in SECTIONS or not re.fullmatch(r'[A-Z]{3}',symbol):
        raise ValueError('Invalid capture identity')
    payload=loads(content.decode('utf-8-sig'))
    if not isinstance(payload,dict) or payload.get('successful') is not True:
        raise ValueError('Provider did not confirm success')
    data=payload.get('data')
    if section=='RATIO':
        if not isinstance(data,list):raise ValueError('Expected financial ratio list')
        groups={'ratios':data}
    else:
        if not isinstance(data,dict) or any(not isinstance(data.get(k),list) for k in ('quarters','years')):
            raise ValueError('Expected statement quarters and years')
        groups={k:data[k] for k in ('quarters','years')}
    rows=[]
    seen=set()
    for group,source_rows in groups.items():
        for source in source_rows:
            if not isinstance(source,dict):raise ValueError('Expected financial row object')
            if 'ticker' in source and source['ticker']!=symbol or 'organCode' in source and source['organCode'] not in (symbol,PROVIDER_ORGAN_IDS.get(symbol,symbol)):
                raise ValueError('Source company mismatch')
            year=_integer(source.get('yearReport',source.get('year')))
            quarter=_integer(source.get('quarter') if section=='RATIO' else source.get('lengthReport'))
            if not 1900<=year<=9998 or quarter not in (1,2,3,4,5):
                raise ValueError('Invalid financial period')
            if group=='quarters' and quarter==5 or group=='years' and quarter!=5:
                raise ValueError('Source period contradicts report group')
            period=f'{year}-YEAR' if quarter==5 else f'{year}-Q{quarter}'
            kind='YEAR' if quarter==5 else 'QUARTER'
            expected={'period_label':period,'period_type':kind,'source_report_group':group}
            if any(k in source and source[k]!=v for k,v in expected.items()):
                raise ValueError('Provider overwrites normalized period identity')
            if 'year' in source and _integer(source['year'])!=year:
                raise ValueError('Conflicting source reporting year')
            if section!='RATIO' and 'quarter' in source and source['quarter'] is not None and _integer(source['quarter'])!=quarter:
                raise ValueError('Conflicting source reporting quarter')
            if period in seen:raise ValueError('Duplicate financial period')
            if not any(_numeric(v) for k,v in source.items() if k not in mapping.META_KEYS):
                raise ValueError('Financial row has no numeric financial fields')
            seen.add(period)
            rows.append({**source,**expected,'year':year,'quarter':None if quarter==5 else quarter,
                'source_fields':dict(source),'published_at':source.get('publicDate'),
                'source_updated_at':source.get('updateDate')})
    if not rows:raise ValueError('Provider returned no financial data')
    return sorted(rows,key=lambda r:(r['year'],r['quarter'] or 5),reverse=True)


def _local_id(kind,*parts):
    digest=hashlib.sha256(dumps(list(parts)).encode('utf-8')).hexdigest()
    return 'local-'+kind+'-'+digest


def financial_records(symbol, profile, sections, *, dataset_version, receipts):
    industry=profile.get('industry')
    if industry not in ('BANK','TECH'):
        raise ValueError('Financial mapping requires an explicit supported industry')
    mapping_sha=hashlib.sha256(Path(mapping.__file__).read_bytes()).hexdigest()
    records=[]
    seen=set()
    for section,json_section in SECTIONS.items():
        receipt=receipts[section]
        field_map=mapping.INDUSTRY_SECTION_MAPS.get(industry,mapping.SECTION_MAPS).get(json_section,{})
        payload_id=_local_id('payload',symbol,section,receipt['url'],receipt['sha256'])
        for row in sections[section]:
            report_id=_local_id('report',payload_id,row['period_label'],industry,mapping_sha)
            for field,value in row.items():
                if field in mapping.META_KEYS or isinstance(value,bool) or not (_numeric(value) or value is None and field in field_map):
                    continue
                code=mapping.get_code(field,json_section,industry)
                identity=(row['period_label'],section,code)
                if identity in seen:raise ValueError('Raw fields collide on canonical financial metric')
                seen.add(identity)
                mapped='MAPPED' if field in field_map else 'UNMAPPED'
                locator=dict(source_field=field,source_section=json_section,dataset_version=dataset_version,
                    source_report_group=row['source_report_group'],source_url=receipt['url'],
                    raw_response_sha256=receipt['sha256'],response_path=receipt['path'],
                    received_at=receipt['received_at'],mapping_sha256=mapping_sha,mapping_status=mapped,
                    ratio_type=row.get('ratioType'),published_at=row.get('published_at'),
                    source_updated_at=row.get('source_updated_at'),unit_status='UNVERIFIED',period_basis='UNVERIFIED',
                    statement_scope='UNKNOWN',comparison_basis='UNKNOWN')
                records.append(dict(symbol=symbol,industry_type=industry,sector=profile.get('industry_name'),
                    period_code=row['period_label'],fiscal_year=row['year'],quarter=row['quarter'],
                    period_type=row['period_type'],statement_scope='UNKNOWN',audit_status='UNKNOWN',
                    published_at=row.get('published_at'),source_updated_at=row.get('source_updated_at'),
                    report_id=report_id,report_version=None,restated_from_id=None,
                    code=code,canonical_name=mapping.get_label_vi(code),section=section,value=value,
                    unit='SOURCE_NATIVE',scale=1,currency=None,locator_json=locator,mapping_status=mapped,
                    observation_id=_local_id('observation',report_id,field,code),payload_id=payload_id,
                    source_uri=receipt['url'],sha256=receipt['sha256'],source_name='VIETCAP_VCI',
                    approval_status='PENDING',storage_status='local_capture'))
    return records


def _write_json(path,value):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('x',encoding='utf-8') as stream:
        stream.write(dumps(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)


def capture_financial(symbols, output_root, profiles, session=None):
    symbols=list(symbols)
    if not symbols or len(set(symbols))!=len(symbols) or any(not isinstance(s,str) or not re.fullmatch(r'[A-Z]{3}',s) for s in symbols):
        raise ValueError('Expected distinct configured company symbols')
    if any(profiles.get(s,{}).get('industry') not in ('BANK','TECH') for s in symbols):
        raise ValueError('Missing supported financial company profile')
    root=Path(output_root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=root))
    own=session is None
    if own:session=requests.Session()
    if own:session.headers.update({'User-Agent':'FinMind financial-data validation/1.0','Accept':'application/json',
        'Origin':'https://trading.vietcap.com.vn','Referer':'https://trading.vietcap.com.vn/'})
    manifest=dict(schema_version='financial-only-v1',dataset_version=run.name,requested=symbols,
        started_at=_now(),run_dir=str(run),status='running',records_path=None,database_written=False,
        records_scope='financial_health_inputs',all_provider_fields_preserved=True,
        original_data_written=False,missing_financial_metadata=UNKNOWN_FIELDS,
        companies={s:dict(status='not_attempted',sections={k:dict(status='not_attempted') for k in SECTIONS}) for s in symbols})
    records=[]
    previous=None
    blocked=False
    try:
        for symbol in symbols:
            if blocked:break
            company=manifest['companies'][symbol]
            company['status']='running'
            decoded={}
            for section in SECTIONS:
                if blocked:break
                suffix='statistics-financial' if section=='RATIO' else 'financial-statement?section='+section
                url=f'{BASE_URL}/{symbol}/{suffix}'
                receipt=dict(status='failed',url=url,attempts=[])
                company['sections'][section]=receipt
                for attempt in range(1,3):
                    if previous is not None:
                        delay=2-(time.monotonic()-previous)
                        if delay>0:time.sleep(delay)
                    previous=time.monotonic()
                    entry=dict(attempt=attempt,url=url,received_at=_now())
                    try:
                        response=session.get(url,timeout=20,allow_redirects=False)
                    except requests.RequestException as exc:
                        entry['failure_class']=type(exc).__name__
                        receipt['attempts'].append(entry)
                        receipt.update(failure_class=entry['failure_class'])
                        continue
                    raw=response.content
                    path=run/f'{symbol}-{section}-{attempt}.response'
                    with path.open('xb') as stream:
                        stream.write(raw);stream.flush();os.fsync(stream.fileno())
                    entry.update(http_status=response.status_code,path=path.name,
                        sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
                    if response.headers.get('Retry-After'):
                        entry['retry_after']=str(response.headers['Retry-After'])[:256]
                    receipt['attempts'].append(entry)
                    receipt.update(entry)
                    if response.status_code in (401,403,429) or response.status_code>=500 and entry.get('retry_after'):
                        blocked=True;receipt['status']='blocked';break
                    if response.status_code>=500:continue
                    if response.status_code!=200:
                        receipt['failure_class']='HTTPError';break
                    try:
                        decoded[section]=decode_section(raw,symbol=symbol,section=section)
                    except (ValueError,UnicodeError) as exc:
                        receipt['failure_class']=type(exc).__name__;break
                    receipt.update(status='complete',rows=len(decoded[section]),
                        latest_period=decoded[section][0]['period_label'])
                    receipt.pop('failure_class',None)
                    break
            company['status']='failed'
            if len(decoded)==len(SECTIONS):
                try:
                    proposed=financial_records(symbol,profiles[symbol],decoded,dataset_version=run.name,receipts=company['sections'])
                except ValueError as exc:
                    company['failure_class']=type(exc).__name__
                    continue
                path=run/f'{symbol}-normalized.json'
                _write_json(path,dict(schema_version='financial-only-v1',symbol=symbol,profile=profiles[symbol],
                    financial_data={SECTIONS[k]:v for k,v in decoded.items()},
                    missing_financial_metadata=UNKNOWN_FIELDS,storage_status='local_capture'))
                selected=[row for row in proposed if row['mapping_status']=='MAPPED' and row['code'] in ANALYSIS_CODES]
                records.extend(selected)
                company.update(status='complete',normalized_path=path.name,observations=len(selected),source_metric_count=len(proposed))
        _write_json(run/'observations.json',records)
        manifest['records_path']='observations.json'
        complete=sum(c['status']=='complete' for c in manifest['companies'].values())
        manifest.update(status='blocked' if blocked else 'complete' if complete==len(symbols) else 'partial' if complete else 'failed',
            complete_companies=complete,observations=len(records))
    except OSError as exc:
        manifest.update(status='failed',failure_class=type(exc).__name__,records_path=None)
        for company in manifest['companies'].values():
            if company['status'] in ('complete','running'):
                company['status']='failed'
                company.pop('normalized_path',None)
    finally:
        manifest['finished_at']=_now()
        try:_write_json(run/'manifest.json',manifest)
        finally:
            if own:session.close()
    return manifest
