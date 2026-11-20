from types import SimpleNamespace

import pytest

from src.documents import admin_news_ocr as ocr
from src.documents.admin_ingestion import Queue, auto_review_reasons


def source_queue(tmp_path):
    q = Queue(tmp_path)
    job, _ = q.create_job('CRAWL', 'admin')
    q.update_job(job, 'RUNNING')
    payload = {'title': 'Thông báo kiểm thử', 'content': 'Xem tệp đính kèm',
               'source': 'fireant', 'url': 'https://fireant.vn/bai-viet/test/123',
               'raw': {'files': [{'fileName': 'report.pdf', 'fileContentUrl': 'https://mobiv2.fireant.vn/file/123'}]}}
    aid, _ = q.save_article(job, payload)
    q.update_job(job, 'COMPLETED')
    return q, aid, payload


def test_ocr_revision_preserves_source_and_requires_review(tmp_path, monkeypatch):
    q, aid, original = source_queue(tmp_path)
    monkeypatch.setattr(ocr, 'download', lambda url, path: path.write_bytes(b'%PDF-fixture'))
    monkeypatch.setattr(ocr, 'extract_file', lambda *args: [{'page_number': 1, 'text': 'Đủ nội dung để đọc', 'method': 'pdf_text'}])
    job, _ = q.create_job('OCR', 'admin', article_ids=[aid])
    ocr.ocr_job(q, job)
    result = q.get_job(job)
    assert result['status'] == 'COMPLETED'
    new = q.article(result['details']['article_id'])
    assert q.article(aid)['payload'] == original
    assert q.article(aid)['status'] == 'SUPERSEDED'
    assert new['status'] == 'PENDING'
    assert 'Đủ nội dung để đọc' in new['payload']['content']
    assert 'OCR_REVIEW_REQUIRED' in auto_review_reasons(new['payload'])


def test_failed_ocr_does_not_replace_source(tmp_path, monkeypatch):
    q, aid, original = source_queue(tmp_path)
    def fail(*args): raise ValueError('TESSERACT_NOT_AVAILABLE')
    monkeypatch.setattr(ocr, 'download', fail)
    job, _ = q.create_job('OCR', 'admin', article_ids=[aid])
    ocr.ocr_job(q, job)
    assert q.get_job(job)['status'] == 'FAILED'
    assert q.article(aid)['status'] == 'PENDING'
    assert q.article(aid)['payload'] == original


def test_cannot_approve_attachment_intro_before_extraction(tmp_path):
    q, aid, _ = source_queue(tmp_path)
    with pytest.raises(ValueError, match='SOURCE_TEXT_EXTRACTION_REQUIRED'):
        q.review(aid, 'APPROVED', 'Thử duyệt', 'admin')
    assert q.article(aid)['status'] == 'PENDING'


def test_inline_image_requires_ocr_even_with_intro_text():
    payload = {'content': 'Lời giới thiệu cho tài liệu trong ảnh. ' * 10,
               'raw': {'content': '<p>Giới thiệu</p><img src="https://images.fireant.vn/a.png">'}}
    assert 'OCR_REQUIRED' in auto_review_reasons(payload)


@pytest.mark.parametrize('url', ['http://fireant.vn/a', 'https://127.0.0.1/a',
                                  'https://fireant.vn.evil.test/a', 'https://fireant.vn:8443/a'])
def test_download_rejects_untrusted_urls(url):
    with pytest.raises(ValueError): ocr.checked_url(url)


def test_native_pdf_reuses_existing_extractor_without_tesseract(tmp_path, monkeypatch):
    path = tmp_path / 'input.bin'; path.write_bytes(b'%PDF-fixture')
    reused = SimpleNamespace(count_pdf_pages=lambda p: 1,
                             extract_native_pages=lambda p: ['Native text'], native_text_usable=lambda t: True)
    monkeypatch.setattr(ocr, 'engine', lambda: reused)
    monkeypatch.setattr(ocr, 'executable', lambda *args: None)
    assert ocr.extract_file(path, tmp_path)[0]['method'] == 'pdf_text'


def test_image_reuses_existing_tesseract_functions(tmp_path, monkeypatch):
    from PIL import Image
    path = tmp_path / 'image.bin'; Image.new('RGB', (10, 10), 'white').save(path, format='PNG')
    reused = SimpleNamespace(native_text_usable=lambda t: False,
                             preprocess_for_tesseract=lambda p: p,
                             run_tesseract=lambda p, exe, lang, psm: 'OCR tiếng Việt')
    monkeypatch.setattr(ocr, 'engine', lambda: reused)
    monkeypatch.setattr(ocr, 'executable', lambda *args: 'existing-engine')
    assert ocr.extract_file(path, tmp_path)[0] == {'page_number': 1, 'text': 'OCR tiếng Việt', 'method': 'tesseract'}


