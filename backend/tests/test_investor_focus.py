import pytest

from src.retrieval_orchestration.investor_focus import (
    FOCUS_LABEL, focus_from_words, is_focus_only, stated_focus,
)
from src.retrieval_orchestration.retrieval_flow.intent import _fold


@pytest.mark.parametrize('text,focus', [
    ('lướt sóng VCB tuần này', 'TECHNICAL'),
    ('toi luot song', 'TECHNICAL'),
    ('RSI và MACD của FPT', 'TECHNICAL'),
    ('vùng hỗ trợ của BID', 'TECHNICAL'),
    ('mua T+3 có kịp không', 'TECHNICAL'),
    ('đầu tư dài hạn', 'FINANCIAL'),
    ('cổ tức VCB', 'FINANCIAL'),
    ('định giá P/E', 'FINANCIAL'),
    ('dau tu gia tri', 'FINANCIAL'),
])
def test_words_pick_focus(text, focus):
    assert focus_from_words(_fold(text)) == focus


@pytest.mark.parametrize('text', [
    'giá trị giao dịch hôm nay', 'hỗ trợ khách hàng', 'cơ bản là vậy', 'ngắn hạn và dài hạn', 'giá VCB hôm nay',
    'có nên mua VCB không', 'nền kinh tế đang phục hồi',
])
def test_ambiguous_or_mixed_words_pick_nothing(text):
    assert focus_from_words(_fold(text)) is None


@pytest.mark.parametrize('text,expected', [
    ('Tôi đầu tư dài hạn', 'FINANCIAL'),
    ('mình hay lướt sóng', 'TECHNICAL'),
    ('Tôi lướt sóng', 'TECHNICAL'),
    ('mình tích sản', 'FINANCIAL'),
    ('em là nhà đầu tư giá trị', 'FINANCIAL'),
    ('phân tích theo hướng ngắn hạn', 'TECHNICAL'),
    ('phân tích chung', 'RESET'),
    ('bỏ hướng đầu tư', 'RESET'),
    ('xu hướng giá VCB', None),
    ('cổ tức VCB năm 2025', None),
])
def test_stated_focus(text, expected):
    assert stated_focus(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('Tôi đầu tư dài hạn', True),
    ('Tôi đầu tư dài hạn, phân tích VCB', False),
    ('mình hay lướt sóng Vietcombank', False),
    ('xu hướng VCB', False),
])
def test_focus_only(text, expected):
    assert is_focus_only(text) is expected


def test_labels():
    assert FOCUS_LABEL == {'TECHNICAL': 'ngắn hạn (kỹ thuật)', 'FINANCIAL': 'dài hạn (cơ bản)'}


# ---- session memory in LiveResearchService.answer ----
import asyncio
import copy

from src.retrieval_orchestration.live_research import LiveResearchService

ACK = ('Đã ghi nhận: các phân tích sau sẽ theo hướng dài hạn (cơ bản). '
       'Muốn đổi, hãy nói “phân tích theo hướng ngắn hạn” hoặc “phân tích chung”.')
LONG = {'focus': 'FINANCIAL', 'source': 'STATED'}


class Turns(LiveResearchService):
    """The real answer() wrapper around a scripted turn: no retrieval, every call recorded."""
    def __init__(self, status='EVIDENCE_READY', reason='SUCCESS'):
        super().__init__(object())
        self.calls, self.status, self.reason = [], status, reason

    async def _answer_turn(self, question, session_id, context=None, *, previous_result=None, today=None):
        self.calls.append((question, copy.deepcopy(context)))
        return dict(status=self.status, reason_code=self.reason, scope={'companies': ['VCB']})


def ask(service, text, context=None):
    return asyncio.run(service.answer(text, 'session', context))


def test_focus_only_message_is_acknowledged_without_retrieval():
    service = Turns()
    result = ask(service, 'Tôi đầu tư dài hạn', {})
    assert result['reason_code'] == 'INVESTOR_FOCUS_SET' and result['message'] == ACK
    assert result['scope']['_investor_focus'] == LONG
    assert service.calls == []


@pytest.mark.parametrize('status,reason', [('ASK_CLARIFICATION', 'MISSING_METRIC'),
                                           ('SYSTEM_UNAVAILABLE', 'GRAPH_CHAT_UNAVAILABLE')])
