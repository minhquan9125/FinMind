"""Offline boundary tests; no real users, network, or database writes."""
import asyncio
import copy
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.b1_answering.evidence.bundle import bundle_packs
from src.b1_answering.evidence.citations import CitationError, prepare_evidence
from src.retrieval_orchestration.conversation_actions import conversation_action
from src.retrieval_orchestration.conversation_summary import group_summary, summarize_session
from src.retrieval_orchestration.chat_logic import new_document
from src.retrieval_orchestration.stored_news import latest_news
from src.retrieval_orchestration.live_research import LiveResearchService
from tests.stored_news_fixture import stored_pack
from tests.test_chat_priority_fixes import price_pack
from tests.test_s5_wbs093_summary import sourced_result


@pytest.mark.parametrize('text', ['Không tổng hợp nội dung chat', 'Tôi không muốn tóm tắt cuộc trao đổi'])
def test_negated_summary_does_not_execute(text):
    assert conversation_action(text) is None


def test_two_selected_articles_in_same_period_are_not_overwritten():
    first=sourced_result(text='FPT công bố sản phẩm mới.')
    second=sourced_result(text='FPT mở thêm văn phòng.')
    first['scope']['_article_urls']=['https://example.org/product']
    second['scope']['_article_urls']=['https://example.org/office']
    doc=new_document(str(uuid4()),str(uuid4()))
    doc['messages']=[dict(role='assistant',result=r) for r in (first,second)]
    draft=group_summary(summarize_session(doc))['answering']['draft']
    assert 'công bố sản phẩm mới' in draft and 'mở thêm văn phòng' in draft


class NewsDB:
    def __init__(self, packs, copies=1):
        self.items={i['chunk_id']:i for p in packs for i in p['items']}
        self.primary=list(self.items.values())
        self.refs={i['source_id']:[i['chunk_id']] for i in self.primary}
        for item in self.primary:
            for _ in range(copies-1):
                extra=copy.deepcopy(item)
                extra['chunk_id']=extra['evidence_id']=str(uuid4())
                self.items[extra['chunk_id']]=extra
                self.refs[item['source_id']].append(extra['chunk_id'])
        self.copies=copies
        self.transactions=[]

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self, **kwargs):
        self.transactions.append(kwargs)
        yield self

    async def fetch(self, query, *args):
        if 'SELECT DISTINCT ON' in query:
            return [dict(document_id=i['source_id'], title=i['title'], source_url=i['source_url'],
                         chunk_id=i['chunk_id'], locator_json=json.dumps(i['locator']),
                         published_at=i['stored_news']['published_at']) for i in self.primary]
        item=next(i for i in self.items.values() if i['source_id']==str(args[0]))
        return [dict(chunk_id=chunk_id) for chunk_id in self.refs[item['source_id']]]

    async def read(self, chunk_id, cid):
        i=self.items[chunk_id]
        return SimpleNamespace(index_version_id=self.iid,active=True,chunk_id=chunk_id,
            document_id=i['source_id'],text=i['passage'],locator=i['locator'],
            source_sha256=i['source_sha256'],content_hash=i['content_sha256'])


def pack_at(day, title='FPT công bố thông tin', url=None):
    return stored_pack([dict(title=title,url=url or 'https://example.org/'+str(uuid4()),
                            published_at=day.isoformat())],dict(companies=['FPT']),title)


def read_news(packs, request, *, copies=1, failure=None):
    db=NewsDB(packs,copies)
    db.iid=str(uuid4())
    retriever=SimpleNamespace(pool=db,corpus_version_id=str(uuid4()),
        _corpus=AsyncMock(return_value=dict(index_version_id=db.iid)))
    reader=SimpleNamespace(read_current=AsyncMock(side_effect=failure or db.read))
    with patch('src.retrieval_orchestration.stored_news.PostgresSourceReader',return_value=reader):
        out=asyncio.run(latest_news(retriever,dict(companies=['FPT'],_market_request=request)))
    assert db.transactions==[dict(readonly=True,isolation='repeatable_read')]
    return out,reader


def test_analysis_news_window_includes_boundaries_and_excludes_later_and_older_articles():
    now=datetime.now(timezone(timedelta(hours=7))).replace(hour=0,minute=0,second=0,microsecond=0)
    anchor=now-timedelta(days=2)
    dates=[anchor-timedelta(days=31),anchor-timedelta(days=30),anchor,
           anchor+timedelta(days=1),now+timedelta(days=1)]
    packs=[pack_at(day) for day in dates]
    out,reader=read_news(packs,dict(action='ANALYSIS',as_of=anchor.date().isoformat()))
    assert len(out['items'])==2 and reader.read_current.await_count==2
    assert [i['stored_news']['published_at'] for i in out['items']]==[dates[2].isoformat(),dates[1].isoformat()]
    prepare_evidence(out)