def test_recheck_extracts_v2_held_article_to_pending(tmp_path, monkeypatch):
    q, aid, _ = source_queue(tmp_path)
    q.auto_review('initial')
    monkeypatch.setattr(ocr, 'download', lambda url, path: path.write_bytes(b'%PDF-fixture'))
    monkeypatch.setattr(ocr, 'extract_file', lambda *args: [{'page_number': 1, 'text': 'Nội dung ảnh', 'method': 'tesseract'}])
    job, _ = q.create_job('RECHECK', 'admin')
    ocr.recheck_job(q, job)
    result = q.get_job(job)
    assert result['status'] == 'COMPLETED'
    assert result['details']['completed'] == 1
    assert result['details']['extracted'] == 1
    assert result['details']['approved'] == 0
    revision = result['details']['results'][0]['article_id']
    assert q.article(revision)['status'] == 'PENDING'
    assert q.article(aid)['status'] == 'SUPERSEDED'


def test_recheck_continues_after_file_error_and_preserves_failed_source(tmp_path, monkeypatch):
    q, aid, payload = source_queue(tmp_path)
    crawl, _ = q.create_job('CRAWL', 'admin'); q.update_job(crawl, 'RUNNING')
    other = {**payload, 'title': 'Bài lỗi', 'raw': {'files': [{'fileContentUrl': 'https://mobiv2.fireant.vn/fail'}]}}
    other_id, _ = q.save_article(crawl, other); q.update_job(crawl, 'COMPLETED')
    q.auto_review('initial')
    def download(url, path):
        if url.endswith('fail'): raise ValueError('FILE_UNREADABLE')
        path.write_bytes(b'%PDF-fixture')
    monkeypatch.setattr(ocr, 'download', download)
    monkeypatch.setattr(ocr, 'extract_file', lambda *args: [{'page_number': 1, 'text': 'OCR result', 'method': 'tesseract'}])
    job, _ = q.create_job('RECHECK', 'admin')
    ocr.recheck_job(q, job)
    result = q.get_job(job)
    assert result['status'] == 'PARTIAL'
    assert result['details']['completed'] == 2
    assert result['details']['extracted'] == 1
    assert result['details']['errors'][0]['article_id'] == other_id
    assert q.article(other_id)['status'] == 'QUARANTINED'
    assert q.article(other_id)['payload'] == other


def test_recheck_does_not_override_manual_hold(tmp_path):
    q, aid, _ = source_queue(tmp_path)
    q.review(aid, 'QUARANTINED', 'Cần người kiểm tra', 'human-reviewer')
    with pytest.raises(ValueError, match='NO_AUTOMATICALLY_HELD_ARTICLES'):
        q.create_job('RECHECK', 'admin')


def test_interrupted_recheck_cannot_save_revision(tmp_path, monkeypatch):
    q, aid, _ = source_queue(tmp_path); q.auto_review('initial')
    job, _ = q.create_job('RECHECK', 'admin')
    monkeypatch.setattr(ocr, 'download', lambda url, path: path.write_bytes(b'%PDF-fixture'))
    def extract(*args):
        q.interrupt(job, 'admin')
        return [{'page_number': 1, 'text': 'OCR', 'method': 'tesseract'}]
    monkeypatch.setattr(ocr, 'extract_file', extract)
    ocr.recheck_job(q, job)
    assert q.get_job(job)['status'] == 'INTERRUPTED'
    assert q.article(aid)['status'] == 'QUARANTINED'
    assert q.article_count('PENDING') == 0


def test_legacy_worker_replacement_is_not_a_rejection(tmp_path):
    q, aid, payload = source_queue(tmp_path)
    job, _ = q.create_job('OCR', 'admin', article_ids=[aid]); q.update_job(job, 'RUNNING')
    revision = q.save_ocr_revision(job, aid, {**payload, 'content':'OCR text', 'extraction':{'parent_article_id':aid}}, 'admin')
    with q.connect() as c:
        c.execute("UPDATE articles SET status='REJECTED' WHERE id=?", (aid,))
        c.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
                  (aid, 'old-worker', 'REJECTED', 'Đã thay bằng bản trích xuất cần duyệt: ' + revision, 'now'))
    assert q.article(aid)['status'] == 'SUPERSEDED'
    assert q.article(aid)['replacement_article_id'] == revision
    assert q.article_count('REJECTED') == 0


def test_existing_replacements_are_migrated_without_changing_human_rejections(tmp_path):
    q, aid, payload = source_queue(tmp_path)
    job, _ = q.create_job('OCR', 'admin', article_ids=[aid]); q.update_job(job, 'RUNNING')
    revision = q.save_ocr_revision(job, aid, {**payload, 'content':'OCR text', 'extraction':{'parent_article_id':aid}}, 'admin')
    with q.connect() as c:
        c.execute('DROP TRIGGER classify_legacy_ocr_replacement')
        c.execute("UPDATE articles SET status='REJECTED' WHERE id=?", (aid,))
        c.execute("UPDATE reviews SET decision='REJECTED' WHERE article_id=?", (aid,))
    migrated = Queue(tmp_path)
    assert migrated.article(aid)['status'] == 'SUPERSEDED'
    assert migrated.article(aid)['reviews'][-1]['actor'] == 'system:ocr-status-correction'
    migrated.review(revision, 'REJECTED', 'Người duyệt từ chối nội dung', 'human')
    assert Queue(tmp_path).article(revision)['status'] == 'REJECTED'
