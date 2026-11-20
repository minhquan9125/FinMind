"""Independent peer medians, cohort eligibility and comparison direction."""
from copy import deepcopy
import unittest

from backend.src.financial.peers import compare_peers


def company(symbol, value, *, name='revenue_yoy_percent', industry='TECH', period='2026-Q2',
            status='complete', **comparison):
    signature = dict(unit='PERCENT', basis='QUARTER', scope='CONSOLIDATED',
                     comparison_basis='reviewed-comparable-v1', fiscal_year_end='12-31',
                     fiscal_label_convention='CALENDAR',
                     period_start='2026-04-01', period_end='2026-06-30', ratio_definition=None)
    if name in {'roe_percent','roa_percent','nim_percent','npl_percent','cost_to_income_percent'}:
        signature.update(basis='TTM',period_start='2025-07-01',
                         ratio_definition='verified-TTM-definition-v1')
    if name=='liabilities_to_assets_percent':
        signature.update(basis='INSTANT',period_start='2026-06-30')
    signature.update(comparison)
    return dict(symbol=symbol, industry=industry, period=period, status=status,
                signals={name:dict(value=value, status=status, reasons=[], inputs=[f'obs-{symbol}'],
                                   comparison=signature)})


class PeerComparisonTests(unittest.TestCase):
    def test_median_excludes_target_and_preserves_source_analyses(self):
        rows = [company('FPT','100.0000'), company('CMG','10.0000'),
                company('ELC','20.0000'), company('ITD','40.0000')]
        before = deepcopy(rows)
        out = compare_peers(rows, symbol='FPT')
        metric = out['metrics']['revenue_yoy_percent']
        self.assertEqual(metric['peer_median'], '20.0000')
        self.assertEqual(metric['difference_pp'], '80.0000')
        self.assertEqual(metric['position'], 'above')
        self.assertTrue(metric['favorable'])
        self.assertEqual(set(metric['peer_symbols']), {'CMG','ELC','ITD'})
        self.assertEqual(rows, before)

    def test_requires_three_distinct_eligible_peers(self):
        rows = [company('FPT','10'), company('CMG','20'), company('ELC','30')]
        metric = compare_peers(rows, symbol='FPT')['metrics']['revenue_yoy_percent']
        self.assertIsNone(metric['peer_median'])
        self.assertIsNone(metric['difference_pp'])
        self.assertEqual(metric['position'], 'insufficient_data')

    def test_minimum_peer_count_cannot_be_reduced_below_three_or_boolean(self):
        rows = [company('FPT','50'), company('CMG','10'), company('ELC','20'), company('ITD','30')]
        for minimum in [0, 1, 2, True, False]:
            with self.subTest(minimum=minimum):
                with self.assertRaises(ValueError):
                    compare_peers(rows,symbol='FPT',minimum_peers=minimum)

    def test_ratio_definition_mismatch_excludes_otherwise_matching_peer(self):
        key='roe_percent'
        rows = [company('FPT','22',name=key), company('CMG','15',name=key),
                company('ELC','20',name=key),
                company('ITD','99',name=key,ratio_definition='verified-nonannualised-definition-v2')]
        metric = compare_peers(rows,symbol='FPT')['metrics'][key]
        self.assertIsNone(metric['peer_median'])
        self.assertEqual(metric['position'],'insufficient_data')
        self.assertNotIn('ITD',metric['peer_symbols'])

    def test_duplicates_do_not_inflate_peer_count(self):
        rows = [company('FPT','10'), company('CMG','20'), company('CMG','20'), company('ELC','30')]
        metric = compare_peers(rows, symbol='FPT')['metrics']['revenue_yoy_percent']
        self.assertIsNone(metric['peer_median'])
        self.assertNotIn('FPT', metric['peer_symbols'])

    def test_wrong_industry_period_or_scope_are_not_included(self):
        rows = [company('FPT','50'), company('CMG','10'), company('ELC','20'), company('ITD','30'),
                company('BID','999',industry='BANK'), company('ICT','999',period='2026-Q1'),
                company('VGI','999',scope='SEPARATE'), company('FOX','999',fiscal_year_end='03-31')]
        metric = compare_peers(rows, symbol='FPT')['metrics']['revenue_yoy_percent']
        self.assertEqual(metric['peer_median'], '20.0000')
        self.assertEqual(set(metric['peer_symbols']), {'CMG','ELC','ITD'})

    def test_lower_leverage_is_favorable_while_position_stays_arithmetic(self):
        key = 'liabilities_to_assets_percent'
        rows = [company('FPT','5',name=key), company('CMG','10',name=key),
                company('ELC','20',name=key), company('ITD','30',name=key)]
        metric = compare_peers(rows, symbol='FPT')['metrics'][key]
        self.assertEqual(metric['position'], 'below')
        self.assertEqual(metric['difference_pp'], '-15.0000')
        self.assertTrue(metric['favorable'])

    def test_equal_metric_and_even_peer_median(self):
        rows = [company('FPT','25'), company('CMG','10'), company('ELC','20'),
                company('ITD','30'), company('ICT','40')]
        metric = compare_peers(rows, symbol='FPT')['metrics']['revenue_yoy_percent']
        self.assertEqual(metric['peer_median'], '25.0000')
        self.assertEqual(metric['difference_pp'], '0.0000')
        self.assertEqual(metric['position'], 'equal')

    def test_pending_peer_makes_comparison_provisional(self):
        rows = [company('FPT','50'), company('CMG','10'), company('ELC','20'),
                company('ITD','30',status='provisional')]
        out = compare_peers(rows, symbol='FPT')
        self.assertEqual(out['metrics']['revenue_yoy_percent']['status'], 'provisional')
        self.assertEqual(out['status'], 'provisional')

    def test_missing_or_ineligible_values_cannot_enter_median(self):
        rows = [company('FPT','50'), company('CMG',None,status='insufficient_data'),
                company('ELC','20'), company('ITD','30')]
        metric = compare_peers(rows, symbol='FPT')['metrics']['revenue_yoy_percent']
        self.assertIsNone(metric['peer_median'])
        self.assertNotIn('CMG', metric['peer_symbols'])

    def test_report_coverage_is_provisional_when_an_applicable_signal_is_missing(self):
        rows=[company('FPT','50'),company('CMG','10'),company('ELC','20'),company('ITD','30')]
        for row in rows:
            signature=deepcopy(row['signals']['revenue_yoy_percent']['comparison'])
            row['signals']['profit_yoy_percent']=dict(value=None,status='insufficient_data',
                reasons=['missing_prior'],inputs=[],comparison=signature)
            row['signals']['nim_percent']=dict(value=None,status='not_applicable',
                reasons=[],inputs=[],comparison=None)
        out=compare_peers(rows,symbol='FPT')
        self.assertEqual(out['metrics']['revenue_yoy_percent']['status'],'complete')
        self.assertEqual(out['metrics']['profit_yoy_percent']['status'],'insufficient_data')
        self.assertEqual(out['status'],'provisional')
        for row in rows:
            del row['signals']['profit_yoy_percent']
        out=compare_peers(rows,symbol='FPT')
        self.assertEqual(out['status'],'complete')
