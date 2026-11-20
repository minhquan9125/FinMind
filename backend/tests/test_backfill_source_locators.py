import importlib.util
import copy
from pathlib import Path

import pytest
from src.documents.db_chunking import chunk_document, company_documents
from src.documents.db_ingest import stored_chunk_id, index_version_id_for

spec = importlib.util.spec_from_file_location('backfill_locator', Path(__file__).resolve().parents[1] / 'scripts/backfill_source_locators.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    doc = company_documents([{'company_id': 'c1', 'symbol': 'FPT', 'company_name': 'FPT', 'exchange': 'HOSE', 'is_active': True}])[0]
    chunks = {c.chunk_index: c for c in chunk_document(doc)}
    ch = chunks[0]
    index = index_version_id_for(130, 'test-model')
    loc = copy.deepcopy(ch.locator)
    del loc['reconstruction']
    loc['custom_key'] = 'preserved'
    row = {'chunker_version': 'db-v1', 'chunk_index': 0, 'chunk_text': ch.text,
           'content_hash': ch.content_hash, 'index_version_id': index,
           'chunk_id': stored_chunk_id(index, ch), 'locator_json': loc}
    return row, doc, chunks


def test_adds_only_reconstruction_and_rerun_has_no_change():
    row, doc, chunks = fixture()
    old, new = module.locator_update(row, doc, chunks)
    assert {k: v for k, v in new.items() if k != 'reconstruction'} == old
    row['locator_json'] = new
    assert module.locator_update(row, doc, chunks) == (new, new)


@pytest.mark.parametrize('change', ['text', 'id', 'keys', 'source'])
def test_rejects_stale_or_invalid_rows(change):
    row, doc, chunks = fixture()
    if change == 'text': row['chunk_text'] += 'changed'
    if change == 'id': row['chunk_id'] = 'incorrect'
    if change == 'keys': row['locator_json']['row_keys'] = ['wrong']
    if change == 'source': doc = None
    with pytest.raises(ValueError): module.locator_update(row, doc, chunks)
