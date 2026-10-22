"""Conservative explicit financial constraints; vector similarity is not a date filter."""
import re
import unicodedata
import json
from pathlib import Path
from functools import lru_cache


def label_text(value):
    text=unicodedata.normalize('NFD',value.lower().replace('đ','d'))
    text=''.join(c for c in text if unicodedata.category(c)!='Mn')
    text=' '.join(w for w in re.findall(r'[a-z0-9]+',text) if w!='va')
    # Equivalent Vietnamese labels, not a conversion of any financial value.
    return text.replace('ty suat sinh loi','ty suat loi nhuan').replace('ty suat loi nhuan','bien loi nhuan')


@lru_cache
def source_metric_labels():
    path=Path(__file__).resolve().parents[1]/'financial/data/reviewed_metric_links_v1.json'
    return json.loads(path.read_text(encoding='utf-8'))['links']


def financial_metric_codes(query,symbols):
    """Exact source labels only; this does not certify units or reporting scope."""
    if not symbols:return None
    # Instructions distinguishing excluded metrics must not become search targets.
    question=re.split(r'\b(?:không|phân biệt|nêu đơn vị|nếu đơn vị)\b',query,flags=re.I)[0]
    normalized=' '+label_text(question)+' ';matches=[]
    for row in source_metric_labels():
        if not set(symbols).intersection(row['symbols']):continue
        target=row.get('target') or {}
        labels=[row['canonical_name'],target.get('chosen_name',''),*target.get('aliases',[])]
        for label in labels:
            name=label_text(label)
            if len(name.split())>=3 and ' '+name+' ' in normalized:matches.append((row['code'],name))
        if re.search(r'\b'+re.escape(row['code'])+r'\b',question):matches.append((row['code'],row['code']))
    # Prefer the full concept over labels contained inside it, e.g. fixed assets
    # inside cash paid to purchase fixed assets.
    selected={code for code,name in matches if not any(
        name!=other and ' '+name+' ' in ' '+other+' ' for _,other in matches)}
    return sorted(selected) or None


def financial_query_scope(query):
    text=unicodedata.normalize('NFD',query.lower())
    text=''.join(c for c in text if unicodedata.category(c)!='Mn').replace('đ','d')
    if any(word in text for word in ('bai tin','tin tuc','bai viet','fireant','cafef','cafe f',
        'gia co phieu','phien gia','lich su gia')):
        return None,None
    if not any(word in text for word in ('bctc','bao cao','clean','du lieu nguon',
        'doanh thu','loi nhuan','tien va','tai san','no vay','roe','eps')):
        return None,None
    symbols=re.findall(r'\b[A-Z]{3}\b',query)
    symbols=[s for s in symbols if s not in {'PDF','ROE','ROA','EPS','VND','BCT','USD'}]
    known={symbol for row in source_metric_labels() for symbol in row['symbols']}
    symbols.extend(symbol for symbol in known if re.search(r'\b'+re.escape(symbol)+r'\b',query,re.I))
    if len(set(symbols))!=1:return None,None
    periods={f'{year}-Q{quarter}' for year,quarter in re.findall(r'\b(20\d{2})[- /]*q([1-4])\b',text)}
    periods.update(f'{year}-Q{quarter}' for quarter,year in re.findall(r'quy\s*([1-4])\s*(?:/|nam)?\s*(20\d{2})',text))
    if not periods:
        years=set(re.findall(r'\b20\d{2}\b',text))
        if len(years)==1:periods={next(iter(years))+'-YEAR'}
    return ([symbols[0]],sorted(periods)) if periods else (None,None)
