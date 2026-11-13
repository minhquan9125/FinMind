"""Scope/confidence/route acceptance; no provider, DB or real encoder calls."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from src.retrieval_orchestration.intent_library import IntentLibrary
from src.retrieval_orchestration.intent_matching import IntentMatcher
from src.retrieval_orchestration.intent_routing import (
    CONFIDENCE_THRESHOLD, GAP_THRESHOLD, INTENT_ROUTES,
    IntentClassificationContractError, IntentRoutingPolicy, decide_intent_route,
)


def diagnostic_route(*args, **kwargs):
    """Exercise score thresholds only with an explicit offline diagnostic opt-in."""
    return decide_intent_route(*args, allow_direct_search=True, **kwargs)


def ranking(first='PERSON_ROLE', score=.88, second='NEWS', second_score=.48):
    return {'ranking_policy': 'cosine-max-per-label-v1',
            'score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY',
            'groups': [{'intent_label': first, 'score': score},
                       {'intent_label': second, 'score': second_score}]}


# Exactly the five acceptance inputs supplied by the task owner; aliases are explicit.
ACCEPTANCE_CASES = [
    ('case1', ranking('CHUC_VU', .88, 'NEWS', .48), 'VCB', 'SEARCH', 'GRAPH', False),
    ('case2', ranking('BCTC_BCTN', .91, 'NEWS', .41), 'FPT', 'SEARCH', 'VECTOR', False),
    ('case3', ranking('KET_HOP', .85, 'NEWS', .55), 'FPT', 'SEARCH', 'BOTH', False),
    ('case4', {'groups': [{'intent_label': 'BCTC_BCTN', 'score': .85}]}, None,
     'ASK_CLARIFICATION', None, False),
    ('case5', ranking('CHUC_VU', .68, 'NEWS', .64), 'VCB', 'NEED_FALLBACK', None, True),
]


@pytest.mark.parametrize('ident,raw,ticker,decision,route,fallback', ACCEPTANCE_CASES,
                         ids=[case[0] for case in ACCEPTANCE_CASES])
def test_five_required_outcomes(ident, raw, ticker, decision, route, fallback):
    # Reviewed contract: BOTH also requires verified components of this query.
    components = dict(query_components=['PERSON_ROLE', 'REPORT_CONTENT'],
                      query_components_confirmed=True) if ident == 'case3' else {}
    result = diagnostic_route(raw, company_ticker=ticker, **components)
    assert (result['decision'], result['route'], result['need_fallback']) == (decision, route, fallback)
    assert result['fallback_task'] == ('S5-WBS07.2' if fallback else None)
    if route:
        assert result['gate'] == 3
    elif decision == 'ASK_CLARIFICATION':
        assert result['gate'] == 1 and result['clarification_question']
    else:
        assert result['gate'] == 2


@pytest.mark.parametrize('label,route', list(INTENT_ROUTES.items()))
def test_all_seven_canonical_labels_map_as_requested(label, route):
    other = 'NUMERIC' if label != 'NUMERIC' else 'NEWS'
    result = diagnostic_route(ranking(label, .90, other, .40), company_ticker='FPT')
    assert result['route'] == route
    if label == 'MIXED':
        assert result['decision'] == 'NEED_FALLBACK' and result['intent_label'] is None
    else:
        assert result['intent_label'] == label


def test_label_mapping_matches_nhan_taxonomy():
    schema = json.loads((Path(__file__).resolve().parents[2]/'docs/sprint5/intent-labels.v1.json').read_text(encoding='utf-8'))
    assert set(INTENT_ROUTES) == {label['id'] for label in schema['labels']}
    assert CONFIDENCE_THRESHOLD == .65 and GAP_THRESHOLD == .08


@pytest.mark.parametrize('first,second,expected,reason', [
    (.65, .57, 'SEARCH', 'CONFIDENT_INTENT'),
    (.73, .65, 'SEARCH', 'CONFIDENT_INTENT'),
    (.649999, .40, 'NEED_FALLBACK', 'LOW_CONFIDENCE'),
    (.90, .820001, 'NEED_FALLBACK', 'SMALL_GAP'),
    (.64, .60, 'NEED_FALLBACK', 'LOW_CONFIDENCE_AND_SMALL_GAP'),
    (.90, .90, 'NEED_FALLBACK', 'SMALL_GAP'),
    (-.1, -.5, 'NEED_FALLBACK', 'LOW_CONFIDENCE'),
])
def test_threshold_boundaries_never_round_away_uncertainty(first, second, expected, reason):
    out = diagnostic_route(ranking(score=first, second_score=second), company_ticker='VCB')
    assert (out['decision'], out['reason_code']) == (expected, reason)


class SpyMatcher:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result if result is not None else ranking()
        self.error = error

    def match(self, question, **kwargs):
        self.calls.append((question, kwargs))
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize('question,ticker,period', [
    ('Doanh thu thuần năm 2025 là bao nhiêu?', None, None),
    ('Ai là Chủ tịch HĐQT?', None, None),
    ('Tóm tắt BCTN 2025.', None, None),
    ('Có những công ty con nào?', None, None),
    ('Doanh thu FPT quý 5/2025', 'FPT', None),
    ('Doanh thu FPT Q0 năm 2025', 'FPT', None),
    ('Doanh thu FPT quý -1/2025', 'FPT', None),
    ('Giá FPT ngày 31/02/2025', 'FPT', None),
    ('Giá FPT ngày 2025-02-30', 'FPT', None),
    ('Doanh thu FPT', 'FPT', '2025-Q5'),
    ('Doanh thu FPT', 'FPT', '2025-02-30'),
    ('Doanh thu ???', '???', None),
])
def test_gate_one_stops_before_matcher_embedding_and_any_fallback(question, ticker, period):
    matcher = SpyMatcher(error=AssertionError('Matcher must not run'))
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker=ticker, period=period)
    assert out['decision'] == 'ASK_CLARIFICATION' and out['gate'] == 1
    assert out['need_fallback'] is False and out['route'] is None
    assert matcher.calls == []


def test_scope_has_priority_over_missing_or_broken_classification():
    assert diagnostic_route(None)['decision'] == 'ASK_CLARIFICATION'
    assert diagnostic_route(None, company_ticker='FPT', period='2025-Q5')['decision'] == 'ASK_CLARIFICATION'
    with pytest.raises(IntentClassificationContractError):
        diagnostic_route(None, company_ticker='FPT')


def test_prior_company_only_when_confirmed_and_same_session():
    for same, confirmed in [(False, False), (False, True), (True, False)]:
        result = diagnostic_route(ranking(), context_company_ticker='VCB',
                                     context_confirmed=confirmed, context_same_session=same)
        assert result['decision'] == 'ASK_CLARIFICATION'
    out = diagnostic_route(ranking(), context_company_ticker='VCB', context_confirmed=True,
                              context_same_session=True, period='2025')
    assert out['route'] == 'GRAPH'
    assert out['scope'] == {'company_ticker': 'VCB', 'period': '2025', 'company_source': 'CONTEXT'}


def test_explicit_company_wins_and_ambiguous_context_asks_instead_of_guessing():
    out = diagnostic_route(ranking(), company_ticker='FPT', context_company_ticker=['VCB', 'BID'],
                              context_confirmed=True, context_same_session=True)
    assert out['scope']['company_ticker'] == 'FPT'
    out = diagnostic_route(ranking(), context_company_ticker=['VCB', 'BID'],
                              context_confirmed=True, context_same_session=True)
    assert out['reason_code'] == 'AMBIGUOUS_CONTEXT_COMPANY'


def test_injected_registry_and_company_optional_market_news():
    assert diagnostic_route(ranking(), company_ticker='XYZ', valid_tickers={'FPT', 'VCB'})['decision'] == 'ASK_CLARIFICATION'
    out = diagnostic_route(ranking('NEWS', .9, 'NUMERIC', .3), company_required=False)
    assert out['route'] == 'VECTOR' and out['scope']['company_ticker'] is None


@pytest.mark.parametrize('bad', [None, {}, {'groups': []}, {'groups': [{}]},
    {'groups': [None, None]}, {'graph_score': .9, 'content_score': .2}])
def test_malformed_classifier_output_is_contract_error_not_fallback(bad):
    with pytest.raises(IntentClassificationContractError):
        diagnostic_route(bad, company_ticker='FPT')


@pytest.mark.parametrize('score', [True, '0.9', float('nan'), float('inf'), 1.01, -1.01])
def test_invalid_cosine_never_passes_gate_two(score):
    with pytest.raises(IntentClassificationContractError):
        diagnostic_route(ranking(score=score), company_ticker='FPT')


@pytest.mark.parametrize('raw', [
    ranking('UNKNOWN'), ranking('PERSON_ROLE', .8, 'PERSON_ROLE', .5),
    ranking('PERSON_ROLE', .5, 'NEWS', .8), ranking('CHUC_VU', .9, 'PERSON_ROLE', .5),
    ranking() | {'score_type': 'PROBABILITY'},
    ranking() | {'ranking_policy': 'different'},
    ranking() | {'question': 'another request'},
])
def test_duplicate_labels_wrong_order_and_stale_queries_fail_closed(raw):
    with pytest.raises(IntentClassificationContractError):
        diagnostic_route(raw, company_ticker='VCB', question='Ai là chủ tịch VCB?')


@pytest.mark.parametrize('error', [TimeoutError('timeout'), ValueError('encoder failed'), RuntimeError('library unavailable')])
def test_matcher_error_signals_fallback_without_running_external_ai(error):
    matcher = SpyMatcher(error=error)
    out = IntentRoutingPolicy(matcher).decide('Ai là chủ tịch VCB?', company_ticker='VCB')
    assert len(matcher.calls) == 1 and out['reason_code'] == 'CLASSIFICATION_ERROR'
    assert out['fallback_task'] == 'S5-WBS07.2' and out['route'] is None


def test_real_nhan_matcher_interface_flows_through_three_gates_without_legacy_route_hints():
    class Encoder:
        model_name = 'UNIT_MODEL'
        revision = 'a' * 40
        def embed_query(self, text):
            return [1., 0.]
    rows = tuple(dict(id=label, text=label, intent_label=label,
                      component_intents=['NUMERIC', 'NEWS'] if label == 'MIXED' else [])
                 for label in INTENT_ROUTES)
    vectors = np.asarray([[1., 0.] if r['intent_label']=='PERSON_ROLE' else [0., 1.] for r in rows],dtype=np.float32)
    library = IntentLibrary(rows, vectors, dict(model=dict(name='UNIT_MODEL', revision='a'*40),
                            library_version='unit', dataset_version='unit', label_schema_version='unit'))
    policy = IntentRoutingPolicy(IntentMatcher(library, Encoder()), allow_direct_search=True)
    result = policy.decide('Ai là chủ tịch VCB?', company_ticker='VCB')
    assert result['route'] == 'GRAPH' and result['intent_label'] == 'PERSON_ROLE'
    assert result['score_gap'] == 1.


def test_input_ranking_is_not_mutated():
    raw = ranking('CHUC_VU'); saved = copy.deepcopy(raw)
    diagnostic_route(raw, company_ticker='VCB')
    assert raw == saved


def test_fallback_handoff_preserves_top_three_distinct_labels_and_verified_scope():
    raw = ranking() | {'groups': [
        {'intent_label': label, 'score': score}
        for label, score in [('CHUC_VU', .68), ('NEWS', .64), ('KET_HOP', .60),
                             ('QUAN_HE', .55), ('SO_LIEU', .50)]
    ]}
    saved = copy.deepcopy(raw)
    out = diagnostic_route(raw, question='Who chairs VCB?', period='2025',
                             context_company_ticker='VCB', context_confirmed=True,
                             context_same_session=True)
    payload = out['fallback_payload']
    assert out['route'] is None and out['intent_label'] is None
    assert payload['question'] == 'Who chairs VCB?'
    assert payload['scope'] == {'company_ticker': 'VCB', 'period': '2025', 'company_source': 'CONTEXT'}
    assert payload['candidates'] == [
        {'rank': 1, 'intent_label': 'PERSON_ROLE', 'score': .68},
        {'rank': 2, 'intent_label': 'NEWS', 'score': .64},
        {'rank': 3, 'intent_label': 'MIXED', 'score': .60},
    ]
    assert set(payload['allowed_labels']) == set(INTENT_ROUTES)
    assert payload['score_type'] == 'COSINE_SIMILARITY_NOT_PROBABILITY'
    json.dumps(out, allow_nan=False)
    payload['scope']['company_ticker'] = 'FPT'
    assert out['scope']['company_ticker'] == 'VCB' and raw == saved


def test_wrapper_hands_candidates_to_fallback_without_calling_external_classifier():
    raw = ranking(score=.68, second_score=.64)
    raw['groups'].append({'intent_label': 'MIXED', 'score': .60})
    matcher = SpyMatcher(result=raw)
    out = IntentRoutingPolicy(matcher).decide('Who chairs VCB?', company_ticker='VCB')
    assert matcher.calls == [('Who chairs VCB?', {'top_groups': 3, 'top_examples': 5})]
    assert len(out['fallback_payload']['candidates']) == 3


@pytest.mark.parametrize('mode', ['invalid', 'exception'])
def test_matcher_failure_forwards_question_but_invalid_payload_is_contract_error(mode):
    matcher = SpyMatcher(result=ranking(score=float('nan')),
                         error=TimeoutError() if mode == 'exception' else None)
    policy = IntentRoutingPolicy(matcher)
    if mode == 'invalid':
        with pytest.raises(IntentClassificationContractError):
            policy.decide('Who chairs VCB?', company_ticker='VCB')
        return
    out = policy.decide('Who chairs VCB?', company_ticker='VCB')
    assert out['fallback_payload']['question'] == 'Who chairs VCB?'
    assert out['fallback_payload']['candidates'] == []
    json.dumps(out, allow_nan=False)


def test_no_fallback_payload_when_gate_one_blocks_or_direct_search_succeeds():
    assert diagnostic_route(None)['fallback_payload'] is None
    assert diagnostic_route(ranking(), company_ticker='VCB')['fallback_payload'] is None


@pytest.mark.parametrize('missing', [('ranking_policy',), ('score_type',),
                                     ('ranking_policy', 'score_type')])
def test_review_requires_explicit_score_metadata_before_thresholds(missing):
    raw = ranking('NUMERIC', .71, 'NEWS', .20)
    for key in missing:
        raw.pop(key)
    with pytest.raises(ValueError):
        diagnostic_route(raw, company_ticker='FPT')


@pytest.mark.parametrize('key', ['ranking_policy', 'score_type'])
@pytest.mark.parametrize('value', [None, '', 'UNKNOWN', [], 123])
def test_review_invalid_metadata_is_contract_error_not_ai_fallback(key, value):
    raw = ranking('NUMERIC', .71, 'NEWS', .20)
    raw[key] = value
    with pytest.raises(ValueError):
        IntentRoutingPolicy(SpyMatcher(result=raw)).decide('Revenue FPT?', company_ticker='FPT')


def classifier_ranking():
    return ranking('PERSON_ROLE', .99, 'NEWS', .01) | {
        'ranking_policy': 'intent-linear-v1',
        'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED',
    }


def resolution(label='NEWS', version='v3'):
    return {'ranking_policy': 'intent-request-objectives-' + version,
            'score_type': 'DECISION_EVIDENCE_NO_CONFIDENCE',
            'intent_label': label, 'confidence': None,
            'reason': 'EXPLICIT_REQUEST_TYPE', 'component_labels': []}


def test_review_uncalibrated_probability_never_uses_cosine_thresholds():
    out = diagnostic_route(classifier_ranking(), company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['route'] is None
    assert out['reason_code'] == 'UNCALIBRATED_CLASSIFICATION'
    assert out['top_1_score'] is None and out['score_gap'] is None
    assert out['fallback_payload']['score_type'] == 'CLASSIFIER_PROBABILITY_UNCALIBRATED'
    assert out['fallback_payload']['candidates'][0]['score'] == .99


@pytest.mark.parametrize('version', ['v1', 'v2', 'v3', 'v4'])
def test_review_decision_evidence_with_null_confidence_needs_verification(version):
    out = diagnostic_route(resolution('PERSON_ROLE', version), company_ticker='FPT')
    assert out['reason_code'] == 'UNCALIBRATED_CLASSIFICATION' and out['route'] is None
    assert out['classification_evidence']['resolution']['intent_label'] == 'PERSON_ROLE'
    assert out['classification_evidence']['resolution']['confidence'] is None
    assert out['fallback_payload']['candidates'] == []


def test_review_label_disagreement_preserves_both_labels_without_borrowing_scores():
    raw = {'base_ranking': classifier_ranking(), 'resolution': resolution()}
    saved = copy.deepcopy(raw)
    out = diagnostic_route(raw, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'LABEL_DISAGREEMENT'
    assert out['route'] is None and out['intent_label'] is None
    assert out['top_1_score'] is None and out['score_gap'] is None
    evidence = out['classification_evidence']
    assert evidence['base_ranking']['groups'][0]['intent_label'] == 'PERSON_ROLE'
    assert evidence['resolution']['intent_label'] == 'NEWS'
    assert evidence['resolution']['reason'] == 'EXPLICIT_REQUEST_TYPE'
    assert evidence['resolution']['confidence'] is None
    assert out['fallback_payload']['classification_evidence'] == evidence
    assert raw == saved


def test_review_even_agreed_labels_with_null_confidence_cannot_search():
    out = diagnostic_route({'base_ranking': ranking(), 'resolution': resolution('PERSON_ROLE')},
                             company_ticker='FPT')
    assert out['reason_code'] == 'UNCALIBRATED_CLASSIFICATION' and out['route'] is None
    assert out['top_1_score'] is None and out['score_gap'] is None


def test_review_resolution_cannot_invent_calibrated_confidence():
    raw = resolution() | {'confidence': .99}
    with pytest.raises(ValueError):
        diagnostic_route(raw, company_ticker='FPT')


def test_review_mixed_without_verified_query_components_never_defaults_to_both():
    raw = ranking('MIXED', .90, 'NEWS', .40)
    raw['groups'][0]['best_example'] = {'component_intents': ['PERSON_ROLE', 'REPORT_CONTENT']}
    out = diagnostic_route(raw, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['route'] is None
    assert out['reason_code'] == 'MIXED_COMPONENTS_REQUIRED'


@pytest.mark.parametrize('components,expected', [
    (['NUMERIC', 'NEWS'], 'VECTOR'),
    (['REPORT_CONTENT', 'NEWS'], 'VECTOR'),
    (['PERSON_ROLE', 'ENTITY_RELATION'], 'GRAPH'),
    (['PERSON_ROLE', 'REPORT_CONTENT'], 'BOTH'),
    (['QUAN_HE', 'SO_LIEU'], 'BOTH'),
])
def test_review_mixed_route_depends_on_verified_query_components(components, expected):
    out = diagnostic_route(ranking('MIXED', .90, 'NEWS', .40), company_ticker='FPT',
                             query_components=components, query_components_confirmed=True)
    assert out['route'] == expected and out['intent_label'] == 'MIXED'


def test_review_unconfirmed_query_components_do_not_allow_search():
    out = diagnostic_route(ranking('MIXED', .9, 'NEWS', .4), company_ticker='FPT',
                             query_components=['PERSON_ROLE', 'NEWS'], query_components_confirmed=False)
    assert out['reason_code'] == 'MIXED_COMPONENTS_REQUIRED' and out['route'] is None


@pytest.mark.parametrize('components', [[], ['NEWS'], ['NEWS', 'NEWS'],
                                          ['MIXED', 'NEWS'], ['UNKNOWN', 'NEWS'], 'NUMERIC,NEWS'])
def test_review_invalid_verified_components_are_contract_errors(components):
    with pytest.raises(ValueError):
        diagnostic_route(ranking('MIXED', .9, 'NEWS', .4), company_ticker='FPT',
                            query_components=components, query_components_confirmed=True)


def test_review_producer_contract_error_must_not_be_reclassified_as_matcher_failure():
    matcher = SpyMatcher(error=IntentClassificationContractError('MISSING_SCORE_METADATA'))
    with pytest.raises(IntentClassificationContractError):
        IntentRoutingPolicy(matcher).decide('Who chairs FPT?', company_ticker='FPT')


def test_review_nhan_real_resolution_interface_keeps_raw_and_final_intents_separate():
    from src.retrieval_orchestration.intent_news_requests import requests, resolve_objectives
    question = 'Chủ tịch HĐQT VCB là ai?'
    labels = ['NUMERIC', 'PERSON_ROLE', 'NEWS', 'REPORT_CONTENT', 'ENTITY_RELATION', 'TREND', 'MIXED']
    resolved = resolve_objectives([.71, .20, .03, .02, .02, .01, .01], [], labels, requests(question))
    raw = ranking('NUMERIC', .71, 'PERSON_ROLE', .20) | {
        'ranking_policy': 'intent-linear-v1', 'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED'}
    out = diagnostic_route({'base_ranking': raw, 'resolution': resolved}, question=question, company_ticker='VCB')
    assert out['reason_code'] == 'LABEL_DISAGREEMENT' and out['route'] is None
    assert out['classification_evidence']['resolution']['intent_label'] == 'PERSON_ROLE'
    assert out['top_1_score'] is None


@pytest.mark.parametrize('field', ['base_ranking', 'resolution'])
def test_review_envelope_does_not_hide_missing_metadata(field):
    raw = {'base_ranking': classifier_ranking(), 'resolution': resolution()}
    raw[field].pop('score_type')
    with pytest.raises(IntentClassificationContractError):
        diagnostic_route(raw, company_ticker='FPT')


def test_review_low_score_is_checked_before_mixed_components():
    out = diagnostic_route(ranking('MIXED', .60, 'NEWS', .50), company_ticker='FPT',
                             query_components=['UNKNOWN'], query_components_confirmed=True)
    assert out['reason_code'] == 'LOW_CONFIDENCE'


def test_review_uncalibrated_evidence_handoff_stays_limited_to_top_three():
    raw = classifier_ranking()
    raw['groups'] = [{'intent_label': label, 'score': score} for label, score in [
        ('PERSON_ROLE', .50), ('NEWS', .20), ('MIXED', .15), ('NUMERIC', .10),
        ('ENTITY_RELATION', .03), ('REPORT_CONTENT', .015), ('TREND', .005)]]
    out = diagnostic_route(raw, company_ticker='FPT')
    payload = out['fallback_payload']
    assert len(payload['candidates']) == 3
    assert len(payload['classification_evidence']['base_ranking']['groups']) == 3
    assert len(raw['groups']) == 7


@pytest.mark.parametrize('label', ['NUMERIC', 'REPORT_CONTENT', 'NEWS', 'PERSON_ROLE',
                                  'ENTITY_RELATION', 'TREND', 'MIXED'])
def test_safety_default_never_searches_on_uncalibrated_cosine_library(label):
    other = 'NEWS' if label != 'NEWS' else 'NUMERIC'
    out = decide_intent_route(ranking(label, .99, other, .01), company_ticker='FPT',
                             query_components=['PERSON_ROLE', 'REPORT_CONTENT'], query_components_confirmed=True)
    assert out['decision'] == 'NEED_FALLBACK' and out['route'] is None
    assert out['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert out['fallback_payload']['candidates'][0]['intent_label'] == label


def test_safety_wrapper_defaults_to_fallback_and_preserves_candidates():
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide('Who chairs FPT?', company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert len(out['fallback_payload']['candidates']) == 2


@pytest.mark.parametrize('value', [1, 0, 'true', 'false', None, [], {}])
def test_safety_direct_search_configuration_requires_actual_boolean(value):
    with pytest.raises(ValueError):
        IntentRoutingPolicy(SpyMatcher(), allow_direct_search=value)
    with pytest.raises(ValueError):
        decide_intent_route(ranking(), company_ticker='FPT', allow_direct_search=value)


def test_safety_request_cannot_override_policy_startup_configuration():
    matcher = SpyMatcher()
    with pytest.raises(ValueError):
        IntentRoutingPolicy(matcher).decide('Who chairs FPT?', company_ticker='FPT', allow_direct_search=True)
    assert matcher.calls == []


@pytest.mark.parametrize('question', [
    'Doanh thu FPT Q 5 năm 2025',
    'Doanh thu FPT quý +5/2025',
    'Doanh thu FPT quý 1.5/2025',
    'Doanh thu FPT quý 1,5/2025',
    'Doanh thu FPT quý 1, 5 năm 2025',
    'Doanh thu FPT Q 0/2025',
    'Doanh thu FPT quý 1 và 5 năm 2025',
    'Doanh thu FPT quý 1-5 năm 2025',
    'Doanh thu FPT quý 1, -2 năm 2025',
])
def test_safety_invalid_quarter_variants_stop_before_matcher(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT', period='2025-Q2')
    assert out['decision'] == 'ASK_CLARIFICATION' and out['reason_code'] == 'INVALID_PERIOD'
    assert matcher.calls == []


@pytest.mark.parametrize('question', [
    'Doanh thu FPT Q 1 năm 2025',
    'Doanh thu FPT quý 1,2 năm 2025',
    'Doanh thu FPT quý 1, 2, 3 năm 2025',
    'Doanh thu FPT quý 1 và 2 năm 2025',
    'Doanh thu FPT quý 1 đến 4 năm 2025',
    'Doanh thu FPT quý 1-4 năm 2025',
    'Doanh thu FPT quý 1 và quý 2 năm 2025',
])
def test_safety_valid_quarter_lists_are_not_blocked(question):
    out = IntentRoutingPolicy(SpyMatcher()).decide(question, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'


@pytest.mark.parametrize('question', [
    'Doanh thu FPT Q3-2025',
    'Doanh thu FPT quý 2 - 2025',
    'Doanh thu FPT từ quý 1 đến 30/6/2025',
    'Doanh thu FPT từ Q1 tới 2025-06-30',
    'Doanh thu FPT Q3–2025',
    'Doanh thu FPT quý 1-4 - 2025',
    'Doanh thu FPT quý 1, 2 - 2025',
    'Doanh thu FPT quý 1 và quý 2 - 2025',
])
def test_review_quarter_year_and_date_endpoints_reach_classification(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert matcher.calls == [(question, {'top_groups': 3, 'top_examples': 5})]


@pytest.mark.parametrize('question', [
    'Doanh thu FPT Q5-2025',
    'Doanh thu FPT quý 0 - 2025',
    'Doanh thu FPT từ quý 1 đến 31/6/2025',
    'Doanh thu FPT từ Q1 tới 2025-02-30',
    'Doanh thu FPT quý 1 đến quý 30/6/2025',
    'Doanh thu FPT quý 1 đến quý 2025',
    'Doanh thu FPT quý 1-5-2025',
    'Doanh thu FPT quý 1 đến quý 5/2025',
    'Doanh thu FPT Q1-2025 và Q5-2025',
])
def test_review_invalid_quarters_and_dates_still_stop_before_classification(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT', period='2025-Q2')
    assert out['decision'] == 'ASK_CLARIFICATION' and out['reason_code'] == 'INVALID_PERIOD'
    assert matcher.calls == []


@pytest.mark.parametrize('question', [
    'Doanh thu FPT quý 1 đến 6/2025',
    'Doanh thu FPT quý 1 đến 5/2025',
    'Doanh thu FPT từ Q1 tới 06/2025',
    'Doanh thu FPT từ quý 1 đến 12/2025',
    'Doanh thu FPT từ quý 1 đến 6 / 2025',
])
def test_review_month_year_range_endpoint_is_not_an_inherited_quarter(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert matcher.calls == [(question, {'top_groups': 3, 'top_examples': 5})]


@pytest.mark.parametrize('question', [
    'Doanh thu FPT quý 1 đến quý 6/2025',
    'Doanh thu FPT quý 1 tới Q6/2025',
    'Doanh thu FPT quý 1 đến 13/2025',
    'Doanh thu FPT quý 1 đến 0/2025',
    'Doanh thu FPT quý 1 đến 6/0000',
    'Doanh thu FPT quý 1 đến 6 năm 2025',
    'Doanh thu FPT quý 1,6/2025',
    'Doanh thu FPT quý 1-Q6/2025',
    'Doanh thu FPT quý 1 đến 6/2025 và quý 5/2025',
])
def test_review_month_endpoint_does_not_hide_invalid_months_or_explicit_quarters(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT', period='2025-Q1')
    assert out['decision'] == 'ASK_CLARIFICATION' and out['reason_code'] == 'INVALID_PERIOD'
    assert matcher.calls == []


@pytest.mark.parametrize('question', [
    'quý 1 - 06/2025',
    'Doanh thu FPT quý 1 - 6/2025',
    'Doanh thu FPT quý 1-6/2025',
    'Doanh thu FPT quý 1–06/2025',
    'Doanh thu FPT quý 1—06/2025',
    'Doanh thu FPT quý 1 - 06 / 2025',
    'Doanh thu FPT quý 1-12/2025',
])
def test_review_dash_month_endpoint_is_equivalent_to_until(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['reason_code'] == 'DIRECT_SEARCH_DISABLED'
    assert matcher.calls == [(question, {'top_groups': 3, 'top_examples': 5})]


@pytest.mark.parametrize('question', [
    'Doanh thu FPT quý 1 - quý 6/2025',
    'Doanh thu FPT Q1–Q6/2025',
    'Doanh thu FPT quý 1—quý 6/2025',
    'Doanh thu FPT quý 1 - 13/2025',
    'Doanh thu FPT quý 1 - 00/2025',
    'Doanh thu FPT quý 1 - 06/0000',
    'Doanh thu FPT quý 1—6 năm 2025',
    'Doanh thu FPT quý 5 - 06/2025',
    'Doanh thu FPT quý 1 - 06/2025 và quý 5/2025',
])
def test_review_dash_month_endpoint_does_not_hide_invalid_periods(question):
    matcher = SpyMatcher()
    out = IntentRoutingPolicy(matcher).decide(question, company_ticker='FPT', period='2025-Q1')
    assert out['decision'] == 'ASK_CLARIFICATION' and out['reason_code'] == 'INVALID_PERIOD'
    assert matcher.calls == []


@pytest.mark.parametrize('allow_direct_search', [False, True])
@pytest.mark.parametrize('mode', ['standalone', 'envelope_agreed', 'envelope_disagreed'])
def test_review_v7_policy_v5_evidence_goes_to_fallback_without_cosine_thresholds(allow_direct_search, mode):
    # V7 producer contract: Nhan e080a889, intent_semantic_requests.resolve_objectives.
    question = 'Ai đang làm CEO của FPT?'
    resolved = resolution('PERSON_ROLE', 'v5') | {
        'runtime_enabled': False,
        'explicit_evidence': [{'text': question, 'intent_label': 'PERSON_ROLE'}],
        'unresolved_requests': [],
    }
    if mode == 'standalone':
        raw = resolved
    else:
        first = 'PERSON_ROLE' if mode == 'envelope_agreed' else 'NUMERIC'
        base = ranking(first, .99, 'NEWS', .01) | {
            'question': question, 'ranking_policy': 'intent-linear-v1',
            'score_type': 'CLASSIFIER_PROBABILITY_UNCALIBRATED',
        }
        raw = {'base_ranking': base, 'resolution': resolved}
    before = copy.deepcopy(raw)
    out = decide_intent_route(raw, question=question, company_ticker='FPT',
                              allow_direct_search=allow_direct_search)
    assert out['decision'] == 'NEED_FALLBACK' and out['need_fallback'] is True
    assert out['reason_code'] == ('LABEL_DISAGREEMENT' if mode == 'envelope_disagreed'
                                  else 'UNCALIBRATED_CLASSIFICATION')
    assert out['route'] is None and out['intent_label'] is None
    assert out['top_1_score'] is None and out['top_2_score'] is None and out['score_gap'] is None
    assert out['classification_evidence']['resolution'] == resolved
    assert out['fallback_payload']['classification_evidence']['resolution'] == resolved
    assert raw == before


def test_review_v5_unresolved_request_evidence_survives_fallback():
    question = 'Lợi nhuận FPT có độc lập với mảng viễn thông không?'
    resolved = resolution('NUMERIC', 'v5') | {
        'reason': 'WHOLE_QUERY_UNCHANGED', 'runtime_enabled': False,
        'explicit_evidence': [], 'unresolved_requests': [question],
    }
    out = IntentRoutingPolicy(SpyMatcher(result=resolved)).decide(question, company_ticker='FPT')
    assert out['decision'] == 'NEED_FALLBACK' and out['route'] is None
    assert out['fallback_payload']['classification_evidence']['resolution'] == resolved


@pytest.mark.parametrize('invalid', [
    {'confidence': .99},
    {'score_type': 'COSINE_SIMILARITY_NOT_PROBABILITY'},
    {'runtime_enabled': True},
    {'runtime_enabled': 'false'},
    {'unresolved_requests': 'unknown request'},
    {'unresolved_requests': [1]},
    {'explicit_evidence': 'PERSON_ROLE'},
    {'explicit_evidence': [{'text': 'Who chairs FPT?', 'intent_label': 'UNKNOWN'}]},
])
def test_review_v5_support_does_not_accept_invalid_evidence(invalid):
    with pytest.raises(IntentClassificationContractError):
        decide_intent_route(resolution('PERSON_ROLE', 'v5') | invalid, company_ticker='FPT')


def test_review_unknown_resolution_version_is_still_a_contract_error():
    with pytest.raises(IntentClassificationContractError):
        decide_intent_route(resolution('PERSON_ROLE', 'v6'), company_ticker='FPT')
