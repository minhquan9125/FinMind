import unittest
import json
import sys
import asyncio
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

# Add backend root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.vector_retrieval.hoi import (
    build_cache,
    search_question,
    parse_args,
)
from src.vector_retrieval.backend import RetrievalError


class TestCLIArgumentParsing(unittest.TestCase):
    """Test argument parsing and command routing."""

    def test_build_command_required_args(self):
        """Build command requires --index."""
        with self.assertRaises(SystemExit):
            with patch('sys.argv', ['hoi.py', 'build']):
                parse_args()

    def test_build_command_with_index(self):
        """Build command accepts --index UUID."""
        with patch('sys.argv', ['hoi.py', 'build', '--index', 'doc-v1-test']):
            args = parse_args()
            self.assertEqual(args.command, 'build')
            self.assertEqual(args.index, 'doc-v1-test')
            self.assertFalse(args.allow_building)

    def test_build_command_allow_building_flag(self):
        """Build command respects --allow-building flag."""
        with patch('sys.argv', ['hoi.py', 'build', '--index', 'doc-v1-test', '--allow-building']):
            args = parse_args()
            self.assertTrue(args.allow_building)

    def test_search_command_required_args(self):
        """Search command requires --index."""
        with self.assertRaises(SystemExit):
            with patch('sys.argv', ['hoi.py', 'search']):
                parse_args()

    def test_search_command_with_question(self):
        """Search command accepts --question."""
        with patch('sys.argv', ['hoi.py', 'search', '--index', 'doc-v1-test', '--question', 'What is revenue?']):
            args = parse_args()
            self.assertEqual(args.command, 'search')
            self.assertEqual(args.question, 'What is revenue?')

    def test_search_command_without_question_interactive(self):
        """Search command without --question enters interactive mode."""
        with patch('sys.argv', ['hoi.py', 'search', '--index', 'doc-v1-test']):
            args = parse_args()
            self.assertIsNone(args.question)

    def test_search_command_filters(self):
        """Search command accepts filter options."""
        with patch('sys.argv', [
            'hoi.py', 'search', '--index', 'doc-v1-test',
            '--company', 'FPT', '--period', '2026-Q2',
            '--doc-type', 'FINANCIAL_STATEMENT',
            '--top-k', '10', '--candidates', '100'
        ]):
            args = parse_args()
            self.assertEqual(args.company, 'FPT')
            self.assertEqual(args.period, '2026-Q2')
            self.assertEqual(args.doc_type, 'FINANCIAL_STATEMENT')
            self.assertEqual(args.top_k, 10)
            self.assertEqual(args.candidates, 100)

    def test_search_json_flag(self):
        """Search command respects --json flag."""
        with patch('sys.argv', ['hoi.py', 'search', '--index', 'doc-v1-test', '--json']):
            args = parse_args()
            self.assertTrue(args.json)


