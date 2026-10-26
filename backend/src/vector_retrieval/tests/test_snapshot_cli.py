import io
import json
import sys
import unittest
from contextlib import ExitStack,redirect_stdout,redirect_stderr
from pathlib import Path
from unittest.mock import AsyncMock,Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from src.vector_retrieval import hoi as cli

INDEX='434ef5e0-6516-578d-8d18-721d21347e01'
PIN='a'*64


class SnapshotCLITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.out,self.err=io.StringIO(),io.StringIO()
        self.stack.enter_context(redirect_stdout(self.out));self.stack.enter_context(redirect_stderr(self.err))
        self.connect=self.stack.enter_context(patch.object(cli,'connect',new_callable=AsyncMock))
        self.disconnect=self.stack.enter_context(patch.object(cli,'disconnect',new_callable=AsyncMock))
        self.stack.enter_context(patch.object(cli,'get_pool',return_value='pool'))
        self.embed=self.stack.enter_context(patch.object(cli,'get_embedding_service',return_value='embed'))
        self.reader=Mock(provenance=dict(mode='FROZEN_SNAPSHOT',manifest_sha256=PIN))
        self.snapshot=self.stack.enter_context(patch.object(cli,'SnapshotResolver',return_value=self.reader))
        self.service=Mock(build_cache=AsyncMock(return_value=dict(status='CACHE_READY',chunks=2)),
                          search=AsyncMock(return_value=dict(results=[],scope_mode='INDEX')))
        self.factory=self.stack.enter_context(patch.object(cli,'HybridRetriever',return_value=self.service))

    def args(self,command='build'):
        return [command,'--index',INDEX,'--source-snapshot','frozen.json','--snapshot-sha256',PIN]

    async def test_flags_and_pair_validation_before_db_model(self):
        parsed=cli.parse_args(self.args())
        self.assertEqual(parsed.source_snapshot,'frozen.json');self.assertEqual(parsed.snapshot_sha256,PIN)
        for suffix in (['--source-snapshot','frozen.json'],['--snapshot-sha256',PIN]):
            with self.subTest(suffix=suffix):
                self.assertEqual(await cli.main(['build','--index',INDEX]+suffix),1)
        self.connect.assert_not_called();self.embed.assert_not_called();self.snapshot.assert_not_called()

    async def test_invalid_manifest_fails_before_connect_and_keeps_safe_code(self):
        for code in ('SNAPSHOT_INVALID_HASH','SNAPSHOT_HASH_MISMATCH','SNAPSHOT_UNAVAILABLE'):
            self.snapshot.side_effect=cli.SnapshotError(code)
            self.assertEqual(await cli.main(self.args()),1)
            self.assertIn(code,self.err.getvalue());self.assertNotIn('SNAPSHOT_SNAPSHOT_',self.err.getvalue())
        self.connect.assert_not_called();self.embed.assert_not_called();self.disconnect.assert_not_called()

    async def test_build_snapshot_injected_once_and_disclosed(self):
        self.assertEqual(await cli.main(self.args()),0)
        self.snapshot.assert_called_once_with('frozen.json',PIN)
        self.factory.assert_called_once_with('pool','embed',resolver=self.reader)
        self.assertEqual(json.loads(self.out.getvalue())['source_provenance'],self.reader.provenance)
        self.connect.assert_awaited_once();self.disconnect.assert_awaited_once()

    async def test_search_json_empty_and_nonempty_keep_provenance(self):
        for rows in ([],[dict(chunk_id='db-uuid',text='snapshot text')]):
            self.out.seek(0);self.out.truncate(0)
            self.service.search.return_value=dict(results=rows)
            self.assertEqual(await cli.main(self.args('search')+['--question','FPT','--json']),0)
            result=json.loads(self.out.getvalue())
            self.assertEqual(result['source_provenance'],self.reader.provenance)
            self.assertEqual(result['results'],rows)
            self.assertIs(self.factory.call_args.kwargs['resolver'],self.reader)

    async def test_human_empty_results_disclose_historical_mode_and_hash(self):
        self.assertEqual(await cli.main(self.args('search')+['--question','FPT']),0)
        self.assertIn('FROZEN_SNAPSHOT',self.out.getvalue());self.assertIn(PIN,self.out.getvalue())

    async def test_interactive_reuses_snapshot_and_disconnects(self):
        with patch('builtins.input',side_effect=['FPT','BID','exit']):
            self.assertEqual(await cli.main(self.args('search')),0)
        self.snapshot.assert_called_once();self.factory.assert_called_once()
        self.assertEqual(self.service.search.await_count,2);self.disconnect.assert_awaited_once()

    async def test_default_live_behavior_and_failure_cleanup(self):
        self.assertEqual(await cli.main(['build','--index',INDEX]),0)
        self.snapshot.assert_not_called();self.factory.assert_called_once_with('pool','embed')
        self.assertNotIn('FROZEN_SNAPSHOT',self.out.getvalue())
        self.service.search.side_effect=cli.RetrievalError('SOURCE_UNAVAILABLE')
        self.assertEqual(await cli.main(self.args('search')+['--question','FPT']),1)
        self.assertEqual(self.disconnect.await_count,2)
        self.assertIn('SOURCE_UNAVAILABLE',self.err.getvalue())
