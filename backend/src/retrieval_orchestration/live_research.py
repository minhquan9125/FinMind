"""Read-only corpus retrieval and B1 composition for the existing web chat.

Fixture grammar/registries are deliberately kept outside this production path.
Conversation state is a value persisted in the owner's existing JSON session.
"""
from __future__ import annotations

import asyncio
import calendar
import copy
from datetime import date, datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path
import re
import threading
import uuid

from ..b1_answering.application.service import complete_retrieval
from ..b1_answering.core.policy import Budget, Limits
from ..b1_answering.evidence.citations import CitationError, prepare_evidence
from ..b1_answering.evidence.live_contract import reporting_entity_matches
from ..documents import repository
from ..documents.chunk_reconstruction import ReconstructionError
from .retrieval_flow.conversation import _resolve_relative_periods, STOP_WORDS
from .retrieval_flow.intent import _fold, _period, TICKERS
from .clarifications import apply_clarification, metric_group, resolve_reply
from .market_dialogue import article_query, calendar_day, news_reference
from .input_normalization import normalize_user_text, conversational_words, registered_symbols
from .market_dates import price_date_request, relative_market_range, temporal_reply
from .metric_vocabulary import (CURATED, find_metrics, label as metric_label, plain, point_in_time_codes,
                                vocabulary_words, without_metrics)

V4_CORPUS = '33d33730-0f0a-5274-a7f8-8d32a6be07e8'
MODEL = 'BAAI/bge-m3@5617a9f61b02'
_embedding_lock = threading.Lock()
# The vocabulary (curated aliases plus the ingestion catalog) lives in metric_vocabulary; the name
# METRIC_ALIASES is kept for the modules that import the curated part from here.
METRIC_ALIASES = CURATED
POINT_METRICS = frozenset({'TOTAL_ASSETS', 'CASH_AND_CASH_EQUIVALENTS', 'SHORT_TERM_LOANS_AND_FINANCE_LEASES',
                 'LONG_TERM_LOANS_AND_FINANCE_LEASES', 'CURRENT_LIABILITIES', 'NON_CURRENT_LIABILITIES',
                 'CHARTER_CAPITAL', 'RETAINED_EARNINGS', 'TOTAL_LIABILITIES', 'TOTAL_EQUITY'}) | point_in_time_codes()


def _live_period(norm, metric, scope):
    """Resolve explicit quarter/year slots even across words or follow-up turns."""
    quarters = set(re.findall(r'\b(?:quy|q)\s*(\d+)\b', norm))
    years = set(re.findall(r'\b(?:19|20|21)\d{2}\b', norm))
    if quarters and (len(quarters) > 1 or any(not 1 <= int(q) <= 4 for q in quarters) or len(years) > 1):
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
        return None, 'AMBIGUOUS_PERIOD'
    whole_year = bool(re.search(r'\b(?:ca nam|toan nam)\b', norm))
    pending = scope.get('_pending_quarter')
    quarter = next(iter(quarters)) if quarters else str(pending) if pending and not whole_year else None
    if quarter and years:
        if len(years) != 1:
            return None, 'AMBIGUOUS_PERIOD'
        ytd = 'luy ke' in norm or (not quarters and scope.get('_pending_ytd', False))
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
        return _period(f"quy {quarter}/{next(iter(years))}"+(' luy ke' if ytd else ''),
                       'TOTAL_ASSETS' if metric in POINT_METRICS else metric)
    if quarters:
        scope['_pending_quarter'] = int(quarter)
        scope['_pending_ytd'] = 'luy ke' in norm
        scope.pop('periods', None)
        scope.pop('measure_basis', None)
        return None, None
    if years or whole_year:
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
    return _period(norm, 'TOTAL_ASSETS' if metric in POINT_METRICS else metric)


def _market_intent(norm, context, today):
    query = article_query(norm)
    if query:
        return {'kind': 'NEWS', 'day': None, 'action': 'SUMMARY' if 'tom tat' in norm else 'DETAIL', 'query': query}
    news = bool(re.search(r'\b(?:tin tuc|tin|news)\b', norm))
    short_price = re.search(r'\bgia\s+([a-z]{3})\b', norm)
    price = bool(re.search(r'\b(?:gia co phieu|thi gia|gia hien tai|gia hom nay|gia ra sao|gia bao nhieu|gia nhu (?:the )?nao)\b', norm)
                 or (short_price and short_price[1] not in {'von', 'tri', 'cua', 'ban', 'mua', 'dat', 'san', 'cao', 'day', 'goc'}))
    causal = bool(re.search(
        r'\b(?:vi sao|tai sao|nguyen nhan|do dau|ly do|tac dong|anh huong|he qua)\b', norm
    ))
    trend = bool(re.search(
        r'\b(?:dao nay|gan day|tinh hinh|khoi sac|trien vong|bien dong|the nao)\b', norm
    ))
    dated = bool(re.search(r'\b(?:quy|thang|nam|ngay)\s+\d|\b(?:19|20|21)\d{2}\b', norm))
    current = bool(re.search(r'\b(?:hom nay|hien tai|moi nhat|moi|bay gio|hn|hnay|nay)\b', norm))
    day = calendar_day(norm, today)
    action = 'SUMMARY' if re.search(r'\b(?:tom tat|tong hop|diem tin)\b', norm) else 'LIST'
    prior = (context or {}).get('_market_request')
    financial = metric_group(norm) or any(_fold(a) in norm for aliases in METRIC_ALIASES.values() for a in aliases)
    market_context = bool(re.search(
        r'\b(?:thi truong|thi truong chung khoan|chung khoan|ttck|tt|ck|vni|vn ?index|vnindex)\b', norm
    ))
    daily_digest_language = bool(re.search(
        r'\b(?:bien dong|co bien|co gi moi|co gi hot|co gi hay|tin moi|tin nong|tin noi bat|'
        r'diem tin|tong hop|do lua|rung lac|co song|day song|sap|lao doc|bung no|'
        r'co drama|co chuyen gi|co tin gi|nong gi|len xuong|bat thuong|xanh|do|the nao|nhu nao)\b', norm
    ))
    if market_context and current and daily_digest_language and not financial:
        return {
            'kind': 'NEWS', 'day': day or today.isoformat(), 'action': 'SUMMARY',
            'market_wide': True,
        }
    if (trend and not financial and (not price or causal)
            and not re.search(r'\b(?:nam|quy|thang)\s+\d|\b(?:19|20|21)\d{2}\b', norm)):
        return {'kind': 'ANALYSIS', 'day': today.isoformat(), 'action': 'ANALYSIS'}
    company_selection = (norm.isdigit() and
                         str(((context or {}).get('_clarification_state') or {}).get('id', '')).startswith('company:'))
    if not financial and not news and not company_selection:
        relative_range = relative_market_range(norm, today) if price else None
        if relative_range:
            return relative_range
        partial = price_date_request(norm, prior, explicit_price=price)
        if partial: return partial
    if (day is None and re.search(r'\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b', norm)
            and (price or (prior and prior.get('kind') == 'QUOTE'))):
        return {'kind': 'QUOTE', 'day': None, 'action': 'LIST', 'invalid_date': True}
    if day and prior and re.fullmatch(r'(?:con\s+)?(?:(?:hom|ngay)\s+)?(?:hom nay|hom qua|hom kia|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})(?:\s+thi sao)?', norm.rstrip(' .?!')):
        return {**copy.deepcopy(prior), 'day': day}
    market_day = day and (price or re.search(r'\bhom (?:nay|qua|kia)\b', norm) or day == today.isoformat())
    if (news or price) and (not dated or market_day):
        if price or news:
            if price and causal:
                return {'kind': 'ANALYSIS', 'day': day, 'action': 'ANALYSIS'}
            return {'kind': 'QUOTE' if price else 'NEWS', 'day': day, 'action': action}
    financial = metric_group(norm) or any(_fold(a) in norm for aliases in METRIC_ALIASES.values() for a in aliases)
    followup = re.fullmatch(r'(?:(?:con|ma|co phieu|cua|la)\s+)?[a-z]{3,5}|[1-9]|fireant|cafef', norm)
    if prior and not news and not price and not dated and not financial:
        if norm in ('hom nay', 'hien tai', 'moi nhat'):
            return {**copy.deepcopy(prior), 'day': today.isoformat() if norm == 'hom nay' else None}
        if prior['kind'] == 'NEWS' and re.fullmatch(r'(?:tom tat|tong hop)(?: lai| di| giup toi)?', norm):
            return {**copy.deepcopy(prior), 'action': 'SUMMARY'}
        if followup:
            return copy.deepcopy(prior)
    return None


def annual_requested(norm, context=None):
    if re.search(r'\b(?:bctn|bao cao thuong nien)\b', norm):
        return True
    return bool((context or {}).get('source_type') == 'BCTN'
                and (context or {}).get('_annual_question')
                and not re.search(r'\b(?:bctc|bao cao tai chinh|tin tuc|news|gia co phieu|thi gia)\b', norm))


