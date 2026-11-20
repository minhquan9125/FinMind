"""Calendar slots and references to articles already shown in this conversation."""
import copy
from datetime import date, timedelta
import re

from .retrieval_flow.intent import _fold, TICKERS
from ..b1_answering.evidence.citations import CitationError, prepare_evidence


def article_query(question):
    """Recognize a supplied headline/body excerpt, without requiring prior news."""
    norm = _fold(question).strip(' .?!')
    quoted = re.search(r'\b(?:bai(?: viet| bao)?|tin(?: tuc)?|trong)\s+[“"‘]([^”"’]+)[”"’]', norm)
    if quoted and len(quoted[1].split()) >= 3:
        return quoted[1]
    match = re.search(r'^(?:(?:cho|giup) (?:toi|minh|em|t) (?:biet )?|(?:ban )?(?:hay )?)?'
                      r'(?:chi tiet|noi dung|tom tat)\s+(?:(?:bai(?: viet)?|ve|tin(?: tuc)?)\s*)?:?\s*(.+)', norm)
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


def article_content_request(question, today):
    """An explicit article/announcement question is content, not graph lookup."""
    norm = _fold(question).strip(' .?!')
    reference = re.search(r'\b(?:trong|theo|ve)\s+(?:bai(?: viet| bao)?|tin(?: tuc)?)\b|\btheo bai\b|\bbai dang\b|\bdang ngay\b|\btin (?:nay|do|dang)\b|'
                          r'\b(?:theo|trong)\s+(?:thong bao|nghi quyet|quyet dinh)\b', norm)
    # A user can name the article directly ("Bài ELC ước doanh thu...")
    # or refer to its wording ("được bài ghi nhận..."). Financial words
    # inside that question must not turn it into statement-metric selection.
    reference = reference or (not article_query(norm) and re.search(
        r'\bbai(?: viet| bao)?\s+(?!(?:toan|hoc|tap|bao cao|nay|do|tren)\b)\w+', norm))
    reference = reference or re.search(
        r'\btin\s+(?:[a-z]{2,5}\s+)?(?:ngay\s+)?\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b',norm)
    reference = reference or re.search(r'\btin\s+(?:ngay\b|\d{1,2}[/.-]\d{1,2})',norm)
    # A supplied article topic need not contain the phrase "theo bài".
    # Keep short/latest feed requests as lists and generic "theo tin tức"
    # relationship discovery with the router below.
    headline_words=set(re.findall(r'[a-z]+',norm))-set(
        'tin tuc moi nhat cua cho toi gi ai nao co la bao nhieu hom nay ve thong biet tim doc xem'.split())
    headline_words-={symbol.lower()for symbol in TICKERS}
    explicit_news_search=re.search(r'^(?:tim|doc|xem)\s+tin\b',norm)
    news_topic_question=(re.search(r'^tin\s+(?!tuc\b|moi\b)',norm)
        and re.search(r'\b(?:gi|nao|ai|vi sao|tai sao|noi dung|tom tat)\b',norm))
    if ((explicit_news_search or news_topic_question) and len(headline_words)>=4):
        reference=True
    report = re.search(r'\b(?:bctn|bctc|bao cao thuong nien|bao cao tai chinh)\b', norm)
    if report:
        reference = reference or re.search(r'\b(?:tim|doc|xem)\s+tin\b', norm)
        if not reference:return None
    announcement = re.search(r'\b(?:thong bao|nghi quyet|quyet dinh)\b', norm)
    relocation = re.search(r'\bchi nhanh\b.*\b(?:thay doi|chuyen|doi)\s+(?:dia diem|dia chi|tru so)\b', norm)
    question_cue = re.search(r'\b(?:ai|gi|nao|bao nhieu|vi sao|tai sao|tom tat|noi dung|cho biet)\b', norm)
    # Loan/deposit rates and corporate transaction announcements are document
    # content, not accounting profit or daily stock-price arithmetic.
    content_event = re.search(r'\b(?:lai suat|lai vay|lai tien gui|lai tiet kiem|'
        r'dang ky mua|dang ky ban|mua lai(?: trai phieu)? truoc han|huy niem yet|chao ban|'
        r'gia ban co phieu|giao dich noi bo|bao cao quan tri)\b', norm)
    if re.search(r'\b(?:theo|trong) tin tuc\b', norm) and not content_event:
        from .hybrid_router.intent_policy import GRAPH_TERMS, contains
        from .metric_vocabulary import find_metrics
        if (contains(norm, GRAPH_TERMS) and not find_metrics(norm)
                and not re.search(r'\b(?:bai|dang|ngay|thong bao|nghi quyet|quyet dinh)\b', norm)):
            return None  # a source type for relation search, not a selected article
    if not reference and not content_event and not ((announcement or relocation) and question_cue):
        return None
    # Keep effective/balance dates in the content query. Only an explicitly
    # requested publication date may narrow the article's published_at field.
    publication = re.search(r'\b(?:dang|cong bo|tin|thong bao|nghi quyet|quyet dinh)\s+(?:vao\s+)?ngay\b|\bngay dang\b', norm)
    publication=publication or re.search(r'\btin\s+\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b',norm)
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    aliases={s.lower()for s in TICKERS}|{alias for alias,ids in DEFAULT_COMPANIES.items()
        if len(ids)==1 and ids[0]in TICKERS}
    company_token='(?:'+'|'.join(re.escape(alias)for alias in sorted(aliases,key=len,reverse=True))+')'
    publication=publication or re.search(
        r'\b(?:tin(?: tuc)?|bai(?: viet| bao| dang)?)\s+(?:cua\s+)?'+company_token+
        r'\s+(?:dang\s+)?ngay\s+\d',norm)
    query = re.sub(r'\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b', '', norm) if publication else norm
    query = re.sub(r'\b(?:trong|theo)\s+(?:bai(?: viet| bao)?|tin)(?: dang)?(?: ngay)?\b', '', query)
    query = re.sub(r'\btheo\s+(?:thong bao|nghi quyet|quyet dinh)(?: ngay)?\b', '', query)
    if re.search(r'\b(?:bai(?: viet| bao)?|tin(?: tuc)?|trong)\s+[“"‘]', norm):
        query = article_query(norm) or query
    month=re.search(r'\b(?:trong\s+)?thang\s+(\d{1,2})[/ -](\d{4})\b',norm)
    month_value=None
    if month and not re.search(r'\b(?:hieu luc|ap dung|du kien|thuc hien|ky bao cao|bao phu)\b',norm):
        if not 1<=int(month[1])<=12:
            return dict(kind='NEWS',action='DETAIL',day=None,query=query.strip(),invalid_date=True)
        month_value=f'{month[2]}-{int(month[1]):02}'
    # A balance/event date inside an article is not its publication date.
    return dict(kind='NEWS', action='DETAIL', day=calendar_day(norm, today) if publication else None,
                query=query.strip(),**({'month':month_value} if month_value else {}))


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
            'cua', 'va', 'la', 'co', 'cac', 'nhung', 'duoc', 'trong', 'voi', 'tu', 'tai', 'the', 'nay', 'do',
            'ai', 'lam', 'gi', 'nao', 'nhu', 'sao', 'dang', 'ngay', 'theo', 'thang', 'nam'}
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
    if (re.search(r'\b(?:bctc|bctn|bao cao tai chinh|bao cao thuong nien)\b',norm)
            and not article_content_request(question,date.today())):
        return None
    if (context or {}).get('source_type') not in ('NEWS','CONTENT'): return None
    if previous.get('scope', {}).get('source_type') not in ('NEWS','CONTENT'): return None
    pack = previous.get('evidence_pack') or {}
    if pack.get('schema_version') not in ('1.1', '1.2'): return None
    if (context or {}).get('companies') != previous['scope'].get('companies'): return None
    try: items = list(prepare_evidence(pack).values())
    except CitationError: return None
    used={eid for claim in (previous.get('answering')or{}).get('claims',[])for eid in claim.get('evidence_ids',[])}
    if used:
        items=[item for item in items if item.get('evidence_id')in used]
    # General content search can return a verified news article. It remains a
    # valid follow-up anchor only when every item is NEWS with a real bound URL.
    if not items or any(i.get('source_type')!='NEWS' or not i.get('locator',{}).get('url')for i in items):return None
    articles = list({item['locator'].get('url'): item for item in reversed(items)}.values())
    articles.reverse()
    elliptical = bool(re.fullmatch(r'(?:(?:con|vay|the)\s+)?(?:ba ay|ong ay|nguoi do|ho|viec do|'
        r'tu ngay nao|khi nao|ten day du|hieu luc|du kien|khoang nao|bao nhieu co phieu|ty le)\b.*', norm))
    elliptical=elliptical or bool(re.fullmatch(
        r'(?:sau do (?:nam giu|so huu)(?: ty le)?(?: nao| bao nhieu| bao nhieu phan tram)?|'
        r'co quan nao (?:nhac|nhac nho|ban hanh)|tu ngay nao co hieu luc)',norm))
    wants_detail = elliptical or bool(re.search(r'\b(?:chi tiet|noi dung|bai nay|bai do|bai tren|tin nay|tom tat)\b', norm))
    from .metric_vocabulary import find_metrics
    metric_followup=bool(find_metrics(norm) and (re.match(r'^(?:the )?con\b',norm)or re.search(r'\bthi sao$',norm))
            and not re.search(r'\b(?:bctc|bctn|bao cao tai chinh|bao cao thuong nien)\b',norm))
    if metric_followup:
        wants_detail=True
    matches = matching_articles(question, items, (previous.get('answering') or {}).get('claims', []))
    numbered = re.search(r'\b(?:bai|tin)\s*(?:so|thu)?\s*(\d+)\b', norm)
    if not numbered and (context or {}).get('_pending_article') and norm.isdigit():
        numbered = re.fullmatch(r'(\d+)', norm)
    if numbered:
        index = int(numbered[1])-1
        matches = [item for item in items if item['locator'].get('url') == articles[index]['locator'].get('url')] if 0 <= index < len(articles) else []
        wants_detail = True
    summarize_list = re.fullmatch(r'(?:tom tat|tong hop)(?: lai| di| giup toi)?', norm)
    if summarize_list:
        selected = {item['locator'].get('url') for item in articles[:2]}
        matches = [item for item in items if item['locator'].get('url') in selected]
    if not matches and not numbered and article_query(question): return None
    if not matches and not numbered and re.search(r'\b(?:tin tuc|news|hom nay|hom qua|moi nhat)\b', norm):
        return None  # a new market request, not an implicit choice of an old article
    article_urls = {item['locator'].get('url') for item in items}
    if not matches and wants_detail and len(article_urls) == 1 and (elliptical or metric_followup or re.search(r'\b(?:bai nay|bai do|bai tren|tin nay)\b', norm)):
        matches = items
    if not wants_detail and not matches: return None
    # A new explicit company request must leave the old article context.
    explicit_symbols = re.findall(r'\b[A-Z]{3}\b', question)
    allowed = previous['scope'].get('companies', [])
    if any(symbol not in allowed and symbol not in ('VND', 'USD', 'UBN') for symbol in explicit_symbols):
        return None
    scope = copy.deepcopy(previous['scope'])
    scope['source_type']='NEWS'
    scope.pop('_content_question',None)
    scope.pop('_clarification_state', None)
    scope.pop('_pending_article', None)
    scope.pop('_article_urls', None)
    if not matches or (len({item['locator'].get('url') for item in matches}) > 1 and not summarize_list):
        scope['_pending_article'] = True
        return dict(decision='ASK_CLARIFICATION', reason_code='MISSING_ARTICLE', scope=scope,
                    message='Bạn muốn xem chi tiết bài nào trong các bài vừa hiển thị?',
                    clarification_options=[dict(id=str(i), label=item['title'],
                                                reply='Chi tiết bài: '+item['title'], description='')
                                           for i, item in enumerate(articles, 1)])
    scope['_article_urls'] = list(dict.fromkeys(item['locator']['url'] for item in matches))[:2 if summarize_list else 1]
    # Carry source pointers, not the whole conversation. The reader replays and
    # verifies these chunks again; important facts may be beyond the PDF prefix.
    scope['_article_anchor']=dict(corpus_version_id=pack['corpus_version_id'],
        index_version_id=pack['data_version']['id'],chunks=[
            dict(document_id=i['source_id'],chunk_id=i['chunk_id'])for i in matches[:8]])
    scope['_article_subject_quotes']=[q['quote']for claim in (previous.get('answering')or{}).get('claims',[])
        for q in claim.get('support_quotes',[])if len(q.get('quote',''))<=400
        and any(i['evidence_id']==q.get('evidence_id')and q['quote']in i['passage']for i in matches)][:2]
    scope['_market_request'] = {key: value for key, value in scope.get('_market_request', {}).items() if key != 'query'}
    scope['_market_request'] = {**scope['_market_request'], 'kind': 'NEWS',
                                'action': 'SUMMARY' if 'tom tat' in norm else 'DETAIL'}
    return dict(decision='MARKET_LOOKUP', reason_code='ARTICLE_REFERENCE', scope=scope,
                message='Đang đọc nội dung bài đã chọn.')
