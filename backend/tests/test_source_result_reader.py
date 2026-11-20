import asyncio
import copy
import hashlib
from dataclasses import replace

import pytest
from src.documents import repository
from src.documents.db_chunking import company_documents, chunk_document
from src.documents.chunk_reconstruction import ReconstructionError


def fixture():
    doc = company_documents([{'company_id': 'c1', 'symbol': 'FPT', 'company_name': 'FPT',
                              'exchange': 'HOSE', 'is_active': True}])[0]
    ch = chunk_document(doc)[0]
    return doc, {'locator_json': ch.locator, 'reference_text': ch.text,
                 'content_hash': ch.content_hash, 'chunker_version': 'db-v1',
                 'chunk_index': 0, 'page': None, 'score': 0.8}


def test_reads_source_without_stored_text_and_caches_source(monkeypatch):
    doc, row = fixture()
    calls = []
    async def fetch(conn, *args, **kwargs):
        calls.append((args, kwargs))
        return doc
    monkeypatch.setattr(repository, 'fetch_locator_document', fetch)
    row['reference_text'] = None
    result = asyncio.run(repository.resolve_result_rows(object(), [row, row]))
    assert len(calls) == 1
    assert result[0]['text'] == chunk_document(doc)[0].text
    assert result[0]['page'] is None


@pytest.mark.parametrize('case,code', [('changed', 'SOURCE_CHANGED'), ('missing', 'SOURCE_MISSING')])
def test_no_fallback_to_retained_text(monkeypatch, case, code):
    doc, row = fixture()
    if case == 'changed': doc.sections[0].header += 'changed'
    if case == 'comparison': row['reference_text'] = 'wrong retained text'
    async def fetch(*args, **kwargs): return None if case == 'missing' else doc
    monkeypatch.setattr(repository, 'fetch_locator_document', fetch)
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(object(), [row]))
    assert error.value.code == code


def test_diagnostic_preview_shows_current_source_and_marks_it_unverified(monkeypatch):
    doc, row = fixture()
    doc.sections[0].header += ' changed'
    old_row = doc.sections[0].rows[0]
    doc.sections[0].rows[0] = replace(old_row, text=old_row.text + ' changed')

    async def fetch(*args, **kwargs):
        return doc

    monkeypatch.setattr(repository, 'fetch_locator_document', fetch)
    result = asyncio.run(repository.resolve_result_rows(
        object(), [row], preview_source_changed=True,
    ))[0]
    assert 'changed' in result['text']
    assert result['source_verified'] is False
    assert result['source_warning'] == 'SOURCE_CHANGED'
    assert result['text'] != row['reference_text']


def test_diagnostic_preview_still_rejects_wrong_row_identity(monkeypatch):
    doc, row = fixture()
    doc.sections[0].header += ' changed'
    row['locator_json']['row_keys'] = ['wrong-key']

    async def fetch(*args, **kwargs):
        return doc

    monkeypatch.setattr(repository, 'fetch_locator_document', fetch)
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(
            object(), [row], preview_source_changed=True,
        ))
    assert error.value.code == 'SOURCE_MISMATCH'


def test_legacy_pdf_requires_source_locator():
    text = 'Uploaded PDF original text'
    row = {'locator_json': None, 'chunker_version': 'word-window-v1', 'reference_text': text,
           'content_hash': hashlib.sha256(text.encode()).hexdigest()}
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(object(), [row]))
    assert error.value.code == 'INVALID_LOCATOR'


def test_legacy_source_chunk_requires_backfill():
    _, row = fixture()
    del row['locator_json']['reconstruction']
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(object(), [row]))
    assert error.value.code == 'INVALID_LOCATOR'


def test_financial_reader_uses_renderer_from_locator(monkeypatch):
    _, row = fixture()
    row['locator_json']['source_table'] = 'financial_reports'
    row['locator_json']['reconstruction']['chunker_version'] = 'db-financial-v3'
    calls = []

    async def fetch(*args, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(repository, 'fetch_locator_document', fetch)
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(object(), [row]))
    assert error.value.code == 'SOURCE_MISSING'
    assert calls == [{'financial_renderer_version': 'db-financial-v3'}]


def test_v4_reader_uses_pinned_shared_source_without_live_fallback(monkeypatch):
    _, row = fixture()
    row['chunker_version'] = 'db-corpus-v2'
    row['index_version_id'] = repository.V4_SHARED_INDEX_ID
    row['locator_json']['source_table'] = 'financial_reports'
    row['locator_json']['reconstruction']['chunker_version'] = 'db-financial-v4'
    calls = []

    async def shared(conn, index_id, locator, expected_hash, cache):
        calls.append((index_id, expected_hash))
        return 'verified historical source'

    async def live(*args, **kwargs):
        raise AssertionError('v4 must not read the mutable live financial tables')

    from src.documents import shared_source
    monkeypatch.setattr(shared_source, 'resolve_shared_source', shared)
    monkeypatch.setattr(repository, 'fetch_locator_document', live)
    result = asyncio.run(repository.resolve_result_rows(object(), [row]))
    assert result[0]['text'] == 'verified historical source'
    assert calls == [(repository.V4_SHARED_INDEX_ID, row['content_hash'])]


def test_v4_source_changed_cannot_be_previewed_as_verified(monkeypatch):
    _, row = fixture()
    row['chunker_version'] = 'db-corpus-v2'
    row['index_version_id'] = repository.V4_SHARED_INDEX_ID
    row['locator_json']['source_table'] = 'financial_reports'
    row['locator_json']['reconstruction']['chunker_version'] = 'db-financial-v4'

    async def changed(*args, **kwargs):
        raise ReconstructionError('SOURCE_CHANGED', 'Historical payload changed')

    from src.documents import shared_source
    monkeypatch.setattr(shared_source, 'resolve_shared_source', changed)
    with pytest.raises(ReconstructionError) as error:
        asyncio.run(repository.resolve_result_rows(
            object(), [row], preview_source_changed=True,
        ))
    assert error.value.code == 'SOURCE_CHANGED'


def test_document_index_selects_correct_chunker():
    from src.documents.db_ingest import index_version_id_for
    assert repository.index_for_document({'file_type': 'DB'}, 130, 30, 'model') == index_version_id_for(130, 'model')
    assert repository.index_for_document({'file_type': 'PDF'}, 130, 30, 'model') == repository.index_version_id_for(130, 30, 'model')
