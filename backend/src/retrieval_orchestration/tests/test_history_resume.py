from retrieval_flow.conversation import ChatSession
import asyncio
import copy
from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import hoi
from retrieval_flow.history import load_history, list_histories, restore_session, MAX_BYTES

def sample(question='Lợi nhuận BID năm nay?'):
    return {'schema_version': '1.0', 'session_id': 'old', 'started_at': '2025-06-01T00:00:00+00:00', 'saved_at': '2025-06-01T00:01:00+00:00', 'messages': [{'role': 'user', 'content': question, 'timestamp': '2025-06-01T00:00:01+00:00'}, {'role': 'assistant', 'content': 'untrusted', 'timestamp': '2025-06-01T00:00:02+00:00', 'result': {'scope': {'companies': ['SSI']}, 'answer': 'untrusted number'}}]}

def temporary():
    base = Path(__file__).resolve().parents[1] / '.agent-state'
    base.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=base)

def write(root, name='parent.json', document=None):
    target = Path(root) / name
    target.write_text(json.dumps(document if document is not None else sample(), ensure_ascii=False), encoding='utf-8')
    return target

async def terminal(root, inputs, persist=False):
    output = io.StringIO()
    with patch('builtins.input', side_effect=inputs), redirect_stdout(output):
        history = await hoi.main(history_dir=Path(root), persist=persist)
    return (history, output.getvalue())

