import asyncio,copy,json
from unittest.mock import AsyncMock,patch
from uuid import uuid4
import pytest
from src.retrieval_orchestration.conversation_actions import conversation_action
from src.retrieval_orchestration.chat_logic import append_turn,new_document
from src.retrieval_orchestration.conversation_summary import summarize_session,group_summary
from src.retrieval_orchestration.live_research import LiveResearchService
from src.b1_answering.evidence.bundle import bundle_packs
from src.b1_answering.evidence.citations import prepare_evidence,CitationError
from tests.test_s5_wbs093_summary import sourced_result,SequenceEngine
from tests.stored_news_fixture import stored_pack
from tests.test_market_research import MarketResearch,Repository,Live,NOW,quote,article


@pytest.mark.parametrize('text',[
    'Gom những gì vừa nói lại cho tôi','Bạn tóm gọn cuộc trao đổi giúp mình nhé',
    'Tổng hợp chat thành 3 ý chính','Tóm tắt nãy giờ thành một đoạn',
    'vậy giờ tôi cần bạn tổng hợp lại thôi không cần chi tiết từng đoạn chat'])
def test_new_paraphrases_resolve_dialogue_not_research(text):
    assert conversation_action(text) in ('SUMMARY','CONFIRM')


@pytest.mark.parametrize('text',['Tổng hợp chat thành 3 ý chính','Tóm tắt cuộc trao đổi thành một đoạn'])
def test_unsupported_summary_format_asks_before_ignoring_constraint(text):
    assert conversation_action(text)=='CONFIRM'


def test_uncertain_summary_is_confirmed_without_retrieval_and_can_be_cancelled():
    async def run():
        engine=SequenceEngine([])
        doc=new_document(str(uuid4()),str(uuid4()))
        pending=await append_turn(doc,'Tổng hợp đi',engine)
        assert pending['messages'][-1]['result']['reason_code']=='CONFIRM_SESSION_SUMMARY'
        cancelled=await append_turn(pending,'Không',engine)
        assert '_pending_conversation_action' not in cancelled['metadata']['live_context']
        accepted=await append_turn(pending,'Đúng',engine)
        assert accepted['messages'][-1]['result']['reason_code']=='NO_SOURCED_SESSION_ANSWERS'
        assert engine.calls==0
    asyncio.run(run())


@pytest.mark.parametrize('text',['Tổng hợp tin tức FPT hôm nay','Tóm tắt BCTN VCB 2025','Đừng tóm tắt nội dung chat',
    'BIDV dự kiến mua lại trước hạn bao nhiêu tỷ đồng trái phiếu, gồm những mã nào?',
    'Giá trị cốt lõi của BIDV gồm những gì?',
    'Mạng lưới của BIDV đến 31/12/2025 gồm bao nhiêu chi nhánh và phòng giao dịch?'])
def test_new_research_and_negated_actions_not_intercepted(text):
    assert conversation_action(text) is None


def test_summary_keeps_late_conclusion_and_financial_claims_and_all_cautions():
    lines=['Giá: FPT ghi nhận giá trong nguồn.','Xu hướng giá: FPT đang giảm theo dữ liệu.',
           'Tình hình tài chính: FPT ghi nhận kết quả trong báo cáo.',
           'Nhận định tổng hợp: Giá và kinh doanh cần được đánh giá riêng.']
    original=sourced_result(text=' '.join(lines))
    original['scope']['source_type']='MARKET_ANALYSIS'
    item=original['evidence_pack']['items'][0]
    original['answering']['claims']=[dict(text=text,evidence_ids=[item['evidence_id']],
        support_quotes=[dict(evidence_id=item['evidence_id'],quote=text)]) for text in lines]
    original['answering']['cautions']=['Kỳ báo cáo cũ','Thiếu đơn vị','Chưa đối chiếu phạm vi']
    doc=new_document(str(uuid4()),str(uuid4()))
    doc['messages']=[dict(role='assistant',result=original)]
    summary=group_summary(summarize_session(doc))
    assert len(summary['answering']['claims'])==4
    assert all(line in summary['answering']['draft'] for line in lines)
    assert 'Chưa đối chiếu phạm vi' in summary['answering']['draft']


def test_summary_replaces_only_same_company_period_topic_with_latest_answer():
    answers=[sourced_result('FPT','2025','FPT có thông tin cũ.'),
             sourced_result('VCB','2025','VCB có thông tin riêng.'),
             sourced_result('FPT','2024','FPT có thông tin năm trước.'),
             sourced_result('FPT','2025','FPT có thông tin mới.')]
    doc=new_document(str(uuid4()),str(uuid4()))
    doc['messages']=[dict(role='assistant',result=result) for result in answers]
    result=group_summary(summarize_session(doc))
    text=result['answering']['draft']
    assert 'FPT có thông tin cũ.' not in text
    assert 'FPT có thông tin mới.' in text and 'VCB có thông tin riêng.' in text
    assert 'FPT · 2024' in text and 'FPT · 2025' in text


