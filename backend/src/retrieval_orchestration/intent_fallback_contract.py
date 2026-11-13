"""S5-WBS07.1: strict provider JSON over the existing 04.2 decision.

No embedding, provider call, retry, timer or Web Chat registration happens here.
Internal producer contract errors remain distinct from failed provider replies.
"""
from copy import deepcopy
from datetime import date
import json
import math
import re
import unicodedata

from jsonschema import Draft202012Validator

from .intent_routing import (
    CLASSIFIER_SCORE_TYPE, COSINE_SCORE_TYPE, EVIDENCE_SCORE_TYPE,
    FALLBACK_TASK, FALLBACK_TOP_GROUPS, INTENT_ROUTES, LABEL_ALIASES, IntentClassificationContractError,
    _mixed_route, _scope_gate, _ticker, _validated_resolution,
)

ALLOWED_LABELS = ('SO_LIEU', 'BCTC_BCTN', 'NEWS', 'CHUC_VU', 'QUAN_HE',
                  'XU_HUONG', 'KET_HOP', 'CLARIFY')
ALLOWED_ROUTES = ('VECTOR', 'GRAPH', 'BOTH', 'ASK_CLARIFICATION')
PROVIDER_CONFIDENCE_THRESHOLD = .60
FALLBACK_REASONS = frozenset({
    'DIRECT_SEARCH_DISABLED', 'LOW_CONFIDENCE', 'SMALL_GAP', 'LOW_CONFIDENCE_AND_SMALL_GAP',
    'CLASSIFICATION_ERROR', 'UNCALIBRATED_CLASSIFICATION', 'LABEL_DISAGREEMENT',
    'MIXED_COMPONENTS_REQUIRED',
})
CLARIFICATION = 'Bạn có thể nêu rõ doanh nghiệp, kỳ và thông tin cần tra cứu không?'

REQUEST_JSON_SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object', 'additionalProperties': False,
    'required': ['question', 'conversation_scope', 'allowed_labels'],
    'properties': {
        'question': {'type': 'string', 'minLength': 1, 'maxLength': 4000, 'pattern': r'\S'},
        'conversation_scope': {
            'type': 'object', 'additionalProperties': False,
            'required': ['company_ticker', 'period'],
            'properties': {
                'company_ticker': {'type': ['string', 'null'], 'minLength': 1},
                'period': {'type': ['string', 'null'], 'minLength': 1},
            },
        },
        'allowed_labels': {'const': list(ALLOWED_LABELS)},
    },
}
RESPONSE_JSON_SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object', 'additionalProperties': False,
    'required': ['intent_label', 'route', 'confidence', 'reason'],
    'properties': {
        'intent_label': {'type': 'string', 'enum': list(ALLOWED_LABELS)},
        'route': {'type': 'string', 'enum': list(ALLOWED_ROUTES)},
        'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'reason': {'type': 'string', 'minLength': 1, 'pattern': r'\S'},
        'extracted_company': {'type': ['string', 'null'], 'minLength': 1},
        'extracted_period': {'type': ['string', 'null'], 'minLength': 1},
    },
}
_REQUEST_VALIDATOR = Draft202012Validator(REQUEST_JSON_SCHEMA)
_RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_JSON_SCHEMA)


def _valid_score(value, lower=0):
    # Check the JSON numeric type before any comparison (SDK dicts may be malformed).
    return type(value) in (int, float) and lower <= value <= 1 and math.isfinite(value)


def _validation_context(policy_result, payload, question):
    """Keep verified V7 rule components local; never forward them to the provider."""
    context = {'query_components': None, 'query_components_confirmed': False}
    evidence = policy_result.get('classification_evidence')
    if evidence is None and payload.get('classification_evidence') is None:
        return context
    if (not isinstance(evidence, dict) or payload.get('classification_evidence') != evidence
            or policy_result['reason_code'] not in {'UNCALIBRATED_CLASSIFICATION', 'LABEL_DISAGREEMENT'}):
        raise IntentClassificationContractError('INVALID_FALLBACK_HANDOFF')
    resolution = evidence.get('resolution')
    if resolution is None:
        return context
    resolved = _validated_resolution(resolution, question)
    if (resolved['ranking_policy'] != 'intent-request-objectives-v5'
            or resolved['intent_label'] != 'MIXED'
            or resolved['reason'] != 'TWO_EXPLICIT_REQUEST_TYPES'
            or resolved.get('runtime_enabled') is not False
            or resolved.get('unresolved_requests') != []):
        return context
    components = resolved['component_labels']
    _mixed_route(components, True)  # Check distinct, canonical component labels.
    explicit = resolved.get('explicit_evidence', [])
    if {item['intent_label'] for item in explicit} != set(components):
        return context
    # 04.2 snapshots have no mandatory question ID. Bind the producer's request
    # texts to this turn, including any newly added clause, before trusting them.
    from .intent_semantic_requests import requests
    def normalized(text):
        return ' '.join(unicodedata.normalize('NFC', text).casefold().split())
    if ([normalized(item['text']) for item in explicit]
            != [normalized(text) for text in requests(question)]):
        raise IntentClassificationContractError('STALE_CLASSIFICATION_EVIDENCE')
    return {'query_components': list(components), 'query_components_confirmed': True}


