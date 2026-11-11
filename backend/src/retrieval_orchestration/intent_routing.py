"""S5-WBS04.2: ordered scope, confidence and route gates over Nhân's matcher.

This module returns a plan/signal only. It never retrieves data or calls a
fallback LLM, and is not registered in the existing WebChat/router factory.
"""
from decimal import Decimal
from datetime import date
import math
import re
import unicodedata

CONFIDENCE_THRESHOLD = 0.65
GAP_THRESHOLD = 0.08
FALLBACK_TASK = 'S5-WBS07.2'
FALLBACK_TOP_GROUPS = 3

INTENT_ROUTES = {
    'NUMERIC': 'VECTOR', 'REPORT_CONTENT': 'VECTOR', 'NEWS': 'VECTOR',
    'PERSON_ROLE': 'GRAPH', 'ENTITY_RELATION': 'GRAPH',
    'MIXED': 'BOTH', 'TREND': 'BOTH',
}
# Compatibility with the names in the task brief; outputs retain Nhân's IDs.
LABEL_ALIASES = {
    'SO_LIEU': 'NUMERIC', 'BCTC_BCTN': 'REPORT_CONTENT',
    'CHUC_VU': 'PERSON_ROLE', 'QUAN_HE': 'ENTITY_RELATION',
    'KET_HOP': 'MIXED', 'XU_HUONG': 'TREND',
}


def _fold(text):
    text = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _invalid_period(question, period):
    text = _fold(question)
    quarters = re.findall(r'\b(?:quy\s*|q)(-?\d+)\b', text)
    if any(int(q) not in (1, 2, 3, 4) for q in quarters):
        return True
    for day, month, year in re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', question):
        try:
            date(int(year), int(month), int(day))
        except ValueError:
            return True
    for stamp in re.findall(r'\b\d{4}-\d{2}-\d{2}\b', question):
        try:
            date.fromisoformat(stamp)
        except ValueError:
            return True
    if period is None:
        return False
    if not isinstance(period, str) or not period.strip():
        return True
    period = period.strip()
    # Relative/coverage periods belong to the existing scope resolver, not this gate.
    if period in {'LATEST_AVAILABLE_PERIOD', 'LATEST_PUBLISHED_PERIOD', 'CURRENT',
                  'CURRENT_YEAR', 'PREVIOUS_YEAR', 'CURRENT_QUARTER', 'PREVIOUS_QUARTER'}:
        return False
    if re.fullmatch(r'\d{4}(?:-Q[1-4])?', period):
        return int(period[:4]) == 0
    try:
        date.fromisoformat(period)
        return False
    except ValueError:
        return True


def _ticker(value):
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if re.fullmatch(r'[A-Z][A-Z0-9]{2,4}', value) and value not in {
        'BCTC', 'BCTN', 'NEWS', 'PRICE', 'CEO', 'CFO', 'HDQT', 'VND', 'USD',
    } else None


def _result(decision, gate, reason, scope, *, route=None, label=None, first=None, second=None, gap=None):
    fallback = decision == 'NEED_FALLBACK'
    return {
        'decision': decision, 'route': route, 'need_fallback': fallback,
        'fallback_task': FALLBACK_TASK if fallback else None,
        'fallback_payload': None,
        'gate': gate, 'reason_code': reason, 'scope': scope,
        'intent_label': label, 'top_1_score': first, 'top_2_score': second, 'score_gap': gap,
        'clarification_question': (
            'Bạn muốn tra cứu thông tin này cho mã doanh nghiệp nào?' if reason in {
                'MISSING_COMPANY', 'INVALID_COMPANY', 'AMBIGUOUS_CONTEXT_COMPANY'} else
            'Kỳ báo cáo chưa hợp lệ. Bạn muốn hỏi kỳ nào? Quý chỉ từ 1 đến 4.' if reason == 'INVALID_PERIOD' else
            'Bạn muốn tra cứu thông tin gì?' if decision == 'ASK_CLARIFICATION' else None
        ),
    }


def _fallback_result(reason, scope, question, *, labels=(), scores=(), first=None, second=None, gap=None):
    result = _result('NEED_FALLBACK', 2, reason, scope, first=first, second=second, gap=gap)
    result['fallback_payload'] = {
        'question': question or None,
        # Only resolved scope is forwarded, never raw chat history or examples.
        'scope': dict(scope),
        'reason_code': reason,
        'allowed_labels': list(INTENT_ROUTES),
        'candidates': [
            {'rank': i + 1, 'intent_label': label, 'score': score}
            for i, (label, score) in enumerate(zip(labels, scores))
            if i < FALLBACK_TOP_GROUPS
        ],
        'score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY',
    }
    return result