def annual_scope(text, norm, scope, previous):
    """Report year is independent of publication dates and metric row codes."""
    previous = previous or {}
    anchors = re.findall(r'\b(?:bctn|bao cao thuong nien)(?:\s+(?:cua\s+)?[a-z]{3})?(?:\s+nam)?\s+((?:19|20|21)\d{2})\b', norm)
    years = list(dict.fromkeys(anchors or re.findall(r'\b(?:19|20|21)\d{2}\b', norm)))
    if re.search(r'\b(?:so sanh|doi chieu)\b', norm):
        years = list(dict.fromkeys(re.findall(r'\b(?:19|20|21)\d{2}\b', norm)))
    followup = bool(re.fullmatch(r'(?:con\s+)?(?:nam\s+)?(?:19|20|21)\d{2}[ ?!.]*', norm)
                    or (not previous.get('companies') and previous.get('_annual_question')
                        and re.fullmatch(r'[a-z]{3}[ ?!.]*', norm)))
    query = previous.get('_annual_question') if followup else text
    if followup and years:
        for old in previous.get('periods') or []:
            if re.fullmatch(r'\d{4}', old):
                query = re.sub(r'\b'+old+r'\b', years[0], query or text)
    for key in list(scope):
        if key.startswith('_pending_') or key in ('_metric_candidates', 'publisher', '_market_request',
                '_hybrid_context', 'graph_relations', 'graph_time_scope', 'measure_basis'):
            scope.pop(key, None)
    scope.update(source_type='BCTN', topic='ANNUAL_REPORT_TOPIC', metric_code=None,
                 reporting_entity='UNKNOWN', _annual_question=query or text)
    prior_years = [p for p in previous.get('periods') or [] if re.fullmatch(r'\d{4}', p)]
    latest = bool(re.search(r'\b(?:moi nhat|gan nhat|ky moi nhat)\b', norm))
    scope['periods'] = years or (prior_years if not latest and previous.get('source_type') == 'BCTN'
        and (not previous.get('companies') or scope.get('companies') == previous.get('companies')) else []) or ['LATEST_AVAILABLE_PERIOD']
    if not scope.get('companies'):
        return 'ASK_CLARIFICATION', 'MISSING_COMPANY', 'Bạn muốn tra báo cáo thường niên của công ty nào?'
    if len(scope['companies']) > 2 or len(scope['periods']) > 2:
        return 'ASK_CLARIFICATION', 'SCOPE_TOO_LARGE', 'Vui lòng hỏi tối đa hai công ty và hai năm báo cáo mỗi lần.'
    if len(years) > 1 and not re.search(r'\b(?:so sanh|doi chieu)\b', norm):
        return 'ASK_CLARIFICATION', 'AMBIGUOUS_ANNUAL_YEAR', 'Bạn muốn tra báo cáo thường niên của năm nào?'
    return 'SEARCH', 'ANNUAL_REPORT_SCOPE_READY', 'Đang tìm nội dung trong báo cáo thường niên đúng công ty và năm báo cáo.'


_FUNCTION_WORDS = STOP_WORDS | set(
    'la bao nhieu gi nao cua trong nam quy thang ngay tai thoi diem theo va cac nhung co duoc da dang se khong '
    'hay cho biet toi minh ban xin hoi ve thi ma voi tu den o ra lam sao ai dau khi nay do kia a nhe giup xem '
    'tra cuu thong tin cong ty tap doan ngan hang phan tram so lieu con mot hai ba'.split())


def _is_open_question(norm, scope):
    """True for a real question (three or more content words), not a bare company, period or reply."""
    tickers = {symbol.lower() for symbol in scope.get('companies') or []}
    words = {word for word in re.findall(r'[a-z]+', plain(norm))
             if len(word) > 1 and word not in _FUNCTION_WORDS and word not in tickers}
    return len(words) >= 3


