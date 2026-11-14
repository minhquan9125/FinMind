import asyncio
import base64
import hashlib
import json

import pytest

from src.documents.repository import resolve_result_rows, insert_chunks
from src.documents.chunk_reconstruction import ReconstructionError
from src.documents.chunking import Page, build_chunks
from src.documents.upload_source import store_upload_source


class Conn:
    def __init__(self):
        self.sources = {}
        self.reads = 0
        self.writes = []

    async def execute(self, sql, *args):
        self.sources[args[0]] = {'sha256': args[2], 'payload': json.loads(args[3])}

    async def fetchrow(self, sql, payload_id):
        self.reads += 1
        return self.sources.get(payload_id)

    async def executemany(self, sql, rows):
        self.writes.append((sql, list(rows)))


def test_json_original_source_roundtrip_and_missing_or_tampered_source():
    async def run():
        conn = Conn()
        source = json.dumps([{'name': 'one', 'value': 2}]).encode()
        source_id = await store_upload_source(conn, source, 'JSON', 'USER_UPLOAD', None)
        from src.documents.json_ingest import generic_json_to_pages
        chunk = build_chunks(generic_json_to_pages(json.loads(source)), 130, 100)[0]
        row = {'chunk_index': 0, 'page': chunk.page, 'content_hash': hashlib.sha256(chunk.text.encode()).hexdigest(),
               'locator_json': {'schema_version': 'upload-source-v1', 'source_table': 'raw_payloads',
                                'source_id': source_id, 'chunk_size': 130, 'chunk_overlap': 30}}
        result = await resolve_result_rows(conn, [row, row])
        assert result[0]['text'] == chunk.text
        assert conn.reads == 1
        payload = next(iter(conn.sources.values()))
        payload['payload']['original_base64'] = base64.b64encode(b'changed').decode()
        with pytest.raises(ReconstructionError) as error:
            await resolve_result_rows(conn, [row])
        assert error.value.code == 'HASH_MISMATCH'
        conn.sources.clear()
        with pytest.raises(ReconstructionError) as error:
            await resolve_result_rows(conn, [row])
        assert error.value.code == 'SOURCE_MISSING'
    asyncio.run(run())


def test_upload_insert_never_writes_chunk_text_column():
    async def run():
        conn = Conn()
        row = {'chunk_index': 0, 'page': 1, 'locator_json': {'source_id': 'test'},
               'text': 'must not persist', 'token_count': 3, 'char_start': 0,
               'char_end': 16, 'content_hash': 'a' * 64, 'embedding': [0.1] * 1024}
        import uuid
        await insert_chunks(conn, str(uuid.uuid4()), str(uuid.uuid4()), [row])
        sql, rows = conn.writes[0]
        assert 'chunk_text' not in sql
        assert 'must not persist' not in str(rows)
    asyncio.run(run())


def test_pdf_original_is_reparsed_and_hash_verified(monkeypatch):
    async def run():
        conn = Conn()
        source_id = await store_upload_source(conn, b'original PDF bytes', 'PDF', 'USER_UPLOAD', None)
        monkeypatch.setattr('src.documents.upload_source.extract_pages', lambda raw: [Page(1, 'PDF content')])
        row = {'chunk_index': 0, 'page': 1, 'content_hash': hashlib.sha256(b'PDF content').hexdigest(),
               'locator_json': {'schema_version': 'upload-source-v1', 'source_table': 'raw_payloads',
                                'source_id': source_id, 'chunk_size': 130, 'chunk_overlap': 30}}
        assert (await resolve_result_rows(conn, [row]))[0]['text'] == 'PDF content'
        row['content_hash'] = '0' * 64
        with pytest.raises(ReconstructionError):
            await resolve_result_rows(conn, [row])
    asyncio.run(run())
