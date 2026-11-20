"""Regressions from the five member workbooks, without network/model calls."""
import asyncio
import copy
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.retrieval_orchestration.context_policy import question_context
from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.market_dialogue import article_content_request, news_reference
from tests.stored_news_fixture import stored_pack
from tests.test_market_research import article

TODAY = date(2026, 11, 19)


def test_calendar_format_changes_preserve_date_identity_without_relaxing_amounts():
    from src.b1_answering.evidence.grounded import _numbers, _unsupported_numbers
    assert _numbers('Ngày 24/08/2026') == _numbers('Ngày 2026-08-24')
    assert _numbers('01/09/2026') == _numbers('1/9/2026')
    assert _unsupported_numbers('25/08/2026', '2026-08-24')
    assert _unsupported_numbers('31/02/2026', '2026-02-28')
    assert _unsupported_numbers('1,47%', '0.0147')
    assert not _unsupported_numbers('10/2026', 'Ngày đăng 2026-10-12')
    assert not _unsupported_numbers('2026', 'Ngày đăng 2026-10-12')
    assert _unsupported_numbers('2026-10-12', 'Tháng 10/2026')
    assert _unsupported_numbers('11/2026', 'Ngày đăng 2026-10-12')


def test_company_alias_identity_does_not_admit_another_company_or_invented_number():
    from src.b1_answering.evidence.grounded import _check_facts
    from src.b1_answering.evidence.citations import CitationError
    _check_facts('CTIN không có công ty con.', 'ICT | Không có công ty con.')
    _check_facts('BIDV giảm 2%.', 'BID giảm 2%.')
    with pytest.raises(CitationError):_check_facts('CTIN không có công ty con.', 'FPT | Không có công ty con.')
    with pytest.raises(CitationError):_check_facts('BIDV giảm 3%.', 'BID giảm 2%.')


def test_news_claim_can_use_local_publication_date_and_exact_effective_date():
    from src.b1_answering.evidence.citations import prepare_evidence
    from src.b1_answering.evidence.grounded import validate_grounded
    entry = dict(article(), title='ITD bổ nhiệm Giám đốc Tài chính', published_at='2026-08-24T09:00:00+07:00')
    quote = 'Bổ nhiệm Bà Nguyễn Thị Thu Sương giữ chức vụ Giám đốc tài chính từ ngày 01/09/2026.'
    pack = stored_pack([entry], {'companies': ['ITD']}, quote)
    eid = pack['items'][0]['evidence_id']
    payload = {'claims': [{'text': 'Theo thông báo ngày 24/08/2026, ITD bổ nhiệm bà Nguyễn Thị Thu Sương làm Giám đốc tài chính từ ngày 01/09/2026.',
        'evidence_ids': [eid], 'support_quotes': [{'evidence_id': eid, 'quote': quote}]}]}
    assert validate_grounded(payload, prepare_evidence(pack), {'source_type': 'NEWS'})['status'] == 'DRAFT_READY'


