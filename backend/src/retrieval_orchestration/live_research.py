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
from .input_normalization import normalize_user_text
from .market_dates import price_date_request, temporal_reply

V4_CORPUS = '33d33730-0f0a-5274-a7f8-8d32a6be07e8'
MODEL = 'BAAI/bge-m3@5617a9f61b02'
_embedding_lock = threading.Lock()
# Explicit semantic aliases; unrelated financial rows must never stand in for a metric.
METRIC_ALIASES = {
    'TOTAL_ASSETS': ('tổng tài sản', 'total assets'),
    'CASH_AND_CASH_EQUIVALENTS': ('tiền và các khoản tương đương tiền', 'tiền và tương đương tiền', 'cash and cash equivalents'),
    'SHORT_TERM_LOANS_AND_FINANCE_LEASES': ('vay và nợ thuê tài chính ngắn hạn', 'nợ vay ngắn hạn'),
    'LONG_TERM_LOANS_AND_FINANCE_LEASES': ('vay và nợ thuê tài chính dài hạn', 'nợ vay dài hạn'),
    'CURRENT_LIABILITIES': ('nợ ngắn hạn', 'current liabilities'),
    'NON_CURRENT_LIABILITIES': ('nợ dài hạn', 'non-current liabilities'),
    'RETAINED_EARNINGS': ('lợi nhuận sau thuế chưa phân phối', 'lợi nhuận chưa phân phối', 'retained earnings'),
    'NET_REVENUE': ('doanh thu thuần', 'net revenue'),
    'GROSS_REVENUE': ('doanh thu bán hàng và cung cấp dịch vụ', 'doanh thu trước giảm trừ', 'gross revenue'),
    'PROFIT_BEFORE_TAX': ('lợi nhuận trước thuế', 'profit before tax', 'LNTT'),
    'PROFIT_AFTER_TAX': ('lợi nhuận sau thuế', 'profit after tax', 'LNST'),
    'PARENT_NET_PROFIT': ('lợi nhuận sau thuế thuộc cổ đông công ty mẹ',
                          'lợi nhuận sau thuế của cổ đông công ty mẹ',
                          'LNST cổ đông công ty mẹ', 'LNST thuộc cổ đông công ty mẹ', 'LNST công ty mẹ', 'parent net profit'),
    'CASH_FLOW_OPERATING': ('lưu chuyển tiền thuần từ hoạt động kinh doanh', 'dòng tiền hoạt động kinh doanh', 'cash flow from operating activities'),
    'CASH_FLOW_INVESTING': ('lưu chuyển tiền thuần từ hoạt động đầu tư', 'dòng tiền hoạt động đầu tư', 'cash flow from investing activities'),
    'CASH_FLOW_FINANCING': ('lưu chuyển tiền thuần từ hoạt động tài chính', 'dòng tiền hoạt động tài chính', 'cash flow from financing activities'),
    'CHARTER_CAPITAL': ('vốn điều lệ', 'charter capital'),
    'TOTAL_LIABILITIES': ('tổng nợ phải trả', 'nợ phải trả'),
    'TOTAL_EQUITY': ('tổng vốn chủ sở hữu', 'vốn chủ sở hữu'),
}
POINT_METRICS = {'TOTAL_ASSETS', 'CASH_AND_CASH_EQUIVALENTS', 'SHORT_TERM_LOANS_AND_FINANCE_LEASES',
                 'LONG_TERM_LOANS_AND_FINANCE_LEASES', 'CURRENT_LIABILITIES', 'NON_CURRENT_LIABILITIES',
                 'CHARTER_CAPITAL', 'RETAINED_EARNINGS', 'TOTAL_LIABILITIES', 'TOTAL_EQUITY'}


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
    price = bool(re.search(r'\b(?:gia co phieu|thi gia|gia hien tai|gia hom nay)\b', norm)
                 or (short_price and short_price[1] not in {'von', 'tri', 'cua', 'ban', 'mua', 'dat', 'san', 'cao', 'day', 'goc'}))
    dated = bool(re.search(r'\b(?:quy|thang|nam|ngay)\s+\d|\b(?:19|20|21)\d{2}\b', norm))
    current = bool(re.search(r'\b(?:hom nay|hien tai|moi nhat|moi|bay gio)\b', norm))
    day = calendar_day(norm, today)
    action = 'SUMMARY' if re.search(r'\b(?:tom tat|tong hop|diem tin)\b', norm) else 'LIST'
    prior = (context or {}).get('_market_request')
    financial = metric_group(norm) or any(_fold(a) in norm for aliases in METRIC_ALIASES.values() for a in aliases)
    company_selection = (norm.isdigit() and
                         str(((context or {}).get('_clarification_state') or {}).get('id', '')).startswith('company:'))
    if not financial and not news and not company_selection:
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
            return {'kind': 'QUOTE' if price else 'NEWS',
                    'day': day, 'action': action}
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


