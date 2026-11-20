import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.stored_news import render_stored_news


def test_body_excerpt_and_missing_body_are_distinguished():
    item=dict(title='Tin VCB',passage='VCB công bố kết quả hoạt động và thông tin tài chính trong kỳ báo cáo. Nội dung được lưu trong kho.',
              stored_news=dict(published_at='2026-11-19T08:00:00+07:00'))
    assert item['passage'] in render_stored_news([item])
    item['passage']='Tin VCB\nNgày đăng: 2026-11-19'
    assert 'chưa có đoạn nội dung đủ' in render_stored_news([item])


@pytest.mark.parametrize('symbol',['BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB'])
def test_latest_news_reads_pipeline_database_without_live_feed_or_ai(symbol):
    market=type('Market',(),{'lookup':AsyncMock(side_effect=AssertionError('No live fetch'))})()
    router=type('Router',(),{'answer':AsyncMock(side_effect=AssertionError('No live router'))})()
    admin=type('Admin',(),{'answer':AsyncMock(side_effect=AssertionError('No article selection by ticker'))})()
    service=LiveResearchService(object(),market=market,hybrid_router=router,admin_news=admin)
    stored=AsyncMock(return_value=dict(items=[]))
    with patch('src.retrieval_orchestration.stored_news.latest_news',stored):
        result=asyncio.run(service.answer(f'Tin tức {symbol} mới nhất','test'))
    assert result['reason_code']=='NO_STORED_NEWS'
    assert stored.call_args.args[1]['companies']==[symbol]
    market.lookup.assert_not_called()
    router.answer.assert_not_called()
    admin.answer.assert_not_called()


def test_database_failure_never_falls_back_to_external_news():
    market=type('Market',(),{'lookup':AsyncMock(side_effect=AssertionError('No live fallback'))})()
    with patch('src.retrieval_orchestration.stored_news.latest_news',AsyncMock(side_effect=RuntimeError('private'))):
        result=asyncio.run(LiveResearchService(object(),market=market).answer('Tin tức FPT mới nhất','test'))
    assert result['status']=='SYSTEM_UNAVAILABLE'
    assert 'private' not in str(result)
    market.lookup.assert_not_called()


def test_list_does_not_present_publication_day_as_crawl_time_or_realtime():
    draft=render_stored_news([dict(title='FPT công bố báo cáo',stored_news=dict(published_at='2026-10-29T12:00:00+07:00'))])
    assert '29/10/2026' in draft
    assert 'không lấy tin trực tiếp' in draft
    assert 'Ngày cập nhật: 29/10/2026' not in draft
