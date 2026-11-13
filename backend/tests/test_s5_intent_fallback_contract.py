"""07.1 contract checks against the real 04.2 policy; no external provider."""
import copy
from decimal import Decimal
import json

import pytest
from jsonschema import Draft202012Validator

from src.retrieval_orchestration.intent_fallback_contract import (
    REQUEST_JSON_SCHEMA, RESPONSE_JSON_SCHEMA,
    prepare_fallback_request, validate_fallback_response,
)
from src.retrieval_orchestration.intent_routing import (
    IntentClassificationContractError, IntentRoutingPolicy, decide_intent_route,
)


LABELS = ['SO_LIEU', 'BCTC_BCTN', 'NEWS', 'CHUC_VU', 'QUAN_HE',
          'XU_HUONG', 'KET_HOP', 'CLARIFY']
QUESTION = 'Ai là Chủ tịch HĐQT FPT năm 2025?'
MIXED_QUESTION = ('Theo báo cáo thường niên FPT năm 2025, ai đảm nhiệm chức Chủ tịch HĐQT? '
                  'Báo cáo giải thích chính sách kiểm soát rủi ro ra sao?')


def ranking(first=.99, second=.01, label='PERSON_ROLE'):
    return {'ranking_policy': 'cosine-max-per-label-v1',
            'score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY',
            'groups': [{'intent_label': label, 'score': first},
                       {'intent_label': 'NEWS', 'score': second}]}


def policy_result(**kwargs):
    return decide_intent_route(ranking(), question=QUESTION, company_ticker='FPT', period='2025', **kwargs)


def v7_policy_result(question=MIXED_QUESTION, envelope=False):
    from src.retrieval_orchestration.intent_semantic_requests import requests, resolve_objectives
    labels = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']
    resolved = resolve_objectives([.1, .1, .1, .4, .1, .1, .1], [], labels, requests(question))
    assert resolved['reason'] == 'TWO_EXPLICIT_REQUEST_TYPES'
    if envelope:
        base = ranking(.71, .20, 'NUMERIC') | {
            'ranking_policy': 'intent-linear-v1', 'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED'}
        resolved = {'base_ranking': base, 'resolution': resolved}
    return decide_intent_route(resolved, question=question, company_ticker='FPT', period='2025')


def request():
    # Literal wire fixture, independent of the request builder under test.
    return {'question': QUESTION, 'conversation_scope': {'company_ticker': 'FPT', 'period': '2025'},
            'allowed_labels': LABELS.copy()}


def response(**changes):
    return {'intent_label': 'CHUC_VU', 'route': 'GRAPH', 'confidence': .85,
            'extracted_company': 'FPT', 'extracted_period': '2025',
            'reason': 'Tra cứu người giữ chức Chủ tịch HĐQT.'} | changes


def assert_failed(out):
    assert out['status'] == 'FALLBACK_FAILED'
    assert out['route'] == 'ASK_CLARIFICATION' and out['intent_label'] == 'CLARIFY'
    assert out['canonical_intent'] is None and out['confidence'] is None
    assert out['clarification_question']


def test_default_high_cosine_still_prepares_fallback_from_actual_042():
    raw = policy_result()
    out = prepare_fallback_request(raw, question=QUESTION)
    assert raw['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert out['need_fallback'] is True and out['decision'] == 'NEED_FALLBACK'
    assert out['request'] == request()
    Draft202012Validator(REQUEST_JSON_SCHEMA).validate(out['request'])


@pytest.mark.parametrize('first,second,reason', [
    (.60, .20, 'LOW_CONFIDENCE'),
    (.90, .85, 'SMALL_GAP'),
    (.60, .59, 'LOW_CONFIDENCE_AND_SMALL_GAP'),
])
def test_diagnostic_fallback_reasons_are_preserved(first, second, reason):
    raw = decide_intent_route(ranking(first, second), question=QUESTION,
                              company_ticker='FPT', allow_direct_search=True)
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['need_fallback'] is True and out['reason_code'] == reason


@pytest.mark.parametrize('label,components', [
    ('PERSON_ROLE', {}),
    ('MIXED', {'query_components': ['PERSON_ROLE', 'REPORT_CONTENT'], 'query_components_confirmed': True}),
])
def test_only_actual_diagnostic_search_skips_fallback(label, components):
    raw = decide_intent_route(ranking(label=label), question=QUESTION, company_ticker='FPT',
                              allow_direct_search=True, **components)
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['decision'] == 'SEARCH' and out['need_fallback'] is False
    assert out['route'] == ('GRAPH' if label == 'PERSON_ROLE' else 'BOTH')
    assert out['request'] is None


@pytest.mark.parametrize('change', [
    {'route': 'VECTOR'}, {'intent_label': 'UNKNOWN'},
    {'reason_code': 'LOW_CONFIDENCE'}, {'scope': None},
    {'scope': {'company_ticker': 'FPT', 'period': '2025'}},
    {'scope': {'company_ticker': 'FPT', 'period': '2025-Q5', 'company_source': 'CURRENT'}},
])
def test_diagnostic_search_handoff_is_checked_even_without_an_external_request(change):
    raw = decide_intent_route(ranking(), question=QUESTION, company_ticker='FPT',
                              period='2025', allow_direct_search=True)
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw | change, question=QUESTION)


