"""Independent offline contract tests for exact, isolated financial capture."""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from backend.src.financial import exact_json
from data_pipeline.financial_data import financial_capture as capture


SECTIONS=('INCOME_STATEMENT','BALANCE_SHEET','CASH_FLOW','RATIO')
FIELDS=dict(INCOME_STATEMENT='isa3',BALANCE_SHEET='bsa53',CASH_FLOW='cfa18',RATIO='roe')
PRECISE=Decimal('12345678901234567890.1234567890123456789')
PROFILES={'FPT':{'industry':'TECH'},'BID':{'industry':'BANK'},'CMG':{'industry':'TECH'}}


def payload(section,symbol='FPT'):
    row=dict(ticker=symbol,organCode=symbol,publicDate='2026-10-24T00:00:00',
             updateDate='2026-10-25T10:11:12',provider_note='unchanged raw text')
    row[FIELDS[section]]=PRECISE
    if section=='RATIO':
        row.update(year='2026',yearReport=2026,quarter=3,ratioType='RATIO_TTM')
        data=[row]
    else:
        row.update(yearReport=2026,lengthReport=3)
        annual={**row,'yearReport':2025,'lengthReport':5}
        data={'quarters':[row],'years':[annual]}
    return {'successful':True,'data':data}


def body(section,symbol='FPT'):
    return exact_json.dumps(payload(section,symbol)).encode('utf-8')


def sections():
    return {s:capture.decode_section(body(s),symbol='FPT',section=s) for s in SECTIONS}


def receipts():
    return {s:dict(url='https://source.example/FPT/financial?section='+s,
                   sha256=hashlib.sha256(body(s)).hexdigest(),path=f'raw/{s}.json',
                   received_at='2026-11-12T01:00:00+00:00') for s in SECTIONS}


def locate(run_dir,path):
    value=Path(path)
    return value if value.is_absolute() else Path(run_dir)/value


class FakeClock:
    def __init__(self):
        self.now=100.0
    def monotonic(self):
        return self.now
    def sleep(self,seconds):
        if seconds<0:
            raise AssertionError('Negative sleep')
        self.now+=seconds


class FakeResponse:
    def __init__(self,status_code=200,content=b'',headers=None):
        self.status_code=status_code
        self.content=content
        self.headers=headers or {}


class FakeSession:
    def __init__(self,clock,plans=None):
        self.clock=clock
        self.plans=deepcopy(plans or {})
        self.calls=[]
        self.closed=False
        self.headers={}
    def get(self,url,*,timeout,allow_redirects):
        self.calls.append(dict(url=url,timeout=timeout,allow_redirects=allow_redirects,at=self.clock.now))
        section='RATIO' if 'statistics-financial' in url else parse_qs(urlparse(url).query).get('section',[None])[0]
        if section not in SECTIONS:
            raise AssertionError('Unexpected financial URL: '+url)
        symbol=next((s for s in PROFILES if s in url),None)
        if symbol is None:
            raise AssertionError('No configured symbol in URL')
        plan=self.plans.get((symbol,section),[])
        item=plan.pop(0) if plan else FakeResponse(200,body(section,symbol))
        if isinstance(item,Exception):
            raise item
        return item
    def close(self):
        self.closed=True


@contextmanager
def clocked(clock):
    with patch.object(capture.time,'monotonic',clock.monotonic),patch.object(capture.time,'sleep',clock.sleep):
        yield


