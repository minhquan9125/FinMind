"""Independent acceptance tests for financial facts and comparable company signals."""
from copy import deepcopy
import calendar
from decimal import Decimal
import json
import unittest

from backend.src.financial.health import analyze_company


def fact(metric, value, period='2026-Q2', **changes):
    year = int(period[:4])
    instant = metric in {'assets', 'equity', 'liabilities'}
    ratio = metric in {'roe', 'roa', 'nim', 'npl', 'cost_to_income'}
    annual = '-Q' not in period
    quarter = None if annual else int(period[-1])
    end_month = 12 if annual else quarter*3
    end = f'{year}-{end_month:02d}-{calendar.monthrange(year,end_month)[1]}'
    start = end if instant else f'{year}-01-01' if annual else f'{year}-{end_month-2:02d}-01'
    if ratio:
        start = f'{year if end_month==12 else year-1}-{end_month%12+1:02d}-01'
    row = dict(symbol='FPT', industry='TECH', period=period, metric=metric, value=value,
               unit='PERCENT' if ratio else 'VND', scale=1, currency=None if ratio else 'VND',
               basis='INSTANT' if instant else 'TTM' if ratio else 'YEAR' if annual else 'QUARTER',
               scope='CONSOLIDATED', comparison_basis='reviewed-comparable-v1',
               fiscal_year_end='12-31', period_start=start, period_end=end,
               published_at=f'{year}-08-01' if not annual else f'{year+1}-03-01',
               observation_id=f'obs-{period}-{metric}', payload_id=f'payload-{period}',
               source_name='VERIFIED_FINANCIAL', source_uri=f'https://issuer.example/{period}.pdf',
               source_sha256='a'*64, approval_status='APPROVED',
               ratio_definition='verified-TTM-definition-v1' if ratio else None)
    row.update(changes)
    return row


def series():
    return [fact(metric, value, period)
            for period, values in [('2025-Q2', {'revenue':'100', 'profit':'20',
                'operating_cash_flow':'18', 'assets':'1000', 'equity':'500',
                'liabilities':'500', 'roe':'20', 'roa':'10'}),
                ('2026-Q2', {'revenue':'120', 'profit':'30', 'operating_cash_flow':'27',
                'assets':'1100', 'equity':'600', 'liabilities':'500', 'roe':'22', 'roa':'12'})]
            for metric, value in values.items()]


def result(rows):
    return analyze_company(rows, symbol='FPT', period='2026-Q2')


