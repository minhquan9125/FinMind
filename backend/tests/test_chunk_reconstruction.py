import asyncio
import copy
from datetime import date, datetime, timezone

import pytest

from src.documents.db_chunking import (
    chunk_document, company_documents, financial_documents, price_documents,
    index_documents, news_documents,
)
from src.documents.chunk_reconstruction import (
    reconstruct_document_chunk, reconstruct_chunk, ReconstructionError,
)


def source_docs():
    company = {'company_id': 'company-1', 'symbol': 'FPT', 'company_name': 'FPT',
               'exchange': 'HOSE', 'industry_type': 'TECH', 'sector': 'Công nghệ', 'is_active': True}
    news = {'article_id': 'article-1', 'title': 'FPT công bố kết quả', 'source': 'cafef',
            'content': ' '.join(['Nội dung câu dài.'] * 90), 'symbols': ['FPT'],
            'published_at': datetime(2026, 10, 1, tzinfo=timezone.utc), 'url': 'https://example.test/article'}
    price = {'price_id': 'price-1', 'symbol': 'FPT', 'company_name': 'FPT',
             'trade_date': date(2026, 10, 1), 'open': 50, 'high': 52, 'low': 49,
             'close': 51, 'volume': 1000, 'price_scale': 1000}
    index = {**price, 'index_symbol': 'VNINDEX', 'index_name': 'VN-Index', 'exchange': 'HOSE'}
    financial = {'report_id': 'report-1', 'symbol': 'FPT', 'company_name': 'FPT',
                 'period_code': '2026-Q2', 'statement_scope': 'UNKNOWN',
                 'section': 'INCOME_STATEMENT', 'code': 'NET_REVENUE', 'canonical_name': 'Doanh thu',
                 'observation_id': 'observation-1', 'value': 123456789, 'unit': 'VND'}
    return [company_documents([company])[0], news_documents([news], max_words=55)[0],
            price_documents([price])[0], index_documents([index])[0], financial_documents([financial])[0]]


@pytest.mark.parametrize('doc', source_docs(), ids=['company', 'long-news', 'price-summary', 'index-summary', 'financial'])
def test_all_source_types_roundtrip_without_database_text(doc):
    for chunk in chunk_document(doc, 55):
        result = reconstruct_document_chunk(doc, chunk.locator, chunk.content_hash)
        assert result.text == chunk.text
        assert result.source_chunk_id == chunk.chunk_id
        assert result.document_id == chunk.document_id
        assert result.content_hash == chunk.content_hash
        assert 'text' not in chunk.locator['reconstruction']


def test_locator_only_change_preserves_chunk_identity():
    doc = source_docs()[0]
    first = chunk_document(doc)[0]
    # Hash and deterministic ID remain the pre-v2 formula, independent of locator.
    import hashlib, uuid
    from src.documents.db_chunking import NAMESPACE, CHUNKER_VERSION
    assert first.content_hash == hashlib.sha256(first.text.encode()).hexdigest()
    assert first.chunk_id == str(uuid.uuid5(NAMESPACE, f'chunk:{doc.document_id}:{CHUNKER_VERSION}:0:0:{first.content_hash}'))


@pytest.mark.parametrize('version', ['db-v1', 'db-financial-v2', 'db-financial-v3'])
def test_financial_reader_preserves_old_text_and_uses_versioned_new_header(version):
    import hashlib
    import uuid
    from src.documents.db_chunking import NAMESPACE
    row = {'report_id': 'report-1', 'symbol': 'FPT', 'company_name': 'FPT',
           'period_code': '2026-Q2', 'statement_scope': 'UNKNOWN',
           'section': 'BALANCE_SHEET', 'code': 'TOTAL_ASSETS', 'canonical_name': 'Tổng tài sản',
           'observation_id': 'observation-1', 'value': 123, 'unit': 'SOURCE_NATIVE'}
    doc = financial_documents([row], renderer_version=version)[0]
    chunk = chunk_document(doc)[0]
    if version == 'db-v1':
        expected = ('FPT (FPT) | Bảng Cân đối kế toán | tại cuối quý 2/2026 | '
                    'Phạm vi: UNKNOWN | Đơn vị: triệu VND, trừ EPS (VND/cổ phiếu) và chỉ số tỷ lệ\n'
                    'Tổng tài sản (TOTAL_ASSETS): 123')
        assert chunk.text == expected
        digest = hashlib.sha256(expected.encode('utf-8')).hexdigest()
        assert chunk.chunk_id == str(uuid.uuid5(NAMESPACE, f'chunk:{doc.document_id}:db-v1:0:0:{digest}'))
    else:
        assert 'triệu VND' not in chunk.text
        assert 'chưa xác minh' in chunk.text
        row_text = doc.sections[0].rows[0].text
        assert ('đơn vị chưa xác minh' in row_text) == (version == 'db-financial-v3')
    assert chunk.locator['reconstruction']['chunker_version'] == version

    class Conn:
        async def fetch(self, sql, *params):
            assert 'text_chunks' not in sql
            return [row]

    assert asyncio.run(reconstruct_chunk(Conn(), chunk.locator, chunk.content_hash)).text == chunk.text


def test_changed_source_cannot_silently_use_new_text():
    doc = source_docs()[0]
    chunk = chunk_document(doc)[0]
    changed = copy.deepcopy(doc)
    changed.sections[0].header += ' changed'
    with pytest.raises(ReconstructionError) as error:
        reconstruct_document_chunk(changed, chunk.locator, chunk.content_hash)
    assert error.value.code == 'SOURCE_CHANGED'


@pytest.mark.parametrize('change', ['hash', 'range', 'version', 'keys', 'legacy'])
def test_invalid_locator_fails_closed(change):
    doc = source_docs()[0]
    chunk = chunk_document(doc)[0]
    locator = copy.deepcopy(chunk.locator)
    if change == 'hash': locator['reconstruction']['content_hash'] = '0' * 64
    if change == 'range': locator['reconstruction']['row_end'] = 9999
    if change == 'version': locator['reconstruction']['chunker_version'] = 'unknown'
    if change == 'keys': locator['row_keys'] = ['another:field']
    if change == 'legacy': del locator['reconstruction']
    with pytest.raises(ReconstructionError):
        reconstruct_document_chunk(doc, locator, chunk.content_hash)


def test_async_reader_queries_source_only_and_detects_deleted_article():
    row = {'article_id': 'article-1', 'title': 'Tin', 'source': 'cafef', 'content': 'Nội dung bài.',
           'symbols': [], 'url': 'https://example.test', 'published_at': date(2026, 10, 1)}
    doc = news_documents([row])[0]
    chunk = chunk_document(doc)[0]

    class Conn:
        deleted = False
        async def fetch(self, sql, *params):
            assert 'FROM public.news_articles' in sql
            assert 'text_chunks' not in sql and 'UPDATE' not in sql
            assert params == ('article-1',)
            return [] if self.deleted else [row]

    conn = Conn()
    assert asyncio.run(reconstruct_chunk(conn, chunk.locator, chunk.content_hash)).text == chunk.text
    conn.deleted = True
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(reconstruct_chunk(conn, chunk.locator, chunk.content_hash))
    assert error.value.code == 'SOURCE_MISSING'
