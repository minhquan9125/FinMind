import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.documents.admin_ingestion import Queue, crawl_job
from src.documents.admin_news_index import prepare, resolve_snapshot, activate
from src.documents.chunk_reconstruction import ReconstructionError
from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal


def article():
    return {'source': 'fireant', 'url': 'https://fireant.vn/bai-viet/fixture/123',
            'title': 'Nguồn kiểm thử', 'content': 'FPT đã hoàn thiện hai AI Factory tại Việt Nam.',
            'published_at': '2026-11-05T07:00:00+07:00', 'symbols': ['FPT'], 'raw': {'original': 'source'}}


def populated(tmp_path):
    q = Queue(tmp_path); jid, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, jid, lambda limit: ([article()], []))
    return q, q.articles()[0]['id']


def test_raw_is_saved_before_review_and_embedding_is_blocked(tmp_path):
    q, aid = populated(tmp_path)
    assert q.article(aid)['payload']['raw'] == {'original': 'source'}
    assert q.article(aid)['status'] == 'PENDING'
    with pytest.raises(ValueError, match='NOT_APPROVED'):
        q.create_job('INDEX', 'operator', article_ids=[aid])
    with pytest.raises(ValueError, match='NOT_APPROVED'): prepare(q.article(aid))
    q.review(aid, 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer-id')
    restored = Queue(tmp_path).article(aid)
    assert restored['reviews'][0]['actor'] == 'reviewer-id'
    assert restored['status'] == 'APPROVED'
    with pytest.raises(ValueError, match='ALREADY_DECIDED'):
        q.review(aid, 'REJECTED', 'Không sửa quyết định cũ.', 'other-reviewer')


def test_repeat_crawl_deduplicates_but_changed_body_requires_new_review(tmp_path):
    q, aid = populated(tmp_path)
    a = article(); a['raw']['view_count'] = 999; a['crawled_at'] = 'later'
    j, _ = q.create_job('CRAWL', 'operator'); crawl_job(q, j, lambda limit: ([a], []))
    assert len(q.articles()) == 1 and q.get_job(j)['details']['duplicates'] == 1
    a['content'] += ' Bản cập nhật.'
    j, _ = q.create_job('CRAWL', 'operator'); crawl_job(q, j, lambda limit: ([a], []))
    assert len(q.articles()) == 2
    assert q.article(aid)['payload']['content'] == article()['content']


def test_daily_claim_is_persisted_and_not_duplicated(tmp_path):
    q = Queue(tmp_path)
    assert q.due(datetime(2026, 11, 5, 1, tzinfo=timezone.utc)) is None
    q.config({'enabled': True, 'hour': 7, 'limit': 20, 'provider': 'fireant'})
    assert q.due(datetime(2026, 11, 4, 23, tzinfo=timezone.utc)) is None  # VN 06:00
    ident = q.due(datetime(2026, 11, 5, 0, tzinfo=timezone.utc))
    assert ident
    q.update_job(ident, 'COMPLETED')
    assert Queue(tmp_path).due(datetime(2026, 11, 5, 5, tzinfo=timezone.utc)) is None
    assert q.due(datetime(2026, 11, 6, 0, tzinfo=timezone.utc))


def test_job_failures_are_recorded_without_secret_exception(tmp_path):
    q = Queue(tmp_path); ident, _ = q.create_job('CRAWL', 'operator')
    def broken(limit): raise RuntimeError('postgres://secret@private')
    crawl_job(q, ident, broken)
    assert q.get_job(ident)['status'] == 'FAILED'
    assert 'secret' not in str(q.jobs())
    q.create_job('CRAWL', 'operator')
    with pytest.raises(ValueError, match='ANOTHER_JOB'): q.create_job('CRAWL', 'operator')


def test_chunker_and_snapshot_reconstruction_keep_exact_source(tmp_path):
    q, aid = populated(tmp_path); q.review(aid, 'APPROVED', 'Đúng nguồn.', 'reviewer')
    payload, pid, checksum, doc, chunks = prepare(q.article(aid))
    assert doc.source_table == 'raw_payloads' and chunks
    class Conn:
        async def fetchrow(self, sql, ident):
            assert ident == pid
            return {'payload': json.dumps(payload), 'sha256': checksum}
    actual = asyncio.run(resolve_snapshot(Conn(), chunks[0].locator, chunks[0].content_hash))
    assert actual == chunks[0].text
    payload['article']['content'] += ' changed'
    with pytest.raises(ReconstructionError, match='Snapshot changed'):
        asyncio.run(resolve_snapshot(Conn(), chunks[0].locator, chunks[0].content_hash))


def test_activate_rejects_unbuilt_job_before_connecting(tmp_path):
    q = Queue(tmp_path); ident, _ = q.create_job('CRAWL', 'operator')
    with pytest.raises(ValueError, match='INDEX_NOT_READY'):
        asyncio.run(activate(q, ident, SimpleNamespace()))


def test_interrupted_job_cannot_resume_writing_sources(tmp_path):
    q = Queue(tmp_path); ident, _ = q.create_job('CRAWL', 'operator')
    q.update_job(ident, 'RUNNING')
    q.interrupt(ident, 'administrator')
    with pytest.raises(ValueError, match='NOT_RUNNING'): q.save_article(ident, article())
    with pytest.raises(ValueError, match='INTERRUPTED'): q.update_job(ident, 'COMPLETED')
    assert q.get_job(ident)['status'] == 'INTERRUPTED'
    assert q.create_job('CRAWL', 'operator')[1]


def qualified_article():
    row = article()
    row['raw'] = {'postID':123,'type':1}
    row['content'] = 'Nội dung bài viết nguồn cung cấp đầy đủ dữ liệu và thông tin. ' * 20
    return row


def test_auto_review_checks_and_preserves_history(tmp_path):
    q = Queue(tmp_path); j,_ = q.create_job('CRAWL','operator')
    good = qualified_article(); bad = {**good,'url':'https://example.org/not-fireant','title':'Khác nguồn'}
    crawl_job(q,j,lambda limit:([good,bad],[]))
    result = q.auto_review('operator-id')
    assert result == {'approved':1,'quarantined':1}
    assert q.auto_review('operator-id') == {'approved':0,'quarantined':0}
    for a in q.articles():
        review = q.article(a['id'])['reviews'][0]
        assert review['actor']=='auto:operator-id' and review['note'].startswith('source-quality-v2:')


def test_auto_review_flag_only_applies_to_new_articles(tmp_path):
    q = Queue(tmp_path); old,_=q.create_job('CRAWL','operator')
    crawl_job(q,old,lambda limit:([article()],[]))
    cfg=q.config();cfg['auto_approve']=True;q.config(cfg)
    newer={**qualified_article(),'url':'https://fireant.vn/bai-viet/new/456','raw':{'type':1,'postID':456}}
    j,_=q.create_job('CRAWL','operator');crawl_job(q,j,lambda limit:([newer],[]))
    assert sorted(a['status'] for a in q.articles())==['APPROVED','PENDING']
    assert q.get_job(j)['details']['auto_review']['approved']==1


def test_api_accepts_larger_crawl_scope_and_paginates(client):
    c,app=client;grant(app)
    cfg={'limit':300,'symbols':['FPT','VCB'],'max_pages':10,'auto_approve':True,'include_market':False}
    response=c.put('/api/v1/admin/ingestion/source',json=cfg)
    assert response.status_code==200 and response.json()['symbols']==['FPT','VCB']
    assert c.put('/api/v1/admin/ingestion/source',json={**cfg,'symbols':['BAD-URL']}).status_code==422
    assert c.put('/api/v1/admin/ingestion/source',json={**cfg,'limit':501}).status_code==422
    q=api.queue();j,_=q.create_job('CRAWL','operator')
    q.update_job(j,'RUNNING')
    for i in range(3): q.save_article(j,{**article(),'title':f'Article {i}'})
    page=c.get('/api/v1/admin/ingestion/articles?offset=1&limit=1').json()
    assert page['total']==3 and len(page['items'])==1


def test_selection_contains_only_approved_and_processed_job_links_survive(tmp_path):
    q, aid = populated(tmp_path)
    assert q.selection()['approved_ids']==[]
    q.review(aid,'APPROVED','Đúng nguồn.','reviewer')
    assert q.selection()['approved_ids']==[aid]
    index_id,_=q.create_job('INDEX','operator',article_ids=[aid])
    q.update_job(index_id,'INDEXED',corpus_version_id='fixture-corpus')
    q.indexed(index_id)
    assert q.selection()['approved_ids']==[]
    assert q.selection()['counts']['INDEXED']==1
    assert q.processed_jobs(aid)[0]['id']==index_id


def test_relaxed_quality_accepts_short_informative_text_but_detects_pdf_and_images():
    from src.documents.admin_ingestion import auto_review_reasons,source_attachments
    row=qualified_article()
    row['content']='Doanh nghiệp công bố thay đổi lịch tổ chức họp cổ đông sang ngày mới và giữ nguyên các quyền của cổ đông.'
    assert 80<=len(row['content'])<300
    assert auto_review_reasons(row)==[]
    row['raw']['files']=[{'fileName':'Nghi quyet.pdf','fileContentUrl':'https://mobiv2.fireant.vn/News/NewsAttachedFile/123'}]
    row['content']='Công ty cổ phần công nghệ công bố nghị quyết của Hội đồng quản trị về điều chỉnh kế hoạch hoạt động như sau:'
    assert 'ATTACHMENT_TEXT_REQUIRED' in auto_review_reasons(row)
    assert source_attachments(row)[0]['name']=='Nghi quyet.pdf'
    row['content']='';row['raw']['content']='<img src="https://example.invalid/image.png">'
    assert 'OCR_REQUIRED' in auto_review_reasons(row)


def test_recheck_only_updates_old_automatic_decisions(tmp_path):
    q=Queue(tmp_path);j,_=q.create_job('CRAWL','operator')
    row=qualified_article()
    row['content']='Doanh nghiệp công bố thay đổi lịch tổ chức họp cổ đông sang ngày mới và giữ nguyên các quyền của cổ đông.'
    other={**row,'title':'Thông báo khác'}
    crawl_job(q,j,lambda limit:([row,other],[]))
    ids=[a['id'] for a in q.articles()]
    q.review(ids[0],'QUARANTINED','source-quality-v1: SHORT_OR_EMPTY_BODY','auto:old-policy')
    q.review(ids[1],'QUARANTINED','Người duyệt yêu cầu đối chiếu thêm.','human-reviewer')
    assert q.auto_review('operator',recheck_previous=True)=={'approved':1,'quarantined':0}
    assert q.article(ids[0])['status']=='APPROVED'
    assert len(q.article(ids[0])['reviews'])==2
    assert q.article(ids[1])['status']=='QUARANTINED'
    assert len(q.article(ids[1])['reviews'])==1


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(admin_ingestion_directory=tmp_path, admin_ingest_database_url=None))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def grant(app):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))


def test_api_requires_auth_and_scopes_user_actions(client, monkeypatch):
    c, app = client
    assert c.get('/api/v1/admin/ingestion/articles').status_code == 401
    grant(app)
    assert c.get('/api/v1/admin/ingestion/source').json()['enabled'] is False
    assert c.put('/api/v1/admin/ingestion/source', json={'hour': 30}).status_code == 422
    assert c.put('/api/v1/admin/ingestion/source', json={'provider': 'arbitrary-url'}).status_code == 422
    assert c.get('/api/v1/admin/ingestion/articles/not-a-uuid').status_code == 422


def test_api_review_survives_reload_and_index_requires_writer_config(client):
    c, app = client; grant(app)
    q = api.queue(); j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article()], []))
    aid = c.get('/api/v1/admin/ingestion/articles').json()['items'][0]['id']
    path = '/api/v1/admin/ingestion/articles/' + aid
    response = c.post(path + '/review', json={'decision': 'APPROVED', 'note': 'Đã xem nguồn.'})
    assert response.status_code == 200
    assert c.get(path).json()['reviews'][0]['actor'] == str(UUID(int=1))
    assert c.post('/api/v1/admin/ingestion/index', json={'article_ids': [aid]}).status_code == 503
