"""Real-export boundary: metadata is evidence, never inferred from section names."""
from copy import deepcopy
import json
import unittest

from backend.src.financial.health_store import canonical_rows
from backend.scripts.report_financial_health import build_report


def record(code='NET_REVENUE', section='INCOME_STATEMENT', *, symbol='FPT',
           industry='TECH', period='2026-Q2', verified=True, **changes):
    year = int(period[:4])
    locator = dict(source_field='isa3', source_section='income_statement', dataset_version='audit-v1')
    if verified:
        locator.update(period_basis='QUARTER', statement_scope='CONSOLIDATED',
                       comparison_basis='reviewed-comparable-v1', fiscal_year_end='12-31',
                       fiscal_label_convention='CALENDAR',
                       period_start=f'{year}-04-01', period_end=f'{year}-06-30', unit_status='VERIFIED')
        if section=='RATIO':
            locator.update(source_field=code.lower(),source_section='ratios',period_basis='TTM',
                           period_start=f'{year-1}-07-01',ratio_definition='verified-TTM-definition-v1')
    row = dict(symbol=symbol, industry_type=industry, sector='TECH' if industry=='TECH' else 'BANK',
               period_code=period, fiscal_year=year, quarter=2, period_type='QUARTER',
               start_date=f'{year}-04-01', end_date=f'{year}-06-30',
               statement_scope=section, audit_status='UNKNOWN', published_at=f'{year}-08-01',
               report_id=f'report-{symbol}-{period}-{section}', report_version=1, restated_from_id=None,
               code=code, section=section, value='120', unit='VND', scale=1, currency='VND',
               locator_json=json.dumps(locator), observation_id=f'obs-{symbol}-{period}-{code}-{section}',
               payload_id=f'payload-{symbol}-{period}', source_uri=f'{symbol}.json#financial_data',
               sha256='a'*64, source_name='VIETCAP_VCI', approval_status='APPROVED')
    row.update(changes)
    return row


class FinancialStoreTests(unittest.TestCase):
    def test_verified_metadata_and_provenance_map_to_canonical_fact(self):
        rows = canonical_rows([record()])
        self.assertEqual(len(rows),1)
        row = rows[0]
        self.assertEqual(row['metric'],'revenue')
        self.assertEqual(row['symbol'],'FPT')
        self.assertEqual(row['period'],'2026-Q2')
        self.assertEqual(row['scope'],'CONSOLIDATED')
        self.assertEqual(row['basis'],'QUARTER')
        self.assertEqual(row['unit'],'VND')
        self.assertEqual(row['source_uri'],'FPT.json#financial_data')
        self.assertEqual(row['source_sha256'],'a'*64)
        self.assertEqual(row['fiscal_label_convention'],'CALENDAR')
        noncalendar=record()
        locator=json.loads(noncalendar['locator_json'])
        locator.update(fiscal_year_end='03-31',fiscal_label_convention='END_YEAR',
                       period_start='2025-07-01',period_end='2025-09-30')
        noncalendar['locator_json']=json.dumps(locator)
        mapped=canonical_rows([noncalendar])[0]
        self.assertEqual(mapped['fiscal_label_convention'],'END_YEAR')
        self.assertEqual(mapped['fiscal_year_end'],'03-31')

    def test_legacy_section_and_importer_unit_are_not_certified_metadata(self):
        row = canonical_rows([record(verified=False)])[0]
        self.assertNotIn(row['scope'], {'CONSOLIDATED','SEPARATE'})
        self.assertNotIn(row['basis'], {'QUARTER','YEAR','YTD'})
        self.assertNotEqual(row['unit'],'VND')
        self.assertEqual(row['raw_unit'],'VND')

    def test_native_ratio_does_not_gain_percent_unit_or_multiplication(self):
        row = canonical_rows([record('ROE','RATIO',unit='SOURCE_NATIVE',currency=None,value='0.22',verified=False)])[0]
        self.assertEqual(row['metric'],'roe')
        self.assertNotEqual(row['unit'],'PERCENT')
        self.assertEqual(str(row['value']),'0.22')

    def test_verified_ratio_definition_is_carried_from_locator(self):
        row = canonical_rows([record('ROE','RATIO',unit='PERCENT',currency=None,value='22')])[0]
        self.assertEqual(row['unit'],'PERCENT')
        self.assertEqual(row['basis'],'TTM')
        self.assertEqual(row['period_start'],'2025-07-01')
        self.assertEqual(row['ratio_definition'],'verified-TTM-definition-v1')

    def test_wrong_section_cannot_supply_cashflow_or_revenue(self):
        rows = canonical_rows([record('CASH_FLOW_OPERATING','INCOME_STATEMENT'),
                               record('NET_REVENUE','BALANCE_SHEET')])
        self.assertEqual(rows,[])

    def test_bank_uses_operating_income_and_never_tech_revenue(self):
        rows = canonical_rows([record('TOTAL_OPERATING_INCOME',industry='BANK',symbol='BID'),
                               record('NET_REVENUE',industry='BANK',symbol='BID')])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['metric'],'revenue')
        self.assertEqual(rows[0]['industry'],'BANK')

    def test_report_uses_current_period_and_preserves_original_snapshot(self):
        records = [record(value='120'), record(period='2025-Q2',value='100')]
        before = deepcopy(records)
        out = build_report(records)
        self.assertEqual(records,before)
        self.assertEqual(out['analyses']['FPT']['period'],'2026-Q2')
        self.assertEqual(out['analyses']['FPT']['signals']['revenue_yoy_percent']['value'],'20.0000')
        self.assertIn('FPT',out['peers'])

    def test_legacy_export_report_is_honestly_insufficient(self):
        out = build_report([record(verified=False),record(period='2025-Q2',verified=False)])
        analysis = out['analyses']['FPT']
        self.assertEqual(analysis['status'],'insufficient_data')
        self.assertIsNone(analysis['signals']['revenue_yoy_percent']['value'])
        self.assertEqual(out['peers']['FPT']['status'],'insufficient_data')
        self.assertIn('FPT.json#financial_data',json.dumps(out,default=str))

    def test_requested_period_does_not_fall_back_to_last_available(self):
        out = build_report([record(),record(period='2025-Q2')],period='2026-Q3')
        analysis = out['analyses']['FPT']
        self.assertEqual(analysis['period'],'2026-Q3')
        self.assertEqual(analysis['status'],'insufficient_data')
        self.assertIsNone(analysis['signals']['revenue_yoy_percent']['value'])

    def test_legacy_year_period_maps_without_overriding_newer_quarter(self):
        annual=record(period='2025-YEAR',verified=False,period_type='YEAR',quarter=None,
                      start_date='2025-01-01',end_date='2025-12-31')
        mapped=canonical_rows([annual])[0]
        self.assertEqual(mapped['period'],'2025')
        self.assertEqual(mapped['source_period'],'2025-YEAR')
        out=build_report([annual,record(verified=False)])
        self.assertEqual(out['analyses']['FPT']['period'],'2026-Q2')