class TestBuildCacheCommand(unittest.TestCase):
    """Test build cache command behavior."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_build_success_returns_zero(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Build succeeds and returns exit code 0."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.build_cache.return_value = {'status': 'CACHE_READY'}
        mock_pool.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()

        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            exit_code = self.loop.run_until_complete(
                build_cache('doc-v1-test', '.cache/index.json', False)
            )

        self.assertEqual(exit_code, 0)
        output = mock_stdout.getvalue()
        self.assertIn('CACHE_READY', output)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_build_cache_required_error(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Build fails with CACHE_BUILD_REQUIRED and returns exit code 1."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        error = RetrievalError('Cache build required')
        error.code = 'CACHE_BUILD_REQUIRED'
        mock_retriever.build_cache.side_effect = error

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                build_cache('doc-v1-test', '.cache/index.json', False)
            )

        self.assertEqual(exit_code, 1)
        output = mock_stderr.getvalue()
        self.assertIn('CACHE_BUILD_REQUIRED', output)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_build_index_not_active_error(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Build fails when index not BUILDING without --allow-building."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        error = RetrievalError('Index not active')
        error.code = 'INDEX_NOT_ACTIVE'
        mock_retriever.build_cache.side_effect = error

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                build_cache('doc-v1-test', '.cache/index.json', allow_building=False)
            )

        self.assertEqual(exit_code, 1)
        output = mock_stderr.getvalue()
        self.assertIn('INDEX_NOT_ACTIVE', output)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_build_passes_allow_building_flag(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Build passes --allow-building flag to retriever."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.build_cache.return_value = {'status': 'CACHE_READY'}

        with patch('sys.stdout', new=StringIO()):
            self.loop.run_until_complete(
                build_cache('doc-v1-test', '.cache/index.json', allow_building=True)
            )

        mock_retriever.build_cache.assert_called_once()
        call_kwargs = mock_retriever.build_cache.call_args[1]
        self.assertTrue(call_kwargs.get('allow_building'))

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_build_unhandled_exception_returns_two(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Build with unhandled exception returns exit code 2."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.build_cache.side_effect = RuntimeError('Unexpected error')

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                build_cache('doc-v1-test', '.cache/index.json', False)
            )

        self.assertEqual(exit_code, 2)
        output = mock_stderr.getvalue()
        self.assertIn('INTERNAL_ERROR', output)


class TestSearchCommand(unittest.TestCase):
    """Test search command behavior."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_single_question_json_output(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search with --question outputs valid JSON."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.search.return_value = {
            'index_version_id': 'v1',
            'scope_mode': 'INDEX',
            'results': [
                {'chunk_id': 'c1', 'text': 'Sample content', 'rrf_score': 0.9}
            ]
        }

        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'What is revenue?',
                    False, None, None, None, 5, 50, json_output=True
                )
            )

        self.assertEqual(exit_code, 0)
        output = mock_stdout.getvalue()
        result = json.loads(output)
        self.assertEqual(result['scope_mode'], 'INDEX')
        self.assertEqual(len(result['results']), 1)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_single_question_text_output(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search with --question outputs formatted text."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.search.return_value = {
            'results': [
                {'chunk_id': 'c1', 'text': 'Sample revenue content'}
            ]
        }

        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'What is revenue?',
                    False, None, None, None, 5, 50, json_output=False
                )
            )

        self.assertEqual(exit_code, 0)
        output = mock_stdout.getvalue()
        self.assertIn('Kết quả cho: What is revenue?', output)
        self.assertIn('c1', output)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_cache_stale_error(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search with stale cache returns error code 1."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        error = RetrievalError('Cache expired')
        error.code = 'CACHE_STALE'
        mock_retriever.search.side_effect = error

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'What is revenue?',
                    False, None, None, None, 5, 50, json_output=True
                )
            )

        self.assertEqual(exit_code, 1)
        output = mock_stderr.getvalue()
        result = json.loads(output)
        self.assertEqual(result['code'], 'CACHE_STALE')

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_source_changed_error(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search detects source changes and reports error."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        error = RetrievalError('Source documents changed')
        error.code = 'SOURCE_CHANGED'
        mock_retriever.search.side_effect = error

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'What is revenue?',
                    False, None, None, None, 5, 50, json_output=False
                )
            )

        self.assertEqual(exit_code, 1)
        output = mock_stderr.getvalue()
        self.assertIn('SOURCE_CHANGED', output)

    @patch('builtins.input', side_effect=['What is revenue?', 'What is profit?', EOFError()])
    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_interactive_mode(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect, mock_input):
        """Search without --question enters interactive loop."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.search.return_value = {'results': []}

        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', None,
                    False, None, None, None, 5, 50, json_output=False
                )
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(mock_retriever.search.call_count, 2)
        first_call = mock_retriever.search.call_args_list[0]
        self.assertEqual(first_call[0][0], 'What is revenue?')

    @patch('builtins.input', side_effect=['Test question', EOFError()])
    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_interactive_error_recovery(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect, mock_input):
        """Interactive mode continues after individual question errors."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        error = RetrievalError('Invalid question')
        error.code = 'INVALID_QUESTION'
        mock_retriever.search.side_effect = error

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', None,
                    False, None, None, None, 5, 50, json_output=False
                )
            )

        self.assertEqual(exit_code, 0)
        output = mock_stderr.getvalue()
        self.assertIn('INVALID_QUESTION', output)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_passes_filters(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search passes filter parameters to retriever."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.search.return_value = {'results': []}

        with patch('sys.stdout', new=StringIO()):
            self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'Question',
                    False, 'FPT', '2026-Q2', 'FINANCIAL_STATEMENT', 10, 100, False
                )
            )

        mock_retriever.search.assert_called_once()
        call_kwargs = mock_retriever.search.call_args[1]
        self.assertEqual(call_kwargs.get('company'), 'FPT')
        self.assertEqual(call_kwargs.get('period'), '2026-Q2')
        self.assertEqual(call_kwargs.get('doc_type'), 'FINANCIAL_STATEMENT')
        self.assertEqual(call_kwargs.get('top_k'), 10)
        self.assertEqual(call_kwargs.get('candidates'), 100)

    @patch('src.vector_retrieval.hoi.disconnect')
    @patch('src.vector_retrieval.hoi.get_embedding_service')
    @patch('src.vector_retrieval.hoi.get_pool')
    @patch('src.vector_retrieval.hoi.HybridRetriever')
    def test_search_unhandled_exception_returns_two(self, mock_retriever_class, mock_pool, mock_embedder, mock_disconnect):
        """Search with unhandled exception returns exit code 2."""
        mock_retriever = AsyncMock()
        mock_retriever_class.return_value = mock_retriever
        mock_retriever.search.side_effect = RuntimeError('Unexpected error')

        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            exit_code = self.loop.run_until_complete(
                search_question(
                    'doc-v1-test', '.cache/index.json', 'Question',
                    False, None, None, None, 5, 50, json_output=True
                )
            )

        self.assertEqual(exit_code, 2)
        output = mock_stderr.getvalue()
        self.assertIn('INTERNAL_ERROR', output)


