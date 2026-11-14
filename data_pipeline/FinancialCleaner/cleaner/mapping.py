"""Load the authorized source mapping without importing the backend app."""
import importlib.util
from pathlib import Path
import json

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SOURCE_DIR = ROOT/'data/normalized'
MAPPING_PATH = ROOT/'backend/src/financial/mapping.py'
MARKET_CODES = {'PE','PB','PS','MARKET_CAP','DIVIDEND_YIELD','PRICE_TO_CASH_FLOW',
                'EV_TO_EBITDA','NUMBER_OF_SHARES_MKT_CAP'}


def load_mapping(industry):
    spec = importlib.util.spec_from_file_location('_financial_source_mapping', MAPPING_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if industry == 'BANK':
        maps = module.SECTION_MAPS
    elif industry == 'TECH':
        maps = module.INDUSTRY_SECTION_MAPS['TECH']
    else:
        raise ValueError(f'Chưa có mapping riêng cho ngành {industry!r}; không dùng mapping ngân hàng thay thế.')
    labels = json.loads((PROJECT/'config/labels_vi.json').read_text(encoding='utf-8'))
    labels.update(module.METRIC_LABELS_VI)
    return maps, labels, module.META_KEYS