@pytest.mark.parametrize('message', [True, 1, [], '   '])
def test_internal_ask_requires_a_real_clarification_message(message):
    raw = decide_intent_route(None, question='Who chairs the company?')
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw | {'clarification_question': message}, question='Who chairs the company?')


def test_verified_both_does_not_bypass_default_fallback_only_mode():
    raw = decide_intent_route(ranking(label='MIXED'), question=QUESTION, company_ticker='FPT',
                              query_components=['PERSON_ROLE', 'REPORT_CONTENT'], query_components_confirmed=True)
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['need_fallback'] is True and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'


@pytest.mark.parametrize('question,ticker', [
    ('Ai là Chủ tịch HĐQT?', None),
    ('Doanh thu FPT quý 5/2025?', 'FPT'),
    ('Doanh thu FPT quý 1.5/2025?', 'FPT'),
])
def test_scope_gate_clarification_never_creates_external_request(question, ticker):
    raw = decide_intent_route(None, question=question, company_ticker=ticker)
    out = prepare_fallback_request(raw, question=question)
    assert out['decision'] == 'ASK_CLARIFICATION' and out['need_fallback'] is False
    assert out['request'] is None and out['clarification_question']


@pytest.mark.parametrize('error', [TimeoutError('internal timeout'), RuntimeError('encoder failed')])
def test_real_policy_matcher_error_is_an_allowed_fallback(error):
    class BrokenMatcher:
        def match(self, question, **kwargs):
            raise error
    raw = IntentRoutingPolicy(BrokenMatcher()).decide(QUESTION, company_ticker='FPT')
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['need_fallback'] is True and out['reason_code'] == 'CLASSIFICATION_ERROR'


def test_empty_matcher_contract_error_is_not_reinterpreted_as_external_fallback():
    class EmptyMatcher:
        def match(self, question, **kwargs):
            return None
    with pytest.raises(IntentClassificationContractError):
        raw = IntentRoutingPolicy(EmptyMatcher()).decide(QUESTION, company_ticker='FPT')
        prepare_fallback_request(raw, question=QUESTION)


def test_real_v7_producer_and_042_consumer_handoff_remains_supported():
    from src.retrieval_orchestration.intent_semantic_requests import requests, resolve_objectives
    labels = ['NUMERIC', 'PERSON_ROLE', 'NEWS', 'REPORT_CONTENT', 'ENTITY_RELATION', 'TREND', 'MIXED']
    resolved = resolve_objectives([.71, .20, .03, .02, .02, .01, .01], [], labels, requests(QUESTION))
    base = ranking(.71, .20, 'NUMERIC') | {
        'ranking_policy': 'intent-linear-v1', 'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED'}
    raw = decide_intent_route({'base_ranking': base, 'resolution': resolved},
                              question=QUESTION, company_ticker='FPT')
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['need_fallback'] is True and out['reason_code'] == 'LABEL_DISAGREEMENT'
    assert set(out['request']) == {'question', 'conversation_scope', 'allowed_labels'}


