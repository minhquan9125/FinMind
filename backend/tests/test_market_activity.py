import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest

from backend.src.market_data.activity import normalize_activity


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent/'fixtures/market_activity.json').read_text(encoding='utf-8'))
        self.now = datetime.fromisoformat(self.data['fetched_at'])

    def parse(self, data=None, **overrides):
        kwargs = dict(symbol='FPT', source_name='vnstock_kbs', now=self.now, session_status='intraday')
        kwargs.update(overrides)
        return normalize_activity(self.data if data is None else data, **kwargs)

    def test_real_kbs_fields_and_units(self):
        result = self.parse()
        self.assertEqual(result['trade_date'].isoformat(), '2026-10-07')
        self.assertEqual(result['volume'], 1736000)
        self.assertEqual(result['foreign_buy_volume']-result['foreign_sell_volume'], -147195)
        self.assertEqual(result['total_value_vnd'], Decimal('105048970000'))
        self.assertIsNone(result['foreign_buy_value_vnd'])
        self.assertIsNone(result['foreign_sell_value_vnd'])
        self.assertIsNone(result['source_updated_at'])
        self.assertEqual(result['quality_status'], 'pending_reconciliation')
        self.assertEqual(result['volume_basis'], 'unknown')

    def test_optional_missing_is_distinct_from_zero(self):
        for field in ('foreign_buy_volume', 'foreign_sell_volume', 'total_value'):
            data = copy.deepcopy(self.data)
            data['rows'][0].pop(field)
            target = 'total_value_vnd' if field == 'total_value' else field
            self.assertIsNone(self.parse(data)[target])
            data['rows'][0][field] = 0
            self.assertEqual(self.parse(data)[target], 0)

    def test_after_close_is_not_validated(self):
        result = self.parse(session_status='after_close')
        self.assertEqual(result['observation_status'], 'after_close')
        self.assertEqual(result['quality_status'], 'pending_reconciliation')
        result = self.parse(session_status='unknown')
        self.assertEqual(result['observation_status'], 'intraday')
        self.assertTrue(result['warnings'])

    def test_invalid_values_and_preopen(self):
        cases = [('TD', '7/10/2026'), ('TD', '31/02/2026'), ('TD', '08/10/2026'),
                 ('exchange', 'OTHER'), ('open_price', '0'), ('close_price', 'NaN'),
                 ('high_price', 'Infinity'), ('low_price', '-1'), ('high_price', '1'),
                 ('close_price', 1.5), ('open_price', True), ('volume_accumulated', None),
                 ('volume_accumulated', True), ('volume_accumulated', 1.5),
                 ('volume_accumulated', -1), ('volume_accumulated', 2**63),
                 ('foreign_buy_volume', -1), ('foreign_sell_volume', True),
                 ('total_value', 'NaN'), ('total_value', 'Infinity'), ('total_value', ''),
                 ('total_value', -1), ('total_value', 1.5), ('total_value', True),
                 ('total_value', '1e20'), ('total_value', '99999999999999999999.99999')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.data);data['rows'][0][field] = value
                with self.assertRaises((ValueError, TypeError)):
                    self.parse(data)
        data = copy.deepcopy(self.data)
        for field in ('open_price','high_price','low_price','close_price'):
            data['rows'][0][field] = '0'
        data['rows'][0]['volume_accumulated'] = 0
        with self.assertRaises(ValueError):self.parse(data)

    def test_money_bounds_decimal_and_zero_volume(self):
        data = copy.deepcopy(self.data)
        data['rows'][0]['total_value'] = Decimal('99999999999999999999.9999')
        data['rows'][0]['volume_accumulated'] = 0
        self.assertEqual(self.parse(data)['total_value_vnd'], Decimal('99999999999999999999.9999'))
        self.assertEqual(self.parse(data)['volume'], 0)
        data['rows'][0]['open_price'] = Decimal(data['rows'][0]['open_price'])
        self.parse(data)

    def test_envelope_symbol_duplicates_and_timezone(self):
        for changes in [dict(symbol='../FPT'), dict(source_name=''), dict(session_status='closed'),
                        dict(now=self.now.replace(tzinfo=None))]:
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                self.parse(**changes)
        for value in (None, '', 'not-a-date', self.now.replace(tzinfo=None).isoformat(),
                      (self.now+timedelta(seconds=31)).isoformat()):
            data = copy.deepcopy(self.data);data['fetched_at'] = value
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.parse(data)
        data = copy.deepcopy(self.data);data['rows'] *= 2
        with self.assertRaises(ValueError):self.parse(data)
        data = copy.deepcopy(self.data);data['rows'] = []
        with self.assertRaises(ValueError):self.parse(data)
        self.parse(symbol='fpt', now=self.now.astimezone(timezone.utc))


if __name__ == '__main__':unittest.main()