class TestCLIImportIsolation(unittest.TestCase):
    """Test that importing CLI does not trigger side effects."""

    def test_hoi_import_no_db_connection(self):
        """Importing hoi.py does not connect to database."""
        with patch('src.vector_retrieval.hoi.connect') as mock_connect:
            # Re-import to test module initialization
            import importlib
            import src.vector_retrieval.hoi
            importlib.reload(src.vector_retrieval.hoi)
            mock_connect.assert_not_called()

    def test_hoi_import_no_model_load(self):
        """Importing hoi.py does not load embedding model."""
        with patch('src.vector_retrieval.hoi.get_embedding_service') as mock_embedder:
            import importlib
            import src.vector_retrieval.hoi
            importlib.reload(src.vector_retrieval.hoi)
            mock_embedder.assert_not_called()


if __name__ == '__main__':
    unittest.main()


class TestMainResourcePolicy(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import src.vector_retrieval.hoi as cli
        self.cli=cli
        self.index='434ef5e0-6516-578d-8d18-721d21347e01'
        self.output=StringIO();self.errors=StringIO()
        self.stack=__import__('contextlib').ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('sys.stdout',self.output))
        self.stack.enter_context(patch('sys.stderr',self.errors))
        self.connect=self.stack.enter_context(patch.object(cli,'connect',new_callable=AsyncMock))
        self.disconnect=self.stack.enter_context(patch.object(cli,'disconnect',new_callable=AsyncMock))
        self.stack.enter_context(patch.object(cli,'get_pool',return_value=object()))
        self.stack.enter_context(patch.object(cli,'get_embedding_service',return_value=object()))
        self.service=AsyncMock()
        self.service.search.return_value={'scope_mode':'INDEX','results':[]}
        self.service.build_cache.return_value={'status':'CACHE_READY','chunks':3}
        self.factory=self.stack.enter_context(patch.object(cli,'HybridRetriever',return_value=self.service))
        self.stack.enter_context(patch.dict(__import__('os').environ,{},clear=False))

    async def test_main_connects_closes_and_keeps_json_stdout_clean(self):
        code=await self.cli.main(['search','--index',self.index,'--question','assets','--json','--allow-building'])
        self.assertEqual(code,0)
        self.connect.assert_awaited_once();self.disconnect.assert_awaited_once()
        self.assertEqual(json.loads(self.output.getvalue())['scope_mode'],'INDEX')
        args,kwargs=self.service.search.call_args
        self.assertTrue(Path(args[2]).is_relative_to(self.cli.CACHE_DIR.resolve()))
        self.assertEqual(Path(args[2]).name,self.index+'.json')
        self.assertTrue(kwargs['allow_building'])
        self.assertIn('BUILDING',self.errors.getvalue())

    async def test_download_is_explicit_and_default_overrides_environment(self):
        import os
        os.environ['HF_HUB_OFFLINE']='0';os.environ['TRANSFORMERS_OFFLINE']='0'
        await self.cli.main(['build','--index',self.index])
        self.assertEqual(os.environ['HF_HUB_OFFLINE'],'1')
        self.assertEqual(os.environ['TRANSFORMERS_OFFLINE'],'1')
        await self.cli.main(['build','--index',self.index,'--allow-model-download'])
        self.assertEqual(os.environ['HF_HUB_OFFLINE'],'0')
        self.assertEqual(os.environ['TRANSFORMERS_OFFLINE'],'0')

    async def test_invalid_uuid_and_external_cache_do_not_connect(self):
        self.assertEqual(await self.cli.main(['build','--index','bad']),1)
        self.assertEqual(await self.cli.main(['build','--index',self.index,'--cache-path',str(self.cli.CACHE_DIR.parent/'outside.json')]),1)
        self.connect.assert_not_called()

    async def test_connection_error_sanitized_and_closed(self):
        self.connect.side_effect=RuntimeError('secret DSN password')
        self.assertEqual(await self.cli.main(['build','--index',self.index]),2)
        self.disconnect.assert_awaited_once()
        self.assertNotIn('secret',self.errors.getvalue())
        self.assertIn('DATABASE_UNAVAILABLE',self.errors.getvalue())

    async def test_build_failure_closed_and_not_claimed_ready(self):
        self.service.build_cache.side_effect=self.cli.RetrievalError('SOURCE_CHANGED')
        self.assertEqual(await self.cli.main(['build','--index',self.index]),1)
        self.disconnect.assert_awaited_once()
        self.assertEqual(self.output.getvalue(),'')
        self.assertIn('SOURCE_CHANGED',self.errors.getvalue())

    async def test_interactive_recovers_then_exits_with_one_session(self):
        self.service.search.side_effect=[self.cli.RetrievalError('INVALID_QUESTION'),{'results':[]}]
        with patch('builtins.input',side_effect=['bad','assets','exit']):
            self.assertEqual(await self.cli.main(['search','--index',self.index]),0)
        self.assertEqual(self.service.search.await_count,2)
        self.factory.assert_called_once();self.connect.assert_awaited_once();self.disconnect.assert_awaited_once()
