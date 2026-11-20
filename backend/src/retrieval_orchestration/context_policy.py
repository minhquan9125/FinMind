"""Select reusable slots from explicit wording; never infer from full history."""
import copy
import re
from .retrieval_flow.intent import _fold
from .input_normalization import registered_symbols,conversational_words,normalize_user_text,ENGLISH_TERMS
from .market_dialogue import article_content_request
from .followup_scope import company_continuation


DETAIL_FOLLOWUP = (r'\b(?:chi tiet hon|chi tiet them|them chi tiet|ky hon|ro hon|cu the hon|sau hon|'
                   r'noi them|giai thich them)\b')


def unrecognized_input(text,context=None):
    """Reject wholly unknown tokens, without treating a vocabulary hit as intent.

    This is a conservative noise check, not a claim to understand arbitrary
    language. Recognized words still go through normal intent/scope resolution.
    """
    normalized=normalize_user_text(text,context)
    if normalized.strip().lower() in ('/new','/moi'):return False
    words=set(re.findall(r'\w+',_fold(normalized)))
    if not words:return True
    if re.fullmatch(r'[\d\s./-]+',normalized):return False
    known=set(conversational_words())|set(ENGLISH_TERMS)|{s.lower() for s in registered_symbols()}
    known.update('nguon source tom tat tong hop chi tiet hon dung huy tiep ke liet ro sao khi nao ai ceo cfo hdqt bctn bctc roa roe eps'.split())
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    known.update(word for alias in DEFAULT_COMPANIES for word in _fold(alias).split())
    if re.fullmatch(r'[A-Z]{3,5}',normalized.strip()):return False
    # A newly supplied multi-word person name is a legitimate graph lookup.
    if re.search(r'\bla ai\b',_fold(normalized)):return False
    return not bool(words&known)


def asks_unspecified_company(text):
    return bool(re.search(r'\b(?:ma|co phieu|cong ty|doanh nghiep|ngan hang)\s+(?:nao|gi|chi)\b',_fold(text)))


def question_context(question, context, today):
    if not context:
        return context
    norm = _fold(question).strip(' .?!')
    if asks_unspecified_company(question):
        # "mã nào..." requests a choice across companies, not the last ticker.
        return {k:copy.deepcopy(v) for k,v in context.items() if k=='_investor_focus'}
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    symbols=[s for s in registered_symbols() if re.search(r'\b'+re.escape(s.lower())+r'\b',norm)]
    for alias,targets in DEFAULT_COMPANIES.items():
        if re.search(r'\b'+re.escape(alias)+r'\b',norm):
            symbols.extend(s for s in targets if s not in symbols)
    if company_continuation(question,symbols,DEFAULT_COMPANIES):
        retained=copy.deepcopy(context)
        if symbols!=context.get('companies'):
            for key in ('_article_urls','_article_anchor','_article_subject_quotes','_admin_source_url'):
                retained.pop(key,None)
        return retained
    # "chi tiết hơn về FPT" right after an analysis continues it, even though it names the company again.
    if (context.get('_market_request') or {}).get('kind') == 'ANALYSIS' and re.search(DETAIL_FOLLOWUP, norm):
        return copy.deepcopy(context)
    # A financial noun alone does not switch an explicitly continuing article
    # to statement rows. New report/price requests still select their own source.
    if (context.get('source_type')=='NEWS'
            and (context.get('_article_urls')or context.get('_market_request',{}).get('query'))
            and (re.match(r'^(?:the )?con\b',norm)or re.search(r'\bthi sao$',norm))
            and (not symbols or set(symbols)==set(context.get('companies')or[]))
            and not re.search(r'\b(?:bctc|bctn|bao cao tai chinh|bao cao thuong nien|gia co phieu|thi gia)\b',norm)):
        return copy.deepcopy(context)
    # Slot replies intentionally continue the previous request.
    if re.fullmatch(r'(?:(?:the )?con |nam |quy )?(?:[a-z]{2,5}|\d{1,4})(?: thi sao)?', norm):
        return copy.deepcopy(context)
    # A linking phrase does not make a new subject inherit stale filters.
    # Explicit role/metric/source words replace the old subject before routing.
    from .metric_vocabulary import find_metrics
    graph_subject=bool(re.search(r'\b(?:chu tich|giam doc|hdqt|hoi dong quan tri|ban dieu hanh|co dong|cong ty con|chuc vu|nhan su)\b',norm))
    explicit_source=bool(re.search(r'\b(?:bctn|bctc|bao cao|tin tuc|gia co phieu|thi gia)\b',norm))
    if re.match(r'^(?:the |vay )?con\b',norm) and (find_metrics(norm) or graph_subject or explicit_source):
        selected={'companies':symbols or list(context.get('companies')or[])}
        compatible=(graph_subject and context.get('source_type')=='BCTN') or (find_metrics(norm) and context.get('source_type')=='BCTC')
        if compatible and not explicit_source:
            for key in ('source_type','periods','reporting_entity'):
                if key in context:selected[key]=copy.deepcopy(context[key])
        return selected
    if (re.search(r'\bgiu (?:nguyen )?(?:chi tieu|ky)\b', norm)
            or re.match(r'^(?:the )?con\b', norm)):
        return copy.deepcopy(context)
    source = None
    if article_content_request(question, today) or re.search(r'\b(?:tin tuc|news)\b', norm):
        source = 'NEWS'
    elif re.search(r'\b(?:bctn|bao cao thuong nien)\b', norm):
        source = 'BCTN'
    elif (re.search(r'\b(?:bctc|bao cao tai chinh|doanh thu|loi nhuan|tong tai san|no phai tra)\b', norm)
          and not (context.get('source_type')=='BCTN' and not re.search(r'\bbctc|bao cao tai chinh\b', norm)
                   and re.search(r'\b(?:ke hoach|chien luoc|dinh huong|thuyet minh)\b', norm))):
        source = 'BCTC'
    elif re.search(r'\b(?:gia co phieu|gia dong cua|thi gia|gia [a-z]{3})\b', norm):
        source = 'PRICE'
    symbols = [s for s in registered_symbols() if re.search(r'\b'+re.escape(s.lower())+r'\b', norm)]
    from .source_intent import generic_annual_report
    if generic_annual_report(question):source='BCTN'
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    for alias, targets in DEFAULT_COMPANIES.items():
        if re.search(r'\b'+re.escape(alias)+r'\b', norm):
            symbols.extend(s for s in targets if s in registered_symbols() and s not in symbols)
    explicit_company = bool(symbols and len(norm.split()) >= 4)
    if explicit_company or (source and source != context.get('source_type')):
        # Never carry a previous year, person, article URL, pending slot or graph
        # restriction into a standalone new company/source question.
        return {'companies': symbols or list(context.get('companies') or [])}
    return copy.deepcopy(context)