@pytest.mark.parametrize('envelope', [False, True])
@pytest.mark.parametrize('question,route,components', [
    (MIXED_QUESTION, 'BOTH', {'PERSON_ROLE', 'REPORT_CONTENT'}),
    ('Cho biết doanh thu FPT năm 2025 rồi tìm bài tin về FPT.', 'VECTOR', {'NUMERIC', 'NEWS'}),
    ('Ai là Chủ tịch FPT? FPT có những công ty con nào?', 'GRAPH', {'PERSON_ROLE', 'ENTITY_RELATION'}),
])
def test_explicit_v7_components_reach_validator_without_manual_confirmation(question, route, components, envelope):
    raw = v7_policy_result(question, envelope)
    before = copy.deepcopy(raw)
    prepared = prepare_fallback_request(raw, question=question)
    out = validate_fallback_response(response(intent_label='KET_HOP', route=route),
                                     request=prepared['request'], **prepared.get('validation_context', {}))
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == route
    assert prepared['need_fallback'] is True  # Evidence does not enable direct SEARCH.
    assert set(prepared['validation_context']['query_components']) == components
    assert prepared['validation_context']['query_components_confirmed'] is True
    assert set(prepared['request']) == {'question', 'conversation_scope', 'allowed_labels'}
    assert raw == before
    prepared['validation_context']['query_components'].clear()
    assert raw == before


@pytest.mark.parametrize('changes', [
    {'reason': 'TWO_REQUESTS_SUPPORTED_BY_WHOLE_QUESTION'},
    {'ranking_policy': 'intent-request-objectives-v4'},
    {'explicit_evidence': []}, {'unresolved_requests': ['Unresolved third request']},
])
def test_incomplete_or_non_explicit_v7_evidence_does_not_confirm_mixed(changes):
    raw = v7_policy_result()
    raw['classification_evidence']['resolution'].update(changes)
    raw['fallback_payload']['classification_evidence'] = copy.deepcopy(raw['classification_evidence'])
    prepared = prepare_fallback_request(raw, question=MIXED_QUESTION)
    out = validate_fallback_response(response(intent_label='KET_HOP', route='BOTH'),
                                     request=prepared['request'], **prepared.get('validation_context', {}))
    assert_failed(out)
    assert out['reason_code'] == 'UNVERIFIED_MIXED_COMPONENTS'


@pytest.mark.parametrize('changes', [
    {'confidence': .9}, {'score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY'},
    {'component_labels': ['PERSON_ROLE', 'UNKNOWN']},
    {'component_labels': ['PERSON_ROLE', 'PERSON_ROLE']},
])
def test_malformed_resolution_cannot_supply_verified_query_components(changes):
    raw = v7_policy_result()
    raw['classification_evidence']['resolution'].update(changes)
    raw['fallback_payload']['classification_evidence'] = copy.deepcopy(raw['classification_evidence'])
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=MIXED_QUESTION)


def test_disagreeing_internal_evidence_copies_are_rejected_before_provider_call():
    raw = v7_policy_result()
    raw['fallback_payload']['classification_evidence']['resolution']['component_labels'] = ['NUMERIC', 'NEWS']
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=MIXED_QUESTION)


@pytest.mark.parametrize('old_question,new_question', [
    ('Ai là Chủ tịch FPT? FPT có những công ty con nào?', MIXED_QUESTION),
    (MIXED_QUESTION, MIXED_QUESTION + ' Cho biết doanh thu FPT năm 2025.'),
])
def test_old_v7_resolution_cannot_confirm_components_for_another_question(old_question, new_question):
    old = v7_policy_result(old_question)['classification_evidence']['resolution']
    raw = decide_intent_route(old, question=new_question, company_ticker='FPT', period='2025')
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=new_question)


def test_candidate_or_sample_components_do_not_become_verified_query_components():
    raw = policy_result()
    raw['fallback_payload']['component_labels'] = ['PERSON_ROLE', 'NEWS']
    raw['fallback_payload']['candidates'][0]['component_labels'] = ['PERSON_ROLE', 'NEWS']
    prepared = prepare_fallback_request(raw, question=QUESTION)
    out = validate_fallback_response(response(intent_label='KET_HOP', route='BOTH'),
                                     request=prepared['request'], **prepared.get('validation_context', {}))
    assert_failed(out)


