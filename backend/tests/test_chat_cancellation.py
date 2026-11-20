import asyncio
from unittest.mock import AsyncMock

import pytest

from src.api.chat_cancellation import while_connected
from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore


def test_disconnect_cancels_generation_and_releases_session_lease(monkeypatch):
    async def scenario():
        started = asyncio.Event()
        closed = asyncio.Event()
        repository = type('Repository', (), {})()
        repository.claim = AsyncMock(return_value=({}, 'lease'))
        repository.commit = AsyncMock()
        repository.release = AsyncMock()
        store = PostgresSessionStore(repository=repository)

        async def generate(*args):
            started.set()
            try:
                await asyncio.Future()
            finally:
                closed.set()

        monkeypatch.setattr('src.retrieval_orchestration.postgres_sessions.append_turn', generate)

        class Request:
            async def is_disconnected(self):
                await started.wait()
                return True

        owner = '00000000-0000-4000-8000-000000000001'
        sid = '00000000-0000-4000-8000-000000000002'
        with pytest.raises(asyncio.CancelledError):
            await while_connected(Request(), store.send(owner, sid, 'Question', 0))
        assert closed.is_set()
        repository.commit.assert_not_called()
        repository.release.assert_awaited_once_with(owner, sid, 'lease')

    asyncio.run(scenario())


def test_completed_response_is_returned_and_disconnect_watcher_is_closed():
    async def scenario():
        request = type('Request', (), {'is_disconnected': AsyncMock(return_value=False)})()
        async def answer():
            return {'revision': 1}
        assert await while_connected(request, answer()) == {'revision': 1}
        assert len(asyncio.all_tasks()) == 1
    asyncio.run(scenario())


def test_generation_failure_is_preserved():
    async def scenario():
        request = type('Request', (), {'is_disconnected': AsyncMock(return_value=False)})()
        async def answer():
            raise ValueError('failure')
        with pytest.raises(ValueError, match='failure'):
            await while_connected(request, answer())
        assert len(asyncio.all_tasks()) == 1
    asyncio.run(scenario())