def _canonical_period(value):
    """Normalize notation only, without merging day/quarter/year or resolving time."""
    if value is None:
        return None
    value = value.strip()
    quarter = re.fullmatch(r'(?:q|qu[yý])\s*([1-4])\s*(?:[/\-]|n[aă]m)\s*([0-9]{4})',
                           value, re.IGNORECASE)
    if quarter:
        return f'{quarter[2]}-Q{quarter[1]}'
    quarter = re.fullmatch(r'([0-9]{4})\s*[-/]\s*q\s*([1-4])', value, re.IGNORECASE)
    if quarter:
        return f'{quarter[1]}-Q{quarter[2]}'
    day = re.fullmatch(r'([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})', value)
    if day:
        try:
            return date(int(day[3]), int(day[2]), int(day[1])).isoformat()
        except ValueError:
            pass  # Existing scope gate still rejects invalid dates.
    return value


def prepare_fallback_request(policy_result, *, question, company_required=True, valid_tickers=None):
    """Allow only an existing 04.2 NEED_FALLBACK; emit exactly three wire fields.

    policy_result is an internal result of 04.2, never a request supplied by an
    LLM/client. Malformed or stale handoffs raise before an external call.
    """
    def reject():
        raise IntentClassificationContractError('INVALID_FALLBACK_HANDOFF')

    if not isinstance(policy_result, dict) or type(company_required) is not bool:
        reject()
    decision = policy_result.get('decision')
    needed = policy_result.get('need_fallback')
    gate = policy_result.get('gate')
    reason = policy_result.get('reason_code')
    if (not isinstance(decision, str) or type(needed) is not bool or type(gate) is not int
            or not isinstance(reason, str) or not reason):
        reject()
    prepared = dict(decision=decision, need_fallback=needed, route=policy_result.get('route'),
                    reason_code=reason, request=None,
                    validation_context={'query_components': None, 'query_components_confirmed': False},
                    clarification_question=policy_result.get('clarification_question'))
    if decision == 'ASK_CLARIFICATION':
        message = prepared['clarification_question']
        if (needed or gate != 1 or prepared['route'] is not None
                or not isinstance(message, str) or not message.strip()):
            reject()
        return prepared
    scope = policy_result.get('scope')
    if (not isinstance(scope, dict)
            or not {'company_ticker', 'period', 'company_source'} <= scope.keys()):
        reject()
    source = scope['company_source']
    if scope['company_ticker'] is None:
        if source is not None:
            reject()
    elif not isinstance(source, str) or source not in {'CURRENT', 'CONTEXT'}:
        reject()
    resolved, stopped = _scope_gate(question=question, company_ticker=scope['company_ticker'],
                                     period=scope['period'], company_required=company_required,
                                     valid_tickers=valid_tickers)
    wire = {'question': question,
            'conversation_scope': {key: resolved[key] for key in ('company_ticker', 'period')},
            'allowed_labels': list(ALLOWED_LABELS)}
    if stopped is not None or not _REQUEST_VALIDATOR.is_valid(wire):
        reject()
    if decision == 'SEARCH':
        label = policy_result.get('intent_label')
        if (needed or gate != 3 or reason != 'CONFIDENT_INTENT'
                or prepared['route'] not in ('VECTOR', 'GRAPH', 'BOTH')
                or not isinstance(label, str) or label not in INTENT_ROUTES
                or (label != 'MIXED' and prepared['route'] != INTENT_ROUTES[label])):
            reject()
        return prepared
    if (decision != 'NEED_FALLBACK' or not needed or gate != 2 or reason not in FALLBACK_REASONS
            or prepared['route'] is not None or policy_result.get('fallback_task') != FALLBACK_TASK):
        reject()
    payload = policy_result.get('fallback_payload')
    if (not isinstance(payload, dict) or payload.get('question') != question
            or payload.get('scope') != scope or payload.get('reason_code') != reason):
        reject()
    kind, candidates = payload.get('score_type'), payload.get('candidates')
    if (not isinstance(kind, str) or kind not in {COSINE_SCORE_TYPE, CLASSIFIER_SCORE_TYPE, EVIDENCE_SCORE_TYPE}
            or payload.get('allowed_labels') != list(INTENT_ROUTES)
            or not isinstance(candidates, list) or len(candidates) > FALLBACK_TOP_GROUPS):
        reject()
    if kind == EVIDENCE_SCORE_TYPE and candidates:
        reject()
    if kind != EVIDENCE_SCORE_TYPE and reason != 'CLASSIFICATION_ERROR' and len(candidates) < 2:
        reject()
    seen, previous = set(), None
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            reject()
        label, score = candidate.get('intent_label'), candidate.get('score')
        if (not isinstance(label, str) or label not in INTENT_ROUTES or label in seen
                or type(candidate.get('rank')) is not int or candidate['rank'] != index + 1
                or not _valid_score(score, -1 if kind == COSINE_SCORE_TYPE else 0)
                or (previous is not None and score > previous)):
            reject()
        seen.add(label)
        previous = score
    prepared['validation_context'] = _validation_context(policy_result, payload, question)
    prepared['request'] = wire
    return prepared