@pytest.mark.parametrize('change', [
    {'need_fallback': False}, {'need_fallback': 1}, {'gate': 3},
    {'reason_code': 'UNKNOWN'}, {'fallback_task': 'OTHER_TASK'},
    {'route': 'GRAPH'}, {'decision': 'UNKNOWN'}, {'fallback_payload': None},
])
def test_malformed_handoff_never_authorizes_an_external_call(change):
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(policy_result() | change, question=QUESTION)


def test_stale_question_and_mismatched_scope_are_rejected_before_external_call():
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(policy_result(), question='Một câu hỏi khác về FPT')
    raw = policy_result()
    raw['fallback_payload']['scope']['company_ticker'] = 'VCB'
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=QUESTION)


@pytest.mark.parametrize('field', ['company_ticker', 'period', 'company_source'])
def test_missing_internal_scope_field_is_not_silently_replaced_with_null(field):
    raw = policy_result()
    del raw['scope'][field], raw['fallback_payload']['scope'][field]
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=QUESTION, company_required=False)


@pytest.mark.parametrize('source', [None, 'UNCONFIRMED', 1, [], {}])
def test_unverified_company_source_cannot_authorize_external_request(source):
    raw = policy_result()
    raw['scope']['company_source'] = source
    raw['fallback_payload']['scope']['company_source'] = copy.deepcopy(source)
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=QUESTION)


@pytest.mark.parametrize('source', ['CURRENT', 'CONTEXT'])
def test_company_source_without_a_company_is_an_invalid_handoff(source):
    question = 'Tin tuc thi truong?'
    raw = decide_intent_route(ranking(), question=question, company_required=False)
    raw['scope']['company_source'] = source
    raw['fallback_payload']['scope']['company_source'] = source
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=question, company_required=False)


@pytest.mark.parametrize('field', ['score_type', 'candidates', 'allowed_labels'])
def test_missing_internal_score_metadata_is_rejected_before_external_call(field):
    raw = policy_result()
    del raw['fallback_payload'][field]
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=QUESTION)


@pytest.mark.parametrize('change', [
    {'score_type': None}, {'score_type': 'UNKNOWN'}, {'candidates': None},
    {'allowed_labels': ['CHUC_VU']},
    {'candidates': [{'rank': 1, 'intent_label': 'UNKNOWN', 'score': .9},
                    {'rank': 2, 'intent_label': 'NEWS', 'score': .1}]},
    {'candidates': [{'rank': 1, 'intent_label': 'PERSON_ROLE', 'score': True},
                    {'rank': 2, 'intent_label': 'NEWS', 'score': .1}]},
])
def test_invalid_internal_score_metadata_is_not_a_reason_to_call_external_ai(change):
    raw = policy_result()
    raw['fallback_payload'].update(change)
    with pytest.raises(IntentClassificationContractError):
        prepare_fallback_request(raw, question=QUESTION)


def test_internal_candidates_and_history_are_not_forwarded_or_mutated():
    raw = policy_result()
    raw['fallback_payload']['history'] = ['SECRET_HISTORY']
    raw['fallback_payload']['candidates'][0]['private'] = 'SECRET_CANDIDATE'
    saved = copy.deepcopy(raw)
    out = prepare_fallback_request(raw, question=QUESTION)
    assert out['request'] == request() and raw == saved
    assert 'SECRET' not in json.dumps(out['request'])
    out['request']['allowed_labels'].clear()
    assert prepare_fallback_request(raw, question=QUESTION)['request']['allowed_labels'] == LABELS


def test_confirmed_context_becomes_only_resolved_company_and_period():
    question = 'Còn quý 2?'
    raw = decide_intent_route(ranking(), question=question, period='2025-Q2',
                              context_company_ticker='FPT', context_same_session=True, context_confirmed=True)
    prepared = prepare_fallback_request(raw, question=question)
    assert prepared['request']['conversation_scope'] == {'company_ticker': 'FPT', 'period': '2025-Q2'}
    assert 'company_source' not in prepared['request']['conversation_scope']