class CompanyFinancialTests(unittest.TestCase):
    def test_exact_growth_margin_leverage_and_direct_ratios(self):
        out = result(series())
        expected = {'revenue_yoy_percent':'20.0000', 'profit_yoy_percent':'50.0000',
                    'operating_cash_flow_yoy_percent':'50.0000', 'net_margin_percent':'25.0000',
                    'liabilities_to_assets_percent':'45.4545', 'roe_percent':'22.0000',
                    'roa_percent':'12.0000'}
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertEqual(out['signals'][name]['value'], value)
                self.assertEqual(out['signals'][name]['status'], 'complete')

    def test_rounds_decimal_half_up_without_binary_float(self):
        out = result([fact('roe', Decimal('1.23445'))])
        self.assertEqual(out['signals']['roe_percent']['value'], '1.2345')

    def test_value_times_scale_is_applied_before_growth(self):
        rows = [fact('revenue', '0.1', '2025-Q2', scale=1000), fact('revenue', 120)]
        self.assertEqual(result(rows)['signals']['revenue_yoy_percent']['value'], '20.0000')

    def test_scale_must_be_a_positive_integer(self):
        for scale in [0, -1, True, 1.5]:
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError):
                    result([fact('revenue', 120, scale=scale)])

    def test_none_is_missing_and_never_coerced_to_zero(self):
        out = result([fact('revenue', None, '2025-Q2'), fact('revenue', 120)])
        self.assertIsNone(out['signals']['revenue_yoy_percent']['value'])
        self.assertEqual(out['signals']['revenue_yoy_percent']['status'], 'insufficient_data')

    def test_nonpositive_base_has_no_growth_percentage(self):
        for prior in [0, -20]:
            with self.subTest(prior=prior):
                sig = result([fact('profit', prior, '2025-Q2'), fact('profit', 10)])['signals']['profit_yoy_percent']
                self.assertIsNone(sig['value'])
                self.assertIn('non_positive_base', sig['reasons'])
                self.assertEqual(set(sig['inputs']), {'obs-2025-Q2-profit', 'obs-2026-Q2-profit'})

    def test_prior_quarter_cannot_substitute_for_same_quarter_last_year(self):
        rows = [fact('revenue', 100, '2025-Q1'), fact('revenue', 120)]
        self.assertIsNone(result(rows)['signals']['revenue_yoy_percent']['value'])

    def test_ytd_is_not_compared_to_standalone_quarter(self):
        rows = [fact('revenue', 100, '2025-Q2', basis='YTD', period_start='2025-01-01'), fact('revenue', 120)]
        self.assertIsNone(result(rows)['signals']['revenue_yoy_percent']['value'])

    def test_same_ytd_window_is_eligible(self):
        rows = [fact('revenue', 100, '2025-Q2', basis='YTD', period_start='2025-01-01'),
                fact('revenue', 120, basis='YTD', period_start='2026-01-01')]
        self.assertEqual(result(rows)['signals']['revenue_yoy_percent']['value'], '20.0000')

    def test_unknown_critical_metadata_blocks_computation(self):
        for field in ['unit', 'basis', 'scope', 'comparison_basis', 'fiscal_year_end', 'period_start', 'period_end']:
            with self.subTest(field=field):
                rows = [fact('revenue', 100, '2025-Q2'), fact('revenue', 120, **{field:None})]
                sig = result(rows)['signals']['revenue_yoy_percent']
                self.assertIsNone(sig['value'])
                self.assertTrue(sig['reasons'])

    def test_scope_perimeter_currency_and_fiscal_end_must_match(self):
        for field, value in [('scope','SEPARATE'), ('comparison_basis','old-unrestated-perimeter'),
                             ('currency','USD'), ('fiscal_year_end','03-31')]:
            with self.subTest(field=field):
                rows = [fact('revenue', 100, '2025-Q2', **{field:value}), fact('revenue', 120)]
                self.assertIsNone(result(rows)['signals']['revenue_yoy_percent']['value'])

    def test_actual_window_mismatch_blocks_even_if_labels_match(self):
        rows = [fact('revenue', 100, '2025-Q2', period_start='2025-01-01'), fact('revenue', 120)]
        self.assertIsNone(result(rows)['signals']['revenue_yoy_percent']['value'])

    def test_matching_six_month_windows_are_not_standalone_quarters(self):
        rows = [fact('revenue', 100, '2025-Q2', period_start='2025-01-01'),
                fact('revenue', 120, period_start='2026-01-01')]
        sig = result(rows)['signals']['revenue_yoy_percent']
        self.assertIsNone(sig['value'])
        self.assertEqual(sig['status'], 'insufficient_data')

    def test_direct_ratio_needs_an_explicit_verified_definition(self):
        sig = result([fact('roe', 22, ratio_definition=None)])['signals']['roe_percent']
        self.assertIsNone(sig['value'])
        self.assertEqual(sig['status'], 'insufficient_data')

    def test_missing_required_provenance_blocks_a_computable_value(self):
        for field in ['observation_id','payload_id','source_uri','source_sha256']:
            with self.subTest(field=field):
                rows = [fact('revenue', 100, '2025-Q2'), fact('revenue', 120, **{field:None})]
                sig = result(rows)['signals']['revenue_yoy_percent']
                self.assertIsNone(sig['value'])
                self.assertEqual(sig['status'], 'insufficient_data')

    def test_provenance_and_basis_identifiers_must_be_nonblank_strings(self):
        for field in ['observation_id','payload_id','source_name','source_uri',
                      'source_sha256','comparison_basis','ratio_definition']:
            for bad in ['   ',123,False]:
                with self.subTest(field=field,bad=bad):
                    sig=result([fact('roe',22,**{field:bad})])['signals']['roe_percent']
                    self.assertIsNone(sig['value'])
                    self.assertEqual(sig['status'],'insufficient_data')

    def test_invalid_liabilities_and_npl_do_not_reject_valid_negative_financial_values(self):
        sig=result([fact('assets',100),fact('liabilities',-1)])['signals']['liabilities_to_assets_percent']
        self.assertIsNone(sig['value'])
        self.assertEqual(sig['status'],'insufficient_data')
        for invalid in ['-0.1','100.01']:
            with self.subTest(npl=invalid):
                sig=result([fact('npl',invalid,industry='BANK')])['signals']['npl_percent']
                self.assertIsNone(sig['value'])
                self.assertEqual(sig['status'],'insufficient_data')
        rows=[fact('profit',20,'2025-Q2'),fact('profit',-10),
              fact('operating_cash_flow',18,'2025-Q2'),fact('operating_cash_flow',-27),
              fact('roe','-2.5'),fact('equity',-5)]
        signals=result(rows)['signals']
        self.assertEqual(signals['profit_yoy_percent']['value'],'-150.0000')
        self.assertEqual(signals['operating_cash_flow_yoy_percent']['value'],'-250.0000')
        self.assertEqual(signals['roe_percent']['value'],'-2.5000')

    def test_industry_mismatch_cannot_form_yoy_pair(self):
        rows = [fact('revenue', 100, '2025-Q2', industry='BANK'), fact('revenue', 120)]
        self.assertIsNone(result(rows)['signals']['revenue_yoy_percent']['value'])

    def test_invalid_numeric_types_and_nonfinite_values_are_rejected(self):
        for value in [True, 1.2, 'NaN', 'Infinity', Decimal('-Infinity')]:
            with self.subTest(value=str(value)):
                with self.assertRaises(ValueError):
                    result([fact('roe', value)])

    def test_invalid_symbol_period_and_dates_are_rejected(self):
        for args in [dict(symbol='../FPT', period='2026-Q2'), dict(symbol='FPT', period='2026-Q5')]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    analyze_company(series(), **args)
        for patch in [dict(period_end='not-a-date'), dict(period_start='2026-07-01')]:
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    result([fact('revenue', 120, **patch)])

    def test_conflicting_revision_is_not_selected_by_observation_id(self):
        rows = [fact('revenue', 120), fact('revenue', 121, observation_id='other-version')]
        with self.assertRaises(ValueError):
            result(rows)

    def test_bank_profile_does_not_apply_tech_cashflow_or_leverage_rules(self):
        rows = [fact('profit', 20, '2025-Q2', industry='BANK'), fact('profit', 30, industry='BANK'),
                fact('nim', '3.5', industry='BANK'), fact('npl', '1.2', industry='BANK')]
        out = result(rows)
        self.assertEqual(out['signals']['profit_yoy_percent']['value'], '50.0000')
        self.assertEqual(out['signals']['nim_percent']['value'], '3.5000')
        for name in ['operating_cash_flow_yoy_percent','net_margin_percent','liabilities_to_assets_percent']:
            self.assertEqual(out['signals'][name]['status'], 'not_applicable')

    def test_tech_profile_does_not_apply_bank_ratio_rules(self):
        out = result(series())
        for name in ['nim_percent','npl_percent','cost_to_income_percent']:
            self.assertEqual(out['signals'][name]['status'], 'not_applicable')

    def test_pending_source_makes_values_provisional(self):
        rows = series()
        for row in rows:
            row['approval_status'] = 'PENDING'
        out = result(rows)
        self.assertEqual(out['signals']['revenue_yoy_percent']['value'], '20.0000')
        self.assertEqual(out['signals']['revenue_yoy_percent']['status'], 'provisional')
        self.assertEqual(out['status'], 'provisional')

    def test_provenance_is_present_and_input_is_not_mutated(self):
        rows = series()
        before = deepcopy(rows)
        out = result(rows)
        self.assertEqual(rows, before)
        encoded = json.dumps(out, default=str)
        self.assertIn('obs-2026-Q2-revenue', encoded)
        self.assertIn('https://issuer.example/2026-Q2.pdf', encoded)
        self.assertIn('comparison', out['signals']['revenue_yoy_percent'])

    def test_annual_yoy_uses_annual_prior(self):
        rows = [fact('revenue', 100, '2025'), fact('revenue', 120, '2026')]
        out = analyze_company(rows, symbol='FPT', period='2026')
        self.assertEqual(out['signals']['revenue_yoy_percent']['value'], '20.0000')

    def test_verified_noncalendar_fiscal_windows_do_not_force_label_year(self):
        rows = [fact('revenue', 100, '2025-Q4', fiscal_year_end='03-31',
                     fiscal_label_convention='START_YEAR',
                     period_start='2026-01-01', period_end='2026-03-31', published_at='2026-04-15'),
                fact('revenue', 120, '2026-Q4', fiscal_year_end='03-31',
                     fiscal_label_convention='START_YEAR',
                     period_start='2027-01-01', period_end='2027-03-31', published_at='2027-04-15')]
        out = analyze_company(rows, symbol='FPT', period='2026-Q4')
        self.assertEqual(out['signals']['revenue_yoy_percent']['value'], '20.0000')

    def test_end_year_fiscal_labels_accept_the_preceding_calendar_year_quarter(self):
        rows=[fact('revenue',100,'2025-Q1',fiscal_year_end='03-31',
                   fiscal_label_convention='END_YEAR',period_start='2024-04-01',
                   period_end='2024-06-30',published_at='2024-08-01'),
              fact('revenue',120,'2026-Q1',fiscal_year_end='03-31',
                   fiscal_label_convention='END_YEAR',period_start='2025-04-01',
                   period_end='2025-06-30',published_at='2025-08-01')]
        out=analyze_company(rows,symbol='FPT',period='2026-Q1')
        self.assertEqual(out['signals']['revenue_yoy_percent']['value'],'20.0000')

    def test_start_year_fiscal_labels_reject_a_consistently_mislabelled_year(self):
        rows=[fact('revenue',100,'2025-Q1',fiscal_year_end='03-31',
                   fiscal_label_convention='START_YEAR',period_start='2026-04-01',
                   period_end='2026-06-30',published_at='2026-08-01'),
              fact('revenue',120,'2026-Q1',fiscal_year_end='03-31',
                   fiscal_label_convention='START_YEAR',period_start='2027-04-01',
                   period_end='2027-06-30',published_at='2027-08-01')]
        sig=analyze_company(rows,symbol='FPT',period='2026-Q1')['signals']['revenue_yoy_percent']
        self.assertIsNone(sig['value'])
        self.assertEqual(sig['status'],'insufficient_data')

    def test_noncalendar_fiscal_label_convention_is_not_inferred(self):
        rows=[fact('revenue',100,'2025-Q1',fiscal_year_end='03-31',
                   period_start='2025-04-01',period_end='2025-06-30'),
              fact('revenue',120,'2026-Q1',fiscal_year_end='03-31',
                   period_start='2026-04-01',period_end='2026-06-30')]
        sig=analyze_company(rows,symbol='FPT',period='2026-Q1')['signals']['revenue_yoy_percent']
        self.assertIsNone(sig['value'])
        self.assertEqual(sig['status'],'insufficient_data')

    def test_source_native_ratio_is_not_assumed_to_be_percentage(self):
        out = result([fact('roe', '0.22', unit='SOURCE_NATIVE')])
        self.assertIsNone(out['signals']['roe_percent']['value'])
        self.assertEqual(out['signals']['roe_percent']['status'], 'insufficient_data')
