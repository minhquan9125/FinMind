"""The source reader must refuse unpinned or writable reads."""

import unittest
from unittest.mock import AsyncMock, patch

from backend.src.sprint4_runtime.bctn_source import read_verified_bctn_chunks


CORPUS = 'a5338f75-5894-5b8a-bf94-0a6da7c26ced'
INDEX = 'bcc6251d-ba1b-51d9-8fd5-92eb893a9ff0'


class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_requires_read_only_transaction(self):
        conn = AsyncMock()
        conn.fetchval.return_value = 'off'
        with self.assertRaisesRegex(ValueError, 'READ ONLY'):
            await read_verified_bctn_chunks(conn, CORPUS)
        conn.fetchrow.assert_not_awaited()

    async def test_rejects_unfrozen_corpus(self):
        conn = AsyncMock()
        conn.fetchval.return_value = 'on'
        conn.fetchrow.return_value = {'corpus_version_id': CORPUS, 'index_version_id': INDEX, 'status': 'DRAFT'}
        with self.assertRaisesRegex(ValueError, 'not frozen'):
            await read_verified_bctn_chunks(conn, CORPUS)
        conn.fetch.assert_not_awaited()

    async def test_rejects_document_hash_mismatch_before_reconstruction(self):
        conn = AsyncMock()
        conn.fetchval.return_value = 'on'
        conn.fetchrow.return_value = {'corpus_version_id': CORPUS, 'index_version_id': INDEX, 'status': 'FROZEN'}
        conn.fetch.return_value = [{'document_hash': 'a' * 64,
                                    'database_document_sha256': 'b' * 64}]
        release = {'corpus_version_id': CORPUS, 'sources': []}
        with patch('backend.src.sprint4_runtime.bctn_source.read_release_root',
                   new=AsyncMock(return_value=release)) as root:
            with self.assertRaisesRegex(ValueError, 'document hash mismatch'):
                await read_verified_bctn_chunks(conn, CORPUS)
        root.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
