"""05.1/07.2: the v2 intent decides only where the chat rules would ask again; failures keep today's behaviour."""
import asyncio
import json
import time

from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.market_research import MarketResearch
from tests.test_market_research import NOW, Live, News, Repository

POLICY = 'intent-request-objectives-v2-11-r2'


def classifier(label, reason='EXPLICIT_REQUEST_TYPE', restricted=False, error=None, delay=0):
    calls = []

    def classify(question, context=None):
        calls.append(question)
        if delay:
            time.sleep(delay)
        if error:
            raise error
        return {'resolution': {'intent_label': label, 'reason': reason, 'status': 'PROPOSED', 'component_labels': [],
                               'contains_restricted_component': restricted, 'unresolved_requests': [],
                               'ranking_policy': POLICY}}
    classify.calls = calls
    return classify


class Provider:
    """Answers the intent fallback with `intent`, and grounded answers with the first evidence line."""
    def __init__(self, intent=None):
        self.intent, self.fallback_calls = intent, 0

    async def count_tokens(self, request):
        return 100

    async def generate(self, request):
        usage = {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}
        if 'intent_label' in json.dumps(request['generationConfig'].get('responseJsonSchema', {})):
            self.fallback_calls += 1
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


def test_rule_detected_out_of_scope_is_refused_before_any_search():
    result = ask('fpt tuần sau lên bao nhiêu', classifier('OUT_OF_SCOPE', restricted=True), admin_news=NoAdminNews())
    assert result['status'] == 'UNSUPPORTED' and result['reason_code'] == 'INTENT_OUT_OF_SCOPE'
    assert result['intent'] == {'label': 'OUT_OF_SCOPE', 'decision': 'REFUSE', 'source': 'RULES', 'applied': True}


def test_rule_detected_analysis_replaces_the_metric_question():
    result = ask('vì sao fpt giảm', classifier('ANALYSIS'))
    assert result['scope']['source_type'] == 'MARKET_ANALYSIS' and result['scope']['companies'] == ['FPT']
    assert result['intent']['applied'] is True and result['intent']['source'] == 'RULES'


def test_a_guess_is_confirmed_by_gemini_before_it_is_used():
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .9, 'reason': 'hỏi định giá'})
    result = ask('fpt đang đắt hay rẻ', classifier('ANALYSIS', 'CLASSIFIER_PROPOSAL'), provider)
    assert provider.fallback_calls == 1
    assert result['scope']['source_type'] == 'MARKET_ANALYSIS'
    assert result['intent'] == {'label': 'ANALYSIS', 'decision': 'FALLBACK', 'source': 'GEMINI', 'applied': True}


def test_an_unconfident_fallback_keeps_the_clarification():
    provider = Provider({'intent_label': 'PHAN_TICH', 'confidence': .4, 'reason': 'không chắc'})
    result = ask('fpt đang đắt hay rẻ', classifier('ANALYSIS', 'CLASSIFIER_PROPOSAL'), provider)
    assert result['status'] == 'ASK_CLARIFICATION'
    assert result['intent']['applied'] is False and result['intent']['reason'] == 'LOW_PROVIDER_CONFIDENCE'


def test_a_question_the_rules_already_route_never_calls_gemini():
    provider = Provider({'intent_label': 'GIA', 'confidence': .9, 'reason': 'x'})
    result = ask('giá fpt hôm nay', classifier('PRICE', 'CLASSIFIER_PROPOSAL'), provider)
    assert provider.fallback_calls == 0 and result['scope']['source_type'] == 'PRICE'
    assert result['intent']['applied'] is False


def test_classifier_errors_and_timeouts_leave_the_chat_unchanged(monkeypatch):
    import src.retrieval_orchestration.live_research as live
    monkeypatch.setattr(live, 'INTENT_TIMEOUT_SECONDS', 0.2)
    for classify in (classifier('ANALYSIS', error=RuntimeError('model not ready')), classifier('ANALYSIS', delay=1)):
        result = ask('vì sao fpt giảm', classify)
        assert result['status'] == 'ASK_CLARIFICATION' and result['intent'] is None


def test_without_a_classifier_nothing_changes():
    result = ask('vì sao fpt giảm', None)
    assert result['status'] == 'ASK_CLARIFICATION' and 'intent' not in result
