"""S5-WBS07.2 runner: Huyền's v2 decision and contract, one Gemini call with a time limit and the request budget."""
import asyncio

import pytest

from src.b1_answering.core.policy import Budget, Limits
from src.b1_answering.providers.gemini import GeminiError
from src.retrieval_orchestration import intent_gate_v2 as gate
from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from tests.test_s5_intent_v2_runtime import Encoder, artifact  # noqa: F401  (pytest fixture)

QUESTION = 'rsi của fpt'  # no v2 rule matches: the model guess needs the fallback


def classify(artifact, question=QUESTION, guess='ANALYSIS'):  # noqa: F811
    return IntentClassifier.load(artifact, Encoder(guess)).classify(question)


@pytest.fixture
def decided(artifact):  # noqa: F811
    return gate.decide(classify(artifact), QUESTION, 'FPT')


def test_decide_sends_a_model_guess_to_the_fallback(decided):
    assert decided['decision'] == 'NEED_FALLBACK' and decided['source'] == 'CLASSIFIER'


def test_decide_refuses_rule_detected_advice_without_a_company(artifact):  # noqa: F811
    question = 'có nên mua fpt'
    assert gate.decide(classify(artifact, question), question)['decision'] == 'REFUSE'


def test_decide_drops_a_stale_or_forged_classification(artifact):  # noqa: F811
    assert gate.decide(classify(artifact), 'vì sao fpt giảm', 'FPT') is None
    forged = classify(artifact)
    forged['resolution']['reason'] = 'EXPLICIT_REQUEST_TYPE'
    assert gate.decide(forged, QUESTION, 'FPT') is None


REQUEST = {'question': QUESTION, 'conversation_scope': {'company_ticker': 'FPT', 'period': None},
           'allowed_labels': ['GIA', 'SO_LIEU', 'PHAN_TICH', 'NEWS', 'BCTC_BCTN', 'CHUC_VU', 'QUAN_HE',
                              'TONG_QUAN', 'HOI_THOAI', 'NGOAI_PHAM_VI', 'KET_HOP', 'CLARIFY']}


@pytest.mark.parametrize('payload,label,reason', [
    ({'intent_label': 'PHAN_TICH', 'confidence': .8, 'reason': 'chỉ báo kỹ thuật'}, 'ANALYSIS', None),
    ({'intent_label': 'PHAN_TICH', 'confidence': .8, 'reason': 'x', 'extracted_company': 'FPT'}, 'ANALYSIS', None),
    ({'intent_label': 'PHAN_TICH', 'confidence': .59, 'reason': 'x'}, None, 'LOW_PROVIDER_CONFIDENCE'),
    ({'intent_label': 'CLARIFY', 'confidence': .9, 'reason': 'x'}, None, 'PROVIDER_ASKED_CLARIFICATION'),
    ({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x', 'route': 'BOTH'}, None, 'INVALID_RESPONSE'),
    ({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x', 'extracted_company': 'VNM'}, None, 'COMPANY_SCOPE_CONFLICT'),
    ({'intent_label': 'KET_HOP', 'confidence': .9, 'reason': 'x'}, None, 'UNVERIFIED_MIXED_COMPONENTS'),
])
def test_validate_uses_huyen_v2_contract(payload, label, reason):
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


def run_fallback(provider, decided, budget=None, timeout=2):
    return asyncio.run(gate.ask_fallback(provider, budget or Budget(Limits.load()), decided, QUESTION, timeout=timeout))


def test_fallback_sends_huyen_wire_request_and_returns_the_label(decided):
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x'})
    checked = run_fallback(provider, decided)
    assert (checked['label'], checked['route']) == ('ANALYSIS', 'MARKET')
    config = provider.requests[0]['generationConfig']
    assert config['responseMimeType'] == 'application/json'
    assert config['responseJsonSchema']['properties']['intent_label']['enum'][-1] == 'CLARIFY'
    import json
    assert json.loads(provider.requests[0]['contents'][0]['parts'][0]['text']) == REQUEST


@pytest.mark.parametrize('provider,reason', [
    (Provider(delay=5), 'PROVIDER_TIMEOUT'),
    (Provider(error=GeminiError('GEMINI_UNAVAILABLE')), 'PROVIDER_ERROR'),
])
def test_fallback_failures_never_invent_a_label(provider, reason, decided):
    checked = run_fallback(provider, decided, timeout=0.2)
    assert (checked['label'], checked['reason']) == (None, reason)


def test_fallback_respects_the_request_budget(decided):
    limits = Limits.load()
    budget = Budget(limits)
    left = limits.max_total_tokens
    while left >= limits.max_output_tokens:  # use up the whole budget, within the per-call input limit
        size = min(limits.max_input_tokens, left - limits.max_output_tokens)
        budget.reserve(size)
        left -= size + limits.max_output_tokens
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x'})
    checked = run_fallback(provider, decided, budget)
    assert (checked['label'], checked['reason']) == (None, 'BUDGET_EXCEEDED') and provider.requests == []