class DecodeFinancialSectionTests(unittest.TestCase):
    def test_ict_provider_internal_id_is_explicitly_bound_to_the_ticker(self):
        for section in SECTIONS:
            value=payload(section,'ICT')
            rows=value['data'] if section=='RATIO' else value['data']['quarters']+value['data']['years']
            for row in rows:
                row['organCode']='CTIN'
                if section=='RATIO':row.pop('ticker')
            decoded=capture.decode_section(exact_json.dumps(value).encode(),symbol='ICT',section=section)
            self.assertTrue(all(row['source_fields']['organCode']=='CTIN' for row in decoded))
            rows[0]['ticker']='FPT'
            with self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='ICT',section=section)
            rows[0]['ticker']='ICT';rows[0]['organCode']='BID'
            with self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='ICT',section=section)

    def test_statement_groups_preserve_exact_numbers_and_source_fields(self):
        raw=body('INCOME_STATEMENT')
        rows=capture.decode_section(raw,symbol='FPT',section='INCOME_STATEMENT')
        self.assertEqual(raw,body('INCOME_STATEMENT'))
        by_period={r['period_label']:r for r in rows}
        self.assertEqual(set(by_period),{'2026-Q3','2025-YEAR'})
        self.assertEqual(by_period['2026-Q3']['isa3'],PRECISE)
        self.assertEqual(by_period['2026-Q3']['source_report_group'],'quarters')
        self.assertEqual(by_period['2025-YEAR']['source_report_group'],'years')
        self.assertEqual(by_period['2025-YEAR']['period_type'],'YEAR')
        self.assertIsNone(by_period['2025-YEAR']['quarter'])
        self.assertEqual(by_period['2026-Q3']['published_at'],'2026-10-24T00:00:00')
        self.assertEqual(by_period['2026-Q3']['source_updated_at'],'2026-10-25T10:11:12')

    def test_ratio_year_group_retains_provider_quarter_and_ratio_type(self):
        value=payload('RATIO')
        value['data'][0]['quarter']=5
        rows=capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='RATIO')
        self.assertEqual(rows[0]['period_label'],'2026-YEAR')
        self.assertIsNone(rows[0]['quarter'])
        self.assertEqual(rows[0]['source_fields']['quarter'],5)
        self.assertEqual(rows[0]['source_fields']['year'],'2026')
        self.assertEqual(rows[0]['year'],2026)
        self.assertEqual(rows[0]['ratioType'],'RATIO_TTM')
        self.assertEqual(rows[0]['source_report_group'],'ratios')

    def test_present_ticker_and_organ_identity_must_both_match(self):
        for field in ['ticker','organCode']:
            value=payload('INCOME_STATEMENT')
            value['data']['quarters'][0][field]='BID'
            with self.subTest(field=field),self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='INCOME_STATEMENT')

    def test_reporting_year_and_quarter_do_not_truncate_invalid_numbers(self):
        for field,bad in [('yearReport',2026.5),('yearReport',True),('yearReport',1899),
                          ('yearReport',9999),('yearReport','2026.0'),('yearReport',None),
                          ('lengthReport',0),('lengthReport',6),('lengthReport',Decimal('1.5')),
                          ('lengthReport',True),('lengthReport',None)]:
            value=payload('INCOME_STATEMENT')
            value['data']['quarters'][0][field]=bad
            with self.subTest(field=field,bad=str(bad)),self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='INCOME_STATEMENT')

    def test_quarters_years_and_ratio_groups_validate_provider_period_codes(self):
        for section,group,field,bad in [('INCOME_STATEMENT','quarters','lengthReport',5),
                                      ('INCOME_STATEMENT','years','lengthReport',3),
                                      ('RATIO',None,'quarter',0),('RATIO',None,'quarter',6)]:
            value=payload(section)
            row=value['data'][0] if group is None else value['data'][group][0]
            row[field]=bad
            with self.subTest(section=section,group=group),self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section=section)

    def test_duplicate_periods_are_not_silently_overwritten(self):
        value=payload('INCOME_STATEMENT')
        value['data']['quarters'].append(deepcopy(value['data']['quarters'][0]))
        with self.assertRaises(ValueError):
            capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='INCOME_STATEMENT')

    def test_json_duplicate_keys_and_nonfinite_values_are_rejected(self):
        bad_bodies=[b'{"successful":true,"successful":false,"data":{}}']
        for bad in ['NaN','Infinity','-Infinity']:
            bad_bodies.append(('{"successful":true,"data":{"quarters":[{"yearReport":2026,"lengthReport":3,"isa3":'+bad+'}],"years":[]}}').encode())
        for raw in bad_bodies:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                capture.decode_section(raw,symbol='FPT',section='INCOME_STATEMENT')

    def test_false_empty_wrong_schema_and_metadata_only_success_are_not_data(self):
        values=[{'successful':False,'data':payload('INCOME_STATEMENT')['data']},
                {'successful':'true','data':payload('INCOME_STATEMENT')['data']},
                {'successful':True,'data':{'quarters':[],'years':[]}},
                {'successful':True,'data':[]},
                {'successful':True,'data':{'quarters':[{'ticker':'FPT','yearReport':2026,'lengthReport':3}],'years':[]}}]
        for value in values:
            with self.subTest(value=value),self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='INCOME_STATEMENT')

    def test_contradictory_reserved_normalized_identity_is_rejected(self):
        for field,bad in [('period_label','2025-Q1'),('period_type','YEAR'),('year',2025)]:
            value=payload('INCOME_STATEMENT')
            value['data']['quarters'][0][field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):
                capture.decode_section(exact_json.dumps(value).encode(),symbol='FPT',section='INCOME_STATEMENT')


