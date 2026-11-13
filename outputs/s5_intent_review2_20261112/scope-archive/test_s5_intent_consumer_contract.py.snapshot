"""Real 04.2 consumer copied from Huyen: required score metadata and price scope."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest

from src.retrieval_orchestration.intent_routing import decide_intent_route, IntentRoutingPolicy


def ranking(**updates):
    raw = dict(ranking_policy='cosine-max-per-label-v1',
               score_type='COSINE_SIMILARITY_NOT_PROBABILITY',
               groups=[dict(intent_label='NUMERIC', score=.71), dict(intent_label='NEWS', score=.40)])
    return raw | updates


@pytest.mark.parametrize('policy,kind', [
    (None, None), (None, 'COSINE_SIMILARITY_NOT_PROBABILITY'),
    ('cosine-max-per-label-v1', None), ('', ''), (False, True),
    ('intent-linear-v1', 'CLASSIFIER_PROBABILITY_UNCALIBRATED'),
    ('intent-request-objectives-v5', 'DECISION_EVIDENCE_NO_CONFIDENCE'),
    ([], {}),
])
def test_bad_metadata_never_searches_or_requests_ai_fallback(policy, kind):
    result = decide_intent_route(ranking(ranking_policy=policy, score_type=kind), company_ticker='FPT')
    assert result['decision'] == 'REJECT_CLASSIFICATION'
    assert result['reason_code'] == 'INVALID_SCORE_CONTRACT'
    assert result['route'] is None and result['need_fallback'] is False
    assert result['fallback_payload'] is None


@pytest.mark.parametrize('keys', [('ranking_policy',), ('score_type',), ('ranking_policy', 'score_type')])
def test_missing_keys_do_not_default_to_cosine(keys):
    raw = ranking()
    for key in keys:
        del raw[key]
    result = decide_intent_route(raw, company_ticker='FPT')
    assert result['decision'] == 'REJECT_CLASSIFICATION'
    assert result['reason_code'] == 'INVALID_SCORE_CONTRACT'


@pytest.mark.parametrize('first,second,decision', [(.65, .57, 'SEARCH'), (.73, .65, 'SEARCH'),
    (.649999, .4, 'NEED_FALLBACK'), (.9, .820001, 'NEED_FALLBACK')])
def test_explicit_cosine_keeps_original_thresholds(first, second, decision):
    raw = ranking(groups=[dict(intent_label='NUMERIC', score=first), dict(intent_label='NEWS', score=second)])
    assert decide_intent_route(raw, company_ticker='FPT')['decision'] == decision


def test_scope_gate_still_precedes_the_matcher():
    class Uncalled:
        def match(self, *args, **kwargs):
            raise AssertionError('Scope must stop before embedding')
    assert IntentRoutingPolicy(Uncalled()).decide('Doanh thu bao nhiêu?')['decision'] == 'ASK_CLARIFICATION'


def test_valid_uncertain_cosine_preserves_top_three_payload():
    raw = ranking(groups=[dict(intent_label=label, score=score) for label,score in
                         [('PERSON_ROLE', .68), ('NEWS', .64), ('MIXED', .6), ('NUMERIC', .55)]])
    result = decide_intent_route(raw, company_ticker='FPT')
    assert result['decision'] == 'NEED_FALLBACK'
    assert len(result['fallback_payload']['candidates']) == 3
    assert result['fallback_payload']['score_type'] == 'COSINE_SIMILARITY_NOT_PROBABILITY'


def test_actual_webchat_price_resolver_keeps_price_out_of_reports():
    from src.retrieval_orchestration.live_research import analyze_live
    result = analyze_live('Giá cổ phiếu FPT hôm nay bao nhiêu?', today=date(2026, 11, 12))
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['source_type'] == 'PRICE'
    assert result['scope']['metric_code'] == 'LAST_PRICE'
    assert result['scope']['_market_request']['kind'] == 'QUOTE'


def test_mixed_without_query_component_evidence_does_not_default_to_both():
    raw = ranking(groups=[dict(intent_label='MIXED', score=.9), dict(intent_label='NEWS', score=.4)])
    result = decide_intent_route(raw, company_ticker='FPT')
    assert result['decision'] == 'NEED_FALLBACK'
    assert result['reason_code'] == 'MIXED_COMPONENTS_UNVERIFIED'
    assert result['route'] is None
    assert result['fallback_payload']['candidates'][0]['intent_label'] == 'MIXED'


@pytest.fixture(scope='module')
def original_consumer():
    path = Path(__file__).resolve().parents[2] / 'outputs/s5_intent_review2_20261112/consumer-original.py'
    spec = importlib.util.spec_from_file_location('huyen_consumer_original', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('label', ['NUMERIC', 'REPORT_CONTENT', 'NEWS', 'PERSON_ROLE', 'ENTITY_RELATION', 'MIXED', 'TREND'])
@pytest.mark.parametrize('scores', [(.9, .4), (.65, .57), (.68, .64), (.6, .4), (.9, .85)])
def test_valid_cosine_matches_original_except_unverified_mixed(original_consumer, label, scores):
    other = 'NEWS' if label != 'NEWS' else 'NUMERIC'
    raw = ranking(groups=[dict(intent_label=label, score=scores[0]), dict(intent_label=other, score=scores[1])])
    before = original_consumer.decide_intent_route(raw, company_ticker='FPT')
    after = decide_intent_route(raw, company_ticker='FPT')
    if label == 'MIXED' and before['decision'] == 'SEARCH':
        assert after['decision'] == 'NEED_FALLBACK' and after['route'] is None
        assert after['reason_code'] == 'MIXED_COMPONENTS_UNVERIFIED'
    else:
        assert after == before