class ResumeTests(unittest.IsolatedAsyncioTestCase):

    async def test_legacy_replay_uses_historical_year_ignores_assistant(self):
        history = sample()
        before = copy.deepcopy(history)
        session = await restore_session(history, today=date(2026, 10, 19))
        self.assertNotEqual(session.session_id, 'old')
        self.assertEqual(session.today, date(2026, 10, 19))
        result = await session.ask('sau thuế')
        self.assertEqual((result['scope']['companies'], result['scope']['periods']), (['BID'], ['2025-12-31']))
        self.assertEqual(history, before)
        result = await session.ask('Lợi nhuận sau thuế BID năm nay?')
        self.assertEqual(result['scope']['periods'], ['2026-12-31'])

    async def test_explicit_per_turn_reference_date_wins_timestamp(self):
        history = sample()
        history['messages'][0]['reference_date'] = '2024-01-01'
        session = await restore_session(history, today=date(2026, 10, 19))
        self.assertEqual((await session.ask('sau thuế'))['scope']['periods'], ['2024-12-31'])

    async def test_assistant_only_data_cannot_seed_a_query(self):
        history = sample()
        history['messages'] = history['messages'][1:]
        session = await restore_session(history)
        self.assertIsNone(session.last_result)
        self.assertEqual((await session.ask('sau thuế'))['status'], 'ASK_CLARIFICATION')

    async def test_reset_and_ui_commands_during_replay(self):
        history = sample()
        for text in ['/moi', '/json', '/mo ../../evil.json', '/help', '/tomtat']:
            history['messages'].append({'role': 'user', 'content': text, 'timestamp': '2025-06-01T00:00:03+00:00'})
        session = await restore_session(history)
        self.assertIn('Không có', session.context_summary())
        self.assertIsNone(session.last_result)

    async def test_all_rows_are_validated_before_replay(self):
        history = sample()
        history['messages'].append({'role': 'invalid', 'content': 'x', 'timestamp': '2025-01-01T00:00:00+00:00'})
        with patch('retrieval_flow.history.ChatSession.ask', new=AsyncMock()) as ask:
            with self.assertRaises(ValueError):
                await restore_session(history)
        ask.assert_not_called()

    async def test_child_file_preserves_source_and_old_transcript(self):
        with temporary() as root:
            source = write(root)
            original = source.read_bytes()
            document, output = await terminal(root, ['/mo parent.json', 'sau thuế', 'exit'], True)
            children = [p for p in Path(root).glob('*.json') if p != source]
            self.assertEqual(len(children), 1)
            child = json.loads(children[0].read_text(encoding='utf-8'))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(child['resumed_from'], 'parent.json')
            self.assertEqual(child['parent_session_id'], 'old')
            self.assertNotEqual(child['session_id'], 'old')
            self.assertEqual(child['messages'][:2], sample()['messages'])
            self.assertEqual(child['messages'][-1]['result']['scope']['companies'], ['BID'])
            self.assertEqual(child['messages'][-1]['result']['scope']['periods'], ['2025-12-31'])
            self.assertIn('reference_date', child['messages'][-2])
            self.assertIn('Đã mở phiên', output)

    async def test_open_and_exit_without_changes_does_not_clone(self):
        with temporary() as root:
            source = write(root)
            original = source.read_bytes()
            await terminal(root, ['/lichsu', '/mo 1', '/tomtat', 'exit'], True)
            self.assertEqual(len(list(Path(root).glob('*.json'))), 1)
            self.assertEqual(source.read_bytes(), original)

    async def test_switch_saves_dirty_current_chat_before_activation(self):
        with temporary() as root:
            source = write(root)
            await terminal(root, ['Tổng tài sản FPT năm 2024?', '/mo 1', 'exit'], True)
            children = [p for p in Path(root).glob('*.json') if p != source]
            self.assertEqual(len(children), 1)
            saved = json.loads(children[0].read_text(encoding='utf-8'))
            self.assertEqual(saved['messages'][0]['content'], 'Tổng tài sản FPT năm 2024?')

    async def test_bad_selector_and_bad_json_keep_active_context(self):
        with temporary() as root:
            write(root)
            (Path(root) / 'bad.json').write_text('{bad', encoding='utf-8')
            document, output = await terminal(root, ['Lợi nhuận BID năm 2024?', '/mo 0', '/mo bad.json', '/mo ../outside.json', 'sau thuế', 'exit'])
            self.assertEqual(document['messages'][-1]['result']['scope']['companies'], ['BID'])
            self.assertEqual(document['messages'][-1]['result']['scope']['periods'], ['2024-12-31'])
            self.assertIn('Không mở được phiên', output)

    async def test_failed_save_before_switch_keeps_unsaved_query(self):
        with temporary() as root:
            write(root, document=sample('Lợi nhuận VCB năm 2025?'))
            with patch('hoi.save_history', side_effect=OSError('disk full')):
                document, output = await terminal(root, ['Lợi nhuận BID năm 2024?', '/mo 1', 'sau thuế', 'exit'], True)
            self.assertEqual(document['messages'][-1]['result']['scope']['companies'], ['BID'])
            self.assertEqual(document['messages'][-1]['result']['scope']['periods'], ['2024-12-31'])
            self.assertNotIn('resumed_from', document)
            self.assertIn('Giữ nguyên phiên', output)

    async def test_help_list_summary_do_not_retrieve_or_log_fake_turns(self):
        with temporary() as root:
            with patch('hoi.ChatSession.ask', new=AsyncMock()) as ask:
                document, output = await terminal(root, ['/help', '/lichsu', '/tomtat', '/mo', 'exit'])
            ask.assert_not_called()
            self.assertEqual(document['messages'], [])