@pytest.mark.parametrize('label,route,canonical', [
    ('SO_LIEU', 'VECTOR', 'NUMERIC'), ('BCTC_BCTN', 'VECTOR', 'REPORT_CONTENT'),
    ('NEWS', 'VECTOR', 'NEWS'), ('CHUC_VU', 'GRAPH', 'PERSON_ROLE'),
    ('QUAN_HE', 'GRAPH', 'ENTITY_RELATION'), ('XU_HUONG', 'BOTH', 'TREND'),
    ('CLARIFY', 'ASK_CLARIFICATION', None),
])
@pytest.mark.parametrize('as_text', [False, True])
def test_valid_wire_labels_normalize_to_nhan_ids(label, route, canonical, as_text):
    raw = response(intent_label=label, route=route)
    Draft202012Validator(RESPONSE_JSON_SCHEMA).validate(raw)
    out = validate_fallback_response(json.dumps(raw) if as_text else raw, request=request())
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == route
    assert out['canonical_intent'] == canonical and out['intent_label'] == label
    assert out['confidence'] == .85


@pytest.mark.parametrize('raw', [
    '', 'not json', 'null', '[]', '{}', '```json\n{}\n```',
    '{"intent_label":"CHUC_VU",}', '{"confidence":NaN}',
    '{"confidence":Infinity}', '{"route":"GRAPH","route":"VECTOR"}',
])
def test_invalid_or_non_object_json_fails_safely(raw):
    assert_failed(validate_fallback_response(raw, request=request()))


@pytest.mark.parametrize('field', ['intent_label', 'route', 'confidence', 'reason'])
def test_missing_required_field_fails_safely(field):
    raw = response()
    del raw[field]
    assert_failed(validate_fallback_response(raw, request=request()))


@pytest.mark.parametrize('change', [
    {'intent_label': 'PERSON_ROLE'}, {'intent_label': 'UNKNOWN'}, {'intent_label': []},
    {'route': 'SQL'}, {'route': []}, {'reason': ''}, {'reason': '   '}, {'reason': 42},
    {'confidence': True}, {'confidence': '0.9'}, {'confidence': None},
    {'confidence': float('nan')}, {'confidence': float('inf')},
    {'confidence': -.01}, {'confidence': 1.001}, {'extra': 'unexpected'},
    {'extracted_company': []}, {'extracted_period': 2025},
])
def test_invalid_response_types_values_and_extra_fields_fail_safely(change):
    assert_failed(validate_fallback_response(response(**change), request=request()))


@pytest.mark.parametrize('score', [1j, Decimal('NaN'), Decimal('.85'), 10**1000])
def test_non_json_sdk_numeric_types_do_not_escape_as_schema_arithmetic_errors(score):
    assert_failed(validate_fallback_response(response(confidence=score), request=request()))


@pytest.mark.parametrize('score,passed', [(.599999, False), (.60, True), (.600001, True), (1, True)])
def test_provider_confidence_boundary_is_distinct_from_cosine_threshold(score, passed):
    out = validate_fallback_response(response(confidence=score), request=request())
    if passed:
        assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == 'GRAPH'
    else:
        assert_failed(out)
        assert out['reason_code'] == 'LOW_PROVIDER_CONFIDENCE'


@pytest.mark.parametrize('options,reason', [
    ({'timed_out': True}, 'PROVIDER_TIMEOUT'),
    ({'provider_error': TimeoutError('timeout')}, 'PROVIDER_TIMEOUT'),
    ({'provider_error': RuntimeError('provider unavailable')}, 'PROVIDER_ERROR'),
])
def test_provider_timeout_or_error_fails_even_when_a_valid_json_is_available(options, reason):
    out = validate_fallback_response(response(), request=request(), **options)
    assert_failed(out)
    assert out['reason_code'] == reason


@pytest.mark.parametrize('label,route', [
    ('CHUC_VU', 'VECTOR'), ('SO_LIEU', 'GRAPH'), ('NEWS', 'BOTH'), ('CLARIFY', 'GRAPH'),
])
def test_label_route_mismatch_is_not_accepted(label, route):
    out = validate_fallback_response(response(intent_label=label, route=route), request=request())
    assert_failed(out)
    assert out['reason_code'] == 'LABEL_ROUTE_MISMATCH'


