from src.documents.admin_ingestion import Queue, crawl_job
from src.documents import admin_news_ocr as ocr


def article(ident, content='Xem tệp đính kèm'):
    return {'title':f'Tài liệu kiểm thử {ident}','source':'fireant',
        'url':f'https://fireant.vn/bai-viet/test/{ident}','content':content,
        'published_at':'2026-11-01T07:00:00+07:00',
        'raw':{'type':1,'postID':ident,'files':[{'fileName':'report.pdf',
            'fileContentUrl':f'https://mobiv2.fireant.vn/News/NewsAttachedFile/{ident}'}]}}


def test_crawl_extracts_before_review_and_retains_raw_source(tmp_path,monkeypatch):
    q=Queue(tmp_path);cfg=q.config();cfg['auto_approve']=True;q.config(cfg)
    monkeypatch.setattr(ocr,'download',lambda url,path:path.write_bytes(b'%PDF-fixture'))
    monkeypatch.setattr(ocr,'extract_file',lambda *args:[{'page_number':1,'text':'Văn bản chính sau khi đọc PDF. '*30,'method':'pdf_text'}])
    j,_=q.create_job('CRAWL','admin');crawl_job(q,j,lambda limit:([article(123)],[]))
    rows=q.articles();assert len(rows)==2
    parent=next(r for r in rows if r['status']=='SUPERSEDED')
    child=next(r for r in rows if r['status']=='PENDING')
    assert q.article(parent['id'])['payload']==article(123)
    assert 'Văn bản chính' in q.article(child['id'])['payload']['content']
    assert q.get_job(j)['details']['extracted']==1
    q.review(child['id'],'APPROVED','Đã kiểm tra phần chữ và số liệu.','admin')
    index,_=q.create_job('INDEX','admin',article_ids=[child['id']])
    assert q.get_job(index)['status']=='QUEUED'


def test_crawl_source_failure_is_held_and_does_not_block_other_articles(tmp_path,monkeypatch):
    q=Queue(tmp_path)
    plain=article(456,'Văn bản chính đầy đủ của bài báo. '*30);plain['raw']['files']=[]
    def fail(*args):raise ValueError('PRIVATE_PROVIDER_DETAIL')
    monkeypatch.setattr(ocr,'download',fail)
    j,_=q.create_job('CRAWL','admin');crawl_job(q,j,lambda limit:([article(123),plain],[]))
    assert q.get_job(j)['status']=='PARTIAL'
    assert sorted(r['status'] for r in q.articles())==['PENDING','QUARANTINED']
    assert 'PRIVATE_PROVIDER_DETAIL' not in str(q.jobs())
    held=next(r for r in q.articles() if r['status']=='QUARANTINED')
    assert 'ValueError' in q.article(held['id'])['reviews'][-1]['note']


def test_duplicate_crawl_does_not_repeat_successful_ocr(tmp_path,monkeypatch):
    q=Queue(tmp_path);calls=[]
    monkeypatch.setattr(ocr,'download',lambda url,path:(calls.append(url),path.write_bytes(b'%PDF-fixture')))
    monkeypatch.setattr(ocr,'extract_file',lambda *args:[{'page_number':1,'text':'Văn bản gốc. '*50,'method':'pdf_text'}])
    for _ in range(2):
        j,_=q.create_job('CRAWL','admin');crawl_job(q,j,lambda limit:([article(123)],[]))
    assert len(calls)==1 and q.article_count()==2


def test_legacy_migration_is_idempotent_and_retains_approval_history(tmp_path):
    q=Queue(tmp_path);j,_=q.create_job('CRAWL','admin');q.update_job(j,'RUNNING')
    aid,_=q.save_article(j,article(123));q.update_job(j,'COMPLETED')
    with q.connect() as conn:
        conn.execute("UPDATE articles SET status='APPROVED' WHERE id=?",(aid,))
        conn.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
            (aid,'legacy-admin','APPROVED','Đã duyệt theo bản cũ','2026-11-01T00:00:00+00:00'))
    assert q.repair_legacy_source_approvals()==[aid]
    assert q.repair_legacy_source_approvals()==[]
    assert [r['decision'] for r in q.article(aid)['reviews']]==['APPROVED','QUARANTINED']
    job,_=q.create_job('RECHECK','admin')
    assert aid in q.get_job(job)['details']['article_ids']