class FileTests(unittest.TestCase):

    def test_json_roundtrip_order_and_preview_sanitization(self):
        with temporary() as root:
            old = sample('Lợi nhuận\n\tBID?')
            old['saved_at'] = '2025-06-01T03:00:00+07:00'
            new = sample()
            new['saved_at'] = '2025-06-01T00:00:00+00:00'
            write(root, 'older.json', old)
            write(root, 'newer.json', new)
            (Path(root) / 'bad.json').write_text('{}', encoding='utf-8')
            entries = list_histories(Path(root))
            self.assertEqual([x['name'] for x in entries], ['newer.json', 'older.json'])
            self.assertNotIn('\n', entries[1]['preview'])
            self.assertNotIn('\t', entries[1]['preview'])

    def test_paths_links_and_missing_file_are_rejected(self):
        with temporary() as root:
            write(root)
            for filename in ['../parent.json', '..\\parent.json', 'C:\\outside.json', '/tmp/x.json', 'parent.txt', 'none.json']:
                with self.assertRaises(ValueError):
                    load_history(filename, Path(root))
            alias = Path(root) / 'alias.json'
            try:
                alias.symlink_to(Path(root) / 'parent.json')
            except OSError:
                return
            with self.assertRaises(ValueError):
                load_history(alias.name, Path(root))

    def test_bounded_read_and_bad_schema_types(self):
        with temporary() as root:
            target = Path(root) / 'large.json'
            target.write_bytes(b' ' * (MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                load_history(target.name, Path(root))
            for mutate in [lambda h: h.update(schema_version='9'), lambda h: h.update(messages='wrong'), lambda h: h.update(session_id=''), lambda h: h.update(saved_at='2025-01-01'), lambda h: h['messages'][0].update(content='x' * 40001), lambda h: h['messages'][0].update(reference_date='2025-02-30')]:
                history = sample()
                mutate(history)
                path = write(root, 'invalid.json', history)
                with self.assertRaises(ValueError):
                    load_history(path.name, Path(root))

    def test_invalid_json_encoding_constants_and_duplicates(self):
        with temporary() as root:
            for payload in [b'{bad', b'\xff', b'{"x":NaN}', b'{"x":1e9999}', b'{"x":1,"x":2}']:
                target = Path(root) / 'invalid.json'
                target.write_bytes(payload)
                with self.assertRaises(ValueError):
                    load_history(target.name, Path(root))

    def test_absent_directory_is_an_empty_list_without_creating_it(self):
        with temporary() as root:
            absent = Path(root) / 'absent'
            self.assertEqual(list_histories(absent), [])
            self.assertFalse(absent.exists())

class IndependentHistoryScenarios(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self._temporary = temporary()
        self.test_dir = Path(self._temporary.name)

    def tearDown(self):
        self._temporary.cleanup()

    def create_test_file(self, filename, content):
        path = self.test_dir / filename
        with path.open('w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_load_valid_history_file(self):
        content = json.dumps({'schema_version': '1.0', 'session_id': 'test-session', 'started_at': '2023-10-10T08:00:00+00:00', 'saved_at': '2023-10-11T08:00:00+00:00', 'messages': [{'role': 'user', 'content': 'Hello', 'timestamp': '2023-10-10T08:00:00+00:00'}]})
        self.create_test_file('valid_history.json', content)
        history = load_history('valid_history.json', self.test_dir)
        self.assertEqual(history['session_id'], 'test-session')
        self.assertEqual(len(history['messages']), 1)

    def test_list_histories(self):
        content = json.dumps({'schema_version': '1.0', 'session_id': 'test-session-2', 'started_at': '2023-10-10T08:00:00+00:00', 'saved_at': '2023-10-11T08:00:00+00:00', 'messages': [{'role': 'user', 'content': 'Hi', 'timestamp': '2023-10-10T08:00:00+00:00'}]})
        self.create_test_file('history2.json', content)
        histories = list_histories(self.test_dir)
        self.assertEqual(len(histories), 1)
        self.assertEqual(histories[0]['session_id'], 'test-session-2')

    async def test_restore_session(self):
        content = json.dumps({'schema_version': '1.0', 'session_id': 'test-session-3', 'started_at': '2023-10-10T08:00:00+00:00', 'saved_at': '2023-10-11T08:00:00+00:00', 'messages': [{'role': 'user', 'content': 'What is the weather like?', 'timestamp': '2023-10-10T08:00:00+00:00'}]})
        self.create_test_file('history3.json', content)
        history = load_history('history3.json', self.test_dir)
        session = await restore_session(history)
        self.assertIsInstance(session, ChatSession)