def analyze_live(text, context=None, *, today=None):
    """Resolve explicit slots and follow-ups without generating values or SQL."""
    today = today or datetime.now(timezone(timedelta(hours=7))).date()
    text = normalize_user_text(text, context)
    market_request = _market_intent(_fold(text), context, today)
    norm = _fold(_resolve_relative_periods(text, today))
    norm = resolve_reply(norm, context)
    scope = copy.deepcopy(context or {})
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
    if not market_request and re.search(r'\b(?:gia co phieu|gia dong cua|gia mo cua|khoi luong giao dich|gia muc tieu)\b', norm):
        return finish('UNSUPPORTED', 'PRICE_QUERY_SEPARATE', 'Câu hỏi giá cần luồng tra cứu giá có cấu trúc; chat này hiện tìm báo cáo tài chính và tin tức.')
    if re.search(r'\b(?:bctn|bao cao thuong nien)\b', norm):
        return finish('UNSUPPORTED', 'SOURCE_NOT_AVAILABLE', 'Luồng chat này chưa có nguồn PDF báo cáo thường niên để xác minh.')
    quarters = re.findall(r'\b(?:quy|q)\s*(\d+)\s*[/ -]?\s*((?:19|20|21)\d{2})\b', norm)
    canonical_quarters = re.findall(r'\b((?:19|20|21)\d{2})-q(\d+)\b', norm)
    if (any(not 1 <= int(q) <= 4 for q, _ in quarters)
            or any(not 1 <= int(q) <= 4 for _, q in canonical_quarters)
            or len(set(quarters)) > 1 or len(set(canonical_quarters)) > 1):
        scope.pop('periods', None)
        scope.pop('_pending_quarter', None)
        scope.pop('_pending_ytd', None)
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_PERIOD', 'Bạn muốn xem quý nào? Vui lòng nêu một kỳ hợp lệ từ quý 1 đến quý 4.')
    companies = [s for s in (*TICKERS, 'SSI', 'CTR', 'VNM', 'MSN', 'NLG') if re.search(r'\b'+s.lower()+r'\b', norm)]
    reserved = {'BCTC', 'BCTN', 'YTD', 'VND', 'USD', 'EUR', 'UBND', 'CTCP', 'TNHH',
                'NEWS', 'CASH', 'TOTAL', 'CAFEF', 'LNST', 'LNTT'}
    companies += [s for s in re.findall(r'\b[A-Z]{3,5}\b', text) if s not in reserved and s not in companies]
    ticker_stop = STOP_WORDS | {'mot', 'cuoi', 'thuan', 'nhat', 'rieng', 'hop', 'ngan', 'dai',
                              'thu', 'phi', 'tuc', 'cafef', 'news', 'trong', 'tai', 'ky',
                              'von', 'loi', 'lai', 'tong', 'vay', 'thue', 'dong', 'tien',
                              'hom', 'hien', 'nay', 'nhieu', 'bao', 'moi', 'nhat'}
    ticker_stop |= {word for aliases in METRIC_ALIASES.values() for alias in aliases for word in _fold(alias).split()}
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
    if not companies and re.fullmatch(r'(?:con |khong,? la |la )?[a-z]{3}', norm):
        token = norm.split()[-1]
        if token not in ticker_stop | {'sau', 'nam', 'nay', 'cho', 'xem', 'moi'}:
            companies = [token.upper()]
    if companies:
        scope['companies'] = list(dict.fromkeys(companies))
        if (context or {}).get('companies') and scope['companies'] != context['companies']:
            scope.pop('_pending_publisher', None)
            scope.pop('_pending_reporting_entity', None)
    if market_request:
        scope = {key: value for key, value in scope.items() if key in ('companies', '_clarification_state')}
        decision['scope'] = scope
        scope.update(source_type='PRICE' if market_request['kind'] == 'QUOTE' else 'NEWS',
                     metric_code='LAST_PRICE' if market_request['kind'] == 'QUOTE' else None,
                     periods=[market_request['day']] if market_request['day'] else [],
                     _market_request=market_request)
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
        if not scope.get('companies'):
            return finish('ASK_CLARIFICATION', 'MISSING_COMPANY', 'Bạn muốn xem công ty nào?')
        if len(scope['companies']) != 1:
            return finish('ASK_CLARIFICATION', 'SCOPE_TOO_LARGE', 'Vui lòng chọn một mã cổ phiếu cho mỗi lần tra cứu giá hoặc tin mới.')
        return finish('MARKET_LOOKUP', 'CURRENT_MARKET_REQUEST', 'Đang tra cứu nguồn giá hoặc tin tức đang cập nhật.')
    if scope.pop('_market_request', None):
        for key in ('periods', 'metric_code', 'source_type', 'publisher', 'measure_basis', 'reporting_entity'):
            scope.pop(key, None)
    found = [code for code, aliases in METRIC_ALIASES.items()
             if any(re.search(r'\b'+re.escape(_fold(a))+r'\b', norm) for a in (*aliases, code))]
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
    if len(found) == 1 and (context or {}).get('metric_code') and found[0] != context['metric_code']:
        scope.pop('_pending_reporting_entity', None)
    publishers = [name for name in ('cafef', 'fireant') if re.search(r'\b'+name+r'\b', norm)]
    news = bool(re.search(r'\b(?:tin tuc|tin|news)\b', norm) or (scope.get('source_type') == 'NEWS' and publishers))
    if news:
        scope.update(source_type='NEWS', metric_code=None, reporting_entity='UNKNOWN')
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
    parent = ('bao cao rieng' in norm or ('cong ty me' in norm and scope.get('metric_code') != 'PARENT_NET_PROFIT')
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
    if not scope.get('companies'):
        return finish('ASK_CLARIFICATION', 'MISSING_COMPANY', 'Bạn muốn xem công ty nào?')
    if scope.get('_pending_publisher'):
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_PUBLISHER', 'Bạn muốn xem nguồn CafeF hay FireAnt trước?')
    if scope.get('_pending_reporting_entity'):
        return finish('ASK_CLARIFICATION', 'AMBIGUOUS_REPORTING_ENTITY', 'Bạn muốn xem báo cáo hợp nhất hay báo cáo riêng?')
    if not metric and scope.get('source_type') != 'NEWS':
        return finish('ASK_CLARIFICATION', 'MULTIPLE_METRICS' if multiple else 'MISSING_METRIC', 'Bạn muốn xem chỉ tiêu nào?')
    if not scope.get('periods'):
        if scope.get('_pending_quarter'):
            return finish('ASK_CLARIFICATION', 'MISSING_YEAR', f"Bạn muốn xem quý {scope['_pending_quarter']} của năm nào?")
        return finish('ASK_CLARIFICATION', 'MISSING_PERIOD', 'Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.')
    if len(scope['companies']) > 2 or len(scope['periods']) > 2:
        return finish('ASK_CLARIFICATION', 'SCOPE_TOO_LARGE', 'Vui lòng hỏi tối đa hai mã và hai kỳ mỗi lần.')
    return finish('SEARCH', 'SCOPE_READY', 'Đang tìm bằng chứng trong corpus đã chọn.')


class DenseEvidenceRetriever:
    """Corpus-bound adapter with dense or independently indexed BM25/RRF retrieval."""
    def __init__(self, pool, embedder, *, corpus_version_id=V4_CORPUS, model_ref=MODEL,
                 backend='dense', cache_dir=None):
        if backend not in ('dense', 'hybrid'):
            raise ValueError('Unsupported retrieval backend')
        self.pool, self.embedder = pool, embedder
        self.corpus_version_id = str(uuid.UUID(corpus_version_id))
        self.model_ref = model_ref
        self.backend = backend
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(__file__).resolve().parents[1] / 'vector_retrieval' / '.cache'
        self._hybrid = None
        self._cache_lock = asyncio.Lock()

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
            self._hybrid = HybridRetriever(self.pool, LockedEmbedder(), corpus_version_id=self.corpus_version_id)
        return self._hybrid

    async def _corpus(self):
        corpus = await repository.get_corpus_index(self.pool, self.corpus_version_id)
        if (not corpus or corpus['corpus_status'] != 'FROZEN' or corpus['index_status'] != 'ACTIVE'
                or corpus['embedding_model'] != self.model_ref):
            raise ReconstructionError('CORPUS_NOT_READY', 'Pinned corpus or model is not ready')
        return corpus

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

    async def _hybrid_rows(self, question, scope, corpus, company, period):
        from ..vector_retrieval.backend import RetrievalError
        self._hybrid_instance()
        cache = self.cache_dir / ('corpus-' + self.corpus_version_id + '.json')
        params = dict(company=company, period=period,
                      doc_type='NEWS' if scope['source_type'] == 'NEWS' else 'FINANCIAL_STATEMENT',
                      publisher=scope.get('publisher'),
                      published_date=period if scope['source_type'] == 'NEWS' and len(period) == 10 else None,
                      exact_period=scope['source_type'] != 'NEWS', top_k=20, candidates=100)
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

    async def retrieve(self, question, scope):
        corpus = await self._corpus()
        vector = await self._embed(question) if self.backend == 'dense' else None
        items, seen = [], set()
        for company in scope['companies']:
            for period in scope['periods']:
                if self.backend == 'hybrid':
                    rows = await self._hybrid_rows(question, scope, corpus, company, period)
                else:
                    rows = await repository.vector_search_filtered(
                        self.pool, corpus['index_version_id'], vector, 20,
                        company_symbol=company, period=period,
                        doc_type='NEWS' if scope['source_type'] == 'NEWS' else 'FINANCIAL_STATEMENT',
                        corpus_version_id=self.corpus_version_id,
                        exact_period=scope['source_type'] != 'NEWS',
                    )
                matching = []
                for row in rows:
                    if row.get('source_verified', True) is not True:
                        raise ReconstructionError('UNVERIFIED_SOURCE', 'Preview cannot be evidence')
                    text = row['text']
                    if scope.get('publisher'):
                        from ..vector_retrieval.backend import _derive_publisher
                        if _derive_publisher(row) != scope['publisher']: continue
                    metric = scope.get('metric_code')
                    if metric and not re.search(r'\('+re.escape(metric)+r'\)', text):
                        continue
                    entity = scope.get('reporting_entity', 'UNKNOWN')
                    header = _fold(text.split('\n', 1)[0])
                    if not reporting_entity_matches(text.split('\n', 1)[0], entity):
                        continue
                    basis = scope.get('measure_basis')
                    if scope['source_type'] != 'NEWS' and basis == 'YTD' and not re.search(r'\b(?:luy ke|ytd)\b', header):
                        continue
                    if (scope['source_type'] != 'NEWS' and basis == 'STANDALONE_QUARTER'
                            and ('luy ke' in header or 'ytd' in header)):
                        continue
                    if row['chunk_id'] in seen: continue
                    seen.add(row['chunk_id'])
                    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
                    if content_hash != row['content_hash'].strip():
                        raise ReconstructionError('HASH_MISMATCH', 'Indexed text differs')
                    matching.append(dict(
                        evidence_id=row['chunk_id'], chunk_id=row['chunk_id'], source_id=row['document_id'],
                        source_type=scope['source_type'], title=row['title'], passage=text,
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

    def __init__(self, retriever, *, provider=None, limits=None, retrieval_timeout=120, market=None):
        self.retriever, self.provider = retriever, provider
        self.market = market
        self.limits = limits or Limits.load()
        self.budget = Budget(self.limits)
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
            title = (citation.get('title') or 'Nguồn thị trường') if citation.get('source_type') in ('NEWS', 'PRICE') else (
                'Báo cáo tài chính '+', '.join(old_scope.get('companies', [])))
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

    async def answer(self, question, session_id, context=None, *, previous_result=None, today=None):
        interpreted = normalize_user_text(question, context)
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
        if decision['decision'] != 'SEARCH': return result
        label = METRIC_ALIASES.get(scope.get('metric_code'), ('tin tức',))[0]
        query = f"{label} {' '.join(scope['companies'])} {' '.join(scope['periods'])}. {interpreted}"
        try:
            pack = await asyncio.wait_for(self.retriever.retrieve(query, scope), self.retrieval_timeout)
            if not isinstance(pack, dict) or not isinstance(pack.get('items'), list):
                raise CitationError('INVALID_EVIDENCE')
            if not pack['items']:
                result.update(status='NO_DATA', reason_code='NO_DATA', message='Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.')
                return result
            prepare_evidence(pack)
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


def render_live_response(result):
    answering = result.get('answering') or {}
    if answering.get('status') == 'DRAFT_READY':
        return answering['draft']
    if result.get('status') != 'EVIDENCE_READY':
        return result['message']
    if answering.get('reason_code') == 'PROVIDER_NOT_CONFIGURED':
        return 'Đã tìm thấy nguồn phù hợp. Chưa cấu hình Gemini để diễn đạt câu trả lời; mở phần nguồn bên dưới để xem chỉ tiêu.'
    if answering.get('status') == 'INSUFFICIENT_EVIDENCE':
        return 'Đã tìm thấy tài liệu nhưng chưa xác minh được câu trả lời. Mở nguồn bên dưới để kiểm tra hoặc thử hỏi lại.'
    return 'Đã tìm thấy tài liệu nhưng dịch vụ tạo câu trả lời đang tạm thời không khả dụng. Vui lòng thử lại sau.'