class FinancialRecordTests(unittest.TestCase):
    def test_exact_records_keep_unverified_metadata_and_actual_source_provenance(self):
        values=sections()
        before=deepcopy(values)
        raw_receipts=receipts()
        rows=capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='capture-test',receipts=raw_receipts)
        self.assertEqual(values,before)
        revenue=next(r for r in rows if r['code']=='NET_REVENUE' and r['period_code']=='2026-Q3')
        self.assertEqual(Decimal(str(revenue['value'])),PRECISE)
        self.assertEqual(revenue['unit'],'SOURCE_NATIVE')
        self.assertEqual(revenue['scale'],1)
        self.assertIsNone(revenue['currency'])
        self.assertEqual(revenue['statement_scope'],'UNKNOWN')
        self.assertEqual(revenue['approval_status'],'PENDING')
        self.assertEqual(revenue['source_name'],'VIETCAP_VCI')
        self.assertEqual(revenue['source_uri'],raw_receipts['INCOME_STATEMENT']['url'])
        self.assertTrue(revenue['observation_id'].startswith('local-'))
        locator=revenue['locator_json']
        locator=json.loads(locator) if isinstance(locator,str) else locator
        self.assertEqual(locator['unit_status'],'UNVERIFIED')
        self.assertEqual(locator['period_basis'],'UNVERIFIED')
        self.assertEqual(locator['source_field'],'isa3')
        self.assertIn(raw_receipts['INCOME_STATEMENT']['sha256'],json.dumps(revenue,default=str))
        again=capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='capture-test',receipts=raw_receipts)
        self.assertEqual(rows,again)

    def test_unknown_numeric_fields_are_unmapped_and_strings_stay_in_raw(self):
        values=sections()
        values['INCOME_STATEMENT'][0].update(customField123=Decimal('1.25'),provider_comment='raw only',isa20=None)
        rows=capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='capture-test',receipts=receipts())
        def locator(row):
            value=row['locator_json']
            return json.loads(value) if isinstance(value,str) else value
        unknown=next(r for r in rows if locator(r)['source_field']=='customField123')
        self.assertEqual(unknown.get('mapping_status') or locator(unknown).get('mapping_status'),'UNMAPPED')
        self.assertFalse(any(locator(r)['source_field']=='provider_comment' for r in rows))
        for row in rows:
            if row['code']=='PROFIT_AFTER_TAX' and row['period_code']=='2026-Q3':
                self.assertIsNone(row['value'])

    def test_raw_aliases_cannot_collide_with_same_canonical_code(self):
        values=sections()
        values['RATIO'][0]['ROE']=Decimal('0.9')
        with self.assertRaises(ValueError):
            capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='capture-test',receipts=receipts())

    def test_unsupported_or_missing_industry_is_not_a_bank_fallback(self):
        for profile in [{},{'industry':'OTHER'}]:
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                capture.financial_records('FPT',profile,sections(),dataset_version='capture-test',receipts=receipts())

    def test_revised_raw_payload_changes_local_record_identity(self):
        values=sections()
        first=receipts()
        second=deepcopy(first)
        second['INCOME_STATEMENT']['sha256']='b'*64
        a=capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='same-run',receipts=first)
        b=capture.financial_records('FPT',PROFILES['FPT'],values,dataset_version='same-run',receipts=second)
        def revenue(rows):
            return next(r for r in rows if r['code']=='NET_REVENUE' and r['period_code']=='2026-Q3')
        self.assertNotEqual(revenue(a)['observation_id'],revenue(b)['observation_id'])