def test_news_empty_claims_means_answer_not_stated_not_invalid_citation():
    from src.b1_answering.application.service import complete_retrieval
    class Provider:
        async def count_tokens(self,request):return 100
        async def generate(self,request):
            return {'payload':{'claims':[]},'model_version':'fixture',
                    'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110}}
    pack=stored_pack([article()],{'companies':['FPT']},'Thông báo công bố tệp đính kèm; nội dung trong kho không nêu ngày hiệu lực.')
    result=asyncio.run(complete_retrieval('Ngày có hiệu lực là khi nào?',
        {'status':'EVIDENCE_READY','execution_mode':'LIVE','scope':{'source_type':'NEWS'},'evidence_pack':pack},provider=Provider()))
    assert result['answering']['reason_code']=='NOT_STATED_IN_SOURCE'


def test_report_local_lexical_search_retains_topic_phrase_and_reuses_verified_index(monkeypatch):
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
    from uuid import uuid4
    cid,iid=str(uuid4()),str(uuid4())
    texts = {'cover':'ICT | BCTN 2025\nCông ty không còn khoản phải trả bên liên quan.',
             'answer':'ICT | BCTN 2025\nCác công ty con, công ty liên kết: Không có.'}
    rows=[dict(chunk_id=k,document_id=str(uuid4()),index_version_id=iid,content_hash=k,
               locator_json='{"source_id":"'+k+'"}') for k in texts]
    @asynccontextmanager
    async def transaction(**kwargs):
        assert kwargs['readonly'] is True
        yield
    conn=SimpleNamespace(transaction=transaction,fetch=AsyncMock(return_value=rows))
    @asynccontextmanager
    async def acquire():yield conn
    reader=AsyncMock(side_effect=lambda c,index,loc,digest,cache:texts[loc['source_id']])
    monkeypatch.setattr('src.documents.shared_source.resolve_shared_source',reader)
    retriever=DenseEvidenceRetriever(SimpleNamespace(acquire=acquire),None,corpus_version_id=cid)
    async def run():
        a=await retriever._annual_lexical_rows('Có công ty con không?', {'index_version_id':iid},'ICT','2025')
        b=await retriever._annual_lexical_rows('Công ty liên kết nào?', {'index_version_id':iid},'ICT','2025')
        assert a[0]['chunk_id']=='answer' and a[0]['_phrase_match']
        assert b[0]['chunk_id']=='answer'
    asyncio.run(run())
    assert reader.await_count==len(rows)
    conn.fetch.assert_awaited_once()


@pytest.mark.parametrize(('question', 'symbol', 'source'), [
    ('Theo BCTN 2025, CTIN có công ty con không?', 'ICT', 'BCTN'),
    ('ELCOM dùng AI và dữ liệu lớn trong các lĩnh vực nào theo bài?', 'ELC', 'NEWS'),
    ('Chủ tịch CMC đăng ký mua bao nhiêu cổ phiếu CMG?', 'CMG', 'NEWS'),
    ('BIDV có phương án mua lại trái phiếu trước hạn nào trong năm 2026?', 'BID', 'NEWS'),
    ('MB giảm lãi suất tới 2%/năm cho ai?', 'MBB', 'NEWS'),
    ('BIDV giảm lãi suất cho vay bao nhiêu?', 'BID', 'NEWS'),
    ('Theo BCTN 2025, VCB có bao nhiêu máy ATM?', 'VCB', 'BCTN'),
    ('Theo BCTN 2025, VCB có bao nhiêu PGD và mã SWIFT là gì?', 'VCB', 'BCTN'),
    ('Chiến lược ICT trong BCTN 2025 có nói giảm phụ thuộc vào VNPT không?', 'ICT', 'BCTN'),
    ('Báo cáo quản trị ICT đăng ngày 30/07/2026 bao phủ khoảng thời gian nào?', 'ICT', 'NEWS'),
    ('Tìm tin ICT giải trình LNST trên BCTC bán niên 2026 soát xét.', 'ICT', 'NEWS'),
    ('Theo bài VCB, BCTN 2025 được công bố lúc nào?', 'VCB', 'NEWS'),
    ('Báo cáo CTG nói gì về nhân sự?', 'CTG', 'BCTN'),
    ('CTG123033 bị hủy niêm yết à? Tin trong kho đang thông báo việc gì?', 'CTG', 'NEWS'),
    ('Bài “CTG: HĐQT thông qua hợp đồng bảo hiểm tài sản với VBI” nói gì?', 'CTG', 'NEWS'),
])
def test_member_aliases_and_document_source(question, symbol, source):
    decision = analyze_live(question, today=TODAY)
    assert decision['scope']['companies'] == [symbol]
    assert decision['scope']['source_type'] == source
    assert decision['decision'] in ('SEARCH', 'MARKET_LOOKUP')


@pytest.mark.parametrize('symbol', ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT'])
def test_explicit_news_content_bypasses_graph_and_old_annual_scope(symbol):
    router = SimpleNamespace(answer=AsyncMock(side_effect=AssertionError('Wrong graph route')))
    service = LiveResearchService(object(), hybrid_router=router)
    old = dict(companies=['FPT'], source_type='BCTN', periods=['2025'], _annual_question='old')
    with patch('src.retrieval_orchestration.stored_news.latest_news', AsyncMock(return_value={'items': []})) as read:
        result = asyncio.run(service.answer(f'{symbol} đăng ký mua cổ phiếu bao nhiêu theo tin?', 'test', old, today=TODAY))
    assert result['reason_code'] == 'NO_STORED_NEWS'
    assert read.call_args.args[1]['companies'] == [symbol]
    assert '_annual_question' not in read.call_args.args[1]
    router.answer.assert_not_called()


def test_date_in_article_is_not_publication_day():
    q = 'Theo bài VCB, tổng tài sản tại 30/09/2026 là bao nhiêu?'
    req = article_content_request(q, TODAY)
    assert req['day'] is None
    assert '30/09/2026' in req['query']
    published = article_content_request('Theo tin VCB đăng ngày 02/11/2026, tổng tài sản là bao nhiêu?', TODAY)
    assert published['day'] == '2026-11-02'
    assert '02/11/2026' not in published['query']


@pytest.mark.parametrize('symbol',['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT',
    'BIDV','CTIN','MB','VietinBank','Techcombank','Vietcombank'])
def test_article_date_with_an_intervening_company_is_a_publication_filter(symbol):
    request=article_content_request(f'Theo tin {symbol} ngày 13/08/2026, số cổ phiếu có quyền biểu quyết là bao nhiêu?',TODAY)
    assert request['day']=='2026-08-13'
    assert '13/08/2026'not in request['query']
    effective=article_content_request(f'Theo tin {symbol}, quyết định có hiệu lực từ ngày 13/08/2026 là gì?',TODAY)
    assert effective['day']is None
    assert '13/08/2026'in effective['query']


def test_multiple_companies_in_a_supplied_headline_are_one_article_request():
    value = analyze_live('Cho tôi 3 ý trong bài “Vietcombank, VietinBank, BIDV phát thông báo khẩn đến người dùng iPhone”.', today=TODAY)
    assert value['decision'] == 'MARKET_LOOKUP'
    assert set(value['scope']['companies']) == {'VCB', 'CTG', 'BID'}
    assert value['scope']['_market_request']['action'] == 'DETAIL'
    # Latest-news lists and quotes retain their original single-company bounds.
    assert analyze_live('Tin tức FPT và VCB mới nhất', today=TODAY)['reason_code'] == 'SCOPE_TOO_LARGE'


def test_article_question_about_parent_or_subsidiary_does_not_become_graph_discovery():
    q='Tin bổ nhiệm bà Phan Thị Hải Yến là của Techcombank hay TCBS vậy? Bà ấy giữ chức gì?'
    decision=analyze_live(q,today=TODAY)
    assert decision['decision']=='MARKET_LOOKUP'
    assert decision['scope']['source_type']=='NEWS'
    assert set(decision['scope']['companies'])=={'TCB','TCBS'}


def test_supplied_title_and_publication_month_are_preserved_as_separate_filters():
    q='Bài “CTG: Giấy chứng nhận đăng ký chào bán trái phiếu ra công chúng”: có hiệu lực từ ngày nào?'
    decision=analyze_live(q,today=TODAY)
    assert decision['scope']['_market_request']['query']=='ctg: giay chung nhan dang ky chao ban trai phieu ra cong chung'
    q='VietinBank có thông báo chào bán trái phiếu nào trong tháng 10/2026?'
    decision=analyze_live(q,today=TODAY)
    assert decision['scope']['_market_request']['month']=='2026-10'
    assert decision['scope']['periods']==['2026-10']


def test_vector_turn_does_not_run_a_second_context_free_legacy_router():
    from tests.test_live_research import Retriever,Provider
    legacy=AsyncMock(side_effect=AssertionError('Duplicate routing loses session context'))
    bridge=SimpleNamespace(answer=AsyncMock(return_value=None))
    reader=Retriever()
    engine=LiveResearchService(reader,provider=Provider(),hybrid_router=bridge,route_runner=legacy)
    result=asyncio.run(engine.answer('Tiền và tương đương tiền FPT quý 2/2026?','test'))
    assert result['scope']['source_type']=='BCTC'
    assert reader.calls
    legacy.assert_not_called()


def test_executive_board_question_filters_roles_instead_of_querying_every_relation():
    from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver,position_matches
    scope=ScopeResolver().resolve('Tôi muốn xem ban điều hành CTG theo báo cáo năm 2025, liệt kê kèm chức vụ nhé.').scope
    assert scope.relation_types==['HOLDS_ROLE']
    assert scope.position_code=='EXECUTIVE_BOARD'
    assert position_matches('Tổng Giám đốc','EXECUTIVE_BOARD','CEO')
    assert not position_matches('Chủ tịch HĐQT','EXECUTIVE_BOARD','BOARD_CHAIR')


@pytest.mark.parametrize('question',[
    'Cho mình danh sách tên với chức vụ cụ thể luôn nhé.',
    'Liệt kê tên và chức vụ nhé.',
    'Cho tôi danh sách họ và tên kèm chức danh đi.',
])
def test_role_list_followup_keeps_confirmed_graph_scope(question):
    from src.retrieval_orchestration.conversation_actions import is_list_followup
    from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver,SessionScope
    from src.retrieval_orchestration.live_research import content_fallback_scope
    assert is_list_followup(question)
    prior=SessionScope(companies=['TCB'],periods=['2025'],source_type='BCTN',
        topic='RELATIONSHIP_LOOKUP',operation='find_relationships',route_hint='GRAPH',
        position_code='BOARD_MEMBER',relation_types=['HOLDS_ROLE'],confirmed=True)
    scope=ScopeResolver().resolve(question,prior).scope
    assert scope.companies==['TCB']
    assert scope.periods==['2025']
    assert scope.position_code=='BOARD_MEMBER'
    assert scope.source_type=='BCTN'
    assert content_fallback_scope(question,{'scope':{'companies':['TCB']},'reason_code':'MISSING_METRIC'}) is None


def test_role_list_recognizer_does_not_consume_a_new_explicit_subject():
    from src.retrieval_orchestration.conversation_actions import is_list_followup
    assert not is_list_followup('Liệt kê tên và chức vụ của FPT năm 2024.')


@pytest.mark.parametrize('symbol',['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
def test_explicit_news_request_never_becomes_price_analysis_from_how_wording(symbol):
    prior={'companies':['FPT'],'source_type':'MARKET_ANALYSIS','_market_request':{'kind':'ANALYSIS','action':'ANALYSIS'}}
    decision=analyze_live(f'Tin tức {symbol} trong kho thế nào?',prior,today=TODAY)
    assert decision['scope']['source_type']=='NEWS'
    assert decision['scope']['companies']==[symbol]
    assert decision['scope']['_market_request']['action']=='LIST'


@pytest.mark.parametrize('question',[
    'Trong báo cáo 2025, MBB kiểm soát rủi ro nội bộ như thế nào?',
    'Mới tìm hiểu MBB, ngân hàng/công ty này kiếm tiền từ những mảng nào theo báo cáo 2025?',
    'Về đào tạo và phát triển nhân lực thì FPT có hoạt động gì trong báo cáo 2025?',
])
def test_named_report_content_stays_annual_instead_of_searching_news(question):
    decision=analyze_live(question,today=TODAY)
    assert decision['scope']['source_type']=='BCTN'
    assert decision['scope']['periods']==['2025']


def test_percentage_fractional_zeros_do_not_change_value_but_units_and_magnitude_remain_strict():
    from src.b1_answering.evidence.grounded import _unsupported_numbers
    assert not _unsupported_numbers('MB 5,7% và 5,8%','MB 5,70% và 5,80%')
    assert _unsupported_numbers('MB 57%','MB 5,70%')
    assert _unsupported_numbers('5,7 triệu VND','5,70 triệu VND')
    assert _unsupported_numbers('1,47%','0.0147')


def test_ticker_can_use_exact_verified_corporate_alias_but_not_a_related_person_or_article_tag():
    from src.b1_answering.evidence.grounded import _check_facts
    from src.b1_answering.evidence.citations import CitationError
    _check_facts('CTG cùng BID có lợi thế.','VietinBank cùng BIDV có lợi thế.')
    with pytest.raises(CitationError):_check_facts('CTG tăng trưởng.','Techcombank tăng trưởng.')
    with pytest.raises(CitationError):_check_facts('FPT giữ chức chủ tịch.','Trương Gia Bình giữ chức chủ tịch.')


def test_article_metric_followup_replays_the_selected_source_even_after_no_verified_answer():
    pack=stored_pack([article()],{'companies':['FPT']},'FPT có lợi nhuận sau thuế 101 tỷ đồng.')
    context={'companies':['FPT'],'source_type':'NEWS',
        '_market_request':{'kind':'NEWS','action':'DETAIL','query':'kết quả kinh doanh FPT'}}
    previous={'scope':context,'evidence_pack':pack,'answering':{'status':'INSUFFICIENT_EVIDENCE'}}
    kept=question_context('Lợi nhuận sau thuế thì sao?',context,TODAY)
    assert kept['source_type']=='NEWS'
    decision=news_reference('Lợi nhuận sau thuế thì sao?',kept,previous)
    assert decision is not None
    assert decision['scope']['source_type']=='NEWS'
    assert decision['scope'].get('_article_urls')or decision['scope'].get('_pending_article')
    changed=question_context('Còn BCTC năm 2025 thì lợi nhuận sau thuế?',context,TODAY)
    # The report query is explicit; the article reference resolver must decline.
    assert news_reference('Còn BCTC năm 2025 thì lợi nhuận sau thuế?',changed,previous)is None


def test_generic_report_source_is_consistent_across_chat_and_router_after_news():
    from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver,SessionScope
    question='Báo cáo CTG nói gì về nhân sự?'
    old={'companies':['FPT'],'source_type':'NEWS','periods':['2026-11-18'],'_article_urls':['https://example.org/old']}
    context=question_context(question,old,TODAY)
    assert context=={'companies':['CTG']}
    assert analyze_live(question,context,today=TODAY)['scope']['source_type']=='BCTN'
    scope=ScopeResolver().resolve(question,SessionScope(companies=('CTG',),source_type='NEWS')).scope
    assert scope.source_type=='BCTN'
    assert scope.relation_types==['HOLDS_ROLE']


def test_standalone_alias_question_does_not_inherit_company_or_period():
    old = dict(companies=['VCB'], source_type='BCTN', periods=['2024'], _annual_question='old')
    context = question_context('BIDV có tổng tài sản năm 2025 bao nhiêu?', old, TODAY)
    assert context == {'companies': ['BID']}
    assert old['periods'] == ['2024']


def test_person_followup_uses_one_article_even_when_it_has_multiple_chunks():
    pack = stored_pack([article()], {'companies': ['ITD']}, 'ITD bổ nhiệm bà Nguyễn Thị Thu Sương làm Giám đốc Tài chính.')
    from src.documents.db_chunking import news_documents, chunk_document
    from datetime import datetime
    from uuid import uuid4
    doc = news_documents([dict(article_id=str(uuid4()), title=article()['title'],
        published_at=datetime.fromisoformat(article()['published_at']), source='fireant',
        symbols=['ITD'], url=article()['url'],
        content='ITD bổ nhiệm bà Nguyễn Thị Thu Sương làm Giám đốc Tài chính.\n'
                'Quyết định có hiệu lực từ ngày 01/09/2026.')], max_words=12)[0]
    chunks = chunk_document(doc, max_words=12)
    assert len(chunks) > 1
    template = pack['items'][0]
    pack['items'] = [{**template, 'source_id': doc.document_id, 'evidence_id': ch.chunk_id,
        'chunk_id': ch.chunk_id, 'passage': ch.text, 'locator': ch.locator,
        'content_sha256': ch.content_hash} for ch in chunks]
    previous = {'scope': {'companies': ['ITD'], 'source_type': 'NEWS'}, 'evidence_pack': pack}
    result = news_reference('Bà ấy tên đầy đủ là gì?', previous['scope'], previous)
    assert result['decision'] == 'MARKET_LOOKUP'
    assert len(result['scope']['_article_urls']) == 1


def test_explicit_other_company_does_not_use_prior_person_article():
    pack = stored_pack([article()], {'companies': ['ITD']}, 'ITD bổ nhiệm bà Nguyễn Thị Thu Sương.')
    previous = {'scope': {'companies': ['ITD'], 'source_type': 'NEWS'}, 'evidence_pack': pack}
    assert news_reference('Bà ấy ở VCB là ai?', previous['scope'], previous) is None


def _news_database_fixture():
    """Metadata title omits the fact that exists in the verified article body."""
    pack = stored_pack([article()], {'companies': ['FPT']},
                       'FPT đầu tư trung tâm nghiên cứu trí tuệ nhân tạo tại Hà Nội.')
    item = pack['items'][0]
    @asynccontextmanager
    async def transaction(**kwargs):
        assert kwargs['readonly'] is True
        yield
    conn = SimpleNamespace(transaction=transaction)
    async def fetch(sql, *args):
        if 'DISTINCT ON' in sql:
            return [dict(document_id=item['source_id'], title=item['title'], source_url=item['source_url'],
                         chunk_id=item['chunk_id'], locator_json=item['locator'],
                         published_at=article()['published_at'])]
        return [dict(chunk_id=item['chunk_id'])]
    conn.fetch = AsyncMock(side_effect=fetch)
    @asynccontextmanager
    async def acquire():
        yield conn
    retriever = SimpleNamespace(pool=SimpleNamespace(acquire=acquire), corpus_version_id=pack['corpus_version_id'],
        _corpus=AsyncMock(return_value={'index_version_id': pack['data_version']['id']}),
        retrieve=AsyncMock(return_value=pack))
    source = SimpleNamespace(chunk_id=item['chunk_id'], document_id=item['source_id'], active=True,
        index_version_id=pack['data_version']['id'], text=item['passage'], locator=item['locator'],
        source_sha256=item['source_sha256'], content_hash=item['content_sha256'])
    reader = SimpleNamespace(read_current=AsyncMock(return_value=source))
    return retriever, reader


def test_news_body_search_does_not_require_question_to_match_headline():
    from src.retrieval_orchestration.stored_news import latest_news
    retriever, reader = _news_database_fixture()
    scope = dict(companies=['FPT'], periods=['2026'], metric_code='TOTAL_ASSETS', source_type='NEWS',
                 _market_request={'action': 'DETAIL', 'query': 'Trung tâm trí tuệ nhân tạo đầu tư ở đâu?'})
    with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader', return_value=reader):
        result = asyncio.run(latest_news(retriever, scope))
    assert len(result['items']) == 1
    assert 'trí tuệ nhân tạo' in result['items'][0]['passage']
    search = retriever.retrieve.call_args.args[1]
    assert search['metric_code'] is None and search['periods'] == ['LATEST_AVAILABLE_PERIOD']
    reader.read_current.assert_awaited_once()
    assert scope['metric_code'] == 'TOTAL_ASSETS'


def test_news_topic_can_name_an_unindexed_counterparty_without_discarding_valid_story():
    from src.retrieval_orchestration.stored_news import latest_news
    retriever,reader=_news_database_fixture()
    first=retriever.retrieve.return_value
    retriever.retrieve.side_effect=[first,{**first,'items':[]}]
    scope={'companies':['FPT','ZZZ'],'_market_request':{'action':'DETAIL','query':'Trung tâm trí tuệ nhân tạo đầu tư ở đâu?'}}
    with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader',return_value=reader):
        result=asyncio.run(latest_news(retriever,scope))
    assert result['items']
    assert [call.args[1]['companies']for call in retriever.retrieve.call_args_list]==[['FPT'],['ZZZ']]


def test_answer_passage_ranks_above_repeated_pdf_cover_header():
    from src.retrieval_orchestration.stored_news import rank_article_chunks
    header = 'ITD: Nghị quyết HĐQT bổ nhiệm Giám đốc Tài chính\n'
    cover = {'passage': header+'Kính gửi Ủy ban chứng khoán. Số điện thoại liên hệ, địa chỉ tổ chức.'}
    answer = {'passage': header+'Bổ nhiệm Bà Nguyễn Thị Thu Sương giữ chức vụ Giám đốc tài chính từ ngày 01/09/2026.'}
    assert rank_article_chunks('ITD bổ nhiệm ai làm Giám đốc Tài chính theo thông báo?', [cover,answer]) == [answer,cover]


def test_multiple_cited_chunks_of_one_article_have_one_heading():
    from src.b1_answering.evidence.news_policy import present_news
    items={eid:dict(source_type='NEWS',source_verified=True,locator={'source_table':'news_articles','url':'https://example.org/article'},
                    title='Một bài báo',source_id='one-document')for eid in ('a','b')}
    draft={'claims':[{'text':'Ý thứ nhất','evidence_ids':['a']},{'text':'Ý thứ hai','evidence_ids':['b']}],
           'citations':[{'evidence_id':'a','citation_number':1},{'evidence_id':'b','citation_number':2}]}
    result=present_news(draft,items,{'source_type':'NEWS'})
    assert result['draft'].count('Một bài báo')==1
    assert '[1]'in result['draft'] and '[2]'in result['draft']


def test_news_search_cannot_mix_serving_corpora():
    from src.retrieval_orchestration.stored_news import latest_news
    from uuid import uuid4
    retriever, reader = _news_database_fixture()
    retriever.retrieve.return_value['corpus_version_id'] = str(uuid4())
    with pytest.raises(ValueError, match='Serving corpus changed'):
        asyncio.run(latest_news(retriever, {'companies': ['FPT'], '_market_request': {'query': 'ai'}}))
    reader.read_current.assert_not_awaited()


def test_publication_day_is_applied_before_semantic_top_k():
    from src.retrieval_orchestration.stored_news import latest_news
    retriever, reader = _news_database_fixture()
    scope = {'companies': ['FPT'], '_market_request': {'action': 'DETAIL',
             'day': '2026-10-23', 'query': 'dự án nào được công bố'}}
    with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader', return_value=reader):
        asyncio.run(latest_news(retriever, scope))
    assert retriever.retrieve.call_args.args[1]['periods'] == ['2026-10-23']


def test_news_replay_errors_are_not_bypassed_by_semantic_match():
    from src.retrieval_orchestration.stored_news import latest_news
    retriever, reader = _news_database_fixture()
    reader.read_current.side_effect = ValueError('source hash changed')
    with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader', return_value=reader):
        with pytest.raises(ValueError, match='source hash changed'):
            asyncio.run(latest_news(retriever, {'companies': ['FPT'],
                        '_market_request': {'action': 'DETAIL', 'query': 'trung tâm ở đâu'}}))


def test_specific_dated_headline_outranks_generic_newer_board_resolution():
    from src.retrieval_orchestration.stored_news import rank_article_chunks
    correct={'title':'ITD: Bổ nhiệm bà Nguyễn Thị Thu Sương giữ chức Giám đốc Tài chính từ 1.9.2026',
        'passage':'Tin cafef | 2026-08-24 | ITD: Bổ nhiệm bà Nguyễn Thị Thu Sương giữ chức Giám đốc Tài chính từ 1.9.2026\nThông báo thay đổi nhân sự, tệp đính kèm.'}
    generic={'title':'ITD: Nghị quyết HĐQT định kỳ Quý 2/2026',
        'passage':'Tin fireant | 2026-11-02 | ITD: Nghị quyết HĐQT định kỳ Quý 2/2026\nTổng Giám đốc ITD, tài chính, bổ nhiệm, ngày ký và năm 2026.'}
    query='Theo tin bổ nhiệm ngày 24/08/2026, ai được ITD bổ nhiệm làm Giám đốc Tài chính và từ ngày nào?'
    assert rank_article_chunks(query,[generic,correct])[0]is correct


def test_body_answer_is_not_discarded_when_headline_is_generic():
    from src.retrieval_orchestration.stored_news import rank_article_chunks
    answer={'title':'ICT: Báo cáo năm 2025','passage':'ICT | BCTN 2025\nGiảm phụ thuộc nguồn thu VNPT bằng dịch vụ số.'}
    teaser={'title':'ICT công bố thông tin về VNPT','passage':'ICT | 2026-11-02\nTệp đính kèm.'}
    assert rank_article_chunks('ICT giảm phụ thuộc nguồn thu VNPT bằng cách nào?',[teaser,answer])[0]is answer


@pytest.mark.parametrize('question',[
    'Bài ELC ước doanh thu quý III/2026 vượt mức nào?',
    'Tài sản ELCOM cuối 2025 được bài ghi nhận ở quy mô nào?',
    'Bài về doanh thu bảo hiểm của ngân hàng có nhắc Techcombank không?',
    'Bài về AI Agent nói công nghệ này tạo cơ hội gì cho doanh nghiệp công nghệ?',
])
def test_direct_article_subject_keeps_financial_words_in_news(question):
    from src.retrieval_orchestration.market_dialogue import article_content_request
    from datetime import date
    request=article_content_request(question,date(2026,11,20))
    assert request['kind']=='NEWS'
    assert request['action']=='DETAIL'
    assert request['day']is None


@pytest.mark.parametrize('question',[
    'Bài toán doanh thu FPT năm 2025',
    'Bài học từ báo cáo thường niên FPT 2025',
    'Bài tập phân tích báo cáo tài chính VCB',
    'Theo BCTC FPT doanh thu quý 2 năm 2026 bao nhiêu?',
])
def test_non_article_uses_of_bai_do_not_force_news(question):
    from src.retrieval_orchestration.market_dialogue import article_content_request
    from datetime import date
    assert article_content_request(question,date(2026,11,20))is None
