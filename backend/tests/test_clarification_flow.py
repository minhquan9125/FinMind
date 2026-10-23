"""Ambiguity must offer concrete choices, retain slots and stop unproductive loops."""
import asyncio
import copy
from uuid import uuid4

import pytest

from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.web_sessions import SessionStore
from tests.test_live_research import Retriever


def test_debt_repeat_offers_relevant_choices_and_accepts_short_answer():
    first = analyze_live('nợ của fpt trong quý 2 2026 là bao nhiêu')
    assert first['decision'] == 'ASK_CLARIFICATION'
    assert first['scope']['companies'] == ['FPT']
    assert first['scope']['periods'] == ['2026-Q2']
    assert 'nợ' in first['message'].lower()
    assert first['clarification_options']
    repeated = analyze_live('nợ', first['scope'])
    assert repeated['message'] != first['message']
    chosen = analyze_live('tổng', repeated['scope'])
    assert chosen['decision'] == 'SEARCH'
    assert chosen['scope']['metric_code'] == 'TOTAL_LIABILITIES'
    assert chosen['scope']['companies'] == ['FPT']
    assert chosen['scope']['periods'] == ['2026-Q2']
    assert chosen['scope']['measure_basis'] == 'POINT_IN_TIME'


def test_borrowing_followup_never_silently_means_all_liabilities():
    first = analyze_live('nợ FPT quý 2/2026')
    loan = analyze_live('nợ vay', first['scope'])
    assert loan['decision'] == 'ASK_CLARIFICATION'
    assert 'ngắn hạn' in loan['message'] and 'dài hạn' in loan['message']
    chosen = analyze_live('dài hạn', loan['scope'])
    assert chosen['scope']['metric_code'] == 'LONG_TERM_LOANS_AND_FINANCE_LEASES'
    assert chosen['decision'] == 'SEARCH'


@pytest.mark.parametrize('word,reply,metric', [
    ('nợ', '1', 'TOTAL_LIABILITIES'),
    ('doanh thu', 'thuần', 'NET_REVENUE'),
    ('doanh thu', 'trước giảm trừ', 'GROSS_REVENUE'),
    ('lợi nhuận', 'sau', 'PROFIT_AFTER_TAX'),
    ('vốn', 'điều lệ', 'CHARTER_CAPITAL'),
    ('tài sản', 'tổng', 'TOTAL_ASSETS'),
    ('dòng tiền', 'đầu tư', 'CASH_FLOW_INVESTING'),
    ('dòng tiền', 'tài chính', 'CASH_FLOW_FINANCING'),
])
def test_registered_metric_groups_accept_choices(word, reply, metric):
    first = analyze_live(f'{word} FPT quý 2/2026')
    assert first['decision'] == 'ASK_CLARIFICATION'
    chosen = analyze_live(reply, first['scope'])
    assert chosen['decision'] == 'SEARCH'
    assert chosen['scope']['metric_code'] == metric
    assert chosen['scope']['companies'] == ['FPT']


@pytest.mark.parametrize('question,repeat', [
    ('nợ FPT quý 2/2026', 'nợ'),
    ('doanh thu FPT quý 2/2026', 'doanh thu'),
    ('vốn FPT quý 2/2026', 'vốn'),
    ('nợ', 'nợ'),
    ('tổng tài sản FPT', 'không biết'),
    ('abc xyz', 'abc xyz'),
])
def test_every_unproductive_clarification_is_bounded(question, repeat):
    result = analyze_live(question)
    for _ in range(4):
        result = analyze_live(repeat, result['scope'])
    assert result['decision'] == 'CLARIFICATION_STALLED'
    assert result['reason_code'] == 'CLARIFICATION_STALLED'
    assert result['clarification_options']


def test_state_survives_stall_but_new_group_or_reset_does_not_reuse_choices():
    first = analyze_live('nợ FPT quý 2/2026')
    state = copy.deepcopy(first['scope'])
    stalled = first
    for _ in range(3): stalled = analyze_live('nợ', stalled['scope'])
    resolved = analyze_live('tổng nợ phải trả', stalled['scope'])
    assert resolved['decision'] == 'SEARCH'
    assert '_clarification_state' not in resolved['scope']
    revenue = analyze_live('doanh thu', first['scope'])
    assert analyze_live('thuần', revenue['scope'])['scope']['metric_code'] == 'NET_REVENUE'
    assert first['scope'] == state
    reset = analyze_live('/moi', first['scope'])
    assert reset['scope'] == {}
    assert analyze_live('1', reset['scope'])['decision'] == 'ASK_CLARIFICATION'


