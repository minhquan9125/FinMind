import copy
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import unittest

from cleaner import codec, clean_financial_data
from cleaner.core import SECTIONS, validate_symbol
from cleaner.files import _inside
from cleaner.display import add_display_values, load_display_config
from cleaner.database import iter_database_records
from cleaner.mapping import PROJECT, SOURCE_DIR, MARKET_CODES, load_mapping


def sample():
    return {'symbol':'FPT','industry':'TECH','price_history':[{'close':100}],
        'financial_data':{'ratios':[{'period_type':'YEAR','period_label':'2025-YEAR',
            'year':'2025','quarter':5,'yearReport':2025,'lengthReport':5,
            'roe':0,'pe':Decimal('12.34567890123456789'),'extra':99,'ps':None}]}}


def clean(payload,industry='TECH',**kwargs):
    maps,labels,meta = load_mapping(industry)
    return clean_financial_data(payload,section_maps=maps,labels_vi=labels,meta_keys=meta,**kwargs)


class CleanerTests(unittest.TestCase):
    def test_identity_mapping_zero_and_exact_values(self):
        result=clean(sample())
        row=result['báo_cáo_tài_chính']['chỉ_số_tài_chính'][0]
        self.assertIsNone(row['quý'])
        values={x['mã_chuẩn']:x['giá_trị'] for x in row['chỉ_tiêu']}
        self.assertEqual(values['ROE'],0)
        self.assertEqual(values['PE'],Decimal('12.34567890123456789'))
        self.assertNotIn('PS',values)
        self.assertNotIn('price_history',result)

    def test_input_not_mutated(self):
        payload=sample(); original=copy.deepcopy(payload)
        clean(payload)
        self.assertEqual(payload,original)

    def test_market_exclusion(self):
        row=clean(sample(),exclude_codes=MARKET_CODES)['báo_cáo_tài_chính']['chỉ_số_tài_chính'][0]
        self.assertEqual([x['mã_chuẩn'] for x in row['chỉ_tiêu']],['ROE'])

    def test_invalid_values(self):
        for value in (True,[],{},float('nan'),Decimal('Infinity'),'1,000'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                payload=sample();payload['financial_data']['ratios'][0]['roe']=value
                clean(payload)

    def test_invalid_period_and_duplicates(self):
        for field,value in [('yearReport',2024),('lengthReport',2),('quarter',1),('period_label','2024-YEAR')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                payload=sample();payload['financial_data']['ratios'][0][field]=value
                clean(payload)
        payload=sample();payload['financial_data']['ratios']*=2
        with self.assertRaises(ValueError):clean(payload)

    def test_sector_isolation(self):
        bank,_,_=load_mapping('BANK');tech,_,_=load_mapping('TECH')
        self.assertNotEqual(bank['balance_sheet']['bsa2'],tech['balance_sheet']['bsa2'])
        with self.assertRaises(ValueError):load_mapping('SECURITIES')

    def test_symbols_and_containment(self):
        for symbol in ('../FPT','CON','COM1','fpt','FPT/xx'):
            with self.subTest(symbol=symbol),self.assertRaises(ValueError):validate_symbol(symbol)
        with self.assertRaises(ValueError):_inside(PROJECT.parent/'escape.json',PROJECT)

    def test_exact_codec_and_invalid_json(self):
        raw='{"a":9007199254740993.123456789,"b":0,"c":-2,"d":"12.30"}'
        result=codec.loads(raw)
        self.assertEqual(codec.loads(codec.dumps(result)),result)
        self.assertIn('9007199254740993.123456789',codec.dumps(result))
        for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):codec.loads(raw)

    def test_every_real_observation_matches_source(self):
        paths=sorted(SOURCE_DIR.glob('*.json'))
        self.assertEqual(len(paths),10)
        for source in paths:
            with self.subTest(symbol=source.stem):
                payload=codec.loads(source.read_text(encoding='utf-8-sig'))
                maps,labels,meta=load_mapping(payload['industry'])
                result=codec.loads((PROJECT/'data'/source.stem/'tai_chinh_clean.json').read_text(encoding='utf-8'))
                expected=clean(payload,payload['industry'])
                self.assertEqual(list(iter_database_records(result)),list(iter_database_records(expected)))
                add_display_values(expected,load_display_config())
                self.assertEqual(result['báo_cáo_tài_chính'],expected['báo_cáo_tài_chính'])
                count=0
                for section,vi in SECTIONS.items():
                    source_rows=payload['financial_data'][section]
                    rows=result['báo_cáo_tài_chính'][vi]
                    self.assertEqual(len(rows),len(source_rows))
                    for original,row in zip(source_rows,rows):
                        self.assertEqual(original['period_label'],row['kỳ_báo_cáo'])
                        expected_raw={raw for raw,value in original.items() if raw not in meta
                            and raw in maps[section] and value is not None
                            and not (maps[section][raw]==raw.upper() and re.fullmatch(r'[a-z]+[0-9]+',raw,re.I))}
                        self.assertEqual({x['trường_gốc'] for x in row['chỉ_tiêu']},expected_raw)
                        for metric in row['chỉ_tiêu']:
                            count+=1
                            raw=metric['trường_gốc'];code=metric['mã_chuẩn']
                            self.assertEqual(metric['giá_trị'],original[raw])
                            self.assertEqual(code,maps[section][raw])
                            self.assertEqual(metric['tên_chỉ_tiêu'],labels[code])
                self.assertEqual(count,result['thống_kê_lọc']['tổng_chỉ_tiêu_giữ'])

    def test_original_hashes_unchanged(self):
        baseline=json.loads((PROJECT/'.agent-state/source-hashes.json').read_text(encoding='utf-8'))
        for name,digest in baseline.items():
            with self.subTest(source=name):
                self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
