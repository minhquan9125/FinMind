import asyncio,copy
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from src.retrieval_orchestration.conditional_assessment import assessment_request,attach_assessment
from src.retrieval_orchestration.live_research import LiveResearchService

TODAY=date(2026,11,20)


@pytest.mark.parametrize('symbol',['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('question',['Vậy nếu mua {symbol} thì có được không?','Có nên mua {symbol} không?','Bán {symbol} lúc này có ổn không?'])
def test_direct_decision_questions_use_the_isolated_assessment_route(symbol,question):
    req=assessment_request(question.format(symbol=symbol))
    assert req and req['companies']==[symbol] and not req['blocked']


@pytest.mark.parametrize('question',[
    'Tổng tài sản FPT quý 2/2026','Ai là Chủ tịch FPT?',
    'FPT mua lại cổ phiếu quỹ bao nhiêu?',
    'Theo bài báo, FPT mua công ty nào?',
    'FPT bán vốn theo thông báo nào?',
    'FPT có mua ABC không?',
    'FPT mua công ty ABC có được không?',
    'Tin FPT mua ABC có đúng không?',
    'FPT bán sản phẩm này được không?',
    'Bạn có biết FPT kinh doanh gì không?',
    'Bạn xem giúp tổng quan FPT được không?',
    'Dạo này mã nào ngon?',
    'Có nên mua FPT ngày 01/01/2025 không?',
])
def test_other_functions_are_not_intercepted(question):
    assert assessment_request(question) is None


@pytest.mark.parametrize('question',[
    'Có nên mua FPT để chắc chắn lãi không?',
    'Có nên mua FPT bằng margin không?',
    'Có nên mua FPT với tỷ trọng 80% không?',
])
def test_the_new_route_does_not_allow_promises_or_position_sizing(question):
    assert assessment_request(question)['blocked']


def result(label='UP',cited=True):
    return {'scope':{'companies':['FPT']},'evidence_pack':{'items':[{
        'evidence_id':'trend','source_type':'PRICE_TREND','snapshot':{'trend':{'source':{'approval_status':'APPROVED'},'horizons':{
            '20':{'label':label},'200':{'label':'DOWN'}}}}}]},
        'answering':{'status':'DRAFT_READY','draft':'Các dữ kiện đã xác minh.',
            'claims':[{'text':'fact','evidence_ids':['trend']}],
            'citations':[{'evidence_id':'trend','citation_number':1}] if cited else [],'manifest':{}}}


@pytest.mark.parametrize('side,label,word',[('BUY','UP','danh sách cân nhắc'),('BUY','DOWN','Ưu tiên theo dõi'),('SELL','DOWN','rà soát lại rủi ro')])
def test_guidance_is_labelled_and_reuses_citations_without_altering_factual_claims(side,label,word):
    value=result(label);claims=copy.deepcopy(value['answering']['claims'])
    out=attach_assessment(value,{'side':side,'horizon':'UNSPECIFIED'})
    assert word in out['answering']['draft']
    assert 'Nhận định có điều kiện' in out['answering']['draft']
    assert '[1]' in out['answering']['draft']
    assert out['answering']['claims']==claims
    assert out['answering']['conditional_assessment']['basis_evidence_ids']==['trend']


def test_an_uncited_trend_cannot_support_a_conclusion():
    out=attach_assessment(result(cited=False),{'side':'BUY','horizon':'SHORT'})
    assert out['answering']['conditional_assessment']['basis_evidence_ids']==[]
    assert 'Chưa đủ cơ sở' in out['answering']['conditional_assessment']['text']


def test_unreviewed_trend_does_not_become_a_positive_buy_assessment():
    value=result('UP')
    value['evidence_pack']['items'][0]['snapshot']['trend']['source']['approval_status']='PENDING'
    out=attach_assessment(value,{'side':'BUY','horizon':'SHORT'})
    assert out['answering']['conditional_assessment']['basis_evidence_ids']==[]
    assert 'Chưa đủ cơ sở' in out['answering']['conditional_assessment']['text']
    assert 'chưa được xác nhận đã duyệt' in out['answering']['draft']


def test_no_validated_answer_means_no_assessment():
    value={'scope':{'companies':['FPT']},'status':'NO_DATA'}
    assert attach_assessment(value,{'side':'BUY','horizon':'SHORT'})==value


def test_service_collects_facts_before_attaching_guidance_and_keeps_other_routes_out():
    engine=LiveResearchService(object(),intent_classifier=lambda *args:pytest.fail('trade should use its own scoped route'))
    market=AsyncMock(return_value=result())
    engine._answer_market=market
    out=asyncio.run(engine.answer('vậy nếu mua FPT thì có được không','test',today=TODAY))
    assert market.await_count==1
    assert market.call_args.args[0]=='Phân tích FPT'
    assert out['answering']['conditional_assessment']['side']=='BUY'


def test_company_clarification_is_retained_for_the_next_reply():
    engine=LiveResearchService(object())
    first=asyncio.run(engine.answer('Có nên mua không?','test',today=TODAY))
    assert first['reason_code']=='ASSESSMENT_COMPANY_REQUIRED'
    req=assessment_request('FPT',first['scope'])
    assert req['side']=='BUY' and req['companies']==['FPT']


def test_time_horizon_reply_continues_only_an_existing_assessment():
    context={'_assessment_request':{'side':'BUY','companies':['FPT'],'horizon':'UNSPECIFIED','blocked':False}}
    assert assessment_request('dài hạn',context)['horizon']=='LONG'
    assert assessment_request('dài hạn') is None


def test_full_market_and_citation_pipeline_precedes_the_assessment(monkeypatch):
    import json
    from tests.test_market_research import trend_snapshot,NOW
    from src.b1_answering.evidence.market_contract import feed_pack
    snapshot=trend_snapshot()
    snapshot['trend']['source']['approval_status']='APPROVED'
    pack=feed_pack([snapshot])
    class Provider:
        calls=0
        async def count_tokens(self,request):return 200
        async def generate(self,request):
            self.calls+=1
            body=json.loads(request['contents'][0]['parts'][0]['text'])
            assert body['question']=='Phân tích FPT'
            item=body['evidence'][0]
            quote=next(line for line in item['passage'].splitlines() if 'Ngắn hạn:' in line)
            return dict(model_version='test',usage=dict(input_tokens=200,output_tokens=40,total_tokens=240),
                payload={'claims':[dict(text='Xu hướng giá: '+quote,evidence_ids=[item['evidence_id']],
                    support_quotes=[{'evidence_id':item['evidence_id'],'quote':quote}])]})
    async def news(*args):return {**pack,'items':[]}
    monkeypatch.setattr('src.retrieval_orchestration.stored_news.latest_news',news)
    market=SimpleNamespace(lookup=AsyncMock(return_value={'status':'EVIDENCE_READY','reason_code':'TEST_MARKET',
        'message':'Test facts','evidence_pack':pack}))
    provider=Provider()
    service=LiveResearchService(object(),market=market,provider=provider)
    out=asyncio.run(service.answer('mua FPT thì có được không','test',today=NOW.date()))
    assert provider.calls==1
    assert out['answering']['status']=='DRAFT_READY'
    assert out['answering']['citations']
    assert out['answering']['conditional_assessment']['basis_evidence_ids']
    assert 'Nhận định có điều kiện' in out['answering']['draft']


def test_invalid_model_wording_uses_exact_verified_source_without_another_call():
    from tests.test_market_research import trend_snapshot
    from src.b1_answering.evidence.market_contract import feed_pack
    from src.retrieval_orchestration.conditional_assessment import recover_source_facts
    snapshot=trend_snapshot();snapshot['trend']['source']['approval_status']='APPROVED'
    pack=feed_pack([snapshot])
    original={'scope':{'companies':['FPT'],'source_type':'MARKET_ANALYSIS'},'evidence_pack':pack,
        'answering':{'status':'INSUFFICIENT_EVIDENCE','reason_code':'UNSUPPORTED_CLAIM','trace':[]}}
    out=recover_source_facts(original,{'side':'BUY','horizon':'SHORT'})
    assert out['answering']['status']=='DRAFT_READY'
    assert out['answering']['reason_code']=='ASSESSMENT_SOURCE_FACTS'
    assert out['answering']['citations']
    for claim in out['answering']['claims']:
        for support in claim['support_quotes']:
            assert support['quote'] in pack['items'][0]['passage']
    out=attach_assessment(out,{'side':'BUY','horizon':'SHORT'})
    assert out['answering']['conditional_assessment']['basis_evidence_ids']


def test_changed_source_is_not_recovered_as_an_assessment():
    from tests.test_market_research import trend_snapshot
    from src.b1_answering.evidence.market_contract import feed_pack
    from src.retrieval_orchestration.conditional_assessment import recover_source_facts
    pack=feed_pack([trend_snapshot()]);pack['items'][0]['passage']+=' forged'
    original={'scope':{'companies':['FPT'],'source_type':'MARKET_ANALYSIS'},'evidence_pack':pack,
        'answering':{'status':'INSUFFICIENT_EVIDENCE','reason_code':'UNSUPPORTED_CLAIM'}}
    out=recover_source_facts(original,{'side':'BUY','horizon':'SHORT'})
    assert out['answering']['status']=='INSUFFICIENT_EVIDENCE'

@pytest.mark.parametrize('symbol',['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('prefix',['mà nếu giờ tôi mua','mà bạn nghĩ tôi mua','mà cho tôi hỏi mua'])
def test_conversational_ma_is_not_an_extra_stock(symbol,prefix):
    req=assessment_request(f'{prefix} {symbol} được không')
    assert req['companies']==[symbol]


def test_explicit_unknown_ticker_syntax_remains_supported():
    from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver
    for text in ['mã abc','ma abc','cổ phiếu abc','co phieu abc']:
        assert ScopeResolver().resolve(text).scope.companies==['ABC']

def test_full_chat_preprocessing_preserves_explicit_elc_in_conversational_question():
    import asyncio
    from unittest.mock import AsyncMock
    from src.retrieval_orchestration.live_research import LiveResearchService
    service=LiveResearchService(object())
    service._answer_conditional_assessment=AsyncMock(return_value={'status':'TEST'})
    asyncio.run(service.answer('mà nếu giờ tôi mua ELC được không','synthetic-elc'))
    assert service._answer_conditional_assessment.call_args.args[0]['companies']==['ELC']