def _scope_gate(*, question='', company_ticker=None, period=None,
                context_company_ticker=None, context_confirmed=False,
                context_same_session=False, company_required=True, valid_tickers=None):
    scope = {'company_ticker': None, 'period': period, 'company_source': None}
    if not isinstance(question, str) or len(question) > 4000 or (question != '' and not question.strip()):
        return scope, _result('ASK_CLARIFICATION', 1, 'INVALID_QUESTION', scope)
    # Invalid explicit quarter is checked even if a previous period was valid.
    if _invalid_period(question, period):
        return scope, _result('ASK_CLARIFICATION', 1, 'INVALID_PERIOD', scope)
    value, origin = company_ticker, 'CURRENT'
    if value is None and context_same_session is True and context_confirmed is True:
        value, origin = context_company_ticker, 'CONTEXT'
        if isinstance(value, (list, tuple)):
            if len(value) != 1:
                return scope, _result('ASK_CLARIFICATION', 1, 'AMBIGUOUS_CONTEXT_COMPANY', scope)
            value = value[0]
    if value is not None:
        ticker = _ticker(value)
        if ticker is None or (valid_tickers is not None and ticker not in valid_tickers):
            return scope, _result('ASK_CLARIFICATION', 1, 'INVALID_COMPANY', scope)
        scope.update(company_ticker=ticker, company_source=origin)
    elif company_required:
        return scope, _result('ASK_CLARIFICATION', 1, 'MISSING_COMPANY', scope)
    return scope, None


def _confidence_and_route(ranking, scope, question):
    try:
        if not isinstance(ranking, dict):
            raise ValueError('Missing classification')
        if 'question' in ranking and question and ranking['question'] != question:
            raise ValueError('Stale query ranking')
        if ranking.get('ranking_policy', 'cosine-max-per-label-v1') != 'cosine-max-per-label-v1':
            raise ValueError('Wrong score policy')
        if ranking.get('score_type', 'COSINE_SIMILARITY_NOT_PROBABILITY') != 'COSINE_SIMILARITY_NOT_PROBABILITY':
            raise ValueError('Wrong score type')
        groups = ranking['groups']
        if not isinstance(groups, list) or not 2 <= len(groups) <= len(INTENT_ROUTES):
            raise ValueError('Two distinct groups are required')
        labels, scores = [], []
        for index, group in enumerate(groups):
            label = group['intent_label']
            label = LABEL_ALIASES.get(label, label)
            score = group['score']
            if label not in INTENT_ROUTES or label in labels:
                raise ValueError('Invalid or duplicate label')
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValueError('Invalid score type')
            if not math.isfinite(score) or not -1 <= score <= 1:
                raise ValueError('Invalid cosine score')
            if 'rank' in group and (type(group['rank']) is not int or group['rank'] != index + 1):
                raise ValueError('Invalid rank')
            labels.append(label); scores.append(score)
        if any(scores[i] < scores[i+1] for i in range(len(scores)-1)):
            raise ValueError('Groups are not ranked')
    except (KeyError, TypeError, ValueError, OverflowError):
        return _fallback_result('INVALID_CLASSIFICATION', scope, question)
    first, second = scores[:2]
    # Compare decimal representations without rounding scores, including equality at 0.08.
    gap = Decimal(str(first)) - Decimal(str(second))
    low = Decimal(str(first)) < Decimal(str(CONFIDENCE_THRESHOLD))
    close = gap < Decimal(str(GAP_THRESHOLD))
    if low or close:
        reason = 'LOW_CONFIDENCE_AND_SMALL_GAP' if low and close else 'LOW_CONFIDENCE' if low else 'SMALL_GAP'
        return _fallback_result(reason, scope, question, labels=labels, scores=scores,
                                first=first, second=second, gap=float(gap))
    return _result('SEARCH', 3, 'CONFIDENT_INTENT', scope, route=INTENT_ROUTES[labels[0]],
                   label=labels[0], first=first, second=second, gap=float(gap))


def decide_intent_route(ranking, **scope_input):
    """Pure gate function over an existing IntentMatcher result (or two-group fixture).

    company_ticker/context tickers must come from the upstream verified company
    resolver. Optional valid_tickers enforces an injected registry, without DB I/O.
    """
    scope, stopped = _scope_gate(**scope_input)
    if stopped is not None:
        return stopped
    return _confidence_and_route(ranking, scope, scope_input.get('question', ''))


class IntentRoutingPolicy:
    """Lazy matcher call: gate 1 stops before query embedding or external services."""
    def __init__(self, matcher):
        self.matcher = matcher

    def decide(self, question, **scope_input):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            return _result('ASK_CLARIFICATION', 1, 'INVALID_QUESTION', {})
        scope, stopped = _scope_gate(question=question, **scope_input)
        if stopped is not None:
            return stopped
        try:
            ranking = self.matcher.match(question, top_groups=FALLBACK_TOP_GROUPS, top_examples=5)
        except Exception:
            return _fallback_result('CLASSIFICATION_ERROR', scope, question)
        return _confidence_and_route(ranking, scope, question)
