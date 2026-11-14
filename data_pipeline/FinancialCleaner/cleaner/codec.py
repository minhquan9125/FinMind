"""UTF-8 JSON with exact Decimal numbers and duplicate-key rejection."""
from decimal import Decimal
import json
import math


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError(f'Khóa JSON bị trùng: {key}')
        result[key]=value
    return result


def loads(text):
    def reject(value):raise ValueError(f'JSON không cho phép {value}')
    return json.loads(text,parse_float=Decimal,parse_constant=reject,object_pairs_hook=_unique)


def dumps(value, level=0):
    """Serialize Decimal as JSON numbers; never convert financial data to float."""
    if value is None or type(value) in (str,bool,int):
        return json.dumps(value,ensure_ascii=False,allow_nan=False)
    if isinstance(value,Decimal):
        if not value.is_finite():raise ValueError('Không ghi số không hữu hạn.')
        return str(value)
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('Không ghi số không hữu hạn.')
        return json.dumps(value,allow_nan=False)
    pad='  '*(level+1);close='  '*level
    if isinstance(value,list):
        if not value:return '[]'
        return '[\n'+',\n'.join(pad+dumps(item,level+1) for item in value)+'\n'+close+']'
    if isinstance(value,dict):
        if any(not isinstance(key,str) for key in value):raise ValueError('Khóa JSON phải là chuỗi.')
        if not value:return '{}'
        return '{\n'+',\n'.join(pad+json.dumps(key,ensure_ascii=False)+': '+dumps(item,level+1) for key,item in value.items())+'\n'+close+'}'
    raise TypeError(f'Không thể ghi JSON cho kiểu {type(value).__name__}')