def analyze_live(text, context=None, *, today=None):
    """Resolve explicit slots and follow-ups without generating values or SQL."""
    today = today or datetime.now(timezone(timedelta(hours=7))).date()
    raw_market_request = _market_intent(_fold(text), context, today)
    text = normalize_user_text(text, context)
    # Normalized Telex/abbreviations contain the reliable date and action.
    # Raw intent is only a fallback; otherwise partial raw matches discard them.
    market_request = _market_intent(_fold(text), context, today) or raw_market_request
    norm = _fold(_resolve_relative_periods(text, today))
    norm = resolve_reply(norm, context)
    annual = annual_requested(norm, context)
    from .hybrid_router.intent_policy import PROFILE_TERMS, contains
    if annual or contains(norm, PROFILE_TERMS):
        market_request = None
    scope = copy.deepcopy(context or {})
    language = conversational_words()
    registered = registered_symbols()
    # Repair scopes persisted by the old heuristic (e.g. 'như' -> NHU).
    # A real catalog ticker that overlaps a language word remains available.
    if scope.get('companies'):
        scope['companies'] = [symbol for symbol in scope['companies']
                              if symbol in registered or symbol.lower() not in language]
    decision = {'decision': 'ASK_CLARIFICATION', 'scope': scope, 'message': '', 'reason_code': 'MISSING_SCOPE'}
    def finish(branch, reason, message):
        decision.update(decision=branch, reason_code=reason, message=message)
        return apply_clarification(decision, context, today or date.today())
    if norm in ('/moi', '/new'):
        decision['scope'] = {}
        return finish('ASK_CLARIFICATION', 'NEW_CONVERSATION', 'Đã bắt đầu câu hỏi mới. Bạn muốn xem mã, chỉ tiêu hoặc tin tức nào?')
    if re.fullmatch(r'(?:nguon(?: dau| o dau| nao| cua cau (?:tra loi )?(?:truoc|vua roi))?|xem nguon|cho (?:toi |minh |t )?xem nguon|trich dan(?: dau| nao)?)', norm.rstrip(' .?!')):
        return finish('RESOLVE_REFERENCE', 'SOURCE_REFERENCE', 'Xem nguồn của câu trả lời trước.')
    if re.search(r'\b(?:nen mua|nen ban|gia muc tieu|tu van dau tu|should i buy|should i sell)\b', norm):
        return finish('UNSUPPORTED', 'UNSUPPORTED_ADVICE', 'Chức năng này không cung cấp tư vấn mua bán.')
    if not annual and not market_request and re.search(r'\b(?:gia co phieu|gia dong cua|gia mo cua|khoi luong giao dich|gia muc tieu)\b', norm):
        return finish('UNSUPPORTED', 'PRICE_QUERY_SEPARATE', ('Mình trả lời được giá lịch sử theo ngày của các mã có trong dữ liệu, ví dụ: "Giá đóng cửa VCB ngày 15/6/2026". '
                      'Mã hoặc ngày bạn hỏi chưa có dữ liệu giá, hoặc câu hỏi chưa nêu rõ mã và ngày.'))
    quarters = re.findall(r'\b(?:quy|q)\s*(\d+)\s*[/ -]?\s*((?:19|20|21)\d{2})\b', norm)
    canonical_quarters = re.findall(r'\b((?:19|20|21)\d{2})-q(\d+)\b', norm)
    if not annual and (any(not 1 <= int(q) <= 4 for q, _ in quarters)
            or any(not 1 <= int(q) <= 4 for _, q in canonical_quarters)
            or len(set(quarters)) > 1 or len(set(canonical_quarters)) > 1):
        scope.pop('periods', None)
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_PERIOD', 'Bạn muốn xem quý nào? Vui lòng nêu một kỳ hợp lệ từ quý 1 đến quý 4.')
    companies = [s for s in (*TICKERS, 'SSI', 'CTR', 'VNM', 'MSN', 'NLG') if re.search(r'\b'+s.lower()+r'\b', norm)]
    reserved = {'BCTC', 'BCTN', 'YTD', 'VND', 'USD', 'EUR', 'UBND', 'CTCP', 'TNHH',
                'NEWS', 'CASH', 'TOTAL', 'CAFEF', 'LNST', 'LNTT', 'HDQT', 'HDTV', 'BKS', 'BGD', 'BDH'}
    ticker_stop = STOP_WORDS | {'mot', 'cuoi', 'thuan', 'nhat', 'rieng', 'hop', 'ngan', 'dai',
                              'thu', 'phi', 'tuc', 'cafef', 'news', 'trong', 'tai', 'ky',
                              'von', 'loi', 'lai', 'tong', 'vay', 'thue', 'dong', 'tien',
                              'hom', 'hien', 'nay', 'nhieu', 'bao', 'moi', 'nhat', 'khong',
                              'tap', 'doan', 'nhom', 'cty'}
    # A ticker is plain ASCII letters, so any word the user typed with Vietnamese diacritics ("Tập" in
    # "Tập đoàn FPT") is ordinary language, never a symbol, once folded.
    ticker_stop |= {_fold(word) for word in re.findall(r'\w+', text) if not word.isascii()}
    ticker_stop |= vocabulary_words()
    # Capital letters alone do not make a company. A registered symbol is one. Otherwise the token must not
    # be a term the router already knows is no company (EPS, ROE, CFO, HOSE ...), a word of a metric name,
    # or an abbreviation given in brackets after the phrase it abbreviates ("... trên cổ phiếu (EPS)").
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES, NON_COMPANY_CODES
    glosses, initialisms = set(), set()
    for before, token in re.findall(r'((?:\S+\s+){1,6})\(\s*([A-Z]{2,6})\s*\)', text):
        glosses.add(token)
        # "Tổng tài sản (TTS)": the letters are the initials of the words before the bracket, so this is an
        # abbreviation of that phrase even when the same letters happen to be a listed symbol.
        if ''.join(word[0] for word in _fold(before).split()[-len(token):]).upper() == token:
            initialisms.add(token)
    companies += [s for s in re.findall(r'\b[A-Z]{3,5}\b', text)
                  if s not in reserved and s not in companies and s not in NON_COMPANY_CODES and s not in initialisms
                  and (s in registered or not (s in glosses or s.lower() in ticker_stop))]
    # Companies are also named by name ("Vinamilk", "Hòa Phát"); the router's name table is the shared source.
    for alias, symbols in DEFAULT_COMPANIES.items():
        if len(alias) > 3 and re.search(r'\b' + re.escape(alias) + r'\b', norm):
            ticker_stop |= set(alias.split())        # the words of a name are not a second, made-up symbol
            if symbols[0] not in companies:
                companies.append(symbols[0])
    # Explicit lowercase symbols must replace old scope too, even if not in this corpus.
    company_patterns = (r'\b(?:cua|cong ty|co phieu|ma ck|ma)\s+([a-z]{3,5})\b',
                        r'\b([a-z]{3,5})\s+(?:nam|quy|thang)\s+(?:\d{4}|\d{1,2}[/ -]\d{4}|nay|truoc)\b')
    if (market_request or {}).get('query'):
        company_patterns = (r'\b(?:co phieu|ma ck|ma)\s+([a-z]{3})\b',)
    for pattern in company_patterns:
        companies += [token.upper() for token in re.findall(pattern, norm)
                      if token not in ticker_stop and token.upper() not in reserved]
    if market_request:
        for pattern in (r'\b(?:gia|tin tuc|news)\s+([a-z]{3})\b',
                        r'\b([a-z]{3})\s+(?:gia|hom nay|hien tai|moi nhat)\b'):
            companies += [token.upper() for token in re.findall(pattern, norm)
                          if token not in ticker_stop and token.upper() not in reserved]
    # Some valid exchange tickers are also ordinary Vietnamese words.  In a
    # causal phrase, "sao" belongs to "vì sao", not ticker SAO.
    if re.search(r'\bvi sao\b', norm):
        companies = [company for company in companies if company != 'SAO']
    if not companies and re.fullmatch(r'(?:con |khong,? la |la )?[a-z]{3}', norm):
        token = norm.split()[-1]
        if token not in ticker_stop | {'sau', 'nam', 'nay', 'cho', 'xem', 'moi'}:
            companies = [token.upper()]
    companies = [symbol for symbol in companies if symbol in registered or symbol.lower() not in language]
    if companies:
        scope['companies'] = list(dict.fromkeys(companies))
        if (context or {}).get('companies') and scope['companies'] != context['companies']:
            scope.pop('_pending_publisher', None)
            scope.pop('_pending_reporting_entity', None)
    if annual:
        return finish(*annual_scope(text, norm, scope, context))
    if market_request:
        scope = {key: value for key, value in scope.items() if key in ('companies', '_clarification_state')}
        decision['scope'] = scope
        source_type = {'QUOTE': 'PRICE', 'NEWS': 'NEWS', 'ANALYSIS': 'MARKET_ANALYSIS'}[
            market_request['kind']
        ]
        scope.update(source_type=source_type,
                     metric_code='LAST_PRICE' if market_request['kind'] in ('QUOTE', 'ANALYSIS') else None,
                     periods=[market_request['day']] if market_request['day'] else [],
                     _market_request=market_request)
        if market_request.get('market_wide'):
            scope['companies'] = []
            scope['topic'] = 'MARKET_DAILY_DIGEST'
        calendar_issue = scope['_market_request'].pop('_calendar_issue', None)
        calendar_message = scope['_market_request'].pop('_calendar_message', '')
        if calendar_issue:
            return finish('ASK_CLARIFICATION', calendar_issue, calendar_message)
        if scope['_market_request'].pop('invalid_date', False):
            return finish('ASK_CLARIFICATION', 'INVALID_DATE', 'Ngày chưa hợp lệ. Bạn muốn xem ngày nào? Ví dụ: 22/10/2026.')
        publishers = [p for p in ('cafef', 'fireant') if re.search(r'\b'+p+r'\b', norm)]
        if len(publishers) > 1:
            scope['_pending_publisher'] = True
            return finish('ASK_CLARIFICATION', 'AMBIGUOUS_PUBLISHER', 'Bạn muốn xem nguồn CafeF hay FireAnt trước?')
        if publishers: scope['publisher'] = publishers[0]
        elif (context or {}).get('publisher'): scope['publisher'] = context['publisher']
        if market_request.get('market_wide'):
            return finish('MARKET_LOOKUP', 'CURRENT_MARKET_DIGEST',
                          'Dang tra cuu ban tin tong hop va tin noi bat trong ngay.')
        if not scope.get('companies'):
            return finish('ASK_CLARIFICATION', 'MISSING_COMPANY', 'Mình tra cứu giá và tin tức của các công ty trong kho dữ liệu. Bạn muốn xem công ty nào?')
        if len(scope['companies']) != 1:
            return finish('ASK_CLARIFICATION', 'SCOPE_TOO_LARGE', 'Vui lòng chọn một mã cổ phiếu cho mỗi lần tra cứu giá hoặc tin mới.')
        return finish('MARKET_LOOKUP', 'CURRENT_MARKET_REQUEST', 'Đang tra cứu nguồn giá hoặc tin tức đang cập nhật.')
    if scope.pop('_market_request', None):
        for key in ('periods', 'metric_code', 'source_type', 'publisher', 'measure_basis', 'reporting_entity'):
            scope.pop(key, None)
    found = find_metrics(norm)
    # What the question says besides the metric names: a word that is part of a metric name ("cổ đông" in
    # "LNST thuộc cổ đông công ty mẹ", "sở hữu" in "vốn chủ sở hữu") says nothing about people or ownership.
    residual = without_metrics(norm)
    # Users often say "lợi nhuận ... sau thuế" without the exact phrase
    # "lợi nhuận sau thuế". Resolve that explicit tax basis in the same turn.
    profit_requested = ('loi nhuan' in norm or bool(re.search(r'\b(?:lời|lãi)\b', text.lower()))
                        or bool(re.search(r'\b(?:loi|lai)\s+bao nhieu\b', norm)))
    if not found and profit_requested:
        if re.search(r'\bsau thue\b', norm): found = ['PROFIT_AFTER_TAX']
        elif re.search(r'\btruoc thue\b', norm): found = ['PROFIT_BEFORE_TAX']
    # Prefer the most specific named metric over a containing phrase (retained earnings vs PAT).
    if 'RETAINED_EARNINGS' in found and 'PROFIT_AFTER_TAX' in found:
        found.remove('PROFIT_AFTER_TAX')
    if 'PARENT_NET_PROFIT' in found and 'PROFIT_AFTER_TAX' in found:
        found.remove('PROFIT_AFTER_TAX')
    if 'NON_CURRENT_LIABILITIES' in found and 'CURRENT_LIABILITIES' in found:
        found.remove('CURRENT_LIABILITIES')
    multiple = len(found) > 1
    from .hybrid_router.intent_policy import PROFILE_TERMS, contains
    company_profile = contains(norm, PROFILE_TERMS) or bool(re.search(r'\bthong tin\b', norm) and scope.get('companies'))
    comparison = bool(re.search(r'\b(?:so sanh|doi chieu|khac nhau|hon kem)\b', norm))
    overall_comparison = comparison and not found and not profit_requested
    relationship_lookup = bool(re.search(
        r'\b(?:chu tich|ceo|tong giam doc|giam doc|lanh dao|co dong|so huu|'
        r'hoi dong|hdqt|hdtv|ban dieu hanh|ban kiem soat|nhan su quan ly)\b', residual if found else norm
    ))
    # A statement row is the company-wide total. A metric restricted to a part of the business (a market,
    # a segment, a subsidiary) or asked "theo thuyết minh" is in the notes of the annual report, never in
    # that row, so it must not be answered with the total.
    part_of_business = bool(found and (re.search(
        r'\b(?:thi truong nuoc ngoai|nuoc ngoai|trong nuoc|noi dia|hai ngoai|xuat khau|phan khuc|'
        r'linh vuc|bo phan|cong ty con|cong ty thanh vien|theo (?:tung )?(?:khu vuc|thi truong|san pham|dich vu)|'
        r'thuyet minh)\b', residual)
        # "mảng" and "khối" lose their meaning without diacritics ("mang lại", "khởi sắc"), so read them as typed.
        or re.search(r'\b(?:mảng|khối)\s+\w+', text.lower())))
    if part_of_business and scope.get('companies'):
        return finish(*annual_scope(text, norm, scope, context))
    ambiguous_members = bool(re.search(r'\bthanh vien\b', norm)) or bool(scope.get('_pending_membership'))
    if ambiguous_members and not relationship_lookup and not found and not profit_requested:
        for key in ('_pending_metric', '_metric_candidates', '_pending_quarter', '_pending_ytd',
                    '_pending_reporting_entity', '_pending_publisher', 'measure_basis', 'publisher'):
            scope.pop(key, None)
        scope.update(source_type='NEWS', metric_code=None, periods=[], reporting_entity='UNKNOWN',
                     topic='MEMBERSHIP_SELECTION', _pending_membership=True)
        if not scope.get('companies'):
            return finish('ASK_CLARIFICATION', 'MISSING_COMPANY', 'Bạn muốn xem thành viên của công ty nào?')
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_COMPANY_MEMBERS',
                      'Bạn muốn xem thành viên hội đồng quản trị hay ban điều hành?')
    if relationship_lookup or found or profit_requested:
        scope.pop('_pending_membership', None)
    event_impact = bool(
        re.search(r'\b(?:bi bat|bat giu|khoi to|dieu tra|truy to|tam giam)\b', norm)
        and re.search(r'\b(?:co phieu|anh huong|tac dong|he qua)\b', norm)
    )
    if len(found) == 1 and (context or {}).get('metric_code') and found[0] != context['metric_code']:
        scope.pop('_pending_reporting_entity', None)
    publishers = [name for name in ('cafef', 'fireant') if re.search(r'\b'+name+r'\b', norm)]
    qualitative_document = bool(re.search(
        r'\b(?:chia se|phat bieu|noi gi|ke hoach|chien luoc|dinh huong|muc tieu|'
        r'cam ket|quan diem|co dong lon|danh sach co dong|chu tich|ceo|tong giam doc|'
        r'lanh dao|bi bat|bat giu|khoi to|dieu tra|truy to|tam giam)\b', norm
    ) or re.search(r'\bAI\b', text))
    news = bool(
        re.search(r'\b(?:tin tuc|tin|news)\b', norm)
        or qualitative_document
        or (relationship_lookup and not found and not profit_requested)
        or (scope.get('source_type') == 'NEWS' and publishers)
    )
    if event_impact:
        scope.update(companies=[], source_type='NEWS', metric_code=None,
                     topic='EVENT_IMPACT', reporting_entity='UNKNOWN')
        scope.pop('_pending_metric', None)
    elif company_profile and not overall_comparison:
        scope.update(source_type='COMPANY_PROFILE', metric_code=None, topic='COMPANY_PROFILE')
        scope['periods'] = []
        for key in list(scope):
            if key.startswith(('_pending_', '_person_', '_source_', '_hybrid_')):
                scope.pop(key, None)
        scope.pop('_pending_metric', None)
    elif overall_comparison:
        scope.update(source_type='COMPANY_OVERVIEW', metric_code=None, topic='OVERALL_COMPARISON')
        scope.pop('_pending_metric', None)
    elif news:
        scope.update(source_type='NEWS', metric_code=None, reporting_entity='UNKNOWN')
        if relationship_lookup:
            scope['topic'] = 'RELATIONSHIP_LOOKUP'
            for key in ('_pending_quarter', '_pending_ytd', '_pending_reporting_entity',
                        'measure_basis', '_metric_candidates'):
                scope.pop(key, None)
            # A new organizational question does not inherit an unrelated report period.
            scope.pop('periods', None)
        scope.pop('_pending_metric', None)
        if len(publishers) > 1:
            scope.pop('publisher', None)
            scope['_pending_publisher'] = True
        elif publishers:
            scope['publisher'] = publishers[0]
            scope.pop('_pending_publisher', None)
    elif multiple:
        scope.update(source_type='BCTC', metric_code=None, _pending_metric='MULTIPLE', _metric_candidates=found)
    elif found:
        scope.update(source_type='BCTC', metric_code=found[0])
        scope.pop('_pending_metric', None)
        scope.pop('_metric_candidates', None)
    elif profit_requested:
        scope.update(source_type='BCTC', metric_code=None, _pending_metric='PROFIT')
    elif scope.get('_pending_metric') == 'PROFIT' and norm in ('sau', 'sau thue', 'truoc', 'truoc thue'):
        scope.update(metric_code='PROFIT_AFTER_TAX' if norm.startswith('sau') else 'PROFIT_BEFORE_TAX')
        scope.pop('_pending_metric', None)
    elif metric_group(norm):
        scope.update(source_type='BCTC', metric_code=None, _pending_metric=metric_group(norm))
        scope.pop('_metric_candidates', None)
    elif re.search(r'\b(?:chi tieu|roe|roa|pe|pb)\b', norm):
        scope.update(source_type='BCTC', metric_code=None, _pending_metric='GENERIC')
    if scope.get('source_type') != 'NEWS':
        scope.pop('publisher', None)
        scope.pop('_pending_publisher', None)
    consolidated = 'hop nhat' in norm
    # "công ty mẹ" inside the metric name "LNST thuộc cổ đông công ty mẹ" is not a request for the parent-only report.
    parent = ('bao cao rieng' in norm or re.search(r'\brieng le\b', norm)
              or bool(re.search(r'\bcong ty me\b', residual if found else norm))
              or (scope.get('_pending_reporting_entity') and norm in ('rieng', 'rieng le')))
    if consolidated and parent:
        scope.update(reporting_entity='UNKNOWN', _pending_reporting_entity=True)
    elif consolidated:
        scope['reporting_entity'] = 'CONSOLIDATED'
        scope.pop('_pending_reporting_entity', None)
    elif parent:
        scope['reporting_entity'] = 'PARENT'
        scope.pop('_pending_reporting_entity', None)
    scope.setdefault('reporting_entity', 'UNKNOWN')
    metric = scope.get('metric_code')
    previous = context or {}
    if ((previous.get('companies') and scope.get('companies') != previous['companies'])
            or (previous.get('metric_code') and metric != previous['metric_code'])):
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
    month = re.search(r'\bthang\s+(\d{1,2})[/ -]((?:19|20|21)\d{2})\b', norm)
    period, error = _live_period(norm, metric, scope)
    if error:
        scope.pop('periods', None)
        return finish('ASK_CLARIFICATION', error, 'Ngày hoặc kỳ chưa hợp lệ hoặc có nhiều kỳ. Bạn muốn xem quý, năm nào?')
    if month and scope.get('source_type') == 'NEWS':
        if not 1 <= int(month[1]) <= 12:
            return finish('ASK_CLARIFICATION', 'INVALID_DATE', 'Tháng chưa hợp lệ.')
        scope['periods'] = [f'{month[2]}-{int(month[1]):02}']
    elif period:
        if period['granularity'] == 'YEAR':
            scope['periods'] = [str(period['year'])]
        elif period['granularity'] == 'QUARTER' or (period['granularity'] == 'DAY' and metric in POINT_METRICS):
            end = date.fromisoformat(period['end'])
            if end.month % 3 or end.day != calendar.monthrange(end.year, end.month)[1]:
                return finish('ASK_CLARIFICATION', 'UNSUPPORTED_PERIOD', 'Báo cáo tài chính cần kỳ năm hoặc ngày cuối quý cụ thể.')
            scope['periods'] = [f'{end.year}-Q{end.month//3}']
        elif scope.get('source_type') == 'NEWS' and period['granularity'] == 'DAY':
            scope['periods'] = [period['end']]
        else:
            return finish('ASK_CLARIFICATION', 'UNSUPPORTED_PERIOD', 'Bạn muốn xem riêng quý hay cả năm nào? Chưa hỗ trợ tự ghép các kỳ.')
        scope['measure_basis'] = period['measure_basis']
    if metric in POINT_METRICS: scope['measure_basis'] = 'POINT_IN_TIME'
    elif metric and scope.get('measure_basis') == 'POINT_IN_TIME' and scope.get('periods'):
        scope['measure_basis'] = 'STANDALONE_QUARTER' if '-Q' in scope['periods'][0] else 'FULL_YEAR'
    if not scope.get('companies') and scope.get('topic') != 'EVENT_IMPACT':
        if metric or scope.get('topic'):
            return finish('ASK_CLARIFICATION', 'MISSING_COMPANY', 'Bạn muốn xem công ty nào?')
        return finish('ASK_CLARIFICATION', 'MISSING_COMPANY',
                      'Mình tra cứu báo cáo, chỉ tiêu tài chính, giá và tin tức của các công ty trong kho dữ liệu. '
                      'Bạn muốn xem công ty nào? Ví dụ: "Doanh thu thuần quý 2/2026 của FPT".')
    if scope.get('_pending_publisher'):
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_PUBLISHER', 'Bạn muốn xem nguồn CafeF hay FireAnt trước?')
    if scope.get('_pending_reporting_entity'):
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_REPORTING_ENTITY', 'Bạn muốn xem báo cáo hợp nhất hay báo cáo riêng?')
    if not metric and scope.get('source_type') not in ('NEWS', 'COMPANY_PROFILE', 'COMPANY_OVERVIEW'):
        if (not multiple and not scope.get('source_type') and not scope.get('_pending_metric')
                and _is_open_question(norm, scope)):
            # A full question about a company that names no statement metric ("tỷ lệ nhân sự nữ", "đơn vị
            # kiểm toán là ai") is a question for its annual report; asking "which metric?" cannot help.
            return finish(*annual_scope(text, norm, scope, context))
        return finish('ASK_CLARIFICATION', 'MULTIPLE_METRICS' if multiple else 'MISSING_METRIC', 'Bạn muốn xem chỉ tiêu nào?')
    if not scope.get('periods'):
        if scope.get('topic') in ('RELATIONSHIP_LOOKUP', 'EVENT_IMPACT'):
            scope['periods'] = ['LATEST_AVAILABLE_PERIOD']
            return finish('SEARCH', 'SCOPE_READY', 'Đang tìm nguồn về quan hệ doanh nghiệp và sự kiện liên quan.')
        if scope.get('source_type') == 'COMPANY_PROFILE':
            return finish('SEARCH', 'SCOPE_READY', 'Đang tìm hồ sơ doanh nghiệp trong corpus đã chọn.')
        if scope.get('source_type') == 'COMPANY_OVERVIEW':
            scope['periods'] = [str(today.year)]
            return finish('SEARCH', 'SCOPE_READY', 'Đang tìm dữ liệu để so sánh tổng quan.')
        if scope.get('_pending_quarter'):
            return finish('ASK_CLARIFICATION', 'MISSING_YEAR', f"Bạn muốn xem quý {scope['_pending_quarter']} của năm nào?")
        scope['periods'] = ['LATEST_AVAILABLE_PERIOD']
        return finish('SEARCH', 'LATEST_PERIOD_DEFAULTED', 'Không có thời gian cụ thể; đang dùng kỳ mới nhất có trong nguồn.')
    if len(scope['companies']) > 2 or len(scope['periods']) > 2:
        return finish('ASK_CLARIFICATION', 'SCOPE_TOO_LARGE', 'Vui lòng hỏi tối đa hai mã và hai kỳ mỗi lần.')
    return finish('SEARCH', 'SCOPE_READY', 'Đang tìm bằng chứng trong corpus đã chọn.')


