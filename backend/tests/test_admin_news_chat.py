import asyncio
import uuid
from types import SimpleNamespace

from src.documents.admin_ingestion import Queue, sha
from src.documents.admin_news_index import prepare
from src.documents.admin_news_chat import AdminNewsChat
from src.documents.admin_news_chat import TimedProvider
from src.b1_answering.application.service import complete_retrieval
from src.b1_answering.evidence.news_extract import source_excerpt
from src.b1_answering.evidence.citations import prepare_evidence
from src.b1_answering.providers.gemini import GeminiError


def evidence():
    payload = {'title':'ICT: Giải trình LNST quý 2/2026', 'source':'fireant',
               'url':'https://fireant.vn/bai-viet/test/123','symbols':['ICT'],
               'published_at':'2026-07-30T10:33:12+07:00',
               'content': ('Diễn giải Q2 - Năm 2026 Q2 - Năm 2025 Tăng/Giảm\n'
                           'Lợi nhuận sau thuế 32.507.122.941 13.443.564.076 141,80%\n'
                           'Doanh thu tăng chủ yếu do dự án chuyển tiếp từ năm 2025.\n'
                           'Chi phí tài chính tăng chủ yếu liên quan đến biến động tỉ giá.')}
    _, _, digest, doc, chunks = prepare({'status':'APPROVED','payload':payload,'digest':sha(payload),'reviews':[]})
    items = [dict(evidence_id=c.chunk_id,chunk_id=c.chunk_id,source_id=doc.document_id,
                  source_type='NEWS',source_sha256=digest,source_verified=True,
                  content_sha256=c.content_hash,passage=c.text,locator=c.locator,
                  score={'type':'RRF','value':0.1}) for c in chunks]
    return {'schema_version':'1.1','query_id':'test','data_version':{'kind':'INDEX','id':str(uuid.uuid4())},
            'corpus_version_id':str(uuid.uuid4()),'items':items}


def scope():
    return {'source_type':'NEWS','companies':['ICT'],'periods':['LATEST_AVAILABLE_PERIOD'],'_allow_source_extract':True}


class Unavailable:
    async def count_tokens(self, request): raise GeminiError('GEMINI_UNAVAILABLE')
    async def generate(self, request): raise AssertionError('No generation retry')


def test_provider_outage_returns_exact_table_with_citation():
    result = asyncio.run(complete_retrieval('Bài ICT: LNST quý 2/2026 là bao nhiêu?',
        {'status':'EVIDENCE_READY','execution_mode':'LIVE','scope':scope(),'evidence_pack':evidence()},provider=Unavailable()))
    a=result['answering']
    assert a['reason_code']=='NEWS_SOURCE_EXTRACT'
    assert a['status']=='DRAFT_READY' and a['citations']
    assert '32.507.122.941' in a['draft'] and '13.443.564.076' in a['draft'] and '141,80%' in a['draft']
    assert a['manifest']['response_mode']=='SOURCE_EXTRACT'
    assert 'Trích nguyên văn' in a['draft']


def test_wrong_quarter_is_rejected_before_model_call():
    class Never:
        async def count_tokens(self, request): raise AssertionError('Wrong quarter must not reach model')
    result=asyncio.run(complete_retrieval('Theo bài ICT, LNST quý 3/2026 bao nhiêu?',
        {'status':'EVIDENCE_READY','execution_mode':'LIVE','scope':scope(),'evidence_pack':evidence()},provider=Never()))
    assert result['answering']['reason_code']=='REQUESTED_PERIOD_NOT_IN_SOURCE'
    assert result['answering']['claims']==[]


def test_wrong_year_cannot_use_the_same_quarter_of_another_year():
    result=asyncio.run(complete_retrieval('Theo bài ICT, LNST quý 2/2024 bao nhiêu?',
        {'status':'EVIDENCE_READY','execution_mode':'LIVE','scope':scope(),'evidence_pack':evidence()},provider=Unavailable()))
    assert result['answering']['reason_code']=='REQUESTED_PERIOD_NOT_IN_SOURCE'
    assert '2024' in result['answering']['message']
    assert not result['answering']['claims']


