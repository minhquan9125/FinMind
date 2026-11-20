import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from src.retrieval_orchestration.live_research import LiveResearchService,analyze_live
from src.retrieval_orchestration.context_policy import question_context

TODAY=date(2026,11,20)


@pytest.mark.parametrize('source',['PRICE','MARKET_ANALYSIS','NEWS','BCTN','BCTC'])
@pytest.mark.parametrize('noise',['dcádá','asdasd','qwerty','asdf qwer zxcv','@@@'])
def test_unknown_input_cannot_trigger_old_answer_or_call_models(source,noise):
    old=dict(companies=['ITD'],source_type=source,metric_code='LAST_PRICE',periods=['2026-11-20'],
        _market_request={'kind':'ANALYSIS','day':'2026-11-20','action':'ANALYSIS'},_last_question='Phân tích ITD')
    retriever=SimpleNamespace(retrieve=AsyncMock())
    market=SimpleNamespace(lookup=AsyncMock())
    router=SimpleNamespace(answer=AsyncMock())
    classifier=AsyncMock()
    engine=LiveResearchService(retriever,market=market,hybrid_router=router,intent_classifier=classifier)
    result=asyncio.run(engine.answer(noise,'test',old,today=TODAY))
    assert result['reason_code']=='UNRECOGNIZED_QUESTION'
    assert result['evidence_pack'] is None
    assert result.get('answering') is None
    retriever.retrieve.assert_not_called()
    market.lookup.assert_not_called()
    router.answer.assert_not_called()
    classifier.assert_not_called()


def test_ambiguous_which_stock_question_does_not_default_to_itd():
    old=analyze_live('Phân tích ITD',today=TODAY)['scope']
    cleaned=question_context('dạo này mã chi ngon',old,TODAY)
    assert not cleaned.get('companies')
    result=analyze_live('dạo này mã chi ngon',old,today=TODAY)
    assert 'ITD' not in result['scope'].get('companies',[])
    assert result['decision']=='ASK_CLARIFICATION'


def test_valid_short_company_continuation_still_works():
    old=analyze_live('Phân tích ITD',today=TODAY)['scope']
    assert analyze_live('còn VCB sao',old,today=TODAY)['scope']['companies']==['VCB']