class DenseEvidenceRetriever:
    """Corpus-bound adapter with dense or independently indexed BM25/RRF retrieval."""
    def __init__(self, pool, embedder, *, corpus_version_id=V4_CORPUS, model_ref=MODEL,
                 backend='dense', cache_dir=None, corpus_resolver=None):
        if backend not in ('dense', 'hybrid'):
            raise ValueError('Unsupported retrieval backend')
        self.pool, self.embedder = pool, embedder
        self.corpus_version_id = str(uuid.UUID(corpus_version_id))
        self.model_ref = model_ref
        self.backend = backend
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(__file__).resolve().parents[1] / 'vector_retrieval' / '.cache'
        self._hybrid = None
        self._cache_lock = asyncio.Lock()
        self.corpus_resolver = corpus_resolver

    def _hybrid_instance(self):
        from ..vector_retrieval.backend import HybridRetriever
        if self._hybrid is None:
            delegate = self.embedder
            class LockedEmbedder:
                model_name = delegate.model_name
                revision = delegate.revision
                def embed_query(self, text):
                    with _embedding_lock:
                        return delegate.embed_query(text)
            # Frozen corpora are immutable. Membership/model fingerprints and
            # returned source hashes are still checked on every search.
            self._hybrid = HybridRetriever(self.pool, LockedEmbedder(), corpus_version_id=self.corpus_version_id,
                                           max_cache_age=7*24*3600)
        return self._hybrid

    async def _corpus(self):
        if self.corpus_resolver is not None:
            current = str(uuid.UUID(await asyncio.to_thread(self.corpus_resolver)))
            if current != self.corpus_version_id:
                self.corpus_version_id = current
                self._hybrid = None
        corpus = await repository.get_corpus_index(self.pool, self.corpus_version_id)
        if (not corpus or corpus['corpus_status'] != 'FROZEN' or corpus['index_status'] != 'ACTIVE'
                or corpus['embedding_model'] != self.model_ref):
            raise ReconstructionError('CORPUS_NOT_READY', 'Pinned corpus or model is not ready')
        return corpus

    async def corpus_companies(self):
        """Symbols with a financial statement or annual report in the serving corpus (cached per corpus)."""
        await self._corpus()
        cached = getattr(self, '_corpus_companies', None)
        if cached is None or cached[0] != self.corpus_version_id:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    '''SELECT DISTINCT c.symbol FROM public.corpus_documents cd
                       JOIN public.documents d USING(document_id) JOIN public.companies c USING(company_id)
                       WHERE cd.corpus_version_id=$1::uuid AND d.doc_type IN ('FINANCIAL_STATEMENT','ANNUAL_REPORT')''',
                    uuid.UUID(self.corpus_version_id))
            cached = self._corpus_companies = (self.corpus_version_id, sorted(row['symbol'] for row in rows))
        return cached[1]

    async def _embed(self, question):
        def embed():
            with _embedding_lock:
                return self.embedder.embed_query(question)
        vector = await asyncio.to_thread(embed)
        if (len(vector) != 1024 or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)
                or not any(vector)):
            raise ReconstructionError('INVALID_QUERY_VECTOR', 'Invalid embedding')
        return vector

    async def warmup(self):
        """Warm the same model/BM25 objects used by chat, without Gemini or history."""
        corpus = await self._corpus()
        await self._embed('Khởi tạo bộ tìm kiếm tài chính')
        if self.backend == 'hybrid':
            async with self._cache_lock:
                await self._hybrid_instance().prepare_cache(
                    corpus['index_version_id'], self.cache_dir / ('corpus-' + self.corpus_version_id + '.json'))
        return {'backend': self.backend, 'index_version_id': corpus['index_version_id']}

    async def _hybrid_rows(self, question, scope, corpus, company, period, doc_type=None):
        from ..vector_retrieval.backend import RetrievalError
        self._hybrid_instance()
        cache = self.cache_dir / ('corpus-' + self.corpus_version_id + '.json')
        doc_type = doc_type or ('ANNUAL_REPORT' if scope['source_type'] == 'BCTN' else
                               'NEWS' if scope['source_type'] == 'NEWS' else 'FINANCIAL_STATEMENT')
        params = dict(company=company, period=period,
                      doc_type=doc_type,
                      publisher=scope.get('publisher'),
                      published_date=period if doc_type == 'NEWS' and period and len(period) == 10 else None,
                      exact_period=doc_type in ('FINANCIAL_STATEMENT', 'ANNUAL_REPORT') and period is not None,
                      top_k=20, candidates=100)
        rebuildable = ('CACHE_BUILD_REQUIRED', 'CACHE_EXPIRED', 'CACHE_STALE', 'CACHE_VERSION_MISMATCH')
        try:
            result = await self._hybrid.search(question, corpus['index_version_id'], cache, **params)
        except RetrievalError as exc:
            if exc.code not in rebuildable: raise
            # Only cache construction is serialized; warm queries may run concurrently.
            async with self._cache_lock:
                try:
                    result = await self._hybrid.search(question, corpus['index_version_id'], cache, **params)
                except RetrievalError as retry_error:
                    if retry_error.code not in rebuildable: raise
                    await self._hybrid.build_cache(corpus['index_version_id'], cache)
                    result = await self._hybrid.search(question, corpus['index_version_id'], cache, **params)
        return [dict(chunk_id=item['chunk_id'], document_id=item['document_id'],
                     text=item['text'], content_hash=item['content_hash'],
                     source_sha256=item['source_sha256'], title=item['title'],
                     locator_json=item['locator'], score=item['rrf_score']) for item in result['results']]

    async def _annual_latest_year(self, company, corpus):
        async with self.pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation='repeatable_read'):
                return await conn.fetchval('''SELECT max(t.locator_json->>'reporting_year')
                    FROM text_chunks t JOIN documents d USING(document_id)
                    JOIN corpus_documents cd ON cd.document_id=d.document_id AND cd.document_hash=d.sha256
                    LEFT JOIN companies c USING(company_id)
                    WHERE cd.corpus_version_id=$1::uuid AND t.index_version_id=$2::uuid
                      AND t.superseded_at IS NULL AND d.doc_type='ANNUAL_REPORT'
                      AND coalesce(c.symbol,t.locator_json->>'symbol')=$3
                      AND t.locator_json->>'reporting_year' ~ '^(19|20|21)[0-9]{2}$' ''',
                    uuid.UUID(str(self.corpus_version_id)), uuid.UUID(str(corpus['index_version_id'])), company)

    async def _annual_rows(self, rows, corpus, company, year):
        from ..documents.annual_source_reader import read_annual_chunk
        from ..documents.shared_source import read_release_root
        verified, cache = [], {}
        async with self.pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation='repeatable_read'):
                for row in rows[:5]:
                    source = await read_annual_chunk(conn, row['chunk_id'], self.corpus_version_id, cache)
                    loc = source['locator']
                    actual_year = str(loc.get('reporting_year', ''))
                    if (source['index_version_id'] != str(corpus['index_version_id'])
                            or loc.get('symbol') != company or actual_year != year):
                        raise ReconstructionError('ANNUAL_SCOPE_MISMATCH', 'Annual source differs from requested company/report year')
                    root = await read_release_root(conn, source['index_version_id'], cache)
                    member = next((m for m in root['sources'] if m['source_table'] == loc['source_table']
                                   and m['source_id'] == loc['source_id']), None)
                    if member is None:
                        raise ReconstructionError('SOURCE_MISSING', 'Annual source absent from release')
                    verified.append({**row, 'text': source['chunk_text'], 'document_id': source['document_id'],
                        'content_hash': source['content_hash'], 'source_sha256': member['sha256'],
                        'locator_json': loc, 'title': source['title'], 'source_url': source['source_url'],
                        'source_verified': True})
        return verified

    async def retrieve(self, question, scope):
        corpus = await self._corpus()
        vector = await self._embed(question) if self.backend == 'dense' else None
        items, seen = [], set()
        source_type = scope['source_type']
        doc_type = (
            'COMPANY_PROFILE'
            if source_type in ('COMPANY_PROFILE', 'COMPANY_OVERVIEW')
            else 'ANNUAL_REPORT' if source_type == 'BCTN'
            else 'NEWS' if source_type == 'NEWS' else 'FINANCIAL_STATEMENT'
        )
        companies = scope['companies'] or ([None] if scope.get('topic') == 'EVENT_IMPACT' else [])
        periods = [None] if doc_type == 'COMPANY_PROFILE' else scope['periods']
        for company in companies:
            for period in periods:
                latest_period = period == 'LATEST_AVAILABLE_PERIOD'
                lookup_period = None if latest_period else period
                if doc_type == 'ANNUAL_REPORT' and latest_period:
                    lookup_period = await self._annual_latest_year(company, corpus)
                    if not lookup_period:
                        items = []
                        break
                if self.backend == 'hybrid':
                    rows = await self._hybrid_rows(question, scope, corpus, company, lookup_period, doc_type)
                else:
                    rows = await repository.vector_search_filtered(
                        self.pool, corpus['index_version_id'], vector, 20,
                        company_symbol=company, period=lookup_period,
                        doc_type=doc_type,
                        corpus_version_id=self.corpus_version_id,
                        exact_period=doc_type in ('FINANCIAL_STATEMENT', 'ANNUAL_REPORT') and lookup_period is not None,
                    )
                if doc_type == 'ANNUAL_REPORT':
                    rows = await self._annual_rows(rows, corpus, company, lookup_period)
                matching = []
                for row in rows:
                    if scope.get('_admin_source_url'):
                        locator = row.get('locator_json') or {}
                        if locator.get('url') != scope['_admin_source_url']: continue
                    if row.get('source_verified', True) is not True:
                        raise ReconstructionError('UNVERIFIED_SOURCE', 'Preview cannot be evidence')
                    text = row['text']
                    if scope.get('publisher'):
                        from ..vector_retrieval.backend import _derive_publisher
                        if _derive_publisher(row) != scope['publisher']: continue
                    metric = scope.get('metric_code')
                    if metric and not re.search(r'\('+re.escape(metric)+r'\)', text):
                        continue
                    header = _fold(text.split('\n', 1)[0])
                    entity = scope.get('reporting_entity', 'UNKNOWN')
                    if doc_type == 'FINANCIAL_STATEMENT' and not reporting_entity_matches(text.split('\n', 1)[0], entity):
                        continue
                    basis = scope.get('measure_basis')
                    if doc_type == 'FINANCIAL_STATEMENT' and basis == 'YTD' and not re.search(r'\b(?:luy ke|ytd)\b', header):
                        continue
                    if (doc_type == 'FINANCIAL_STATEMENT' and basis == 'STANDALONE_QUARTER'
                            and ('luy ke' in header or 'ytd' in header)):
                        continue
                    if row['chunk_id'] in seen: continue
                    seen.add(row['chunk_id'])
                    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
                    if content_hash != row['content_hash'].strip():
                        raise ReconstructionError('HASH_MISMATCH', 'Indexed text differs')
                    matching.append(dict(
                        evidence_id=row['chunk_id'], chunk_id=row['chunk_id'], source_id=row['document_id'],
                        source_type='BCTN' if doc_type == 'ANNUAL_REPORT' else 'BCTC' if doc_type == 'FINANCIAL_STATEMENT' else doc_type,
                        title=row['title'], passage=text,
                        source_url=row.get('source_url'),
                        source_sha256=row['source_sha256'].strip(), content_sha256=content_hash,
                        source_verified=True, locator=row['locator_json'],
                        score={'type': 'RRF' if self.backend == 'hybrid' else 'COSINE_SIMILARITY', 'value': float(row['score'])},
                    ))
                    if len(matching) == 5: break
                # Every explicitly requested company/period must have evidence.
                if not matching:
                    items = []
                    break
                items.extend(matching)
            if not items: break
        return dict(schema_version='1.1', query_id=str(uuid.uuid4()),
                    data_version={'kind': 'INDEX', 'id': corpus['index_version_id']},
                    corpus_version_id=self.corpus_version_id, items=items,
                    retrieval_backend=self.backend)


