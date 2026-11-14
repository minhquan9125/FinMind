import importlib.util
from pathlib import Path
from decimal import Decimal

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('clean_import', ROOT / 'backend/scripts/import_clean_financials.py')
import sys
sys.path.insert(0, str(ROOT / 'backend/scripts'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_fpt_keeps_exact_values_and_both_period_types():
    item = module.read_input(ROOT / 'data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json')
    values = {(p, m['trường_gốc']): value for p, _, m, value in item['values']}
    assert values['2026-Q2', 'bsa2'] == Decimal('8843161132730')
    assert len({p for p, *_ in item['values']}) == 42
    assert any(p.endswith('-YEAR') for p, *_ in item['values'])
    assert any(v != v.quantize(Decimal('.0001')) for v in values.values())


def test_bank_long_code_is_preserved():
    item = module.read_input(ROOT / 'data_pipeline/FinancialCleaner/data/BID/tai_chinh_clean.json')
    assert any(len(m['mã_chuẩn']) == 53 for _, _, m, _ in item['values'])


def test_rejects_tampered_mapping(tmp_path):
    original = module.read_input(ROOT / 'data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json')
    data = original['data']
    data['báo_cáo_tài_chính']['bảng_cân_đối_kế_toán'][0]['chỉ_tiêu'][0]['mã_chuẩn'] = 'WRONG'
    path = tmp_path / 'FPT/tai_chinh_clean.json'
    path.parent.mkdir()
    path.write_text(module.codec.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='mapping mismatch'):
        module.read_input(path)