class CaptureFinancialTests(unittest.TestCase):
    def test_complete_capture_saves_raw_exactly_and_records_decimal_precision(self):
        clock=FakeClock()
        session=FakeSession(clock)
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'complete')
            self.assertEqual(len(session.calls),4)
            self.assertEqual(set(out['companies']['FPT']['sections']),set(SECTIONS))
            for section,receipt in out['companies']['FPT']['sections'].items():
                raw=locate(out['run_dir'],receipt['path']).read_bytes()
                self.assertEqual(raw,body(section))
                self.assertEqual(receipt['sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(receipt['http_status'],200)
            self.assertTrue(locate(out['run_dir'],out['companies']['FPT']['normalized_path']).is_file())
            rows=exact_json.loads(locate(out['run_dir'],out['records_path']).read_text(encoding='utf-8'))
            revenue=next(r for r in rows if r['code']=='NET_REVENUE' and r['period_code']=='2026-Q3')
            self.assertEqual(Decimal(str(revenue['value'])),PRECISE)
        self.assertFalse(session.closed)

    def test_incomplete_company_is_not_published_while_other_company_can_complete(self):
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','INCOME_STATEMENT'):[FakeResponse(200,b'{"successful":false,"data":{}}')]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT','CMG'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'partial')
            self.assertNotEqual(out['companies']['FPT']['status'],'complete')
            self.assertFalse(out['companies']['FPT'].get('normalized_path'))
            self.assertEqual(out['companies']['CMG']['status'],'complete')
            rows=exact_json.loads(locate(out['run_dir'],out['records_path']).read_text(encoding='utf-8'))
            self.assertEqual({r['symbol'] for r in rows},{'CMG'})

    def test_auth_and_rate_limit_status_stop_immediately_without_rotation(self):
        for code in [401,403,429]:
            clock=FakeClock()
            blocked=FakeResponse(code,b'{"error":"blocked"}',{'Retry-After':'120'})
            session=FakeSession(clock,{('FPT',s):[blocked] for s in SECTIONS})
            with self.subTest(code=code),tempfile.TemporaryDirectory() as folder,clocked(clock):
                out=capture.capture_financial(['FPT','CMG'],folder,PROFILES,session=session)
                self.assertEqual(out['status'],'blocked')
                self.assertEqual(len(session.calls),1)
                self.assertEqual(out['companies']['CMG']['status'],'not_attempted')
                statuses=[r['status'] for r in out['companies']['CMG']['sections'].values()]
                self.assertEqual(set(statuses),{'not_attempted'})

    def test_service_unavailable_retry_after_stops_run_without_immediate_retry(self):
        clock=FakeClock()
        blocked=FakeResponse(503,b'{"error":"temporarily unavailable"}',{'Retry-After':'120'})
        session=FakeSession(clock,{('FPT',s):[blocked] for s in SECTIONS})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT','CMG'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'blocked')
            self.assertEqual(len(session.calls),1)
            self.assertEqual(out['companies']['CMG']['status'],'not_attempted')
            self.assertTrue(all(r['status']=='not_attempted' for r in out['companies']['CMG']['sections'].values()))
            receipt=next(r for r in out['companies']['FPT']['sections'].values() if r.get('http_status')==503)
            self.assertEqual(locate(out['run_dir'],receipt['path']).read_bytes(),blocked.content)

    def test_server_retry_is_bounded_and_every_dispatch_is_spaced(self):
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','INCOME_STATEMENT'):[FakeResponse(503,b'first'),FakeResponse(503,b'second')]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            attempts=[x for x in session.calls if 'section=INCOME_STATEMENT' in x['url']]
            self.assertEqual(len(attempts),2)
            self.assertEqual(out['status'],'failed')
            self.assertTrue(all(b['at']-a['at']>=2 for a,b in zip(session.calls,session.calls[1:])))
            self.assertTrue(all(c['timeout']==20 and c['allow_redirects'] is False for c in session.calls))

    def test_network_retry_can_recover_without_real_sleep(self):
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','INCOME_STATEMENT'):[requests.ConnectionError('offline'),FakeResponse(200,body('INCOME_STATEMENT'))]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'complete')
            self.assertEqual(len(session.calls),5)
            self.assertTrue(all(b['at']-a['at']>=2 for a,b in zip(session.calls,session.calls[1:])))

    def test_prior_runs_are_immutable_and_run_directories_unique(self):
        clock=FakeClock()
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            first=capture.capture_financial(['FPT'],folder,PROFILES,session=FakeSession(clock))
            existing={str(p.relative_to(first['run_dir'])):p.read_bytes() for p in Path(first['run_dir']).rglob('*') if p.is_file()}
            second=capture.capture_financial(['FPT'],folder,PROFILES,session=FakeSession(clock))
            self.assertNotEqual(first['run_dir'],second['run_dir'])
            self.assertEqual(existing,{str(p.relative_to(first['run_dir'])):p.read_bytes() for p in Path(first['run_dir']).rglob('*') if p.is_file()})

    def test_only_owned_sessions_are_closed(self):
        clock=FakeClock()
        owned=FakeSession(clock)
        with tempfile.TemporaryDirectory() as folder,clocked(clock),patch.object(capture.requests,'Session',return_value=owned):
            out=capture.capture_financial(['FPT'],folder,PROFILES)
            self.assertEqual(out['status'],'complete')
        self.assertTrue(owned.closed)

    def test_invalid_http_200_body_is_saved_before_decode_failure(self):
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','INCOME_STATEMENT'):[FakeResponse(200,b'not json')]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            receipt=out['companies']['FPT']['sections']['INCOME_STATEMENT']
            self.assertEqual(out['status'],'failed')
            self.assertEqual(locate(out['run_dir'],receipt['path']).read_bytes(),b'not json')
            self.assertEqual(receipt['sha256'],hashlib.sha256(b'not json').hexdigest())
            self.assertFalse(out['companies']['FPT'].get('normalized_path'))

    def test_normalized_write_failure_is_manifested_without_false_publication(self):
        clock=FakeClock()
        session=FakeSession(clock)
        original_write=capture._write_json
        def write_with_failure(path,value):
            if Path(path).name=='FPT-normalized.json':
                raise OSError('injected normalized write failure')
            return original_write(path,value)
        with tempfile.TemporaryDirectory() as folder,clocked(clock),patch.object(capture,'_write_json',side_effect=write_with_failure):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'failed')
            self.assertEqual(out['companies']['FPT']['status'],'failed')
            self.assertFalse(out['companies']['FPT'].get('normalized_path'))
            self.assertIsNone(out['records_path'])
            self.assertTrue((Path(out['run_dir'])/'manifest.json').is_file())
        self.assertFalse(session.closed)

    def test_redirect_is_not_followed_or_accepted_as_valid_data(self):
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','INCOME_STATEMENT'):[FakeResponse(302,b'redirect',{'Location':'https://other.example'})]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'failed')
            self.assertTrue(all(c['allow_redirects'] is False for c in session.calls))
            self.assertFalse(any('other.example' in c['url'] for c in session.calls))

    def test_configuration_is_validated_before_any_request(self):
        for symbols,profiles in [(['FPT','FPT'],PROFILES),(['../FPT'],PROFILES),
                                 (['FPT'],{}),(['FPT'],{'FPT':{'industry':'OTHER'}})]:
            clock=FakeClock()
            session=FakeSession(clock)
            with self.subTest(symbols=symbols,profiles=profiles),tempfile.TemporaryDirectory() as folder,clocked(clock):
                with self.assertRaises(ValueError):
                    capture.capture_financial(symbols,folder,profiles,session=session)
                self.assertEqual(session.calls,[])

    def test_captured_snapshot_feeds_existing_report_without_false_certification(self):
        from backend.scripts.report_financial_health import build_report
        clock=FakeClock()
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=FakeSession(clock))
            rows=exact_json.loads(locate(out['run_dir'],out['records_path']).read_text(encoding='utf-8'))
            report=build_report(rows)
            self.assertEqual(report['analyses']['FPT']['period'],'2026-Q3')
            self.assertEqual(report['analyses']['FPT']['status'],'insufficient_data')
            self.assertIsNone(report['analyses']['FPT']['signals']['revenue_yoy_percent']['value'])

    def test_unmapped_canonical_name_is_preserved_but_not_published_as_health_input(self):
        ratio_payload=payload('RATIO')
        raw_row=ratio_payload['data'][0]
        raw_row['ROE']=raw_row.pop('roe')
        raw_body=exact_json.dumps(ratio_payload).encode('utf-8')
        decoded=sections()
        decoded['RATIO']=capture.decode_section(raw_body,symbol='FPT',section='RATIO')
        evidence=receipts()
        evidence['RATIO']['sha256']=hashlib.sha256(raw_body).hexdigest()
        full_records=capture.financial_records('FPT',PROFILES['FPT'],decoded,dataset_version='unmapped-case',receipts=evidence)
        unmapped=next(r for r in full_records if r['code']=='ROE')
        locator=unmapped['locator_json']
        locator=json.loads(locator) if isinstance(locator,str) else locator
        self.assertEqual(unmapped.get('mapping_status') or locator.get('mapping_status'),'UNMAPPED')
        self.assertEqual(locator['source_field'],'ROE')
        clock=FakeClock()
        session=FakeSession(clock,{('FPT','RATIO'):[FakeResponse(200,raw_body)]})
        with tempfile.TemporaryDirectory() as folder,clocked(clock):
            out=capture.capture_financial(['FPT'],folder,PROFILES,session=session)
            self.assertEqual(out['status'],'complete')
            rows=exact_json.loads(locate(out['run_dir'],out['records_path']).read_text(encoding='utf-8'))
            self.assertFalse(any(r['code']=='ROE' for r in rows))
            normalized=locate(out['run_dir'],out['companies']['FPT']['normalized_path']).read_text(encoding='utf-8')
            self.assertIn('"ROE"',normalized)
            receipt=out['companies']['FPT']['sections']['RATIO']
            self.assertEqual(locate(out['run_dir'],receipt['path']).read_bytes(),raw_body)