class LiveResearchService:
    execution_mode = 'LIVE'

    def __init__(self, retriever, *, provider=None, limits=None, retrieval_timeout=120, market=None, admin_news=None, hybrid_router=None,
                 limits_source=None, prices=None):
        self.retriever, self.provider = retriever, provider
        self.prices = prices
        self.market = market
        self.admin_news = admin_news
        self.hybrid_router = hybrid_router
        self.limits = limits or Limits.load()
        self.budget = Budget(self.limits)
        # Optional callable returning the limits to use for the next request (admin overrides).
        self.limits_source = limits_source
        self.retrieval_timeout = retrieval_timeout

    def _source_reference(self, result, previous_result):
        previous = previous_result or {}
        old_scope = previous.get('scope', {})
        same_scope = all(result['scope'].get(key) == old_scope.get(key)
                         for key in ('companies', 'periods', 'metric_code', 'reporting_entity', 'source_type',
                                     'measure_basis', 'publisher'))
        answer = previous.get('answering') or {}
        if not same_scope or answer.get('status') != 'DRAFT_READY' or not answer.get('citations'):
            previous_scope = copy.deepcopy(result['scope'])
            choice = apply_clarification({'decision': 'ASK_CLARIFICATION', 'reason_code': 'NO_REFERENCED_EVIDENCE',
                                         'scope': result['scope'],
                                         'message': 'Chưa có câu trả lời có nguồn trong phạm vi hiện tại. Bạn muốn tra cứu chỉ tiêu hoặc tin tức nào?'},
                                        previous_scope, date.today())
            result.update(status=choice['decision'], reason_code=choice['reason_code'], message=choice['message'],
                          clarification_options=choice.get('clarification_options', []))
            result['clarification'] = result['message']
            return result
        try:
            evidence = prepare_evidence(previous.get('evidence_pack'))
            for citation in answer['citations']:
                item = evidence.get(citation.get('evidence_id'))
                if item is None or any(citation.get(key) != item.get(key)
                                       for key in ('source_id', 'chunk_id', 'source_sha256', 'locator')):
                    raise CitationError('INVALID_CITATION')
        except CitationError:
            result.update(status='INSUFFICIENT_EVIDENCE', reason_code='INVALID_EVIDENCE',
                          message='Chưa xác minh được nguồn đã lưu của câu trả lời trước.')
            return result
        citations = copy.deepcopy(answer['citations'])
        parts = ['Nguồn của câu trả lời trước:']
        for number, citation in enumerate(citations, 1):
            citation.setdefault('citation_number', number)
            if citation.get('source_type') in ('NEWS', 'PRICE', 'BCTN'):
                title = citation.get('title') or (
                    'Báo cáo thường niên' if citation.get('source_type') == 'BCTN' else 'Nguồn thị trường')
            else:
                title = 'Báo cáo tài chính ' + ', '.join(old_scope.get('companies', []))
            section = citation['locator'].get('section')
            parts.append(f"[{citation['citation_number']}] {title}"+(f' — {section}' if section else ''))
        manifest = copy.deepcopy(answer.get('manifest', {}))
        manifest['referenced_model'] = manifest.get('model_returned')
        manifest['model_returned'] = None
        manifest['response_mode'] = 'SAVED_SOURCE_REFERENCE'
        manifest.setdefault('components', {})['gemini'] = False
        result.update(status='EVIDENCE_READY', reason_code='SOURCE_REFERENCE',
                      presentation=copy.deepcopy(previous.get('presentation') or {}),
                      evidence_pack=copy.deepcopy(previous['evidence_pack']), query_id=previous.get('query_id'),
                      answering={'status': 'DRAFT_READY', 'reason_code': 'SOURCE_REFERENCE',
                                 'message': 'Nguồn đã lưu của câu trả lời trước; không tìm kiếm hoặc sinh lại.',
                                 'draft': '\n\n'.join(parts), 'claims': [], 'citations': citations,
                                 'manifest': manifest, 'cautions': [], 'budget': self.budget.snapshot(),
                                 'trace': [{'event': 'saved_source_reference'}]})
        return result

    async def _absent_from_corpus(self, scope):
        """(asked companies without any report in the serving corpus, companies that have reports).

        The corpus itself is the source of truth, so this follows whatever corpus is being served. It is
        asked only after a search found nothing, and never fails the answer.
        """
        if scope.get('source_type') not in ('BCTC', 'BCTN', 'COMPANY_PROFILE', 'COMPANY_OVERVIEW'):
            return [], []
        lookup = getattr(self.retriever, 'corpus_companies', None)
        if lookup is None:
            return [], []
        try:
            available = list(await asyncio.wait_for(lookup(), 10))
        except Exception:
            return [], []
        if not available:
            return [], []
        return [symbol for symbol in scope.get('companies') or [] if symbol not in available], available

    async def _missing_companies(self, companies):
        """(asked companies the serving corpus has no report of, the companies it has); ([], []) when unknown."""
        lookup = getattr(self.retriever, 'corpus_companies', None)
        if lookup is None:
            return [], []
        try:
            available = list(await asyncio.wait_for(lookup(), 10))
        except Exception:
            return [], []
        return ([symbol for symbol in companies if symbol not in available], available) if available else ([], [])

    def _current_limits(self):
        """Limits for this request: the admin overrides when configured, else the fixed ones."""
        if self.limits_source is None:
            return self.limits
        try:
            limits = self.limits_source()
        except Exception:
            return self.limits
        provider = self.provider
        from ..b1_answering.providers.gemini import GeminiProvider
        if isinstance(provider, GeminiProvider):
            provider.limits = limits           # keeps the HTTP timeout in step with the limits
        return limits

    async def answer(self, question, session_id, context=None, *, previous_result=None, today=None):
        # The API caches this service. Never attach request usage to that shared
        # instance or reset it in place: concurrent users would share/reset it.
        # A shallow request worker keeps pooled retrievers/providers reusable,
        # while every route and fallback in this turn receives the same budget.
        worker = copy.copy(self)
        worker.limits = self._current_limits()
        worker.budget = Budget(worker.limits)
        result = await worker._answer_turn(question, session_id, context,
            previous_result=previous_result, today=today)
        if isinstance(result.get('answering'), dict):
            result['answering']['budget_scope'] = 'REQUEST'
        return result

    async def _answer_turn(self, question, session_id, context=None, *, previous_result=None, today=None):
        interpreted = normalize_user_text(question, context)
        norm = _fold(interpreted).strip(' .?!')
        if norm in ('chao', 'chao ban', 'xin chao', 'hello', 'hi'):
            return dict(request_id=str(uuid.uuid4()), query_id=None, execution_mode='LIVE',
                b1_decision='GREETING', status='GREETING', reason_code='GREETING',
                message='Chào bạn! Bạn có thể hỏi thông tin công ty, nhân sự, báo cáo hoặc tin tức của doanh nghiệp.',
                scope=copy.deepcopy(context or {}), evidence_pack=None, errors=[])
        if self.prices is not None:
            # Historical price questions are arithmetic on stored bars, not reading: answer them exactly.
            priced = await self.prices.answer(interpreted, today)
            if priced is not None:
                if priced.get('answering'):
                    priced['answering']['budget'] = self.budget.snapshot()
                return priced
        from .hybrid_router.intent_policy import PROFILE_TERMS, contains
        explicit_profile = contains(norm, PROFILE_TERMS) or bool(re.search(r'\bthong tin\s+(?:cong ty\s+)?(?:' + '|'.join(s.lower() for s in registered_symbols()) + r')\b', norm))
        bare_company = norm.upper() in (set(TICKERS) | set(registered_symbols()))
        prior = (context or {}).get('_hybrid_context') or context or {}
        pending_company = not prior.get('companies') and bool(prior.get('position_code') or prior.get('person_name') or prior.get('metric_code') or prior.get('_pending_metric'))
        if explicit_profile or (bare_company and not pending_company):
            # A new company topic must not inherit an old person/role/financial filter.
            context = {'companies': list((context or {}).get('companies') or [])}
            if bare_company:
                interpreted = 'Thông tin công ty ' + norm.upper()
        if self.hybrid_router is not None:
            routed = await self.hybrid_router.answer(interpreted, context, provider=self.provider,
                limits=self.limits, budget=self.budget)
            if routed is not None:
                return routed
        if self.admin_news is not None and not annual_requested(_fold(interpreted), context) and not (explicit_profile or bare_company):
            indexed = await self.admin_news.answer(interpreted, session_id, provider=self.provider,
                                                   limits=self.limits, budget=self.budget)
            # A processed-article lookup that finds nothing must not shadow the general news path
            # (e.g. "tin tức FPT mới nhất" matches an FPT article only by ticker, not by content).
            if indexed is not None and indexed.get('status') != 'NO_DATA': return indexed
        prior_scope = (previous_result or {}).get('scope') or {}
        # Recover only legacy, topic-less clarification state; never override an
        # explicitly active financial/news question or a different company.
        if (context and not context.get('source_type') and not context.get('metric_code')
                and not context.get('_pending_metric') and prior_scope.get('source_type') == 'PRICE'
                and context.get('companies') == prior_scope.get('companies')
                and temporal_reply(_fold(interpreted))):
            context = copy.deepcopy(prior_scope)
        decision = news_reference(interpreted, context, previous_result) or analyze_live(interpreted, context, today=today)
        scope = decision['scope']
        result = dict(request_id=str(uuid.uuid4()), query_id=None, execution_mode='LIVE',
                      b1_decision=decision['decision'], status=decision['decision'],
                      reason_code=decision['reason_code'], message=decision['message'], scope=scope,
                      clarification=decision['message'] if decision['decision'] in ('ASK_CLARIFICATION', 'CLARIFICATION_STALLED') else None,
                      clarification_options=decision.get('clarification_options', []),
                      evidence_pack=None, errors=[])
        if decision['decision'] == 'RESOLVE_REFERENCE':
            return self._source_reference(result, previous_result)
        if decision['decision'] == 'MARKET_LOOKUP':
            return await self._answer_market(interpreted, result, previous_result)
        if (decision['decision'] == 'ASK_CLARIFICATION' and scope.get('companies')
                and decision['reason_code'] in ('MISSING_METRIC', 'MULTIPLE_METRICS', 'MISSING_PERIOD', 'MISSING_YEAR')):
            # Asking "which metric?" about a company the corpus does not hold would only lead to a dead end.
            absent, available = await self._missing_companies(scope['companies'])
            if absent and len(absent) == len(scope['companies']):
                result.update(status='NO_DATA', b1_decision='NO_DATA', reason_code='COMPANY_NOT_IN_CORPUS', clarification=None,
                              clarification_options=[],
                              message=f"Kho tài liệu chưa có báo cáo của {', '.join(absent)}. "
                                      f"Hiện có báo cáo của {len(available)} mã: {', '.join(available)}.")
                return result
        if decision['decision'] != 'SEARCH': return result
        label = ('Hồ sơ doanh nghiệp' if scope.get('source_type') == 'COMPANY_PROFILE'
                 else metric_label(scope['metric_code']) if scope.get('metric_code') else 'tin tức')
        query = (f"Báo cáo thường niên {' '.join(scope['companies'])}. {scope.get('_annual_question', interpreted)}"
                 if scope.get('source_type') == 'BCTN' else
                 f"{label} {' '.join(scope['companies'])} {' '.join(scope['periods'])}. {interpreted}")
        try:
            pack = await asyncio.wait_for(self.retriever.retrieve(query, scope), self.retrieval_timeout)
            if not isinstance(pack, dict) or not isinstance(pack.get('items'), list):
                raise CitationError('INVALID_EVIDENCE')
            if not pack['items']:
                result.update(status='NO_DATA', reason_code='NO_DATA', message='Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.')
                absent, available = await self._absent_from_corpus(scope)
                if absent:
                    # Not a missing row: the corpus has no reports of this company at all. Say which it has.
                    result.update(reason_code='COMPANY_NOT_IN_CORPUS',
                                  message=f"Kho tài liệu chưa có báo cáo của {', '.join(absent)}. "
                                          f"Hiện có báo cáo của {len(available)} mã: {', '.join(available)}.")
                return result
            prepare_evidence(pack)
            if scope.get('source_type') == 'BCTN':
                requested = [p for p in scope['periods'] if p != 'LATEST_AVAILABLE_PERIOD']
                if any(i.get('source_type') != 'BCTN' or i['locator'].get('symbol') not in scope['companies']
                       or not re.fullmatch(r'(?:19|20|21)\d{2}', str(i['locator'].get('reporting_year')))
                       or (requested and str(i['locator']['reporting_year']) not in requested) for i in pack['items']):
                    raise ReconstructionError('ANNUAL_SCOPE_MISMATCH', 'Annual evidence differs from requested scope')
                scope['periods'] = sorted({str(i['locator']['reporting_year']) for i in pack['items']})
        except TimeoutError:
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='RETRIEVAL_TIMEOUT', message='Tìm kiếm tạm thời quá thời gian chờ. Vui lòng thử lại.')
            return result
        except (CitationError, ReconstructionError) as exc:
            result.update(status='INSUFFICIENT_EVIDENCE', reason_code=exc.code, message='Chưa xác minh được bằng chứng phù hợp; chưa thể trả lời.')
            return result
        except Exception:
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='RETRIEVAL_UNAVAILABLE', message='Dịch vụ tìm kiếm tạm thời chưa khả dụng. Vui lòng thử lại.')
            return result
        result.update(status='EVIDENCE_READY', reason_code='EVIDENCE_READY', query_id=pack['query_id'],
                      evidence_pack=pack, retrieval_backend=pack.get('retrieval_backend', 'dense'),
                      message='Đã tìm được nguồn ứng viên có nội dung khớp hash.')
        return await complete_retrieval(query, result, provider=self.provider, limits=self.limits, budget=self.budget)

    async def _answer_market(self, question, result, previous_result=None):
        if self.market is None:
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='MARKET_NOT_CONFIGURED',
                          message='Dịch vụ giá và tin mới chưa được kết nối. Vui lòng thử lại sau.')
            return result
        try:
            lookup = (self.market.lookup(result['scope'], previous_pack=(previous_result or {}).get('evidence_pack'))
                      if result['scope'].get('_article_urls') else self.market.lookup(result['scope']))
            market = await asyncio.wait_for(lookup, self.retrieval_timeout)
            pack = market.get('evidence_pack')
            evidence = prepare_evidence(pack) if pack else None
        except (TimeoutError, CitationError):
            result.update(status='SYSTEM_UNAVAILABLE', reason_code='MARKET_LOOKUP_FAILED',
                          message='Chưa lấy được dữ liệu giá hoặc tin mới hợp lệ. Vui lòng thử lại sau.')
            return result
        result.update(market)
        result['retrieval_backend'] = 'shared_market_feed'
        source_type = result['scope']['source_type']
        result['presentation'] = {'sources': 'HIDDEN' if source_type == 'PRICE' else 'USED_LINKS'}
        if not evidence: return result
        result['query_id'] = pack['query_id']
        if market['status'] == 'PRICE_READY':
            item = next(iter(evidence.values()))
            result['scope']['_market_request']['anchor_day'] = item['snapshot']['trading_day']
            citation = {key: copy.deepcopy(item[key]) for key in (
                'evidence_id', 'source_id', 'chunk_id', 'source_sha256', 'content_sha256',
                'source_verified', 'source_type', 'title', 'locator')}
            citation['citation_number'] = 1
            result.update(status='EVIDENCE_READY', answering={
                'status': 'DRAFT_READY', 'reason_code': market['reason_code'], 'draft': market['draft'],
                'message': market['message'], 'claims': [], 'citations': [citation],
                'manifest': {'mode': 'B1', 'response_mode': 'MARKET_QUOTE',
                             'config_version': self.limits.version, 'retrieval_backend': 'shared_market_feed',
                             'components': {'gemini': False, 'citation_binding': True,
                                            'b3_evidence_gate': False, 'b3_answer_verification': False}},
                'budget': self.budget.snapshot(), 'trace': [{'event': 'shared_market_quote'}]})
            return result
        if (result['scope'].get('_market_request') or {}).get('action', 'LIST') == 'LIST':
            citations = []
            lines = []
            for number, item in enumerate(evidence.values(), 1):
                stamp = datetime.fromisoformat(item['snapshot']['published_at'])
                lines.append(f"{number}. {item['title']} ({stamp:%d/%m/%Y})")
                citations.append({**{key: copy.deepcopy(item[key]) for key in (
                    'evidence_id', 'source_id', 'chunk_id', 'source_sha256', 'content_sha256',
                    'source_verified', 'source_type', 'title', 'locator')}, 'citation_number': number})
            result['presentation']['sources'] = 'LINKS'
            result['answering'] = {'status': 'DRAFT_READY', 'reason_code': 'NEWS_LIST',
                'draft': '\n\n'.join(lines), 'claims': [], 'citations': citations,
                'manifest': {'mode': 'B1', 'response_mode': 'NEWS_LIST',
                             'components': {'gemini': False, 'b3_evidence_gate': False, 'b3_answer_verification': False}},
                'budget': self.budget.snapshot(), 'trace': [{'event': 'shared_news_listing'}]}
            return result
        out = await complete_retrieval(question, result, provider=self.provider, limits=self.limits, budget=self.budget)
        if out.get('answering', {}).get('status') == 'DRAFT_READY':
            for item in evidence.values():
                published = item.get('snapshot', {}).get('published_at')
                if published:
                    formatted = datetime.fromisoformat(published).strftime('%d/%m/%Y')
                    out['answering']['draft'] = out['answering']['draft'].replace(published, formatted)
        if market.get('freshness', {}).get('stale') and out.get('answering', {}).get('status') == 'DRAFT_READY':
            out['answering']['draft'] += '\n\nĐây là tin lưu gần nhất; lần lấy tin mới vừa thất bại.'
        return out


