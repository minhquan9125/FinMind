"""S5-WBS07.2: when to trust Nhân's v2 intent, and the Gemini fallback contract (rules ported from Huyền's 07.1)."""
import asyncio

import pytest

from src.b1_answering.core.policy import Budget, Limits
from src.b1_answering.providers.gemini import GeminiError
from src.retrieval_orchestration import intent_gate_v2 as gate


def classification(label, reason='EXPLICIT_REQUEST_TYPE', status='PROPOSED', restricted=False, components=()):
    return {'resolution': {'intent_label': label, 'reason': reason, 'status': status, 'component_labels': list(components),
                           'contains_restricted_component': restricted, 'unresolved_requests': [],
                           'ranking_policy': 'intent-request-objectives-v2-11-r2'}}


@pytest.mark.parametrize('result,expected', [
    (classification('ANALYSIS'), ('DIRECT', 'ANALYSIS')),
    (classification('MIXED', 'MULTIPLE_REQUEST_TYPES', components=('NUMERIC', 'PERSON_ROLE')), ('DIRECT', 'MIXED')),
    (classification('ANALYSIS', 'CLASSIFIER_PROPOSAL'), ('FALLBACK', 'ANALYSIS')),
    (classification('NUMERIC', 'CLASSIFIER_PROPOSAL', status='UNRESOLVED'), ('FALLBACK', 'NUMERIC')),
    (classification('CONVERSATION', status='NEEDS_CONTEXT'), ('NEEDS_CONTEXT', 'CONVERSATION')),
    (classification('OUT_OF_SCOPE', restricted=True), ('REFUSE', 'OUT_OF_SCOPE')),
    # A guessed OUT_OF_SCOPE never refuses on its own: Gemini confirms it first.
    (classification('OUT_OF_SCOPE', 'CLASSIFIER_PROPOSAL', restricted=True), ('FALLBACK', 'OUT_OF_SCOPE')),
])
def test_decide_trusts_rule_evidence_and_sends_guesses_to_fallback(result, expected):
    decided = gate.decide(result)
    assert (decided['decision'], decided['label']) == expected


def test_decide_rejects_an_unknown_policy():
    bad = classification('ANALYSIS')
    bad['resolution']['ranking_policy'] = 'intent-request-objectives-v5'
    assert gate.decide(bad)['decision'] == 'IGNORE'


def test_request_has_exactly_three_wire_fields_and_eleven_labels_plus_clarify():
    request = gate.fallback_request('vì sao fpt giảm', company='FPT', period=None)
    assert set(request) == {'question', 'conversation_scope', 'allowed_labels'}
    assert request['conversation_scope'] == {'company_ticker': 'FPT', 'period': None}
    assert len(request['allowed_labels']) == 12 and request['allowed_labels'][-1] == 'CLARIFY'
    assert 'PHAN_TICH' in request['allowed_labels'] and 'NGOAI_PHAM_VI' in request['allowed_labels']


REQUEST = gate.fallback_request('vì sao fpt giảm', company='FPT', period=None)


@pytest.mark.parametrize('payload,label,reason', [
    ({'intent_label': 'PHAN_TICH', 'confidence': .8, 'reason': 'hỏi nguyên nhân giá'}, 'ANALYSIS', None),
    ({'intent_label': 'PHAN_TICH', 'confidence': .8, 'reason': 'x', 'extracted_company': 'FPT'}, 'ANALYSIS', None),
    ({'intent_label': 'PHAN_TICH', 'confidence': .59, 'reason': 'x'}, None, 'LOW_PROVIDER_CONFIDENCE'),
    ({'intent_label': 'CLARIFY', 'confidence': .9, 'reason': 'x'}, None, 'PROVIDER_ASKED_CLARIFICATION'),
    ({'intent_label': 'TREND', 'confidence': .9, 'reason': 'x'}, None, 'INVALID_RESPONSE'),
    ({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x', 'route': 'BOTH'}, None, 'INVALID_RESPONSE'),
    ({'intent_label': 'PHAN_TICH', 'confidence': True, 'reason': 'x'}, None, 'INVALID_RESPONSE'),
    ({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x', 'extracted_company': 'VNM'}, None, 'COMPANY_SCOPE_CONFLICT'),
    ('not a dict', None, 'INVALID_RESPONSE'),
])
def test_validate_accepts_only_a_confident_in_scope_label(payload, label, reason):
    checked = gate.validate_fallback(payload, request=REQUEST)
    assert (checked['label'], checked['reason']) == (label, reason)


class Provider:
    def __init__(self, reply=None, error=None, delay=0):
        self.reply, self.error, self.delay, self.requests = reply, error, delay, []

    async def count_tokens(self, request):
        return 50

    async def generate(self, request):
        self.requests.append(request)
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return {'payload': self.reply, 'usage': {'input_tokens': 50, 'output_tokens': 10, 'total_tokens': 60},
                'model_version': 'fake'}


def run_fallback(provider, budget=None, timeout=2):
    limits = Limits.load()
    return asyncio.run(gate.ask_fallback(provider, budget or Budget(limits), REQUEST, timeout=timeout))


def test_fallback_asks_gemini_with_the_response_schema_and_returns_the_label():
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x'})
    assert run_fallback(provider)['label'] == 'ANALYSIS'
    config = provider.requests[0]['generationConfig']
    assert config['responseMimeType'] == 'application/json'
    assert config['responseJsonSchema']['properties']['intent_label']['enum'][-1] == 'CLARIFY'


@pytest.mark.parametrize('provider,reason', [
    (Provider(delay=5), 'PROVIDER_TIMEOUT'),
    (Provider(error=GeminiError('GEMINI_UNAVAILABLE')), 'PROVIDER_ERROR'),
])
def test_fallback_failures_never_invent_a_label(provider, reason):
    checked = run_fallback(provider, timeout=0.2)
    assert (checked['label'], checked['reason']) == (None, reason)


def test_fallback_respects_the_request_budget():
    limits = Limits.load()
    budget = Budget(limits)
    left = limits.max_total_tokens
    while left >= limits.max_output_tokens:  # use up the whole budget, within the per-call input limit
        size = min(limits.max_input_tokens, left - limits.max_output_tokens)
        budget.reserve(size)
        left -= size + limits.max_output_tokens
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x'})
    checked = run_fallback(provider, budget)
    assert (checked['label'], checked['reason']) == (None, 'BUDGET_EXCEEDED') and provider.requests == []