@pytest.mark.parametrize('components,route', [
    (['NUMERIC', 'NEWS'], 'VECTOR'), (['PERSON_ROLE', 'ENTITY_RELATION'], 'GRAPH'),
    (['PERSON_ROLE', 'REPORT_CONTENT'], 'BOTH'),
])
def test_mixed_route_uses_verified_components_not_an_unconditional_both(components, route):
    out = validate_fallback_response(response(intent_label='KET_HOP', route=route), request=request(),
                                     query_components=components, query_components_confirmed=True)
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == route
    assert out['canonical_intent'] == 'MIXED'


@pytest.mark.parametrize('components,confirmed,route', [
    (None, False, 'BOTH'), (['PERSON_ROLE', 'NEWS'], False, 'BOTH'),
    (['UNKNOWN', 'NEWS'], True, 'BOTH'), (['NUMERIC', 'NEWS'], True, 'BOTH'),
])
def test_missing_or_conflicting_mixed_components_fail_safely(components, confirmed, route):
    out = validate_fallback_response(response(intent_label='KET_HOP', route=route), request=request(),
                                     query_components=components, query_components_confirmed=confirmed)
    assert_failed(out)


@pytest.mark.parametrize('explicit_null', [False, True])
def test_four_required_fields_can_reuse_verified_scope_without_extracted_fields(explicit_null):
    raw = response()
    if explicit_null:
        raw.update(extracted_company=None, extracted_period=None)
    else:
        del raw['extracted_company'], raw['extracted_period']
    out = validate_fallback_response(raw, request=request())
    assert out['status'] == 'FALLBACK_VALIDATED'
    assert out['extracted_company'] == 'FPT' and out['extracted_period'] == '2025'


@pytest.mark.parametrize('change', [
    {'extracted_company': 'VCB'}, {'extracted_company': '???'},
    {'extracted_period': '2024'}, {'extracted_period': '2025-Q5'},
    {'extracted_period': '2025-02-30'},
])
def test_provider_cannot_silently_change_or_invent_invalid_scope(change):
    assert_failed(validate_fallback_response(response(**change), request=request()))


@pytest.mark.parametrize('period', ['Q3/2025', 'q3-2025', 'quý 3/2025', 'quý 3 năm 2025', '2025-q3'])
def test_equivalent_quarter_formats_match_verified_period(period):
    req = request() | {'question': 'Doanh thu FPT Q3-2025?'}
    req['conversation_scope']['period'] = '2025-Q3'
    out = validate_fallback_response(response(intent_label='SO_LIEU', route='VECTOR', extracted_period=period),
                                     request=req)
    assert out['status'] == 'FALLBACK_VALIDATED'
    assert out['extracted_period'] == '2025-Q3'
    assert req['conversation_scope']['period'] == '2025-Q3'


@pytest.mark.parametrize('period', ['04/11/2025', '4/11/2025'])
def test_equivalent_day_formats_preserve_full_verified_date(period):
    req = request() | {'question': 'Gia FPT ngay 04/11/2025?'}
    req['conversation_scope']['period'] = '2025-11-04'
    out = validate_fallback_response(response(intent_label='SO_LIEU', route='VECTOR', extracted_period=period),
                                     request=req)
    assert out['status'] == 'FALLBACK_VALIDATED'
    assert out['extracted_period'] == '2025-11-04'


@pytest.mark.parametrize('period', ['Q4/2025', 'Q3/2024', '2025', '2025-09-30', 'Q5/2025', 'Q3/0000'])
def test_period_normalization_never_merges_different_periods_or_precision(period):
    req = request() | {'question': 'Doanh thu FPT Q3-2025?'}
    req['conversation_scope']['period'] = '2025-Q3'
    assert_failed(validate_fallback_response(response(extracted_period=period), request=req))


def test_missing_verified_company_asks_even_if_provider_invents_a_ticker():
    req = request()
    req['conversation_scope']['company_ticker'] = None
    for extracted in [None, 'FPT']:
        assert_failed(validate_fallback_response(response(extracted_company=extracted), request=req))


