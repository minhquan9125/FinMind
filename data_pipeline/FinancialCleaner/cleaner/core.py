"""Pure filtering: retain mapped observations and their reporting periods."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import math
import re

SECTIONS = {
    'balance_sheet':'bảng_cân_đối_kế_toán',
    'income_statement':'kết_quả_kinh_doanh',
    'cash_flow_statement':'lưu_chuyển_tiền_tệ',
    'ratios':'chỉ_số_tài_chính',
}
RESERVED = {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}


def validate_symbol(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z][A-Z0-9]{0,9}',value) or value in RESERVED:
        raise ValueError('Mã chứng khoán không hợp lệ hoặc trùng tên thiết bị Windows.')
    return value


def _integer(value, field):
    if type(value) is int:
        return value
    if isinstance(value,str) and re.fullmatch(r'[0-9]{1,4}',value):
        return int(value)
    raise ValueError(f'{field} phải là số nguyên hợp lệ.')


def _period(row):
    year=_integer(row.get('year'),'Năm')
    if not 1900 <= year <= 2200:
        raise ValueError('Năm báo cáo ngoài khoảng cho phép.')
    kind=row.get('period_type')
    label=row.get('period_label')
    if kind=='QUARTER':
        quarter=_integer(row.get('quarter'),'Quý')
        if quarter not in (1,2,3,4) or label!=f'{year}-Q{quarter}':
            raise ValueError('Nhãn kỳ, năm và quý không khớp.')
        report_type='Quý'
    elif kind=='YEAR':
        # Vietcap's 5 means annual report, not a fifth quarter.
        raw_quarter=row.get('quarter')
        if raw_quarter is not None and _integer(raw_quarter,'Quý') not in (0,5):
            raise ValueError('Kỳ năm không được có quý từ 1 đến 4.')
        if label not in (str(year),f'{year}-YEAR'):
            raise ValueError('Nhãn kỳ và năm không khớp.')
        quarter=None;report_type='Năm'
    else:
        raise ValueError('Loại kỳ phải là YEAR hoặc QUARTER.')
    if row.get('yearReport') is not None and _integer(row['yearReport'],'Năm nguồn')!=year:
        raise ValueError('Năm nguồn và năm báo cáo không khớp.')
    if row.get('lengthReport') is not None:
        length=_integer(row['lengthReport'],'Kỳ nguồn')
        if length!=(quarter if kind=='QUARTER' else 5):
            raise ValueError('Kỳ nguồn và kỳ báo cáo không khớp.')
    return {'kỳ_báo_cáo':label,'loại_kỳ':report_type,'năm':year,'quý':quarter}


def _validate_value(value):
    if type(value) is bool or not isinstance(value,(int,float,Decimal,str)):
        raise ValueError('Chỉ tiêu tài chính phải là số hoặc chuỗi số.')
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('Chỉ tiêu không được là NaN hoặc vô cực.')
    if isinstance(value,Decimal) and not value.is_finite():
        raise ValueError('Chỉ tiêu không được là NaN hoặc vô cực.')
    if isinstance(value,str):
        if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',value):
            raise ValueError('Chuỗi chỉ tiêu phải là chuỗi số, không có dấu phân cách nghìn.')
        try:
            if not Decimal(value).is_finite():raise ValueError('Chuỗi số không hữu hạn.')
        except InvalidOperation as issue:
            raise ValueError('Chuỗi chỉ tiêu không hợp lệ.') from issue


def clean_financial_data(payload, *, section_maps, labels_vi, meta_keys, exclude_codes=()):
    """Return Vietnamese financial data, without mutating or writing the input.

    section_maps must already be selected for BANK or TECH by the file adapter.
    Unknown fields and null metrics are removed; zeros/negative/exact values stay.
    """
    if not isinstance(payload,dict) or not isinstance(payload.get('financial_data'),dict):
        raise ValueError('Thiếu đối tượng financial_data.')
    symbol=validate_symbol(payload.get('symbol'))
    financial=payload['financial_data'];report={};audits={};total=0
    excluded=set(exclude_codes)
    for section,vi_name in SECTIONS.items():
        rows=financial.get(section,[])
        if not isinstance(rows,list):raise ValueError(f'{section} phải là danh sách kỳ.')
        fields=section_maps.get(section,{})
        cleaned=[];removed=Counter();reasons=Counter();retained=0;periods=set()
        for row in rows:
            if not isinstance(row,dict):raise ValueError('Kỳ báo cáo phải là đối tượng.')
            period=_period(row)
            identity=(period['loại_kỳ'],period['kỳ_báo_cáo'])
            if identity in periods:raise ValueError(f'Kỳ báo cáo bị trùng: {identity[1]}')
            periods.add(identity);metrics=[];codes=set()
            for raw,value in row.items():
                if raw in meta_keys:continue
                code=fields.get(raw)
                placeholder = code == raw.upper() and re.fullmatch(r'[a-z]+[0-9]+', raw, re.I)
                reason=('chưa_có_mapping' if not code or placeholder else
                        'chỉ_số_định_giá_được_yêu_cầu_bỏ' if code in excluded else
                        'giá_trị_null' if value is None else None)
                if reason:removed[raw]+=1;reasons[reason]+=1;continue
                _validate_value(value)
                label=labels_vi.get(code)
                if not isinstance(label,str) or not label.strip():raise ValueError(f'Thiếu tên tiếng Việt cho {code}.')
                if code in codes:raise ValueError(f'Mapping trùng mã chuẩn trong một kỳ: {code}')
                codes.add(code)
                metrics.append({'mã_chuẩn':code,'tên_chỉ_tiêu':label,'trường_gốc':raw,'giá_trị':value})
            retained+=len(metrics)
            cleaned.append({**period,'chỉ_tiêu':metrics})
        report[vi_name]=cleaned;total+=retained
        audits[vi_name]={'số_kỳ_nguồn':len(rows),'số_kỳ_giữ':len(cleaned),'số_chỉ_tiêu_giữ':retained,
            'số_giá_trị_loại':sum(removed.values()),'trường_đã_loại':dict(sorted(removed.items())),
            'lý_do_loại':dict(reasons)}
    prices=payload.get('price_history',[])
    if not isinstance(prices,list):raise ValueError('price_history phải là danh sách.')
    return {'mã_chứng_khoán':symbol,'tên_doanh_nghiệp':payload.get('company_name',''),
        'sàn':payload.get('exchange',''),'ngành':payload.get('industry',''),'tên_ngành':payload.get('industry_name',''),
        'báo_cáo_tài_chính':report,'thống_kê_lọc':{'tổng_chỉ_tiêu_giữ':total,
            'số_bản_ghi_giá_đã_bỏ':len(prices),'chi_tiết_phần':audits}}