def _failure(reason):
    return dict(status='FALLBACK_FAILED', reason_code=reason, intent_label='CLARIFY',
                canonical_intent=None, route='ASK_CLARIFICATION', confidence=None,
                confidence_type=None, extracted_company=None, extracted_period=None,
                reason='Chưa xác định được yêu cầu tra cứu an toàn.', clarification_question=CLARIFICATION)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON number')


def validate_fallback_response(raw, *, request, timed_out=False, provider_error=None,
                               company_required=True, valid_tickers=None,
                               query_components=None, query_components_confirmed=False):
    """Validate a provider reply without promoting its self-reported score.

    query_components can come from prepare_fallback_request's local validation
    context or another verified resolver. A provider reason or a sample's
    components cannot establish them. Timeout is a signal
    from the provider runner in 07.2; this function does not measure a deadline.
    """
    if timed_out is True or isinstance(provider_error, TimeoutError):
        return _failure('PROVIDER_TIMEOUT')
    if provider_error is not None:
        return _failure('PROVIDER_ERROR')
    if (type(timed_out) is not bool or type(company_required) is not bool
            or not isinstance(request, dict) or not _REQUEST_VALIDATOR.is_valid(request)):
        return _failure('INVALID_REQUEST')
    try:
        if isinstance(raw, str):
            data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        elif isinstance(raw, dict):
            data = deepcopy(raw)
        else:
            return _failure('INVALID_JSON')
    except (ValueError, TypeError, RecursionError):
        return _failure('INVALID_JSON')
    if isinstance(data, dict) and 'confidence' in data and not _valid_score(data['confidence']):
        return _failure('INVALID_CONFIDENCE')
    if not _RESPONSE_VALIDATOR.is_valid(data):
        return _failure('INVALID_RESPONSE')
    score = data['confidence']
    if score < PROVIDER_CONFIDENCE_THRESHOLD:
        return _failure('LOW_PROVIDER_CONFIDENCE')
    label, route = data['intent_label'], data['route']
    canonical = None if label == 'CLARIFY' else LABEL_ALIASES.get(label, label)
    if label == 'CLARIFY':
        if route != 'ASK_CLARIFICATION':
            return _failure('LABEL_ROUTE_MISMATCH')
    elif route != 'ASK_CLARIFICATION':
        expected = INTENT_ROUTES[canonical]
        if canonical == 'MIXED':
            try:
                expected = _mixed_route(query_components, query_components_confirmed)
            except IntentClassificationContractError:
                return _failure('INVALID_QUERY_COMPONENTS')
            if expected is None:
                return _failure('UNVERIFIED_MIXED_COMPONENTS')
        if route != expected:
            return _failure('LABEL_ROUTE_MISMATCH')
    scope = request['conversation_scope']
    company = scope['company_ticker']
    period = _canonical_period(scope['period'])
    extracted_company = data.get('extracted_company')
    extracted_period = data.get('extracted_period')
    if route != 'ASK_CLARIFICATION' and company_required and company is None:
        return _failure('MISSING_VERIFIED_COMPANY')
    if extracted_company is not None:
        if company is None:
            return _failure('UNVERIFIED_COMPANY')
        ticker = _ticker(extracted_company)
        if ticker is None:
            return _failure('INVALID_SCOPE')
        if company is not None and ticker != _ticker(company):
            return _failure('COMPANY_SCOPE_CONFLICT')
        company = ticker
    if extracted_period is not None:
        if period is None:
            return _failure('UNVERIFIED_PERIOD')
        if _canonical_period(extracted_period) != period:
            return _failure('PERIOD_SCOPE_CONFLICT')
    resolved, stopped = _scope_gate(question=request['question'], company_ticker=company, period=period,
                                     company_required=company_required and route != 'ASK_CLARIFICATION',
                                     valid_tickers=valid_tickers)
    if stopped is not None:
        return _failure(stopped['reason_code'])
    return dict(status='FALLBACK_VALIDATED', reason_code='VALID_RESPONSE', intent_label=label,
                canonical_intent=canonical, route=route, confidence=float(score),
                confidence_type='PROVIDER_SELF_REPORTED_UNCALIBRATED',
                extracted_company=resolved['company_ticker'], extracted_period=resolved['period'],
                reason=data['reason'].strip(),
                clarification_question=CLARIFICATION if route == 'ASK_CLARIFICATION' else None)
