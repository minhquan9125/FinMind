"""Prevent period/source/budget regressions in the web's real retrieval path."""
import asyncio
from dataclasses import replace

import pytest

from src.retrieval_orchestration.live_research import LiveResearchService, analyze_live
from src.b1_answering.core.policy import Limits
from tests.test_live_research import Retriever, Provider, pack


def test_new_metric_does_not_inherit_news_or_ambiguous_profit():
    scope = analyze_live('tin tức FPT tháng 9/2026')['scope']
    out = analyze_live('tổng tài sản FPT quý 2/2026', scope)
    assert out['scope']['source_type'] == 'BCTC'
    assert out['scope']['periods'] == ['2026-Q2']
    assert analyze_live('/moi', out['scope'])['scope'] == {}


def test_explicit_ytd_is_not_silently_treated_as_standalone_quarter():
    decision = analyze_live('lợi nhuận sau thuế FPT lũy kế quý 2/2026')
    assert decision['scope']['measure_basis'] == 'YTD'


@pytest.mark.parametrize('question', ['tổng tài sản FPT 2026-Q5',
    'tổng tài sản FPT quý 2/2026 hay quý 3/2026', 'nợ của FPT',
    'giá đóng cửa FPT quý 2/2026', 'báo cáo thường niên FPT 2025'])
def test_explicit_unsupported_or_ambiguous_request_does_not_reuse_old_metric(question):
    previous = analyze_live('tiền và tương đương tiền FPT quý 2/2026')['scope']
    assert analyze_live(question, previous)['decision'] != 'SEARCH'


@pytest.mark.parametrize('question', ['tổng tài sản vic năm 2025', 'tiền và tương đương tiền của vic quý 2/2026'])
def test_lowercase_new_ticker_must_replace_previous_company(question):
    previous = analyze_live('tổng tài sản FPT quý 2/2026')['scope']
    assert analyze_live(question, previous)['scope']['companies'] == ['VIC']


def test_metric_words_are_not_treated_as_new_lowercase_tickers():
    previous = analyze_live('tổng tài sản FPT quý 2/2026')['scope']
    assert analyze_live('lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2025', previous)['scope']['companies'] == ['FPT']


def test_explicit_news_publisher_is_retained_as_scope_not_just_query_words():
    decision = analyze_live('Tin tức FPT theo CafeF ngày 29/9/2026')
    assert decision['scope']['publisher'] == 'cafef'
    assert decision['scope']['periods'] == ['2026-09-29']


def test_live_budget_does_not_reset_on_new_question():
    async def run():
        provider = Provider()
        engine = LiveResearchService(Retriever(), provider=provider,
                    limits=replace(Limits.load(), max_generation_calls=1))
        await engine.answer('tiền và tương đương tiền FPT quý 2/2026', 's')
        await engine.answer('/moi', 's')
        result = await engine.answer('tiền và tương đương tiền FPT quý 2/2026', 's')
        assert result['answering']['status'] == 'BUDGET_EXCEEDED'
        assert provider.calls == 1
    asyncio.run(run())


def test_timeout_and_dependency_error_are_not_no_data():
    class Broken:
        async def retrieve(self, *args): raise OSError('private DSN must not escape')
    class Slow:
        async def retrieve(self, *args): await asyncio.sleep(1)
    async def run():
        for adapter in (Broken(), Slow()):
            result = await LiveResearchService(adapter, retrieval_timeout=0.01).answer(
                'tổng tài sản FPT quý 2/2026', 's')
            assert result['status'] == 'SYSTEM_UNAVAILABLE'
            assert 'private' not in str(result)
    asyncio.run(run())
