"""Prepare raw financial records; display strings never become DB values."""
from .core import SECTIONS


def iter_database_records(cleaned):
    """Yield canonical records for a future importer, without connecting to a DB.

    Always use value, never giá_trị_hiển_thị. Decimal should go to NUMERIC/DECIMAL
    columns through a compatible driver; do not cast it to float.
    """
    for section, vietnamese in SECTIONS.items():
        for row in cleaned['báo_cáo_tài_chính'][vietnamese]:
            kind = {'Năm':'YEAR','Quý':'QUARTER'}[row['loại_kỳ']]
            for metric in row['chỉ_tiêu']:
                yield {'symbol':cleaned['mã_chứng_khoán'],
                    'industry':cleaned['ngành'],'section':section,
                    'period_label':row['kỳ_báo_cáo'],'period_type':kind,
                    'year':row['năm'],'quarter':row['quý'],
                    'metric_code':metric['mã_chuẩn'],'value':metric['giá_trị']}
