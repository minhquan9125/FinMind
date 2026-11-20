import copy
from decimal import Decimal
import unittest

from cleaner import codec
from cleaner.database import iter_database_records
from cleaner.display import format_value, validate_config, add_display_values
from tests.test_cleaner import sample, clean


class DisplayTests(unittest.TestCase):
    def test_large_numbers_no_precision_loss(self):
        value=Decimal('9007199254740993.123456789')
        self.assertEqual(format_value(value,{}),'9.007.199.254.740.993,123456789')
        self.assertEqual(format_value(Decimal('45603129033273.0'),{}),'45.603.129.033.273')

    def test_zero_negative_exponents_and_numeric_strings(self):
        cases=[(0,'0'),(Decimal('-0.00'),'0'),(-1234,'-1.234'),
            ('-1234.500','-1.234,5'),(Decimal('1E+6'),'1.000.000'),
            (Decimal('1E-7'),'0,0000001')]
        for value,expected in cases:
            with self.subTest(value=value):self.assertEqual(format_value(value,{}),expected)

    def test_display_rounding_and_separators(self):
        config={'số_chữ_số_thập_phân':2,'bỏ_số_0_thập_phân_cuối':False,
            'dấu_phân_cách_nghìn':' ','dấu_thập_phân':','}
        self.assertEqual(format_value(Decimal('999.995'),config),'1 000,00')
        self.assertEqual(format_value(Decimal('-1.235'),config),'-1,24')
        self.assertEqual(format_value(Decimal('9007199254740993.12345'),config),'9 007 199 254 740 993,12')

    def test_invalid_config_and_values(self):
        for config in ({'không_hợp_lệ':1},{'bật':'true'},
            {'số_chữ_số_thập_phân':True},{'số_chữ_số_thập_phân':-1},
            {'dấu_phân_cách_nghìn':','},{'dấu_thập_phân':'5'}):
            with self.subTest(config=config),self.assertRaises(ValueError):validate_config(config)
        for value in (True,Decimal('NaN'),float('inf'),'not numeric'):
            with self.subTest(value=value),self.assertRaises(ValueError):format_value(value,{})

    def test_extreme_exponent_bounded(self):
        self.assertLess(len(format_value(Decimal('1e100000'),{})),100)
        self.assertLess(len(format_value(Decimal('1e-100000'),{})),100)

    def test_db_export_unchanged_for_any_display_config(self):
        configs=[{}, {'số_chữ_số_thập_phân':0}, {'bật':False},
            {'dấu_phân_cách_nghìn':' ','dấu_thập_phân':'.'}]
        raw=clean(sample())
        before=list(iter_database_records(raw))
        for config in configs:
            with self.subTest(config=config):
                decorated=copy.deepcopy(raw)
                add_display_values(decorated,config)
                persisted=codec.loads(codec.dumps(decorated))
                self.assertEqual(list(iter_database_records(persisted)),before)
                for record in iter_database_records(persisted):
                    self.assertNotIn('giá_trị_hiển_thị',record)
                    if record['metric_code']=='PE':
                        self.assertEqual(record['value'],Decimal('12.34567890123456789'))
        disabled=copy.deepcopy(raw);add_display_values(disabled,{'bật':False})
        self.assertNotIn('giá_trị_hiển_thị',disabled['báo_cáo_tài_chính']['chỉ_số_tài_chính'][0]['chỉ_tiêu'][0])


if __name__=='__main__':unittest.main()
