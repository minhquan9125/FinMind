"""S5-WBS04.2: ordered scope, confidence and route gates over Nhân's matcher.

This module returns a plan/signal only. It never retrieves data or calls a
fallback LLM, and is not registered in the existing WebChat/router factory.
"""
from copy import deepcopy
from decimal import Decimal
from datetime import date
import math
import re
import unicodedata

CONFIDENCE_THRESHOLD = 0.65
GAP_THRESHOLD = 0.08
FALLBACK_TASK = 'S5-WBS07.2'
FALLBACK_TOP_GROUPS = 3
COSINE_POLICY = 'cosine-max-per-label-v1'
COSINE_SCORE_TYPE = 'COSINE_SIMILARITY_NOT_PROBABILITY'
CLASSIFIER_POLICY = 'intent-linear-v1'
CLASSIFIER_SCORE_TYPE = 'CLASSIFIER_PROBABILITY_UNCALIBRATED'
EVIDENCE_SCORE_TYPE = 'DECISION_EVIDENCE_NO_CONFIDENCE'
RESOLUTION_POLICIES = frozenset({
    'intent-request-consensus-v1',
    *(f'intent-request-objectives-v{version}' for version in range(1, 6)),
})

INTENT_ROUTES = {
    'NUMERIC': 'VECTOR', 'REPORT_CONTENT': 'VECTOR', 'NEWS': 'VECTOR',
    'PERSON_ROLE': 'GRAPH', 'ENTITY_RELATION': 'GRAPH',
    'MIXED': None, 'TREND': 'BOTH',
}
# Compatibility with the names in the task brief; outputs retain Nhân's IDs.
LABEL_ALIASES = {
    'SO_LIEU': 'NUMERIC', 'BCTC_BCTN': 'REPORT_CONTENT',
    'CHUC_VU': 'PERSON_ROLE', 'QUAN_HE': 'ENTITY_RELATION',
    'KET_HOP': 'MIXED', 'XU_HUONG': 'TREND',
}


