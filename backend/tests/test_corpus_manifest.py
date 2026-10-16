import asyncio
import copy
import hashlib
import uuid

import pytest

from src.documents.corpus_manifest import build_manifest, register_manifest

INDEX = {'index_version_id': str(uuid.uuid4()), 'chunker_version': 'db-v1',
         'chunk_size': 130, 'chunk_overlap': 0, 'embedding_model': 'test'}


def rows():
    return [{'document_id': str(uuid.uuid4()), 'chunk_id': str(uuid.uuid4()),
             'document_hash': 'a' * 64, 'doc_type': 'NEWS', 'title': 'Tin',
             'external_id': 'article', 'source_url': 'https://example.com',
             'chunk_index': 0, 'chunk_text': 'Nội dung',
             'content_hash': hashlib.sha256('Nội dung'.encode()).hexdigest(),
             'dimensions': 1024, 'locator_json': {'source_table': 'news_articles',
                                                'source_id': 'article', 'row_keys': ['p1']}}
            for _ in range(2)]


def test_order_does_not_change_version():
    data = rows()
    assert build_manifest(INDEX, data) == build_manifest(INDEX, data[::-1])


def test_locator_change_creates_new_version_without_changing_chunk_ids():
    data = rows()
    before = build_manifest(INDEX, data)
    data[0]['locator_json']['row_keys'] = ['p2']
    after = build_manifest(INDEX, data)
    assert before['corpus_version_id'] != after['corpus_version_id']
    assert {d['chunks'][0]['chunk_id'] for d in before['manifest']['documents']} == {r['chunk_id'] for r in data}


@pytest.mark.parametrize('failure', ['empty', 'duplicate', 'hash', 'vector', 'locator'])
def test_refuses_invalid_snapshot(failure):
    data = rows()
    if failure == 'empty': data = []
    if failure == 'duplicate': data.append(data[0])
    if failure == 'hash': data[0]['content_hash'] = 'b' * 64
    if failure == 'vector': data[0]['dimensions'] = 384
    if failure == 'locator': data[0]['locator_json'] = None
    with pytest.raises(ValueError): build_manifest(INDEX, data)


class Conn:
    def __init__(self):
        self.existing = []
        self.members = []
        self.writes = []

    async def execute(self, sql, *args):
        if 'INSERT' in sql: self.writes.append((sql, args))

    async def executemany(self, sql, args):
        self.writes.append((sql, args))

    async def fetch(self, sql, *args):
        return self.members if 'corpus_documents' in sql else self.existing


def test_register_and_idempotent_rerun():
    manifest = build_manifest(INDEX, rows())
    conn = Conn()
    assert asyncio.run(register_manifest(conn, manifest, 'v1'))
    assert len(conn.writes) == 2
    conn.existing = [{'corpus_version_id': manifest['corpus_version_id'],
                      'version_label': 'v1', 'manifest_sha256': manifest['manifest_sha256']}]
    conn.members = manifest['manifest']['documents']
    conn.writes = []
    assert not asyncio.run(register_manifest(conn, manifest, 'v1'))
    assert not conn.writes
    conn.existing[0]['manifest_sha256'] = 'b' * 64
    with pytest.raises(ValueError): asyncio.run(register_manifest(conn, manifest, 'v1'))
    assert not conn.writes


def test_rejects_tampered_payload_before_writing():
    manifest = copy.deepcopy(build_manifest(INDEX, rows()))
    manifest['manifest']['documents'][0]['chunks'][0]['text'] = 'changed'
    conn = Conn()
    with pytest.raises(ValueError): asyncio.run(register_manifest(conn, manifest, 'v1'))
    assert not conn.writes