def test_focus_survives_following_turns(status, reason):
    result = ask(Turns(status, reason), 'Phân tích VCB', {'_investor_focus': LONG})
    assert result['scope']['_investor_focus'] == LONG


def test_reset_clears_focus():
    service = Turns()
    result = ask(service, 'phân tích chung', {'_investor_focus': LONG, 'companies': ['VCB']})
    assert result['reason_code'] == 'INVESTOR_FOCUS_CLEARED'
    assert result['message'] == 'Đã bỏ hướng đầu tư đã ghi nhận; các phân tích sau sẽ trình bày chung.'
    assert '_investor_focus' not in result['scope'] and service.calls == []


def test_statement_with_question_answers_with_that_focus():
    service = Turns()
    result = ask(service, 'Tôi đầu tư dài hạn, phân tích VCB', {})
    assert result['reason_code'] != 'INVESTOR_FOCUS_SET'
    assert service.calls[0][1]['_investor_focus'] == LONG       # the turn already sees the stated style
    assert result['scope']['_investor_focus'] == LONG


def test_advice_still_refused_but_focus_kept():
    result = ask(Turns('UNSUPPORTED', 'INTENT_OUT_OF_SCOPE'), 'Tôi lướt sóng, có nên mua VCB không?', {})
    assert result['reason_code'] == 'INTENT_OUT_OF_SCOPE'
    assert result['scope']['_investor_focus'] == {'focus': 'TECHNICAL', 'source': 'STATED'}


# ---- final review findings (C1, C2, I1, I2, I3, I4) ----
@pytest.mark.parametrize('text', [
    # C1: "chứng" folds to "chung"
    'Phân tích chứng khoán VCB', 'phân tích chứng khoán hôm nay',
    # C2: questions that use a metric word after "tôi muốn/thích"
    'Tôi muốn biết cổ tức', 'tôi muốn hỏi về nợ xấu của ngân hàng', 'Tôi muốn xem định giá',
    'anh muốn xem phân tích kỹ thuật', 'tôi thích cổ phiếu trả cổ tức cao',
    # I1: "chỉ", "hãy", "theo dõi", holdings are not a stated style
    'chỉ số P/E theo quý của VCB', 'em hãy phân tích kỹ thuật VCB', 'Tôi theo dõi RSI của VCB', 'tôi nắm giữ VCB',
    # I2: negation
    'Tôi không lướt sóng', 'tôi không đầu tư ngắn hạn',
])
def test_questions_and_negations_state_no_style(text):
    assert stated_focus(text) is None


@pytest.mark.parametrize('text', ['Tôi lướt sóng, thị trường hôm nay thế nào?',
                                  'Tôi đầu tư dài hạn, vậy cổ phiếu này thế nào?',
                                  'Tôi đầu tư dài hạn, ngân hàng ngoại thương thì sao',
                                  'Tôi đang đầu tư dài hạn nhé'])
def test_focus_only_needs_nothing_left_but_the_statement(text):
    assert is_focus_only(text) is (text == 'Tôi đang đầu tư dài hạn nhé')


def test_question_after_a_statement_is_asked_without_the_style_clause():
    service = Turns()
    result = ask(service, 'Tôi đang đầu tư dài hạn, phân tích VCB', {})
    assert service.calls[0][0] == 'phân tích VCB'
    assert result['scope']['_last_question'] == 'phân tích VCB'
    assert result['scope']['_investor_focus'] == LONG


def test_advice_question_after_a_statement_still_reaches_the_gate():
    service = Turns('UNSUPPORTED', 'INTENT_OUT_OF_SCOPE')
    result = ask(service, 'Tôi lướt sóng, có nên mua không?', {})
    assert service.calls[0][0] == 'có nên mua không?' and result['reason_code'] == 'INTENT_OUT_OF_SCOPE'


def test_reset_words_inside_a_question_clear_the_style_and_still_answer():
    service = Turns()
    result = ask(service, 'phân tích chung VCB', {'_investor_focus': LONG})
    assert service.calls[0][0] == 'phân tích chung VCB'
    assert '_investor_focus' not in service.calls[0][1] and '_investor_focus' not in result['scope']


def test_reset_with_nothing_stored_is_a_normal_question():
    service = Turns()
    ask(service, 'phân tích chung', {})
    assert service.calls and service.calls[0][0] == 'phân tích chung'
