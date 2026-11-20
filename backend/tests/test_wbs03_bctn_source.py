"""The source reader must refuse unpinned or writable reads."""

import unittest
from unittest.mock import AsyncMock, patch

from backend.src.documents.chunk_reconstruction import ReconstructionError
from backend.src.documents.release_identity import release_document_id, validate_document_binding
from backend.src.sprint4_runtime.bctn_source import read_verified_bctn_chunks


CORPUS = 'a5338f75-5894-5b8a-bf94-0a6da7c26ced'
INDEX = 'bcc6251d-ba1b-51d9-8fd5-92eb893a9ff0'
SOURCE_DOCUMENT = '0be7ae10-6a32-5b37-9247-db09708bfe11'
RELEASE_INDEX = 'ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d'
RELEASE_DOCUMENT = 'f0730a07-8ab5-548a-a3b8-e099489d0f29'


class DocumentBindingTests(unittest.TestCase):
    def test_direct_source_and_release_alias(self):
        locator = {'reconstruction': {'document_id': SOURCE_DOCUMENT}}
        direct = validate_document_binding(SOURCE_DOCUMENT, INDEX, locator)
        alias = validate_document_binding(RELEASE_DOCUMENT, RELEASE_INDEX, locator)
        self.assertEqual(direct['mode'], 'DIRECT_SOURCE_ID')
        self.assertEqual(alias['mode'], 'RELEASE_DOCUMENT_ALIAS_V1')
        self.assertEqual(release_document_id(RELEASE_INDEX, SOURCE_DOCUMENT), RELEASE_DOCUMENT)

    def test_rejects_alias_from_another_index(self):
        locator = {'reconstruction': {'document_id': SOURCE_DOCUMENT}}
        with self.assertRaises(ReconstructionError):
            validate_document_binding(RELEASE_DOCUMENT, INDEX, locator)


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