def price_pack(symbol='FPT'):
    payload=quote();payload['symbol']=symbol
    bridge=MarketResearch(Repository(),services=lambda:(Live(payload),None),now=lambda:NOW)
    return bridge._quote(symbol,dict(source_type='PRICE',_market_request={}),Live(payload))['evidence_pack']


def test_bundle_preserves_versions_and_rejects_mutated_items_or_nested_bundles():
    database=stored_pack([article()],dict(companies=['FPT']),'FPT công bố kết quả kinh doanh mới.')
    feed=price_pack()
    combined=bundle_packs([feed,database])
    assert len(prepare_evidence(combined))==2
    assert combined['evidence_packs'][0]['data_version']==feed['data_version']
    assert combined['evidence_packs'][1]['corpus_version_id']==database['corpus_version_id']
    changed=copy.deepcopy(combined);changed['items'][0]['passage']+=' forged'
    with pytest.raises(CitationError): prepare_evidence(changed)
    changed=copy.deepcopy(combined);changed['evidence_packs'][1]['items'][0]['passage']+=' forged'
    with pytest.raises(CitationError): prepare_evidence(changed)
    with pytest.raises(CitationError): bundle_packs([combined])


@pytest.mark.parametrize('symbol',['BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB'])
def test_analysis_gets_database_news_for_right_company_and_date(symbol):
    class Provider:
        async def count_tokens(self,request): return 100
        async def generate(self,request):
            body=json.loads(request['contents'][0]['parts'][0]['text'])
            item=next(item for item in body['evidence'] if item['source_type']=='NEWS')
            text=f'{symbol} công bố kết quả kinh doanh mới.'
            return dict(model_version='fake',usage=dict(input_tokens=100,output_tokens=20,total_tokens=120),
                payload=dict(claims=[dict(text=text,evidence_ids=[item['evidence_id']],support_quotes=[dict(
                    evidence_id=item['evidence_id'],quote=text)])]))
    news=stored_pack([{**article(),'title':f'{symbol} công bố kết quả kinh doanh'}],
        dict(companies=[symbol]),f'{symbol} công bố kết quả kinh doanh mới.')
    market=type('Market',(),{'lookup':AsyncMock(return_value=dict(status='EVIDENCE_READY',
        reason_code='MARKET_ANALYSIS_READY',evidence_pack=price_pack(symbol)))})()
    reader=AsyncMock(return_value=news)
    result=dict(status='MARKET_LOOKUP',execution_mode='LIVE',scope=dict(companies=[symbol],
        source_type='MARKET_ANALYSIS',_market_request=dict(action='ANALYSIS',focus='STOCK',day='2026-10-23')))
    with patch('src.retrieval_orchestration.stored_news.latest_news',reader):
        out=asyncio.run(LiveResearchService(object(),market=market,provider=Provider())._answer_market('phân tích '+symbol,result))
    assert out['answering']['status']=='DRAFT_READY'
    assert out['evidence_pack']['schema_version']=='1.3'
    assert out['answering']['citations'][0]['source_id']==news['items'][0]['source_id']
    assert reader.call_args.args[1]['companies']==[symbol]
    assert reader.call_args.args[1]['_market_request']['as_of']=='2026-10-23'


@pytest.mark.parametrize('text,previous,old,expected', [
    ('Còn BID thì sao?', 'Giá đóng cửa cổ phiếu VCB phiên 13/11/2026 là bao nhiêu?', 'VCB',
     'Giá đóng cửa cổ phiếu BID phiên 13/11/2026 là bao nhiêu?'),
    ('BIDV thì sao?', 'Vietcombank đang giảm lãi suất cho vay bao nhiêu?', 'VCB', 'BID đang giảm lãi suất cho vay bao nhiêu?'),
    ('Còn BIDV cùng kỳ hạn?', 'Lãi suất kỳ 36 tháng của Vietcombank là bao nhiêu?', 'VCB', 'Lãi suất kỳ 36 tháng của BID là bao nhiêu?'),
    ('Nếu gửi 24 tháng thì sao?', 'Gửi 300 triệu ở Vietcombank kỳ 12 tháng?', 'VCB', None),
    ('Còn VCB thì sao?', 'Giá VCB?', 'VCB', None),
])
def test_bare_company_switch_reasks_previous_question(text, previous, old, expected):
    from src.retrieval_orchestration.conversation_actions import company_switch_question
    assert company_switch_question(text, {'_last_question': previous, 'companies': [old]}) == expected