class IntentClassificationContractError(ValueError):
    """Invalid producer data; caller must report the error, not call fallback AI."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _fold(text):
    text = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _invalid_period(question, period):
    text = _fold(question)
    number = r'[+-]?\s*\d+(?:\.\d+)?'
    quarter = re.compile(r'\b(?:quy|q)\s*(' + number + r')\b')
    continuation = re.compile(
        r'\s*(?:,|va\b|den\b|toi\b|[-–])\s*'
        r'(?:(?P<quarter>quy|q)\s*)?(?P<number>' + number + r')\b')
    for match in quarter.finditer(text):
        values = [match.group(1)]
        end = match.end()
        while following := continuation.match(text, end):
            # A bare year or full date ends a quarter list/range. An explicit
            # Q/quy prefix still means a quarter and must pass the 1..4 check.
            if following.group('quarter') is None and (
                    re.fullmatch(r'\d{4}', following.group('number'))
                    or re.match(r'\d{1,2}/\d{1,2}/\d{4}\b', text[following.start('number'):])):
                break
            values.append(following.group('number'))
            end = following.end()
        for value in values:
            value = re.sub(r'\s+', '', value)
            # A comma is a list separator: 1,2 is valid; 1,5 contains Q5.
            # A decimal point never turns a fractional quarter into Q1.
            if not re.fullmatch(r'[+-]?\d+', value) or int(value) not in (1, 2, 3, 4):
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
        'classification_evidence': None,
        'gate': gate, 'reason_code': reason, 'scope': scope,
        'intent_label': label, 'top_1_score': first, 'top_2_score': second, 'score_gap': gap,
        'clarification_question': (
            'Bạn muốn tra cứu thông tin này cho mã doanh nghiệp nào?' if reason in {
                'MISSING_COMPANY', 'INVALID_COMPANY', 'AMBIGUOUS_CONTEXT_COMPANY'} else
            'Kỳ báo cáo chưa hợp lệ. Bạn muốn hỏi kỳ nào? Quý chỉ từ 1 đến 4.' if reason == 'INVALID_PERIOD' else
            'Bạn muốn tra cứu thông tin gì?' if decision == 'ASK_CLARIFICATION' else None
        ),
    }


def _fallback_result(reason, scope, question, *, labels=(), scores=(), first=None, second=None,
                     gap=None, score_type=COSINE_SCORE_TYPE):
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
        'score_type': score_type,
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


def _metadata(payload, question):
    if not isinstance(payload, dict):
        raise IntentClassificationContractError('INVALID_CLASSIFICATION')
    if 'question' in payload and question and payload['question'] != question:
        raise IntentClassificationContractError('STALE_CLASSIFICATION')
    for key in ('ranking_policy', 'score_type'):
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise IntentClassificationContractError('MISSING_SCORE_METADATA')
    return payload['ranking_policy'], payload['score_type']


def _canonical_label(value):
    if not isinstance(value, str):
        raise IntentClassificationContractError('INVALID_INTENT_LABEL')
    label = LABEL_ALIASES.get(value, value)
    if label not in INTENT_ROUTES:
        raise IntentClassificationContractError('INVALID_INTENT_LABEL')
    return label


def _validated_ranking(ranking, question):
    policy, score_type = _metadata(ranking, question)
    if (policy, score_type) not in {
        (COSINE_POLICY, COSINE_SCORE_TYPE),
        (CLASSIFIER_POLICY, CLASSIFIER_SCORE_TYPE),
    }:
        raise IntentClassificationContractError('UNSUPPORTED_SCORE_CONTRACT')
    try:
        groups = ranking['groups']
        if not isinstance(groups, list) or not 2 <= len(groups) <= len(INTENT_ROUTES):
            raise ValueError('Two distinct groups are required')
        labels, scores = [], []
        for index, group in enumerate(groups):
            label = _canonical_label(group['intent_label'])
            score = group['score']
            if label in labels:
                raise ValueError('Duplicate label')
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValueError('Invalid score type')
            lower = -1 if score_type == COSINE_SCORE_TYPE else 0
            if not math.isfinite(score) or not lower <= score <= 1:
                raise ValueError('Invalid score')
            if 'rank' in group and (type(group['rank']) is not int or group['rank'] != index + 1):
                raise ValueError('Invalid rank')
            labels.append(label); scores.append(score)
        if any(scores[i] < scores[i+1] for i in range(len(scores)-1)):
            raise ValueError('Groups are not ranked')
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise IntentClassificationContractError('INVALID_CLASSIFICATION') from exc
    snapshot = dict(ranking_policy=policy, score_type=score_type,
                    groups=[dict(rank=i + 1, intent_label=label, score=score)
                            for i, (label, score) in enumerate(zip(labels, scores))])
    return snapshot, labels, scores


def _validated_resolution(resolution, question):
    policy, score_type = _metadata(resolution, question)
    if policy not in RESOLUTION_POLICIES or score_type != EVIDENCE_SCORE_TYPE:
        raise IntentClassificationContractError('UNSUPPORTED_SCORE_CONTRACT')
    if 'confidence' not in resolution or resolution['confidence'] is not None:
        raise IntentClassificationContractError('INVALID_RESOLUTION_CONFIDENCE')
    label = _canonical_label(resolution.get('intent_label'))
    reason = resolution.get('reason')
    if not isinstance(reason, str) or not reason.strip():
        raise IntentClassificationContractError('INVALID_RESOLUTION_REASON')
    components = resolution.get('component_labels', [])
    if not isinstance(components, list):
        raise IntentClassificationContractError('INVALID_QUERY_COMPONENTS')
    components = [_canonical_label(value) for value in components]
    if 'MIXED' in components or len(set(components)) != len(components):
        raise IntentClassificationContractError('INVALID_QUERY_COMPONENTS')
    snapshot = dict(ranking_policy=policy, score_type=score_type, intent_label=label,
                    confidence=None, reason=reason, component_labels=components)
    if policy == 'intent-request-objectives-v5':
        if 'runtime_enabled' in resolution:
            if resolution['runtime_enabled'] is not False:
                raise IntentClassificationContractError('INVALID_RESOLUTION_RUNTIME')
            snapshot['runtime_enabled'] = False
        if 'unresolved_requests' in resolution:
            unresolved = resolution['unresolved_requests']
            if (not isinstance(unresolved, list)
                    or any(not isinstance(text, str) or not text.strip() for text in unresolved)):
                raise IntentClassificationContractError('INVALID_RESOLUTION_EVIDENCE')
            snapshot['unresolved_requests'] = list(unresolved)
        if 'explicit_evidence' in resolution:
            explicit = resolution['explicit_evidence']
            if not isinstance(explicit, list):
                raise IntentClassificationContractError('INVALID_RESOLUTION_EVIDENCE')
            snapshot['explicit_evidence'] = []
            for item in explicit:
                if (not isinstance(item, dict) or not isinstance(item.get('text'), str)
                        or not item['text'].strip()):
                    raise IntentClassificationContractError('INVALID_RESOLUTION_EVIDENCE')
                snapshot['explicit_evidence'].append(
                    dict(text=item['text'], intent_label=_canonical_label(item.get('intent_label'))))
    return snapshot


def _evidence_fallback(scope, question, base=None, resolution=None):
    groups = base['groups'] if base else []
    disagreement = bool(groups and resolution and groups[0]['intent_label'] != resolution['intent_label'])
    result = _fallback_result('LABEL_DISAGREEMENT' if disagreement else 'UNCALIBRATED_CLASSIFICATION',
                              scope, question,
                              labels=[group['intent_label'] for group in groups],
                              scores=[group['score'] for group in groups],
                              score_type=base['score_type'] if base else EVIDENCE_SCORE_TYPE)
    base_evidence = deepcopy(base)
    if base_evidence is not None:
        base_evidence['groups'] = base_evidence['groups'][:FALLBACK_TOP_GROUPS]
    evidence = dict(base_ranking=base_evidence, resolution=deepcopy(resolution),
                    label_disagreement=disagreement)
    result['classification_evidence'] = evidence
    result['fallback_payload']['classification_evidence'] = deepcopy(evidence)
    return result


def _mixed_route(components, confirmed):
    if confirmed is not True:
        return None
    if not isinstance(components, (list, tuple)):
        raise IntentClassificationContractError('INVALID_QUERY_COMPONENTS')
    labels = [_canonical_label(value) for value in components]
    if len(labels) < 2 or len(labels) != len(set(labels)) or 'MIXED' in labels:
        raise IntentClassificationContractError('INVALID_QUERY_COMPONENTS')
    routes = {INTENT_ROUTES[label] for label in labels}
    return 'BOTH' if 'BOTH' in routes or len(routes) > 1 else routes.pop()


def _confidence_and_route(ranking, scope, question, components=None, components_confirmed=False,
                          allow_direct_search=False):
    if isinstance(ranking, dict) and ('base_ranking' in ranking or 'resolution' in ranking):
        if (not {'base_ranking', 'resolution'} <= ranking.keys()
                or {'groups', 'intent_label', 'ranking_policy', 'score_type'} & ranking.keys()
                or ('question' in ranking and question and ranking['question'] != question)):
            raise IntentClassificationContractError('INVALID_CLASSIFICATION_ENVELOPE')
        base, _, _ = _validated_ranking(ranking['base_ranking'], question)
        resolved = _validated_resolution(ranking['resolution'], question)
        return _evidence_fallback(scope, question, base, resolved)
    if isinstance(ranking, dict) and ranking.get('score_type') == EVIDENCE_SCORE_TYPE:
        return _evidence_fallback(scope, question, resolution=_validated_resolution(ranking, question))
    base, labels, scores = _validated_ranking(ranking, question)
    if base['score_type'] == CLASSIFIER_SCORE_TYPE:
        return _evidence_fallback(scope, question, base)
    first, second = scores[:2]
    # Compare decimal representations without rounding scores, including equality at 0.08.
    gap = Decimal(str(first)) - Decimal(str(second))
    if not allow_direct_search:
        return _fallback_result('DIRECT_SEARCH_DISABLED', scope, question, labels=labels, scores=scores,
                                first=first, second=second, gap=float(gap))
    low = Decimal(str(first)) < Decimal(str(CONFIDENCE_THRESHOLD))
    close = gap < Decimal(str(GAP_THRESHOLD))
    if low or close:
        reason = 'LOW_CONFIDENCE_AND_SMALL_GAP' if low and close else 'LOW_CONFIDENCE' if low else 'SMALL_GAP'
        return _fallback_result(reason, scope, question, labels=labels, scores=scores,
                                first=first, second=second, gap=float(gap))
    route = INTENT_ROUTES[labels[0]]
    if labels[0] == 'MIXED':
        route = _mixed_route(components, components_confirmed)
        if route is None:
            return _fallback_result('MIXED_COMPONENTS_REQUIRED', scope, question,
                                    labels=labels, scores=scores, first=first, second=second, gap=float(gap))
    return _result('SEARCH', 3, 'CONFIDENT_INTENT', scope, route=route,
                   label=labels[0], first=first, second=second, gap=float(gap))


def decide_intent_route(ranking, *, query_components=None, query_components_confirmed=False,
                        allow_direct_search=False, **scope_input):
    """Pure gate function over an existing IntentMatcher result (or two-group fixture).

    company_ticker/context tickers must come from the upstream verified company
    resolver. Optional valid_tickers enforces an injected registry, without DB I/O.
    """
    scope, stopped = _scope_gate(**scope_input)
    if stopped is not None:
        return stopped
    if type(allow_direct_search) is not bool:
        raise IntentClassificationContractError('INVALID_ROUTING_CONFIGURATION')
    return _confidence_and_route(ranking, scope, scope_input.get('question', ''),
                                 query_components, query_components_confirmed, allow_direct_search)


class IntentRoutingPolicy:
    """Fallback-only by default; direct cosine routing is an offline diagnostic opt-in."""
    def __init__(self, matcher, *, allow_direct_search=False):
        if type(allow_direct_search) is not bool:
            raise IntentClassificationContractError('INVALID_ROUTING_CONFIGURATION')
        self.matcher = matcher
        self._allow_direct_search = allow_direct_search

    def decide(self, question, *, query_components=None, query_components_confirmed=False, **scope_input):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            return _result('ASK_CLARIFICATION', 1, 'INVALID_QUESTION', {})
        if 'allow_direct_search' in scope_input:
            raise IntentClassificationContractError('INVALID_ROUTING_CONFIGURATION')
        scope, stopped = _scope_gate(question=question, **scope_input)
        if stopped is not None:
            return stopped
        try:
            ranking = self.matcher.match(question, top_groups=FALLBACK_TOP_GROUPS, top_examples=5)
        except IntentClassificationContractError:
            raise
        except Exception:
            return _fallback_result('CLASSIFICATION_ERROR', scope, question)
        return _confidence_and_route(ranking, scope, question, query_components, query_components_confirmed,
                                     self._allow_direct_search)
