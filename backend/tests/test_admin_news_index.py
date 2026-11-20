"""Transactional indexing/activation contract using the real chunker and fake DB."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import pytest
from src.documents.admin_ingestion import Queue, crawl_job
from src.documents import admin_news_index as index
from src.documents import corpus_manifest


def approved(tmp_path):
    q = Queue(tmp_path); j, _ = q.create_job('CRAWL', 'actor')
    row = {'source':'fireant','url':'https://fireant.vn/bai-viet/test/123', 'title':'Fixture News',
           'content':'FPT đã hoàn thiện hai AI Factory tại Việt Nam.', 'symbols':['FPT'],
           'published_at':'2026-11-05T07:00:00+07:00'}
    crawl_job(q, j, lambda limit: ([row], [])); aid = q.articles()[0]['id']
    q.review(aid, 'APPROVED', 'Đúng nguồn.', 'reviewer')
    j, _ = q.create_job('INDEX', 'actor', article_ids=[aid])
    return q, j, aid


def test_draft_index_build_reuses_embedding_and_never_activates(tmp_path, monkeypatch):
    q, j, aid = approved(tmp_path); calls = []
    class Conn:
        @asynccontextmanager
        async def transaction(self):
            calls.append('BEGIN'); yield; calls.append('COMMIT')
        async def execute(self, sql, *args): calls.append(sql)
        async def close(self): calls.append('CLOSE')
    async def connect(settings): return Conn()
    async def document(*args): calls.append('DOCUMENT')
    async def chunks(conn, doc, pieces, vectors, ident):
        assert ident == j and len(pieces) == len(vectors)
        assert all('admin_news_snapshot' in c.locator for c in pieces)
        calls.append('CHUNKS')
    async def manifest(conn, ident):
        assert ident == j
        return {'corpus_version_id':'fixture-corpus','manifest_sha256':'a'*64}
    class Embedder:
        def embed_texts(self, texts): return [[1.0] + [0.0]*1023 for _ in texts]
    monkeypatch.setattr(index, 'connect_writer', connect)
    monkeypatch.setattr(index, 'upsert_document', document)
    monkeypatch.setattr(index, 'write_chunks', chunks)
    monkeypatch.setattr(corpus_manifest, 'read_manifest', manifest)
    asyncio.run(index.build(q, j, SimpleNamespace(embedding_model_ref='fixture-model'), Embedder()))
    assert q.get_job(j)['status'] == 'INDEXED' and q.article(aid)['status'] == 'INDEXED'
    assert any("'BUILDING'" in c for c in calls)
    assert not any("'ACTIVE'" in c for c in calls)
    assert calls.index('CHUNKS') < calls.index('COMMIT')


def test_failed_embeddings_do_not_write_index_or_promote_article(tmp_path, monkeypatch):
    q, j, aid = approved(tmp_path); writes=[]
    class Conn:
        async def execute(self,*args): writes.append(args)
        async def close(self): pass
    async def connect(settings): return Conn()
    class Embedder:
        def embed_texts(self,texts): return [[float('nan')]*1024 for _ in texts]
    monkeypatch.setattr(index,'connect_writer',connect)
    with pytest.raises(ValueError):
        asyncio.run(index.build(q,j,SimpleNamespace(embedding_model_ref='fixture-model'),Embedder()))
    assert not writes and q.article(aid)['status']=='APPROVED'


def test_activation_rechecks_hash_and_never_updates_live_settings(tmp_path, monkeypatch):
    q, j, _ = approved(tmp_path)
    q.update_job(j,'INDEXED',manifest_sha256='a'*64)
    statements=[]
    class Conn:
        @asynccontextmanager
        async def transaction(self): yield
        async def fetchval(self,*args): return 'BUILDING'
        async def execute(self,sql,*args): statements.append(sql)
        async def close(self): pass
    async def connect(settings): return Conn()
    async def manifest(*args): return {'manifest_sha256':'b'*64}
    monkeypatch.setattr(index,'connect_writer',connect)
    monkeypatch.setattr(corpus_manifest,'read_manifest',manifest)
    with pytest.raises(ValueError,match='CHANGED_SINCE_BUILD'):
        asyncio.run(index.activate(q,j,SimpleNamespace()))
    assert statements==[] and q.get_job(j)['status']=='INDEXED'


def test_admin_snapshot_supports_existing_b1_citation_contract(tmp_path):
    import uuid
    from src.b1_answering.evidence.live_contract import validate_live_item
    q, j, aid = approved(tmp_path)
    payload, pid, checksum, doc, chunks = index.prepare(q.article(aid))
    item = {'evidence_id':str(uuid.uuid4()), 'chunk_id':str(uuid.uuid4()), 'source_id':doc.document_id,
            'source_type':'NEWS', 'source_verified':True, 'passage':chunks[0].text,
            'content_sha256':chunks[0].content_hash, 'locator':chunks[0].locator,
            'score':{'type':'RRF','value':0.03}}
    validate_live_item(item)
    del item['locator']['admin_news_snapshot']
    from src.b1_answering.evidence.citations import CitationError
    with pytest.raises(CitationError): validate_live_item(item)


def test_one_job_publishes_automatically_and_keeps_articles_pending_until_done(tmp_path,monkeypatch):
    import uuid
    q,j,aid=approved(tmp_path);calls=[]
    base=str(uuid.uuid4());corpus=str(uuid.uuid4())
    async def build(queue,ident,settings,*,publish):
        assert publish is True
        calls.append('chunk-vector-save')
        queue.update_job(ident,'RUNNING',phase='PUBLISHING',auto_publish=True,manifest_sha256='a'*64)
        assert queue.article(aid)['status']=='APPROVED'
    async def activate(queue,ident,settings):
        calls.append('auto-publish')
        with pytest.raises(ValueError,match='ANOTHER_JOB'):
            queue.create_job('CRAWL','other')
        queue.finish_index(ident,{'phase':'PUBLISHED_NEW_VERSION'},corpus_id=corpus,default_corpus=base,expected_base=base)
    monkeypatch.setattr(index,'build',build);monkeypatch.setattr(index,'activate',activate)
    index.index_job(q,j,SimpleNamespace())
    assert calls==['chunk-vector-save','auto-publish']
    assert q.get_job(j)['status']=='ACTIVE'
    assert q.article(aid)['status']=='INDEXED'
    assert q.serving_corpus(base)==corpus


def test_publication_failure_can_retry_without_embedding_again(tmp_path,monkeypatch):
    q,j,aid=approved(tmp_path);calls=[]
    async def build(queue,ident,settings,*,publish):
        calls.append('embedding')
        queue.update_job(ident,'RUNNING',phase='PUBLISHING',auto_publish=publish,manifest_sha256='a'*64)
    async def down(*args): raise OSError('temporary publish error')
    monkeypatch.setattr(index,'build',build);monkeypatch.setattr(index,'activate',down)
    index.index_job(q,j,SimpleNamespace())
    assert q.get_job(j)['status']=='FAILED' and q.article(aid)['status']=='APPROVED'
    q.retry_index(j,'actor')
    async def recovered(queue,ident,settings): queue.finish_index(ident,{'phase':'PUBLISHED_NEW_VERSION'})
    monkeypatch.setattr(index,'activate',recovered)
    index.index_job(q,j,SimpleNamespace())
    assert calls==['embedding']
    assert q.get_job(j)['status']=='ACTIVE' and q.article(aid)['status']=='INDEXED'


def test_failed_pointer_switch_cannot_report_success_or_mark_article_processed(tmp_path):
    import uuid
    q,j,aid=approved(tmp_path)
    old,current,new=[str(uuid.uuid4()) for _ in range(3)]
    q.publish_corpus(current,str(uuid.uuid4()))
    q.update_job(j,'RUNNING',phase='PUBLISHING')
    with pytest.raises(ValueError,match='SHARED_BASE_CHANGED'):
        q.finish_index(j,{},corpus_id=new,default_corpus=old,expected_base=old)
    assert q.serving_corpus(old)==current
    assert q.get_job(j)['status']=='RUNNING' and q.article(aid)['status']=='APPROVED'
