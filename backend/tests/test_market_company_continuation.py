import asyncio
from datetime import date
import pytest
from src.retrieval_orchestration.live_research import analyze_live
from tests.test_market_dialogue import engine

TODAY=date(2026,11,20)


@pytest.mark.parametrize('symbol',['VCB','BID','CTG','MBB','TCB','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('wording',['thế còn {} sao','còn {} thì sao','đổi sang {}','thế còn {}'])
def test_company_switch_retains_price_subject_and_calendar_day(symbol,wording):
    first=analyze_live('Giá FPT hôm nay',today=TODAY)
    second=analyze_live(wording.format(symbol),first['scope'],today=TODAY)
    assert second['decision']=='MARKET_LOOKUP'
    assert second['scope']['companies']==[symbol]
    assert second['scope']['source_type']=='PRICE'
    assert second['scope']['_market_request']['day']==first['scope']['_market_request']['day']


def test_complete_new_question_does_not_reuse_price_subject():
    first=analyze_live('Giá FPT hôm nay',today=TODAY)
    second=analyze_live('Tổng tài sản VCB quý 2/2026',first['scope'],today=TODAY)
    assert second['scope']['source_type']=='BCTC'
    assert second['scope']['metric_code']=='TOTAL_ASSETS'


def test_same_company_switch_without_prior_subject_cannot_invent_price():
    assert analyze_live('thế còn VCB sao',today=TODAY)['decision']!='MARKET_LOOKUP'


def test_service_uses_price_for_the_actual_screenshot_followup():
    async def run():
        service=engine()
        first=await service.answer('Giá FPT hôm nay','test',today=TODAY)
        second=await service.answer('thế còn VCB sao','test',first['scope'],previous_result=first,today=TODAY)
        assert second['scope']['companies']==['VCB']
        assert second['scope']['source_type']=='PRICE'
        assert second['reason_code'] not in ('MISSING_METRIC','MULTIPLE_METRICS')
    asyncio.run(run())
