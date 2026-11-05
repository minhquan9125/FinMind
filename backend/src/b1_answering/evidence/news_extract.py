"""Exact source excerpts for indexed admin News when generation is unavailable."""
import re

from .grounded import _fold, validate_grounded
from .citations import CitationError


def missing_quarters(question, evidence):
    pattern = r'\b(?:quy\s*|q)([1-4])\b'
    requested = set(re.findall(pattern, _fold(question)))
    present = set(re.findall(pattern, _fold('\n'.join(e['passage'] for e in evidence.values()))))
    return sorted(requested - present)


def missing_years(question, evidence):
    requested=set(re.findall(r'\b20\d{2}\b',question))
    text=_fold('\n'.join(e['passage'] for e in evidence.values()))
    # Law numbers such as 96/2020/TT-BTC are not a reporting-period assertion.
    present=set(re.findall(r'(?:\bnam\s*|\b(?:q[1-4]|quy\s*[1-4])\s*[/\-]?\s*(?:nam\s*)?)(20\d{2})',text))
    return sorted(requested-present)


def source_excerpt(question, evidence, scope):
    """Return exact, validated passages only; never infer facts or repair OCR."""
    query = _fold(question)
    reason = any(term in query for term in ('nguyen nhan', 'vi sao', 'tai sao'))
    all_metrics = ('doanh thu','loi nhuan gop','loi nhuan sau thue',
                   'chi phi tai chinh','loi nhuan khac')
    metrics = [term for term in all_metrics if term in query]
    if reason:
        terms = ('chu yeu', 'lien quan', 'nguyen nhan')
    elif 'loi nhuan sau thue' in query or 'lnst' in query:
        terms = ('loi nhuan sau thue',)
    else:
        return None
    candidates = []
    for eid, item in evidence.items():
        if item.get('source_type') != 'NEWS': continue
        passage = item['passage']
        lines = list(re.finditer(r'[^\n]+', passage))
        for i, line in enumerate(lines[1:], 1):
            text = line.group()
            folded = _fold(text)
            if not any(term in folded for term in terms): continue
            score = 0
            if reason:
                if any(term in folded for term in all_metrics) and not any(term in folded for term in metrics):
                    continue
                window = folded + (' ' + _fold(lines[i+1].group()) if i+1 < len(lines) else '')
                score = 20 * sum(term in folded for term in metrics) + 10 * sum(term in window for term in metrics)
                if not metrics: continue
            else:
                score = 10 * bool(re.search(r'\d[\d.,]{5,}', text))
            if not score: continue
            start = lines[i-1].start() if not reason and re.search(r'\b(?:q[1-4]|dien giai)\b', _fold(lines[i-1].group())) else line.start()
            end = line.end()
            next_is_other_metric = reason and i+1 < len(lines) and any(
                term in _fold(lines[i+1].group()) for term in all_metrics if term not in metrics)
            if reason and i+1 < len(lines) and not next_is_other_metric and lines[i+1].end()-start <= 300:
                end = lines[i+1].end()
            quote = passage[start:end]
            if len(quote) > 300:
                quote = quote[:300].rsplit(' ', 1)[0]
            candidates.append((score, eid, quote))
    for _, eid, quote in sorted(candidates, key=lambda c:c[0], reverse=True):
        try:
            return validate_grounded({'claims':[{'text':quote,'evidence_ids':[eid],
                'support_quotes':[{'evidence_id':eid,'quote':quote}]}]}, evidence, scope)
        except CitationError:
            continue
    return None