@pytest.mark.parametrize('question', ['Who chairs FPT?', QUESTION])
@pytest.mark.parametrize('period', ['2024', '2025', 'LATEST_AVAILABLE_PERIOD'])
@pytest.mark.parametrize('label,route', [('CHUC_VU', 'GRAPH'), ('CLARIFY', 'ASK_CLARIFICATION')])
def test_provider_cannot_add_an_unverified_period_filter(question, period, label, route):
    req = request() | {'question': question}
    req['conversation_scope']['period'] = None
    out = validate_fallback_response(response(intent_label=label, route=route, extracted_period=period), request=req)
    assert_failed(out)
    assert out['reason_code'] == 'UNVERIFIED_PERIOD'


@pytest.mark.parametrize('route,label', [('VECTOR', 'NEWS'), ('ASK_CLARIFICATION', 'CLARIFY')])
def test_provider_cannot_add_a_company_to_a_market_wide_request(route, label):
    req = request() | {'question': 'Tin tuc thi truong?'}
    req['conversation_scope'] = {'company_ticker': None, 'period': None}
    out = validate_fallback_response(response(intent_label=label, route=route, extracted_period=None),
                                     request=req, company_required=False)
    assert_failed(out)
    assert out['reason_code'] == 'UNVERIFIED_COMPANY'


@pytest.mark.parametrize('include_null_fields', [False, True])
def test_verified_company_without_a_period_can_still_use_graph(include_null_fields):
    req = request() | {'question': 'Who chairs FPT?'}
    req['conversation_scope']['period'] = None
    raw = response(extracted_period=None)
    if not include_null_fields:
        del raw['extracted_company'], raw['extracted_period']
    out = validate_fallback_response(raw, request=req)
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == 'GRAPH'
    assert out['extracted_company'] == 'FPT' and out['extracted_period'] is None


def test_registry_and_company_optional_news_are_supported_without_database_calls():
    assert_failed(validate_fallback_response(response(), request=request(), valid_tickers={'VCB'}))
    question = 'Tóm tắt tin tức thị trường.'
    raw = decide_intent_route(ranking(), question=question, company_required=False)
    prepared = prepare_fallback_request(raw, question=question, company_required=False)
    assert prepared['request']['conversation_scope'] == {'company_ticker': None, 'period': None}
    result = response(intent_label='NEWS', route='VECTOR', extracted_company=None, extracted_period=None)
    out = validate_fallback_response(result, request=prepared['request'], company_required=False)
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == 'VECTOR'


@pytest.mark.parametrize('question', [
    'Doanh thu FPT Q3-2025', 'Doanh thu FPT quý 1 đến 30/6/2025',
    'Doanh thu FPT quý 1 đến 6/2025', 'Doanh thu FPT quý 1 - 06/2025',
])
def test_fallback_uses_existing_period_guard_without_losing_previous_fixes(question):
    raw = decide_intent_route(ranking(), question=question, company_ticker='FPT', period='2025')
    prepared = prepare_fallback_request(raw, question=question)
    out = validate_fallback_response(response(), request=prepared['request'])
    assert out['status'] == 'FALLBACK_VALIDATED'


@pytest.mark.parametrize('question', ['Doanh thu FPT quý 5/2025', 'Giá FPT ngày 31/2/2025'])
def test_bad_current_question_cannot_be_rescued_by_a_plausible_provider_scope(question):
    req = request() | {'question': question}
    assert_failed(validate_fallback_response(response(), request=req))


def test_clarification_does_not_require_a_company_and_never_becomes_search():
    req = request()
    req['conversation_scope']['company_ticker'] = None
    raw = response(intent_label='CLARIFY', route='ASK_CLARIFICATION', extracted_company=None)
    out = validate_fallback_response(raw, request=req)
    assert out['status'] == 'FALLBACK_VALIDATED' and out['route'] == 'ASK_CLARIFICATION'
    assert out['clarification_question'] and out['canonical_intent'] is None


@pytest.mark.parametrize('bad', [None, {}, {'question': QUESTION},
    request() | {'history': ['not allowed']}, request() | {'allowed_labels': ['PERSON_ROLE']}])
def test_response_to_an_invalid_request_is_always_clarification(bad):
    assert_failed(validate_fallback_response(response(), request=bad))


def test_validator_does_not_mutate_request_or_provider_output():
    req, raw = request(), response()
    before = copy.deepcopy((req, raw))
    out = validate_fallback_response(raw, request=req)
    assert out['status'] == 'FALLBACK_VALIDATED'
    assert (req, raw) == before
