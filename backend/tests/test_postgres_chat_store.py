"""Storage-independent store tests; real RLS and transactions have a DB smoke test."""
import asyncio
import copy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
from src.retrieval_orchestration.chat_types import ChatError


class Repository:
    def __init__(self): self.docs, self.leases = {}, {}
    async def create(self, owner, doc):
        assert doc['owner'] == owner
        self.docs[(owner, doc['session_id'])] = copy.deepcopy(doc)
    async def get(self, owner, sid):
        if (owner, sid) not in self.docs: raise ChatError(404, 'Phiên không tồn tại.')
        return copy.deepcopy(self.docs[(owner, sid)])
    async def list(self, owner):
        from src.retrieval_orchestration.chat_logic import descriptor
        return [descriptor(doc) for (uid, _), doc in self.docs.items() if uid == owner]
    async def claim(self, owner, sid, revision, seconds):
        doc = await self.get(owner, sid)
        if doc['revision'] != revision or (owner, sid) in self.leases: raise ChatError(409, 'Phiên đang bận.')
        lease = str(uuid4())
        self.leases[(owner, sid)] = lease
        return doc, lease
    async def commit(self, owner, sid, lease, revision, doc):
        if self.leases.get((owner, sid)) != lease or self.docs[(owner, sid)]['revision'] != revision:
            raise ChatError(409, 'Xung đột phiên.')
        self.docs[(owner, sid)] = copy.deepcopy(doc)
        self.leases.pop((owner, sid))
    async def release(self, owner, sid, lease):
        if self.leases.get((owner, sid)) == lease: self.leases.pop((owner, sid))
    async def delete(self, owner, sid):
        await self.get(owner, sid)
        self.docs.pop((owner, sid))


class Engine:
    retrieval_timeout = 1
    limits = SimpleNamespace(read_timeout_seconds=1)
    calls = 0
    async def answer(self, text, sid, context, **kwargs):
        self.calls += 1
        return {'scope': {'companies': ['FPT']}, 'status': 'ASK_CLARIFICATION', 'message': 'Bạn muốn xem ngày nào?'}


def test_two_accounts_cannot_read_send_resume_delete_each_others_chats():
    async def run():
        repo, engine = Repository(), Engine()
        store = PostgresSessionStore(repository=repo, engine=engine)
        a, b = str(uuid4()), str(uuid4())
        session = await store.create(a)
        sid = session['session_id']
        for operation in (lambda: store.get(b, sid), lambda: store.send(b, sid, 'xin chào', 0),
                          lambda: store.resume(b, sid), lambda: store.delete(b, sid)):
            with pytest.raises(ChatError) as exc: await operation()
            assert exc.value.status == 404
        assert await store.list(b) == []
        assert engine.calls == 0
        await store.send(a, sid, 'giá FPT bn', 0)
        reopened = PostgresSessionStore(repository=repo, engine=engine)
        saved = await reopened.get(a, sid)
        assert saved['revision'] == 1 and len(saved['messages']) == 2
        assert saved['messages'][0]['content'] == 'giá FPT bn'
        fork = await reopened.resume(a, sid)
        assert fork['messages'] == saved['messages'] and fork['revision'] == 0
        assert repo.docs[(a, fork['session_id'])]['metadata']['live_context'] == {'companies': ['FPT']}
    asyncio.run(run())


def test_concurrent_same_revision_has_one_generation_and_no_lost_messages():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class BlockingEngine(Engine):
            async def answer(self, *args, **kwargs):
                entered.set()
                await release.wait()
                return await super().answer(*args, **kwargs)
        repo, engine = Repository(), BlockingEngine()
        store = PostgresSessionStore(repository=repo, engine=engine)
        owner = str(uuid4())
        sid = (await store.create(owner))['session_id']
        pending = asyncio.create_task(store.send(owner, sid, 'giá FPT', 0))
        await entered.wait()
        with pytest.raises(ChatError) as exc: await store.send(owner, sid, 'giá SSI', 0)
        assert exc.value.status == 409
        release.set()
        await pending
        assert len((await store.get(owner, sid))['messages']) == 2
        assert engine.calls == 1
        with pytest.raises(ChatError): await store.send(owner, sid, 'giá SSI', 0)
    asyncio.run(run())


def test_generation_failure_releases_lease_without_writing_a_partial_turn():
    async def run():
        class Broken(Engine):
            async def answer(self, *args, **kwargs): raise RuntimeError('test error')
        repo = Repository()
        store = PostgresSessionStore(repository=repo, engine=Broken())
        owner = str(uuid4())
        sid = (await store.create(owner))['session_id']
        with pytest.raises(RuntimeError): await store.send(owner, sid, 'giá FPT', 0)
        assert not repo.leases
        assert (await store.get(owner, sid))['messages'] == []
        with pytest.raises(ChatError): await store.send(owner, sid, 'x', True)
    asyncio.run(run())
