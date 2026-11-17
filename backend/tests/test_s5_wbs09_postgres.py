"""Opt-in real SQL/RLS persistence for the new conversation commands; always rollback."""
import asyncio
from contextlib import asynccontextmanager
import os
from uuid import UUID, uuid4

import pytest


@pytest.mark.skipif(os.getenv('RUN_S5_WBS09_DB_SMOKE') != '1', reason='explicit rollback-only PostgreSQL smoke opt-in')
def test_real_postgres_persists_summary_sources_and_resets_new_session():
    import asyncpg
    from src.auth import repository as auth_repository
    from src.core.config import get_settings
    from src.retrieval_orchestration.chat_types import ChatError
    from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
    from tests.test_s5_wbs093_summary import SequenceEngine, sourced_result

    class Savepoints:
        """Keep production SQL/RLS, using nested savepoints for outer rollback.

        This smoke does not measure isolation levels or concurrency semantics.
        """
        def __init__(self, connection): self.connection = connection
        def __getattr__(self, name): return getattr(self.connection, name)
        def transaction(self, **options): return self.connection.transaction()

    class Pool:
        def __init__(self, connection): self.connection = connection
        @asynccontextmanager
        async def acquire(self): yield Savepoints(self.connection)

    async def run():
        connection = await asyncpg.connect(get_settings().database_url, timeout=10, command_timeout=15)
        transaction = connection.transaction()
        await transaction.start()
        owner, sids = None, []
        try:
            await connection.execute("SET LOCAL statement_timeout='15s'")
            pool = Pool(connection)
            account = await auth_repository.create_user(pool, f's5wbs09-{uuid4().hex}@example.com',
                                                       'Rollback-only summary test', 'disabled-synthetic-login')
            owner = str(account['user_id'])
            engine = SequenceEngine([sourced_result(), sourced_result('VCB', '2024')])
            store = PostgresSessionStore(pool, engine=engine)
            snap = await store.create(owner)
            sid = snap['session_id']
            sids.append(sid)
            for text in ('Hỏi tin FPT', 'Hỏi tin VCB', 'Tổng hợp nãy giờ'):
                snap = await store.send(owner, sid, text, snap['revision'])
            assert len(snap['messages'][-1]['result']['answering']['citations']) == 2
            reopened = PostgresSessionStore(pool, engine=engine)
            assert await reopened.get(owner, sid) == snap
            child = await reopened.resume(owner, sid)
            sids.append(child['session_id'])
            child = await reopened.send(owner, child['session_id'], 'Tổng hợp nãy giờ', 0)
            assert len(child['messages'][-1]['result']['evidence_packs']) == 2
            assert await store.get(owner, sid) == snap
            fresh = await store.create(owner)
            sids.append(fresh['session_id'])
            fresh = await store.send(owner, fresh['session_id'], 'Tổng hợp nãy giờ', 0)
            assert fresh['messages'][-1]['result']['status'] == 'ASK_CLARIFICATION'
            with pytest.raises(ChatError) as error:
                await store.get(str(uuid4()), sid)
            assert error.value.status == 404
            assert engine.calls == 2
        finally:
            try:
                await transaction.rollback()
                if owner is not None:
                    assert await connection.fetchval('SELECT count(*) FROM public.users WHERE user_id=$1', UUID(owner)) == 0
                if sids:
                    async with connection.transaction():
                        await connection.execute('SET LOCAL ROLE finmind_chat_runtime')
                        await connection.fetchval("SELECT set_config('app.chat_user_id',$1,true)", owner)
                        assert await connection.fetchval(
                            'SELECT count(*) FROM research_chat.conversations WHERE conversation_id=ANY($1::uuid[])',
                            [UUID(sid) for sid in sids]) == 0
            finally:
                await connection.close()
    asyncio.run(run())
