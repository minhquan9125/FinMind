"""05.1/07.2: the v2 intent decides only where the chat rules would ask again; failures keep today's behaviour.

Classifications come from Nhân's real IntentClassifier (fake encoder picks the model guess), so Huyền's
04.2 v2 contract re-checks the same rule evidence the chat sees in production.
"""
import asyncio
import json
import time

from src.retrieval_orchestration.intent_v2_classifier import IntentClassifier
from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.market_research import MarketResearch
from tests.test_market_research import NOW, Live, News, Repository
from tests.test_s5_intent_v2_runtime import Encoder, artifact  # noqa: F401  (pytest fixture)


def classifier(artifact, guess='NUMERIC', error=None, delay=0, change=None):  # noqa: F811
    model, calls = IntentClassifier.load(artifact, Encoder(guess)), []

    def classify(question, context=None):
        calls.append(question)
        if delay:
            time.sleep(delay)
        if error:
            raise error
        result = model.classify(question)
        if change:
            result['resolution'].update(change)
        return result
    classify.calls = calls
    return classify


class Provider:
    """Answers the intent fallback with `intent`, and grounded answers with the first evidence line."""
    def __init__(self, intent=None):
        self.intent, self.fallback_calls, self.requests = intent, 0, []

    async def count_tokens(self, request):
        return 100

    async def generate(self, request):
        usage = {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}
        if 'intent_label' in json.dumps(request['generationConfig'].get('responseJsonSchema', {})):
            self.fallback_calls += 1
            self.requests.append(json.loads(request['contents'][0]['parts'][0]['text']))
            return {'model_version': 'fake', 'usage': usage, 'payload': self.intent}
        item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
        line = item['passage'].splitlines()[0]
        return {'model_version': 'fake', 'usage': usage, 'payload': {'claims': [
            {'text': line, 'evidence_ids': [item['evidence_id']], 'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': line}]}]}}


class NoAdminNews:
    async def answer(self, *args, **kwargs):
        raise AssertionError('a refused question must not reach the news search')


def ask(question, classify, provider=None, admin_news=None):
    engine = LiveResearchService(object(), provider=provider or Provider(), admin_news=admin_news,
                                 market=MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW),
                                 intent_classifier=classify)
    return asyncio.run(engine.answer(question, 'session', today=NOW.date()))


def test_rule_detected_out_of_scope_is_refused_before_any_search(artifact):
    result = ask('fpt tuần sau lên bao nhiêu', classifier(artifact), admin_news=NoAdminNews())
    assert result['status'] == 'UNSUPPORTED' and result['reason_code'] == 'INTENT_OUT_OF_SCOPE'
    assert result['intent'] == {'label': 'OUT_OF_SCOPE', 'decision': 'REFUSE', 'source': 'RULES', 'applied': True}


def test_rule_detected_analysis_replaces_the_metric_question(artifact):
    result = ask('vì sao fpt giảm', classifier(artifact))
    assert result['scope']['source_type'] == 'MARKET_ANALYSIS' and result['scope']['companies'] == ['FPT']
    assert result['intent'] == {'label': 'ANALYSIS', 'decision': 'SEARCH', 'source': 'RULES', 'applied': True}


def test_a_guess_is_confirmed_by_gemini_before_it_is_used(artifact):
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'chỉ báo kỹ thuật'})
    result = ask('rsi của fpt', classifier(artifact, 'ANALYSIS'), provider)
    assert provider.fallback_calls == 1
    # Huyền's 07.1 wire: three keys, the chat-verified company, no history.
    assert provider.requests[0]['conversation_scope'] == {'company_ticker': 'FPT', 'period': None}
    assert set(provider.requests[0]) == {'question', 'conversation_scope', 'allowed_labels'}
    assert result['scope']['source_type'] == 'MARKET_ANALYSIS'
    assert result['intent'] == {'label': 'ANALYSIS', 'decision': 'NEED_FALLBACK', 'source': 'AI', 'applied': True}


def test_an_unconfident_fallback_keeps_the_clarification(artifact):
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .4, 'reason': 'không chắc'})
    result = ask('rsi của fpt', classifier(artifact, 'ANALYSIS'), provider)
    assert result['status'] == 'ASK_CLARIFICATION'
    assert result['intent']['applied'] is False and result['intent']['reason'] == 'LOW_PROVIDER_CONFIDENCE'


def test_gemini_cannot_name_another_company(artifact):
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'x', 'extracted_company': 'MBB'})
    result = ask('rsi của fpt', classifier(artifact, 'ANALYSIS'), provider)
    assert result['status'] == 'ASK_CLARIFICATION' and result['intent']['reason'] == 'COMPANY_SCOPE_CONFLICT'


def test_a_question_the_rules_already_route_never_calls_gemini(artifact):
    provider = Provider({'intent_label': 'GIA', 'confidence': .9, 'reason': 'x'})
    result = ask('giá fpt hôm nay', classifier(artifact, 'NEWS'), provider)
    assert provider.fallback_calls == 0 and result['scope']['source_type'] == 'PRICE'
    assert result['intent']['applied'] is False


def test_classifier_errors_and_timeouts_leave_the_chat_unchanged(artifact, monkeypatch):
    import src.retrieval_orchestration.live_research as live
    monkeypatch.setattr(live, 'INTENT_TIMEOUT_SECONDS', 0.2)
    for classify in (classifier(artifact, error=RuntimeError('model not ready')), classifier(artifact, delay=1)):
        result = ask('vì sao fpt giảm', classify)
        assert result['status'] == 'ASK_CLARIFICATION' and result['intent'] is None


def test_forged_rule_evidence_is_ignored(artifact):
    # Huyền's contract re-checks the rules: a resolution claiming evidence the question lacks is dropped.
    result = ask('vì sao fpt giảm', classifier(artifact, change={'explicit_evidence': []}))
    assert result['status'] == 'ASK_CLARIFICATION' and result['intent'] is None


def test_without_a_classifier_nothing_changes():
    result = ask('vì sao fpt giảm', None)
    assert result['status'] == 'ASK_CLARIFICATION' and 'intent' not in result


def test_valuation_wording_is_analysis_not_a_price_quote():
    result = ask('fpt định giá thế nào', None)
    assert result['scope']['source_type'] == 'MARKET_ANALYSIS'


def test_company_overview_label_opens_the_company_profile(artifact):
    result = ask('fpt là công ty gì', classifier(artifact))
    assert result['scope']['source_type'] == 'COMPANY_PROFILE' and result['scope']['companies'] == ['FPT']
    assert result['intent']['applied'] is True