def test_reason_extract_does_not_confuse_cost_and_revenue():
    pack=prepare_evidence(evidence())
    answer=source_excerpt('Vì sao chi phí tài chính tăng?',pack,scope())
    assert 'tỉ giá' in answer['draft']
    assert 'dự án chuyển tiếp' not in answer['draft']


def test_new_corpus_pointer_does_not_change_default_or_approval(tmp_path):
    q=Queue(tmp_path); original=str(uuid.uuid4());new=str(uuid.uuid4());index=str(uuid.uuid4())
    assert q.serving_corpus(original)==original
    q.publish_corpus(new,index)
    assert Queue(tmp_path).serving_corpus(original)==new
    assert original != new and q.article_count()==0


def test_article_selector_cannot_use_unpublished_news(tmp_path):
    q=Queue(tmp_path)
    settings=SimpleNamespace(admin_ingestion_directory=tmp_path)
    service=AdminNewsChat(None,None,settings)
    assert service.select('Bài ICT giải trình LNST quý 2/2026 nói gì?') is None
    assert service.select('Tổng tài sản ICT năm 2026?') is None


def test_fresh_checkout_reads_published_article_from_shared_db_without_local_history(tmp_path):
    from contextlib import asynccontextmanager
    from src.core.config import get_settings
    from src.b1_answering.core.policy import Limits,Budget
    pack=evidence();calls=[]
    class Conn:
        async def fetch(self,sql,*args):
            assert "cv.status='FROZEN'" in sql and "iv.status='ACTIVE'" in sql
            assert 'cd.document_hash=d.sha256' in sql and 'admin_news_snapshot' in sql
            return [{'id':pack['items'][0]['source_id'],'title':'ICT: Giải trình LNST quý 2/2026',
                     'url':'https://fireant.vn/bai-viet/test/123','symbol':'ICT'}]
    class Pool:
        @asynccontextmanager
        async def acquire(self):yield Conn()
    class Retriever:
        async def retrieve(self,question,scope):
            calls.append(scope);return pack
    settings=get_settings().model_copy(update={'admin_ingestion_directory':tmp_path})
    service=AdminNewsChat(Pool(),None,settings,retriever=Retriever())
    limits=Limits.load()
    result=asyncio.run(service.answer('Theo bài ICT, LNST quý 2/2026 là bao nhiêu?',
        'fresh-checkout',provider=Unavailable(),limits=limits,budget=Budget(limits)))
    assert Queue(tmp_path).article_count()==0
    assert calls and result['answering']['status']=='DRAFT_READY'
    assert '32.507.122.941' in result['answering']['draft']


def test_news_timeout_is_bounded_without_retries():
    class Slow:
        calls=0
        async def generate(self,request):
            self.calls+=1
            await asyncio.sleep(1)
    slow=Slow()
    provider=TimedProvider(slow,None,0.01)
    import pytest
    with pytest.raises(GeminiError,match='GEMINI_TIMEOUT'):
        asyncio.run(provider.generate({}))
    assert slow.calls==1


def test_shared_release_reuses_original_sources_without_changing_locator(monkeypatch):
    from src.documents import shared_source
    original=str(uuid.uuid4());new=str(uuid.uuid4());locator={'source_id':'unchanged'}
    root={'index_version_id':new,'source_index_version_id':original}
    async def read(*args): return root
    async def resolve(conn,index_id,actual_root,actual_locator,*args):
        assert index_id==original and actual_root is root and actual_locator is locator
        return 'verified original text'
    monkeypatch.setattr(shared_source,'read_release_root',read)
    monkeypatch.setattr(shared_source,'_resolve_member',resolve)
    assert asyncio.run(shared_source._resolve_shared_source(None,new,locator,'hash',{}))=='verified original text'
