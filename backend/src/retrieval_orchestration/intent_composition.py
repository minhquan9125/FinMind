"""Experimental clause evidence; never maps a query to a production route."""
import re
import unicodedata
import numpy as np


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('đ','d'))
                   if unicodedata.category(c)!='Mn')


def _request(text):
    text=_plain(text.strip())
    return bool(re.match(r'^(ai|cho|hay|tim|liet ke|tom tat|tom luoc|trich|chep|giai thich|xac dinh|danh gia|nhan dinh|so sanh|doi chieu|tong hop|xin)\b',text)
                or re.search(r'\b(ai|nao|la gi|bao nhieu|the nao|ra sao|hay khong)\b',text))


def _support(text):
    plain=_plain(text)
    return bool(re.search(r'\b(lam bang chung|bang chung cho cau tra loi|dan nguon cho cau tra loi|kem nguon cho cau tra loi)\b',plain)
                or re.match(r'^\s*[A-ZĐ]{2,8}\s*=',text))


def requests(text):
    if not isinstance(text,str) or not text.strip():
        raise ValueError('INVALID_QUESTION')
    sentences=re.split(r'[?;\n]+|\.\s+(?=[A-ZĐ])',text)
    result=[]
    support_removed=False
    connector=r'\s+(và|va|rồi|roi|đồng thời|dong thoi|sau đó|sau do|kèm|kem)\s+'
    for sentence in sentences:
        if not sentence.strip(): continue
        tokens=re.split(connector,sentence,flags=re.IGNORECASE)
        current=tokens[0]
        chunks=[]
        for i in range(1,len(tokens),2):
            word,right=tokens[i],tokens[i+1]
            if _request(current) and (_request(right) or _support(right)):
                chunks.append(current.strip()); current=right
            else:
                current+=' '+word+' '+right
        chunks.append(current.strip().rstrip('.'))
        for chunk in chunks:
            if result and _support(chunk):
                support_removed=True
                continue
            if _request(chunk): result.append(chunk)
    # Remove explicit support text only; do not rewrite ordinary single requests.
    return result if len(result)>=2 or (result and support_removed) else [text]


def combine_scores(base,parts,labels):
    base=np.asarray(base,dtype=np.float64)
    values=np.asarray(parts,dtype=np.float64)
    if (base.shape!=(len(labels),) or not np.isfinite(base).all()
            or (base<0).any() or (base>1).any() or 'MIXED' not in labels):
        raise ValueError('INVALID_BASE_SCORES')
    support=0.
    component_labels=[]
    if values.size:
        if values.ndim!=2 or values.shape[1]!=len(labels) or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
            raise ValueError('INVALID_COMPONENT_SCORES')
        best=[min(range(len(labels)),key=lambda j:(-row[j],labels[j])) for row in values]
        for i,a in enumerate(best):
            for j in range(i+1,len(best)):
                b=best[j]
                if a!=b and labels[a]!='MIXED' and labels[b]!='MIXED':
                    score=min(values[i,a],values[j,b])
                    if score>support:
                        support=float(score); component_labels=[labels[a],labels[b]]
    scores=base.copy()
    scores[labels.index('MIXED')]=max(scores[labels.index('MIXED')],support)
    return dict(scores=scores,support=support,component_labels=component_labels)
