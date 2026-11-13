"""Independent fixtures for the pure price/flow calculator; no provider or DB."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import importlib.util
import json
import statistics
import unittest

if importlib.util.find_spec('backend.src.market_data.analysis'):
    from backend.src.market_data.analysis import analyze_series
else:
    analyze_series = None


def prices(count=21):
    return [dict(symbol='FPT', trade_date=date(2026, 9, 1)+timedelta(days=i*2),
                 open=str(100+i), high=str(102+i), low=str(99+i), close=str(100+i),
                 volume=200 if i==20 else 100, price_scale=1000, is_adjusted=True,
                 source_id='price-source', source_name='historical', approval_status='APPROVED',
                 price_id=f'price-{i}', payload_id=f'raw-price-{i}') for i in range(count)]


def flows(rows):
    return [dict(trade_date=r['trade_date'], symbol='FPT', source_id='flow-source',
                 source_name='verified-flow', approval_status='APPROVED',
                 payload_id=f'flow-{i}', field_payload_ids={'total_value_vnd':f'earlier-{i}'},
                 quality_status='validated', observation_status='after_close',
                 volume_basis='matched', value_basis='matched', total_value_vnd='1000.1250',
                 foreign_buy_volume=10, foreign_sell_volume=12,
                 foreign_buy_value_vnd='700', foreign_sell_value_vnd='800')
            for i,r in enumerate(rows)]


def benchmarks(rows):
    return [dict(index_symbol='VNINDEX',trade_date=r['trade_date'],close=str(1000+i),
                 source_id='index-source',source_name='benchmark',approval_status='APPROVED',
                 price_id=f'index-{i}',payload_id=f'raw-index-{i}') for i,r in enumerate(rows)]


class PriceAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analyze_series, 'PF06 calculator has not been implemented')
        self.rows=prices()

    def run_analysis(self, rows=None, activity=None, benchmark=None, **kwargs):
        return analyze_series(self.rows if rows is None else rows,
                              flows(self.rows) if activity is None else activity,
                              benchmarks(self.rows) if benchmark is None else benchmark,
                              symbol='FPT', requested_as_of=kwargs.get('requested_as_of',date(2026,10,11)),
                              today=kwargs.get('today',date(2026,10,11)))

    def test_independent_twenty_session_price_volume_and_volatility_oracles(self):
        out=self.run_analysis(rows=list(reversed(self.rows)))
        m=out['metrics']
        self.assertEqual(m['return_20_percent'],'20.0000')
        self.assertEqual(m['return_5_percent'],'4.3478')
        self.assertEqual(m['return_1_percent'],'0.8403')
        self.assertEqual(m['sma20'],'110.5000')
        self.assertEqual(m['close_vs_sma20_percent'],'8.5973')
        self.assertEqual(m['volume_vs_prior20'],'2.0000')
        self.assertEqual(m['average_volume_prior20'],'100.0000')
        self.assertEqual(m['average_volume_latest5'],'120.0000')
        self.assertEqual(m['average_volume_prior5'],'100.0000')
        self.assertEqual(m['intraday_range_percent'],'2.5210')
        self.assertEqual(m['close_vnd'],'120000.0000')
        independent=statistics.stdev([100*((101+i)/(100+i)-1) for i in range(20)])
        self.assertAlmostEqual(float(m['daily_volatility20_percent']),independent,places=4)
        self.assertEqual(out['session_count'],21)
        self.assertEqual(out['status'],'ok')
        json.dumps(out)

    def test_half_up_rounding_and_decimal_input(self):
        self.rows[-1].update(open=Decimal('120.00005'),high='122',close=Decimal('120.00005'))
        self.assertEqual(self.run_analysis()['metrics']['close'],'120.0001')

    def test_empty_and_short_histories_are_null_safe(self):
        for count in (0,1,5,20):
            with self.subTest(count=count):
                out=self.run_analysis(rows=self.rows[:count],activity=[],benchmark=[])
                self.assertIsNone(out['metrics']['return_20_percent'])
                self.assertIsNone(out['metrics']['volume_vs_prior20'])
                self.assertEqual(out['status'],'no_data' if count==0 else 'partial')
                self.assertEqual(out['session_count'],count)
                json.dumps(out)

    def test_max_twenty_one_sessions_and_requested_date_filter(self):
        rows=prices(26)
        out=self.run_analysis(rows=rows,requested_as_of=date(2026,10,21),today=date(2026,10,21))
        self.assertEqual(out['session_count'],21)
        self.assertEqual(out['first_date'],'2026-09-11')
        early=self.run_analysis(requested_as_of=date(2026,9,9))
        self.assertEqual(early['session_count'],5)
        self.assertEqual(early['as_of'],'2026-09-09')

    def test_missing_and_zero_volume_never_invent_denominators(self):
        self.rows[0]['volume']=None
        out=self.run_analysis()['metrics']
        self.assertIsNone(out['average_volume_prior20'])
        self.assertIsNone(out['volume_vs_prior20'])
        self.assertEqual(out['average_volume_latest5'],'120.0000')
        for row in self.rows:row['volume']=0
        self.assertIsNone(self.run_analysis()['metrics']['volume_vs_prior20'])

    def test_invalid_ohlc_types_metadata_and_duplicate_dates_rejected(self):
        for field,value in [('close',True),('close',1.2),('close','NaN'),('close','Infinity'),
                            ('close','0'),('close','-1'),('low','500'),('volume',True),
                            ('volume',Decimal('100')),('volume',-1),('price_scale',True),
                            ('price_scale',0),('is_adjusted',None),('is_adjusted',1),
                            ('trade_date','2026-9-01')]:
            with self.subTest(field=field,value=value):
                rows=deepcopy(self.rows);rows[-1][field]=value
                with self.assertRaises(ValueError):self.run_analysis(rows=rows)
        with self.assertRaises(ValueError):self.run_analysis(rows=self.rows+[self.rows[0]])

    def test_mixed_basis_or_source_rejected(self):
        for field,value in [('source_id','other'),('source_name','other'),('price_scale',1),('is_adjusted',False)]:
            rows=deepcopy(self.rows);rows[-1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_analysis(rows=rows)

    def test_future_rows_requests_and_alias_conflicts_rejected(self):
        with self.assertRaises(ValueError):self.run_analysis(today=date(2026,10,10))
        with self.assertRaises(ValueError):self.run_analysis(rows=prices(22))
        self.rows[-1]['date']='2026-10-10'
        with self.assertRaises(ValueError):self.run_analysis()
        self.rows[-1]['date']='2026-10-11'
        self.assertEqual(self.run_analysis()['as_of'],'2026-10-11')
        for row in self.rows:row['date']=row.pop('trade_date')
        self.assertEqual(self.run_analysis(activity=[],benchmark=[])['as_of'],'2026-10-11')

    def test_staleness_unadjusted_source_and_provenance_are_visible(self):
        for row in self.rows:
            row['is_adjusted']=False;row['approval_status']='PENDING'
        self.rows[-1]['payload_id']=None
        out=self.run_analysis(requested_as_of=date(2026,10,15),today=date(2026,10,15))
        self.assertEqual(out['freshness'],{'staleness_calendar_days':4,'stale':True})
        self.assertTrue(any('unadjusted' in w for w in out['warnings']))
        self.assertTrue(any('provenance' in w for w in out['warnings']))
        self.assertTrue(any('source_not_approved' in w for w in out['warnings']))
        self.assertEqual(out['sources']['prices'][-1]['price_id'],'price-20')

    def test_complete_activity_windows_and_real_foreign_money(self):
        out=self.run_analysis()
        w=out['activity']['windows']['20']
        self.assertEqual(w['status'],'complete')
        self.assertEqual(w['available_sessions'],20)
        self.assertEqual(w['total_value_vnd'],'20002.5000')
        self.assertEqual(w['foreign_buy_volume'],200)
        self.assertEqual(w['foreign_net_volume'],-40)
        self.assertEqual(w['foreign_net_value_vnd'],'-2000.0000')
        latest=out['activity']['latest_observation']
        self.assertEqual(latest['payload_id'],'flow-20')
        self.assertEqual(latest['field_payload_ids'],{'total_value_vnd':'earlier-20'})
        self.assertEqual(out['sources']['activity'][-1]['field_payload_ids'],{'total_value_vnd':'earlier-20'})

    def test_pending_or_missing_activity_suppresses_totals_but_exposes_latest(self):
        activity=flows(self.rows)
        activity[-1]['quality_status']='pending_reconciliation'
        activity[-1]['observation_status']='intraday'
        out=self.run_analysis(activity=activity)
        for w in out['activity']['windows'].values():
            self.assertIsNone(w['foreign_net_volume'])
            self.assertIsNone(w['total_value_vnd'])
            self.assertIn('2026-10-11',w['missing_dates'])
        self.assertEqual(out['activity']['latest_observation']['quality_status'],'pending_reconciliation')
        self.assertTrue(any('activity_pending' in w for w in out['warnings']))
        out=self.run_analysis(activity=flows(self.rows)[1:])
        self.assertEqual(out['activity']['windows']['20']['status'],'complete')

    def test_latest_activity_can_be_newer_than_price_but_not_requested_date(self):
        activity=flows(self.rows)
        newest=dict(activity[-1],trade_date=date(2026,10,12),payload_id='newest',quality_status='pending_reconciliation')
        future=dict(newest,trade_date=date(2026,10,13),payload_id='excluded')
        out=self.run_analysis(activity=activity+[newest,future],requested_as_of=date(2026,10,12),today=date(2026,10,13))
        self.assertEqual(out['activity']['latest_observation']['payload_id'],'newest')
        self.assertEqual(out['activity']['windows']['1']['status'],'complete')

    def test_activity_missing_field_and_unknown_or_mixed_basis_are_not_zero(self):
        for field,value in [('foreign_buy_value_vnd',None),('value_basis','unknown'),('value_basis','all')]:
            activity=flows(self.rows);activity[-2][field]=value
            w=self.run_analysis(activity=activity)['activity']['windows']['5']
            self.assertIsNone(w['foreign_net_value_vnd'])
            self.assertEqual(w['foreign_net_volume'],-10)
        activity=flows(self.rows);activity[-1]['volume_basis']='unknown'
        w=self.run_analysis(activity=activity)['activity']['windows']['1']
        self.assertIsNone(w['foreign_net_volume'])
        self.assertEqual(w['total_value_vnd'],'1000.1250')

    def test_duplicate_activity_and_mixed_sources_never_sum(self):
        activity=flows(self.rows)
        out=self.run_analysis(activity=activity+[activity[-1]])
        self.assertIsNone(out['activity']['windows']['1']['total_value_vnd'])
        activity[-1]['source_id']='other-source'
        w=self.run_analysis(activity=activity)['activity']['windows']['5']
        self.assertIsNone(w['total_value_vnd'])
        self.assertEqual(w['status'],'incomplete')

    def test_malformed_activity_values_cannot_fabricate_flow(self):
        for field,value in [('foreign_buy_volume',True),('foreign_sell_volume',-1),
                            ('total_value_vnd','NaN'),('foreign_buy_value_vnd',2.5)]:
            activity=flows(self.rows);activity[-1][field]=value
            out=self.run_analysis(activity=activity)
            self.assertEqual(out['activity']['windows']['1']['status'],'incomplete')

    def test_benchmark_exact_stock_dates_and_difference(self):
        w=self.run_analysis()['benchmark']['windows']['20']
        self.assertEqual(w['return_percent'],'2.0000')
        self.assertEqual(w['difference_percentage_points'],'18.0000')
        self.assertEqual(w['available_sessions'],21)
        self.assertEqual(w['status'],'complete')

    def test_benchmark_missing_middle_duplicate_zero_or_wrong_index_unavailable(self):
        for variant in ('missing','duplicate','zero','other-index','float'):
            benchmark=benchmarks(self.rows)
            if variant=='missing':benchmark.pop(10)
            elif variant=='duplicate':benchmark.append(benchmark[10])
            elif variant=='zero':benchmark[10]['close']='0'
            elif variant=='float':benchmark[10]['close']=1010.0
            else:benchmark[10]['index_symbol']='HNXINDEX'
            with self.subTest(variant=variant):
                out=self.run_analysis(benchmark=benchmark)
                self.assertIsNone(out['benchmark']['windows']['20']['return_percent'])
                self.assertIn('2026-09-21',out['benchmark']['windows']['20']['missing_dates'])
                self.assertEqual(out['benchmark']['windows']['1']['status'],'complete')


if __name__=='__main__':unittest.main()