def test_news_list_selects_three_latest_unique_urls_and_avoids_recommendations():
    now=datetime.now(timezone(timedelta(hours=7)))-timedelta(days=1)
    packs=[pack_at(now-timedelta(days=n),url='https://example.org/'+str(n)) for n in range(5)]
    packs += [pack_at(now-timedelta(hours=1),url='https://example.org/0'),
              pack_at(now,title='Khuyến nghị mua FPT')]
    out,reader=read_news(packs,dict(action='LIST'))
    assert len(out['items'])==3 and reader.read_current.await_count==3
    assert len({i['source_url'] for i in out['items']})==3
    assert all('Khuyến nghị' not in i['title'] for i in out['items'])


@pytest.mark.parametrize('copies,truncated',[(1,False),(8,False),(9,True)])
def test_partial_article_flag_is_only_set_when_chunks_are_actually_omitted(copies,truncated):
    now=datetime.now(timezone.utc)-timedelta(days=1)
    out,_=read_news([pack_at(now)],dict(action='SUMMARY'),copies=copies)
    assert len(out['items'])==min(copies,8)
    assert all(i['stored_news']['content_truncated'] is truncated for i in out['items'])


def test_news_reader_failure_is_not_hidden_as_empty_results():
    now=datetime.now(timezone.utc)-timedelta(days=1)
    with pytest.raises(ValueError,match='hash mismatch'):
        read_news([pack_at(now)],dict(action='LIST'),failure=ValueError('hash mismatch'))


@pytest.mark.parametrize('mutation',['digest','version','missing_item','conflicting_id'])
def test_bundle_rejects_version_and_identity_corruption(mutation):
    feed=price_pack()
    db=pack_at(datetime.now(timezone.utc)-timedelta(days=1))
    pack=bundle_packs([feed,db])
    if mutation=='digest': pack['data_version']['id']='0'*64
    elif mutation=='version': pack['evidence_packs'][0]['data_version']['id']='changed'
    elif mutation=='missing_item': pack['items'].pop()
    else:
        db['items'][0]['evidence_id']=feed['items'][0]['evidence_id']
        with pytest.raises(CitationError): bundle_packs([feed,db])
        return
    with pytest.raises(CitationError): prepare_evidence(pack)


@pytest.mark.parametrize('failure',[None,TimeoutError(),RuntimeError('private connection details'),
                                  CitationError('INVALID_EVIDENCE')])
def test_analysis_preserves_verified_price_when_news_is_empty_or_fails(failure):
    feed=price_pack()
    market=SimpleNamespace(lookup=AsyncMock(return_value=dict(status='EVIDENCE_READY',
        reason_code='MARKET_ANALYSIS_READY',evidence_pack=feed)))
    reader=AsyncMock(side_effect=failure) if failure else AsyncMock(return_value=dict(items=[]))
    async def complete(question,result,**kwargs):
        assert result['evidence_pack']==feed
        prepare_evidence(result['evidence_pack'])
        result['answering']=dict(status='DRAFT_READY',draft='Giá đã xác minh.',citations=[])
        return result
    result=dict(status='MARKET_LOOKUP',scope=dict(companies=['FPT'],source_type='MARKET_ANALYSIS',
        _market_request=dict(action='ANALYSIS')))
    with patch('src.retrieval_orchestration.stored_news.latest_news',reader), patch(
            'src.retrieval_orchestration.live_research.complete_retrieval',side_effect=complete):
        out=asyncio.run(LiveResearchService(object(),market=market)._answer_market('phân tích FPT',result))
    assert out['scope']['_analysis_news']['count']==0
    assert bool(out['scope']['_analysis_news'].get('error')) is (failure is not None)
    assert ('lỗi truy xuất' in out['answering']['draft']) is (failure is not None)
    assert 'private connection details' not in str(out)


def test_mixed_market_news_answer_can_be_summarized_without_losing_source_versions():
    result=sourced_result(text='FPT công bố sản phẩm mới.')
    original=result['evidence_pack']
    result['evidence_pack']=bundle_packs([price_pack(),original])
    result['scope']['source_type']='MARKET_ANALYSIS'
    doc=new_document(str(uuid4()),str(uuid4()))
    doc['messages']=[dict(role='assistant',result=result)]
    out=group_summary(summarize_session(doc))
    assert out['answering']['status']=='DRAFT_READY'
    assert out['evidence_packs'][0]['evidence_packs'][1]==original
    assert out['answering']['citations'][0]['source_id']==original['items'][0]['source_id']
