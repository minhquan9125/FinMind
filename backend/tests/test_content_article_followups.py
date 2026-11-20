import copy
import pytest
from src.retrieval_orchestration.market_dialogue import news_reference
from tests.stored_news_fixture import stored_pack
from tests.test_market_research import article


@pytest.mark.parametrize('question',[
    'Sau đó nắm giữ tỷ lệ nào?',
    'Cơ quan nào nhắc?',
    'Từ ngày nào có hiệu lực?',
])
def test_general_content_news_can_anchor_a_short_followup(question):
    scope={'companies':['FPT'],'source_type':'CONTENT','periods':['LATEST_AVAILABLE_PERIOD']}
    pack=stored_pack([article()],scope,'Nguồn đã thu thập về sự kiện của FPT.')
    previous={'scope':copy.deepcopy(scope),'evidence_pack':pack}
    result=news_reference(question,scope,previous)
    assert result['decision']=='MARKET_LOOKUP'
    assert result['scope']['source_type']=='NEWS'
    assert result['scope']['_article_urls']==[pack['items'][0]['locator']['url']]
    assert result['scope']['_article_anchor']['chunks'][0]['chunk_id']==pack['items'][0]['chunk_id']
    assert previous['scope']['source_type']=='CONTENT'


@pytest.mark.parametrize('question',[
    'Theo BCTC FPT lợi nhuận năm 2025 bao nhiêu?',
    'Sau đó phân tích VCB',
    'Cơ quan nào nhắc VCB?',
])
def test_new_subject_does_not_reuse_the_content_article(question):
    scope={'companies':['FPT'],'source_type':'CONTENT','periods':[]}
    previous={'scope':scope,'evidence_pack':stored_pack([article()],scope,'Nguồn FPT')}
    assert news_reference(question,scope,previous)is None


def test_uncited_other_source_does_not_destroy_the_selected_article_anchor():
    scope={'companies':['FPT'],'source_type':'CONTENT','periods':[]}
    pack=stored_pack([article()],scope,'Nguồn FPT')
    cited=pack['items'][0]['evidence_id']
    from uuid import uuid4
    other=copy.deepcopy(pack['items'][0]);other['evidence_id']=str(uuid4());other['chunk_id']=other['evidence_id']
    other['locator']['url']='https://example.org/other-article';pack['items'].append(other)
    previous={'scope':scope,'evidence_pack':pack,'answering':{'claims':[{'evidence_ids':[cited]}]}}
    assert news_reference('Sau đó nắm giữ tỷ lệ nào?',scope,previous)['decision']=='MARKET_LOOKUP'


def test_same_url_keeps_the_previously_cited_document_snapshot():
    import asyncio
    from unittest.mock import patch
    from tests.test_member_workbooks_20261119 import _news_database_fixture
    from src.retrieval_orchestration.stored_news import latest_news
    retriever,reader=_news_database_fixture()
    pack=retriever.retrieve.return_value;item=pack['items'][0]
    async def run():
        async with retriever.pool.acquire()as conn:
            old_fetch=conn.fetch.side_effect
            async def fetch(sql,*args):
                rows=await old_fetch(sql,*args)
                if 'DISTINCT ON'in sql:
                    competing={**rows[0],'document_id':'ffffffff-ffff-ffff-ffff-ffffffffffff',
                        'chunk_id':'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'}
                    return [competing,*rows]
                assert str(args[0])==item['source_id'],'Must read the cited snapshot, not another document at the same URL'
                return rows
            conn.fetch.side_effect=fetch
        scope={'companies':['FPT'],'_article_urls':[item['locator']['url']],
            '_market_request':{'action':'DETAIL','query':'Cơ quan nào nhắc?'},
            '_article_anchor':{'corpus_version_id':pack['corpus_version_id'],
                'index_version_id':pack['data_version']['id'],
                'chunks':[{'document_id':item['source_id'],'chunk_id':item['chunk_id']}]}}
        with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader',return_value=reader):
            actual=await latest_news(retriever,scope)
        assert actual['items'][0]['source_id']==item['source_id']
    asyncio.run(run())


def test_model_question_names_the_source_subject_of_the_followup():
    import json
    from src.b1_answering.evidence.grounded import build_grounded_request
    from src.b1_answering.evidence.citations import prepare_evidence
    from src.b1_answering.core.policy import Limits
    scope={'companies':['FPT'],'source_type':'NEWS','_article_subject_quotes':['Nhóm bà Lan mua cổ phiếu.']}
    evidence=prepare_evidence(stored_pack([article()],scope,'Nhóm bà Lan mua cổ phiếu.'))
    request=build_grounded_request('Sau đó nắm giữ tỷ lệ nào?',evidence,Limits.load(),scope)
    question=json.loads(request['contents'][0]['parts'][0]['text'])['question']
    assert 'Nhóm bà Lan mua cổ phiếu.'in question
    assert 'Sau đó nắm giữ tỷ lệ nào?'in question
