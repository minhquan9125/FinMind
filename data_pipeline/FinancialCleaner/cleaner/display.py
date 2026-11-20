"""Presentation-only formatting; canonical financial values remain untouched."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
import unicodedata

from .mapping import PROJECT

DEFAULT_CONFIG = {
    'bật':True,
    'dấu_phân_cách_nghìn':'.',
    'dấu_thập_phân':',',
    'số_chữ_số_thập_phân':None,
    'bỏ_số_0_thập_phân_cuối':True,
}


def validate_config(config):
    if config is None:
        config={}
    if not isinstance(config,dict):
        raise ValueError('Cấu hình hiển thị phải là đối tượng JSON.')
    unknown=set(config)-set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(f'Trường cấu hình hiển thị không hợp lệ: {unknown}')
    result={**DEFAULT_CONFIG,**config}
    for key in ('bật','bỏ_số_0_thập_phân_cuối'):
        if type(result[key]) is not bool:
            raise ValueError(f'{key} phải là true hoặc false.')
    decimals=result['số_chữ_số_thập_phân']
    if decimals is not None and (type(decimals) is not int or not 0<=decimals<=12):
        raise ValueError('Số chữ số thập phân phải là null hoặc số nguyên từ 0 đến 12.')
    for key in ('dấu_phân_cách_nghìn','dấu_thập_phân'):
        separator=result[key]
        if (not isinstance(separator,str) or len(separator)!=1
                or separator in '0123456789+-eE'
                or unicodedata.category(separator)[0] not in 'PSZ'):
            raise ValueError(f'{key} phải là một ký tự dấu hoặc khoảng trắng.')
    if result['dấu_phân_cách_nghìn']==result['dấu_thập_phân']:
        raise ValueError('Hai dấu phân cách phải khác nhau.')
    return result


def load_display_config():
    return validate_config(json.loads((PROJECT/'config/display.json').read_text(encoding='utf-8')))


def format_value(value, config=None):
    """Format an independent string, never changing value or its stored type."""
    config=validate_config(config)
    if type(value) is bool or not isinstance(value,(int,float,Decimal,str)):
        raise ValueError('Giá trị hiển thị phải là số hoặc chuỗi số.')
    try:
        number=value if isinstance(value,Decimal) else Decimal(str(value))
    except InvalidOperation as issue:
        raise ValueError('Giá trị hiển thị không phải số hợp lệ.') from issue
    if not number.is_finite():
        raise ValueError('Không hiển thị NaN hoặc vô cực.')
    if not config['bật']:
        return str(value)
    digits=number.as_tuple().digits
    exponent=number.as_tuple().exponent
    # Bound both huge integers and tiny fractions before expanding or rounding.
    if max(len(digits)+max(0,exponent),-exponent+2)>10000:
        return str(number)
    places=config['số_chữ_số_thập_phân']
    if places is not None:
        with localcontext() as context:
            context.prec=max(28,len(digits)+max(0,number.adjusted())+places+4)
            number=number.quantize(Decimal((0,(1,),-places)),rounding=ROUND_HALF_UP)
    negative=number.is_signed() and not number.is_zero()
    fixed=format(number.copy_abs(),'f')
    integer,_,fraction=fixed.partition('.')
    if config['bỏ_số_0_thập_phân_cuối']:
        fraction=fraction.rstrip('0')
    first=len(integer)%3 or 3
    groups=[integer[:first]]+[integer[index:index+3] for index in range(first,len(integer),3)]
    text=config['dấu_phân_cách_nghìn'].join(groups)
    if fraction:
        text+=config['dấu_thập_phân']+fraction
    return ('-' if negative else '')+text


def add_display_values(cleaned, config):
    """Decorate the newly generated output; do not modify any canonical value."""
    config=validate_config(config)
    for rows in cleaned['báo_cáo_tài_chính'].values():
        for row in rows:
            for metric in row['chỉ_tiêu']:
                if config['bật']:
                    metric['giá_trị_hiển_thị']=format_value(metric['giá_trị'],config)
                else:
                    metric.pop('giá_trị_hiển_thị',None)
    cleaned['cấu_hình_hiển_thị']=dict(config)
