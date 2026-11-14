import asyncio
import json
import io
import unittest
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from hoi import main, save_history


def temp_directory():
    base = Path(__file__).resolve().parents[1]/'.agent-state'
    base.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=base)


class TestChatHistory(unittest.IsolatedAsyncioTestCase):
    async def test_save_history_roundtrip_and_unique_name(self):
        sample = {
            "schema_version": "1.0",
            "session_id": "test-id",
            "started_at": "2023-01-01T00:00:00Z",
            "saved_at": "2023-01-01T00:00:01Z",
            "messages": [
                {"role": "user", "content": "Xin chào", "timestamp": "2023-01-01T00:00:00Z"},
                {"role": "assistant", "content": "Chào bạn", "timestamp": "2023-01-01T00:00:01Z"},
            ],
        }
        with temp_directory() as td:
            directory = Path(td)
            path = save_history(sample, directory)
            # filename contains timestamp and 8‑char hex
            self.assertRegex(path.name, r"session_\d{8}_\d{6}_[0-9a-f]{32}\.json")
            second = save_history(sample, directory)
            self.assertNotEqual(path, second)
            # content round‑trips unchanged
            with path.open(encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, sample)
            # ensure indent=2 and UTF‑8 (by reading as text)
            text = path.read_text(encoding="utf-8")
            self.assertIn("  \"schema_version\": \"1.0\"", text)

    async def test_main_persist_false_creates_no_file(self):
        with temp_directory() as td:
            directory = Path(td)
            with patch("builtins.input", side_effect=["exit"]):
                await main(persist=False, history_dir=directory)
            self.assertEqual(list(directory.iterdir()), [])

    async def test_main_persist_true_writes_file(self):
        with temp_directory() as td:
            directory = Path(td)
            # simulate a simple conversation then exit
            inputs = ["Hello", "/json", "exit"]
            with patch("builtins.input", side_effect=inputs):
                await main(persist=True, history_dir=directory)
            files = list(directory.iterdir())
            self.assertEqual(len(files), 1)
            path = files[0]
            data = json.loads(path.read_text(encoding="utf-8"))
            # top‑level fields
            self.assertIn("schema_version", data)
            self.assertIn("session_id", data)
            self.assertIn("started_at", data)
            self.assertIn("saved_at", data)
            self.assertIn("messages", data)
            # there should be two messages: user + assistant
            self.assertEqual(len(data["messages"]), 2)
            # timestamps are ISO‑8601 strings
            for msg in data["messages"]:
                self.assertRegex(msg["timestamp"], r"\d{4}-\d{2}-\d{2}T.*Z?")

    async def test_moi_records_reset_and_keeps_history(self):
        with temp_directory() as td:
            directory = Path(td)
            inputs = ["Hi", "/moi", "Bye", "exit"]
            with patch("builtins.input", side_effect=inputs):
                await main(persist=True, history_dir=directory)
            files = list(directory.iterdir())
            self.assertEqual(len(files), 1)
            data = json.loads(files[0].read_text(encoding="utf-8"))
            # Expected 4 messages: user Hi, assistant reply, user /moi, assistant reset, user Bye, assistant reply
            self.assertEqual(len(data["messages"]), 6)
            # Verify reset message content
            reset_msg = data["messages"][3]
            self.assertEqual(reset_msg["role"], "assistant")
            self.assertIn("đã xóa ngữ cảnh", reset_msg["content"].lower())

    async def test_no_file_when_no_messages(self):
        with temp_directory() as td:
            directory = Path(td)
            with patch("builtins.input", side_effect=["exit"]):
                await main(persist=True, history_dir=directory)
            self.assertEqual(list(directory.iterdir()), [])

    async def test_oserror_is_handled_gracefully(self):
        with temp_directory() as td:
            directory = Path(td)
            # Force write_text to raise OSError
            with patch("hoi.save_history", side_effect=OSError("disk full")):
                inputs = ["Hello", "exit"]
                with patch("builtins.input", side_effect=inputs):
                    f = io.StringIO()
                    with redirect_stdout(f):
                        await main(persist=True, history_dir=directory)
                    output = f.getvalue()
            self.assertIn("Lỗi lưu lịch sử", output)
            self.assertNotIn("Đã lưu lịch sử:", output)
            # No file should have been created despite the OSError
            self.assertEqual(list(directory.iterdir()), [])

    async def test_eof_and_keyboard_interrupt_save_completed_turns(self):
        for ending in (EOFError(), KeyboardInterrupt()):
            with temp_directory() as folder:
                with patch('builtins.input', side_effect=['Lợi nhuận BID năm 2025?', ending]), redirect_stdout(io.StringIO()):
                    await main(persist=True, history_dir=Path(folder))
                history = json.loads(next(Path(folder).glob('*.json')).read_text(encoding='utf-8'))
                self.assertEqual([m['role'] for m in history['messages']], ['user','assistant'])
                self.assertEqual(history['messages'][0]['content'], 'Lợi nhuận BID năm 2025?')
                self.assertEqual(history['messages'][1]['result']['status'], 'ASK_CLARIFICATION')

    async def test_cancellation_saves_incomplete_user_turn_and_propagates(self):
        from unittest.mock import AsyncMock
        with temp_directory() as folder:
            with patch('builtins.input', return_value='Tổng tài sản BID năm 2025?'), patch('hoi.ChatSession.ask', new=AsyncMock(side_effect=asyncio.CancelledError())), redirect_stdout(io.StringIO()):
                with self.assertRaises(asyncio.CancelledError):
                    await main(persist=True, history_dir=Path(folder))
            data = json.loads(next(Path(folder).glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(len(data['messages']),1)
            self.assertEqual(data['messages'][0]['role'],'user')

    async def test_default_main_does_not_persist_nonempty_chat(self):
        with patch('builtins.input', side_effect=['Tổng tài sản BID năm 2025?', 'exit']), patch('hoi.save_history') as saver, redirect_stdout(io.StringIO()):
            await main()
        saver.assert_not_called()

    async def test_collision_does_not_overwrite_existing_file(self):
        with temp_directory() as folder:
            with patch('hoi.uuid.uuid4',return_value=SimpleNamespace(hex='a'*32)), patch('hoi.datetime') as clock:
                clock.now.return_value.strftime.return_value='20261016_000000'
                target=save_history({'messages':['first']},Path(folder))
                with self.assertRaises(FileExistsError):
                    save_history({'messages':['second']},Path(folder))
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')),{'messages':['first']})

    async def test_default_directory_uses_module_location(self):
        with temp_directory() as folder:
            with patch('hoi.__file__',str(Path(folder)/'hoi.py')):
                target=save_history({'messages':['test']})
            self.assertEqual(target.parent,Path(folder)/'chat_history')

if __name__ == "__main__":
    unittest.main()