def test_each_button_reply_resolves_the_advertised_metric():
    for group in ('nợ', 'doanh thu', 'lợi nhuận', 'tài sản', 'vốn', 'dòng tiền'):
        first = analyze_live(f'{group} FPT quý 2/2026')
        for option in first['clarification_options']:
            result = analyze_live(option['reply'], first['scope'])
            if option.get('metric_code'):
                assert result['scope']['metric_code'] == option['metric_code']
                assert result['decision'] == 'SEARCH'
            else:
                assert result['decision'] == 'ASK_CLARIFICATION'


def test_short_metric_reply_is_remembered_even_before_company_is_known():
    first = analyze_live('nợ quý 2/2026')
    chosen = analyze_live('tổng', first['scope'])
    assert chosen['scope']['metric_code'] == 'TOTAL_LIABILITIES'
    assert chosen['decision'] == 'ASK_CLARIFICATION'
    final = analyze_live('FPT', chosen['scope'])
    assert final['decision'] == 'SEARCH'


def test_multiple_metrics_keep_company_and_period_and_offer_the_actual_choices():
    first = analyze_live('tổng tài sản và doanh thu thuần FPT quý 2/2026')
    assert [o['metric_code'] for o in first['clarification_options']] == ['TOTAL_ASSETS', 'NET_REVENUE']
    second = analyze_live('2', first['scope'])
    assert second['scope']['metric_code'] == 'NET_REVENUE'
    assert second['scope']['periods'] == ['2026-Q2']
    assert second['decision'] == 'SEARCH'


def test_service_level_missing_reference_is_bounded_too():
    async def run():
        retriever = Retriever()
        service = LiveResearchService(retriever)
        context = {}
        for _ in range(4):
            result = await service.answer('nguồn đâu', 'session', context)
            context = result['scope']
        assert result['status'] == 'CLARIFICATION_STALLED'
        assert not retriever.calls
    asyncio.run(run())


def test_switching_between_ambiguous_groups_cannot_keep_clarifying_forever():
    result = analyze_live('nợ FPT quý 2/2026')
    for word in ['doanh thu', 'nợ', 'doanh thu', 'nợ', 'doanh thu', 'nợ', 'doanh thu']:
        result = analyze_live(word, result['scope'])
    assert result['decision'] == 'CLARIFICATION_STALLED'
    assert analyze_live('thuần', result['scope'])['decision'] == 'SEARCH'


def test_publisher_clarification_keeps_original_company_and_date():
    first = analyze_live('tin tức FPT theo CafeF và FireAnt ngày 29/9/2026')
    assert [o['reply'] for o in first['clarification_options']] == ['CafeF', 'FireAnt']
    chosen = analyze_live('CafeF', first['scope'])
    assert chosen['decision'] == 'SEARCH'
    assert chosen['scope']['publisher'] == 'cafef'
    assert chosen['scope']['periods'] == ['2026-09-29']


def test_conflicting_reporting_entity_requires_explicit_choice():
    first = analyze_live('tổng tài sản FPT báo cáo hợp nhất và báo cáo riêng quý 2/2026')
    assert first['decision'] == 'ASK_CLARIFICATION'
    assert first['reason_code'] == 'AMBIGUOUS_REPORTING_ENTITY'
    chosen = analyze_live('riêng', first['scope'])
    assert chosen['decision'] == 'SEARCH'
    assert chosen['scope']['reporting_entity'] == 'PARENT'


def test_session_reload_retains_choice_context_and_no_retrieval_while_ambiguous(tmp_path):
    async def run():
        retriever = Retriever()
        owner = str(uuid4())
        store = SessionStore(tmp_path, engine=LiveResearchService(retriever))
        snap = await store.create(owner)
        sid = snap['session_id']
        snap = await store.send(owner, sid, 'nợ FPT quý 2/2026', 0)
        assert snap['messages'][-1]['result']['clarification_options']
        fresh = SessionStore(tmp_path, engine=LiveResearchService(retriever))
        snap = await fresh.send(owner, sid, 'nợ', 1)
        assert not retriever.calls
        snap = await fresh.send(owner, sid, 'tổng', 2)
        assert retriever.calls[-1][1]['metric_code'] == 'TOTAL_LIABILITIES'
        assert retriever.calls[-1][1]['periods'] == ['2026-Q2']
    asyncio.run(run())