@contextmanager
def pipeline_fixture(status='complete'):
    name='data_pipeline.financial_data.run_financial_pipeline'
    collector=ModuleType('collect_financial_data')
    collector.TARGET_SYMBOLS=['FPT','BID']
    collector.COMPANIES_INFO={s:PROFILES[s] for s in collector.TARGET_SYMBOLS}
    constructor=Mock()
    collector.VietnamStockDataCollector=constructor
    operation=Mock(return_value=dict(status=status,run_dir='local-test-run',records_path='observations.json',companies={}))
    with patch.dict(sys.modules,{'collect_financial_data':collector,
                                'data_pipeline.financial_data.collect_financial_data':collector}):
        sys.modules.pop(name,None)
        module=importlib.import_module(name)
        with patch.object(capture,'capture_financial',operation),patch.object(module,'capture_financial',operation,create=True):
            yield module,constructor,operation


class FinancialPipelineCliTests(unittest.TestCase):
    def test_financial_only_does_not_instantiate_the_price_collector(self):
        with pipeline_fixture() as (module,constructor,operation):
            self.assertEqual(module.main(['--financial-only','--symbols','FPT','--output-root','chosen-output']),0)
            constructor.assert_not_called()
            operation.assert_called_once()

    def test_financial_partial_failed_and_blocked_exit_nonzero(self):
        for status in ['partial','failed','blocked']:
            with self.subTest(status=status),pipeline_fixture(status) as (module,constructor,operation):
                self.assertEqual(module.main(['--financial-only','--symbols','FPT']),1)
                constructor.assert_not_called()

    def test_default_branch_preserves_existing_collector_call(self):
        with pipeline_fixture() as (module,constructor,operation):
            self.assertIn(module.main(['--symbols','FPT']),[None,0])
            constructor.assert_called_once_with()
            constructor.return_value.run_all.assert_called_once_with(['FPT'])
            operation.assert_not_called()

    def test_output_root_without_financial_only_is_rejected(self):
        with pipeline_fixture() as (module,constructor,operation):
            with self.assertRaises(SystemExit) as caught:
                module.main(['--output-root','chosen-output'])
            self.assertNotEqual(caught.exception.code,0)
            constructor.assert_not_called()

    def test_module_entrypoint_propagates_financial_failure_exit_code(self):
        with pipeline_fixture('blocked') as (module,constructor,operation),patch.object(sys,'argv',['run_financial_pipeline','--financial-only','--symbols','FPT']):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_module(module.__name__,run_name='__main__')
            self.assertEqual(caught.exception.code,1)
            constructor.assert_not_called()
