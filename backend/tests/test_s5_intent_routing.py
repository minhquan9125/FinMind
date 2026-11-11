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
    IntentRoutingPolicy, decide_intent_route,
)


def ranking(first='PERSON_ROLE', score=.88, second='NEWS', second_score=.48):
    return {'groups': [{'intent_label': first, 'score': score},
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
    result = decide_intent_route(raw, company_ticker=ticker)
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
    result = decide_intent_route(ranking(label, .90, other, .40), company_ticker='FPT')
    assert result['route'] == route and result['intent_label'] == label


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
    out = decide_intent_route(ranking(score=first, second_score=second), company_ticker='VCB')
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
    assert decide_intent_route(None)['decision'] == 'ASK_CLARIFICATION'
    assert decide_intent_route(None, company_ticker='FPT', period='2025-Q5')['decision'] == 'ASK_CLARIFICATION'
    assert decide_intent_route(None, company_ticker='FPT')['decision'] == 'NEED_FALLBACK'


def test_prior_company_only_when_confirmed_and_same_session():
    for same, confirmed in [(False, False), (False, True), (True, False)]:
        result = decide_intent_route(ranking(), context_company_ticker='VCB',
                                     context_confirmed=confirmed, context_same_session=same)
        assert result['decision'] == 'ASK_CLARIFICATION'
    out = decide_intent_route(ranking(), context_company_ticker='VCB', context_confirmed=True,
                              context_same_session=True, period='2025')
    assert out['route'] == 'GRAPH'
    assert out['scope'] == {'company_ticker': 'VCB', 'period': '2025', 'company_source': 'CONTEXT'}


def test_explicit_company_wins_and_ambiguous_context_asks_instead_of_guessing():
    out = decide_intent_route(ranking(), company_ticker='FPT', context_company_ticker=['VCB', 'BID'],
                              context_confirmed=True, context_same_session=True)
    assert out['scope']['company_ticker'] == 'FPT'
    out = decide_intent_route(ranking(), context_company_ticker=['VCB', 'BID'],
                              context_confirmed=True, context_same_session=True)
    assert out['reason_code'] == 'AMBIGUOUS_CONTEXT_COMPANY'


def test_injected_registry_and_company_optional_market_news():
    assert decide_intent_route(ranking(), company_ticker='XYZ', valid_tickers={'FPT', 'VCB'})['decision'] == 'ASK_CLARIFICATION'
    out = decide_intent_route(ranking('NEWS', .9, 'NUMERIC', .3), company_required=False)
    assert out['route'] == 'VECTOR' and out['scope']['company_ticker'] is None


@pytest.mark.parametrize('bad', [None, {}, {'groups': []}, {'groups': [{}]},
    {'groups': [None, None]}, {'graph_score': .9, 'content_score': .2}])
def test_malformed_classifier_output_needs_fallback(bad):
    result = decide_intent_route(bad, company_ticker='FPT')
    assert result['decision'] == 'NEED_FALLBACK'
    assert result['route'] is None and result['reason_code'] == 'INVALID_CLASSIFICATION'


@pytest.mark.parametrize('score', [True, '0.9', float('nan'), float('inf'), 1.01, -1.01])
def test_invalid_cosine_never_passes_gate_two(score):
    assert decide_intent_route(ranking(score=score), company_ticker='FPT')['need_fallback']


@pytest.mark.parametrize('raw', [
    ranking('UNKNOWN'), ranking('PERSON_ROLE', .8, 'PERSON_ROLE', .5),
    ranking('PERSON_ROLE', .5, 'NEWS', .8), ranking('CHUC_VU', .9, 'PERSON_ROLE', .5),
    ranking() | {'score_type': 'PROBABILITY'},
    ranking() | {'ranking_policy': 'different'},
    ranking() | {'question': 'another request'},
])
def test_duplicate_labels_wrong_order_and_stale_queries_fail_closed(raw):
    assert decide_intent_route(raw, company_ticker='VCB', question='Ai là chủ tịch VCB?')['need_fallback']


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
    policy = IntentRoutingPolicy(IntentMatcher(library, Encoder()))
    result = policy.decide('Ai là chủ tịch VCB?', company_ticker='VCB')
    assert result['route'] == 'GRAPH' and result['intent_label'] == 'PERSON_ROLE'
    assert result['score_gap'] == 1.


def test_input_ranking_is_not_mutated():
    raw = ranking('CHUC_VU'); saved = copy.deepcopy(raw)
    decide_intent_route(raw, company_ticker='VCB')
    assert raw == saved


def test_fallback_handoff_preserves_top_three_distinct_labels_and_verified_scope():
    raw = {'groups': [
        {'intent_label': label, 'score': score}
        for label, score in [('CHUC_VU', .68), ('NEWS', .64), ('KET_HOP', .60),
                             ('QUAN_HE', .55), ('SO_LIEU', .50)]
    ]}
    saved = copy.deepcopy(raw)
    out = decide_intent_route(raw, question='Who chairs VCB?', period='2025',
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
def test_failed_classification_forwards_question_but_no_untrusted_candidates(mode):
    matcher = SpyMatcher(result=ranking(score=float('nan')),
                         error=TimeoutError() if mode == 'exception' else None)
    out = IntentRoutingPolicy(matcher).decide('Who chairs VCB?', company_ticker='VCB')
    assert out['fallback_payload']['question'] == 'Who chairs VCB?'
    assert out['fallback_payload']['candidates'] == []
    json.dumps(out, allow_nan=False)


def test_no_fallback_payload_when_gate_one_blocks_or_direct_search_succeeds():
    assert decide_intent_route(None)['fallback_payload'] is None
    assert decide_intent_route(ranking(), company_ticker='VCB')['fallback_payload'] is None
