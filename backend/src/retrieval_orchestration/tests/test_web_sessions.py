import os
import tempfile
import uuid
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from backend.src.retrieval_orchestration.web_sessions import SessionStore, ChatError


class TestSessionStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # create a temporary root directory for the store
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store = SessionStore(self.root)
        # generate a valid owner UUID for all tests
        self.owner = str(uuid.uuid4())

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_create_returns_proper_snapshot(self):
        snap = await self.store.create(self.owner)
        self.assertIn("session_id", snap)
        self.assertEqual(snap["revision"], 0)
        self.assertEqual(snap["messages"], [])
        self.assertIn("context", snap)
        self.assertEqual(snap["execution_mode"], "FIXTURE")
        # ensure file exists on disk
        session_file = self.root / self.owner / f"{snap['session_id']}.json"
        self.assertTrue(session_file.is_file())

    async def test_list_includes_created_session(self):
        snap = await self.store.create(self.owner)
        lst = await self.store.list(self.owner)
        self.assertTrue(any(item["session_id"] == snap["session_id"] for item in lst))
        # preview should be empty string because no user messages yet
        entry = next(item for item in lst if item["session_id"] == snap["session_id"])
        self.assertEqual(entry["preview"], "")
        self.assertEqual(entry["turns"], 0)

    async def test_get_returns_same_snapshot(self):
        snap = await self.store.create(self.owner)
        fetched = await self.store.get(self.owner, snap["session_id"])
        self.assertEqual(fetched["session_id"], snap["session_id"])
        self.assertEqual(fetched["revision"], 0)
        self.assertEqual(fetched["messages"], [])
        self.assertIn("context", fetched)

    async def test_send_adds_user_and_assistant_messages_and_increments_revision(self):
        snap = await self.store.create(self.owner)
        rev = snap["revision"]
        text = "Hello world"
        updated = await self.store.send(self.owner, snap["session_id"], text, rev)
        self.assertEqual(updated["revision"], rev + 1)
        self.assertEqual(len(updated["messages"]), 2)
        self.assertEqual(updated["messages"][0]["role"], "user")
        self.assertEqual(updated["messages"][0]["content"], text)
        self.assertEqual(updated["messages"][1]["role"], "assistant")
        # context should be recomputed (non‑empty string expected)
        self.assertTrue(isinstance(updated["context"], str))

    async def test_send_revision_conflict_raises_409(self):
        snap = await self.store.create(self.owner)
        # first send succeeds
        await self.store.send(self.owner, snap["session_id"], "msg1", snap["revision"])
        # second send uses old revision -> conflict
        with self.assertRaises(ChatError) as ctx:
            await self.store.send(self.owner, snap["session_id"], "msg2", snap["revision"])
        self.assertEqual(ctx.exception.status, 409)

    async def test_send_invalid_text_length_raises_422(self):
        snap = await self.store.create(self.owner)
        # empty after strip
        with self.assertRaises(ChatError) as ctx:
            await self.store.send(self.owner, snap["session_id"], "   ", 0)
        self.assertEqual(ctx.exception.status, 422)
        # overly long text
        long_text = "a" * 4001
        with self.assertRaises(ChatError) as ctx2:
            await self.store.send(self.owner, snap["session_id"], long_text, 0)
        self.assertEqual(ctx2.exception.status, 422)

    async def test_resume_creates_child_session_with_parent_metadata(self):
        snap = await self.store.create(self.owner)
        # add a message to have some content
        snap2 = await self.store.send(self.owner, snap["session_id"], "first", 0)
        child = await self.store.resume(self.owner, snap2["session_id"])
        self.assertNotEqual(child["session_id"], snap2["session_id"])
        self.assertEqual(child["revision"], 0)
        self.assertEqual(child["messages"], snap2["messages"])  # same transcript
        # verify parent metadata persisted on disk
        child_path = self.root / self.owner / f"{child['session_id']}.json"
        import json
        with child_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        self.assertIn("parent_session_id", data.get("metadata", {}))
        self.assertEqual(data["metadata"]["parent_session_id"], snap2["session_id"])

    async def test_invalid_owner_uuid_raises_422(self):
        with self.assertRaises(ChatError) as ctx:
            await self.store.create("not-a-uuid")
        self.assertEqual(ctx.exception.status, 422)

    async def test_invalid_session_id_raises_404(self):
        with self.assertRaises(ChatError) as ctx:
            await self.store.get(self.owner, "00000000-0000-0000-0000-000000000000")
        self.assertEqual(ctx.exception.status, 404)

    async def test_lock_conflict_raises_409(self):
        snap = await self.store.create(self.owner)
        session_path = self.root / self.owner / f"{snap['session_id']}.json"
        # manually create lock file to simulate another process holding the lock
        lock_path = session_path.with_suffix('.lock')
        lock_path.touch()
        try:
            with self.assertRaises(ChatError) as ctx:
                await self.store.send(self.owner, snap["session_id"], "msg", 0)
            self.assertEqual(ctx.exception.status, 409)
        finally:
            # clean up lock file for teardown
            if lock_path.exists():
                lock_path.unlink()

    async def test_cross_owner_access_is_forbidden(self):
        # create a session for owner A
        owner_a = str(uuid.uuid4())
        snap_a = await self.store.create(owner_a)
        # attempt to access it with a different owner B
        owner_b = str(uuid.uuid4())
        with self.assertRaises(ChatError) as ctx:
            await self.store.get(owner_b, snap_a["session_id"])
        self.assertEqual(ctx.exception.status, 404)

    async def test_real_multiturn_restart_and_correction(self):
        snap = await self.store.create(self.owner)
        sid = snap['session_id']
        for text in ('lợi nhuận năm nay là bao nhiêu', 'BID, sau thuế', 'không, là VCB'):
            snap = await SessionStore(self.root).send(self.owner, sid, text, snap['revision'])
        self.assertIn('VCB', snap['context'])
        self.assertIn('sau thuế', snap['context'].lower())
        self.assertEqual(len(snap['messages']), 6)
        self.assertEqual(snap['messages'][-1]['result']['execution_mode'], 'FIXTURE')
        restored = await SessionStore(self.root).get(self.owner, sid)
        self.assertEqual(restored, snap)

    async def test_failed_write_keeps_original(self):
        from unittest.mock import patch
        snap = await self.store.create(self.owner)
        path = self.root / self.owner / (snap['session_id']+'.json')
        before = path.read_bytes()
        with patch('pathlib.Path.replace', side_effect=OSError('private disk path')):
            with self.assertRaises(ChatError) as failure:
                await self.store.send(self.owner, snap['session_id'], 'BID', 0)
        self.assertEqual(failure.exception.status, 503)
        self.assertNotIn('private disk path', str(failure.exception))
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(path.with_suffix('.lock').exists())

    async def test_parent_bytes_unchanged_after_child(self):
        snap = await self.store.create(self.owner)
        snap = await self.store.send(self.owner, snap['session_id'], 'tổng tài sản BID năm 2025', 0)
        path = self.root / self.owner / (snap['session_id']+'.json')
        before = path.read_bytes()
        child = await self.store.resume(self.owner, snap['session_id'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(child['messages'], snap['messages'])
        child = await self.store.send(self.owner, child['session_id'], 'năm 2024', child['revision'])
        self.assertIn('2024', child['context'])
        self.assertEqual(before, path.read_bytes())

    async def test_invalid_revision_traversal_and_tamper_rejected(self):
        import json
        snap = await self.store.create(self.owner)
        sid = snap['session_id']
        for revision in (True, -1, '0'):
            with self.assertRaises(ChatError) as failure:
                await self.store.send(self.owner, sid, 'BID', revision)
            self.assertEqual(failure.exception.status, 422)
        with self.assertRaises(ChatError):
            await self.store.get(self.owner, '../'+sid)
        path = self.root / self.owner / (sid+'.json')
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['owner'] = str(uuid.uuid4())
        path.write_text(json.dumps(doc), encoding='utf-8')
        with self.assertRaises(ChatError) as failure:
            await self.store.get(self.owner, sid)
        self.assertEqual(failure.exception.status, 503)

    async def test_busy_lock_does_not_block_other_sessions(self):
        import asyncio
        first = await self.store.create(self.owner)
        second = await self.store.create(self.owner)
        path = self.root / self.owner / (first['session_id']+'.lock')
        path.touch()
        with self.assertRaises(ChatError) as failure:
            await asyncio.wait_for(self.store.send(self.owner, first['session_id'], 'BID', 0), timeout=0.5)
        self.assertEqual(failure.exception.status, 409)
        self.assertTrue(path.exists())
        await self.store.send(self.owner, second['session_id'], 'BID', 0)