_EN_NUMBER = re.compile(r'(?<![\d.,])\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?(?![\d,])|(?<![\d.,])\d{1,3},\d{3}\.\d+(?![\d])')


def vietnamese_numbers(text):
    """Show 13,788,503.46 as 13.788.503,46. Only unambiguous thousands groupings are touched."""
    return _EN_NUMBER.sub(lambda m: m.group(0).translate({44: 46, 46: 44}), text)


def render_live_response(result):
    answering = result.get('answering') or {}
    if answering.get('status') == 'DRAFT_READY':
        if (answering.get('manifest') or {}).get('response_mode') in ('PRICE_ANALYTICS', 'MARKET_QUOTE', 'NEWS_LIST'):
            return answering['draft']
        return vietnamese_numbers(answering['draft'])
    if (answering.get('reason_code') == 'NOT_STATED_IN_SOURCE'
            and (result.get('hybrid_router') or {}).get('route') in ('GRAPH', 'BOTH')):
        return ('Dữ liệu quan hệ và tài liệu hiện có chưa ghi nhận thông tin này. '
                'Có thể công ty không có thông tin đó hoặc dữ liệu chưa được cập nhật; mình không suy đoán.')
    if answering.get('reason_code') in ('REQUESTED_PERIOD_NOT_IN_SOURCE', 'NOT_STATED_IN_SOURCE'):
        return answering['message']
    if result.get('status') != 'EVIDENCE_READY':
        return result['message']
    if answering.get('reason_code') == 'PROVIDER_NOT_CONFIGURED':
        return 'Đã tìm thấy nguồn phù hợp. Chưa cấu hình Gemini để diễn đạt câu trả lời; mở phần nguồn bên dưới để xem chỉ tiêu.'
    if answering.get('status') == 'INSUFFICIENT_EVIDENCE':
        return 'Đã tìm thấy tài liệu nhưng chưa xác minh được câu trả lời. Mở nguồn bên dưới để kiểm tra hoặc thử hỏi lại.'
    return 'Đã tìm thấy tài liệu nhưng dịch vụ tạo câu trả lời đang tạm thời không khả dụng. Vui lòng thử lại sau.'
