"""Calendar slots and references to articles already shown in this conversation."""
import copy
from datetime import date, timedelta
import re

from .retrieval_flow.intent import _fold, TICKERS
from ..b1_answering.evidence.citations import CitationError, prepare_evidence


def article_query(question):
    """Recognize a supplied headline/body excerpt, without requiring prior news."""
    norm = _fold(question).strip(' .?!')
    match = re.search(r'\b(?:chi tiet|noi dung|tom tat)\s+(?:(?:bai(?: viet)?|ve|tin(?: tuc)?)\s*)?:?\s*(.+)', norm)
    if not match: return None
    target = re.sub(r'\s+(?:cho (?:t|toi|minh)|giup (?:toi|minh))$', '', match[1]).strip(' :')
    if len(target.split()) < 3: return None
    scope_words = {'tin', 'tuc', 'news', 'moi', 'nhat', 'hom', 'nay', 'qua', 'kia', 'cua', 'cho', 'toi', 'minh',
                   'giup', 'ngay', 'thang', 'nam', 've', 'hien', 'tai', 'tren', 'fireant', 'cafef'}
    ticker_words = {symbol.lower() for symbol in (*TICKERS, 'SSI', 'CTR', 'VNM', 'MSN', 'NLG')}
    meaningful = [word for word in re.findall(r'[a-z]+', target)
                  if word not in scope_words | ticker_words]
    if len(meaningful) < 2: return None
    if re.fullmatch(r'(?:tin tuc|news)\s+\w+\s+(?:hom nay|moi nhat)', target): return None
    if re.match(r'(?:tong tai san|loi nhuan|doanh thu|no phai tra|tien va tuong duong tien)\b', target): return None
    return target


def _search_text(text):
    return ' '.join(re.findall(r'[a-z0-9]+', _fold(text)))


def matching_articles(query, items, claims=()):
    """Prefer titles and saved claim bindings; use conservative content overlap."""
    norm = _search_text(query)
    exact = [item for item in items if _search_text(item['title']) in norm]
    if exact: return exact
    for claim in claims:
        text = _search_text(claim.get('text', ''))
        if len(text.split()) >= 5 and text in norm:
            ids = claim.get('evidence_ids', [])
            matches = [item for item in items if item.get('evidence_id') in ids]
            if matches: return matches
    stop = {'cho', 'toi', 'minh', 'biet', 'chi', 'tiet', 'tom', 'tat', 'noi', 'dung', 've', 'bai', 'tin', 'tuc',
            'cua', 'va', 'la', 'co', 'cac', 'nhung', 'duoc', 'trong', 'voi', 'tu', 'tai', 'the', 'nay', 'do'}
    words = set(norm.split())-stop
    if len(words) < 4: return []
    scored = []
    for item in items:
        source = item.get('passage') or ' '.join(str(item.get(k) or '') for k in ('title', 'description', 'content'))
        score = len(words & set(_search_text(source).split()))/len(words)
        if score >= .75: scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for score, item in scored if scored[0][0]-score < .15] if scored else []


def calendar_day(norm, today):
    for phrase, offset in (('hom kia', 2), ('hom qua', 1), ('hom nay', 0)):
        if phrase in norm: return (today-timedelta(days=offset)).isoformat()
    match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', norm)
    parts = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', norm)
    try:
        if match: return date.fromisoformat(match[1]).isoformat()
        if parts: return date(int(parts[3]), int(parts[2]), int(parts[1])).isoformat()
    except ValueError:
        return None
    return None


def news_reference(question, context, previous):
    """Only select URLs from a verified prior pack, never fetch arbitrary pasted URLs."""
    norm = _fold(question).strip(' .?!')
    previous = previous or {}
    if (context or {}).get('source_type') != 'NEWS': return None
    if previous.get('scope', {}).get('source_type') != 'NEWS': return None
    pack = previous.get('evidence_pack') or {}
    if pack.get('schema_version') != '1.2': return None
    if (context or {}).get('companies') != previous['scope'].get('companies'): return None
    try: items = list(prepare_evidence(pack).values())
    except CitationError: return None
    wants_detail = bool(re.search(r'\b(?:chi tiet|noi dung|bai nay|bai do|bai tren|tin nay|tom tat)\b', norm))
    matches = matching_articles(question, items, (previous.get('answering') or {}).get('claims', []))
    numbered = re.search(r'\b(?:bai|tin)\s*(?:so|thu)?\s*(\d+)\b', norm)
    if not numbered and (context or {}).get('_pending_article') and norm.isdigit():
        numbered = re.fullmatch(r'(\d+)', norm)
    if numbered:
        index = int(numbered[1])-1
        matches = [items[index]] if 0 <= index < len(items) else []
        wants_detail = True
    summarize_list = re.fullmatch(r'(?:tom tat|tong hop)(?: lai| di| giup toi)?', norm)
    if summarize_list: matches = items[:2]
    if not matches and not numbered and article_query(question): return None
    if not matches and not numbered and re.search(r'\b(?:tin tuc|news|hom nay|hom qua|moi nhat)\b', norm):
        return None  # a new market request, not an implicit choice of an old article
    if not matches and wants_detail and len(items) == 1 and re.search(r'\b(?:bai nay|bai do|bai tren|tin nay)\b', norm):
        matches = items
    if not wants_detail and not matches: return None
    # A new explicit company request must leave the old article context.
    explicit_symbols = re.findall(r'\b[A-Z]{3}\b', question)
    allowed = previous['scope'].get('companies', [])
    if any(symbol not in allowed and symbol not in ('VND', 'USD', 'UBN') for symbol in explicit_symbols):
        return None
    scope = copy.deepcopy(previous['scope'])
    scope.pop('_clarification_state', None)
    scope.pop('_pending_article', None)
    scope.pop('_article_urls', None)
    if not matches or (len(matches) > 1 and not summarize_list):
        scope['_pending_article'] = True
        return dict(decision='ASK_CLARIFICATION', reason_code='MISSING_ARTICLE', scope=scope,
                    message='Bạn muốn xem chi tiết bài nào trong các bài vừa hiển thị?',
                    clarification_options=[dict(id=str(i), label=item['title'],
                                                reply='Chi tiết bài: '+item['title'], description='')
                                           for i, item in enumerate(items, 1)])
    scope['_article_urls'] = [item['locator']['url'] for item in matches[:2 if summarize_list else 1]]
    scope['_market_request'] = {key: value for key, value in scope.get('_market_request', {}).items() if key != 'query'}
    scope['_market_request'] = {**scope['_market_request'], 'kind': 'NEWS',
                                'action': 'SUMMARY' if 'tom tat' in norm else 'DETAIL'}
    return dict(decision='MARKET_LOOKUP', reason_code='ARTICLE_REFERENCE', scope=scope,
                message='Đang đọc nội dung bài đã chọn.')
