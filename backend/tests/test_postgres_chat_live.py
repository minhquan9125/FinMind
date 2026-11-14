"""Opt-in real Supabase persistence, token isolation, RLS, pool reset and cleanup."""
import asyncio
import json
import os
from uuid import UUID, uuid4

import pytest


@pytest.mark.skipif(os.getenv('RUN_CHAT_DB_SMOKE') != '1', reason='requires explicit Supabase write/isolation smoke opt-in')
def test_real_database_chat_isolation_and_api_contract(monkeypatch):
    import asyncpg
    import httpx
    from fastapi import FastAPI
    from src.api.routers import research_chat as api
    from src.auth.service import create_access_token
    from src.core.config import get_settings
    from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
    from src.retrieval_orchestration.chat_types import ChatError
    from src.retrieval_orchestration.chat_logic import append_turn
    from src.retrieval_orchestration.web_sessions import SessionStore
    from tests.test_postgres_chat_store import Engine

    def no_file_write(*args, **kwargs): raise AssertionError('web history must not write JSON')
    monkeypatch.setattr(SessionStore, '_atomic_write_json', no_file_write)

    async def run():
        settings = get_settings()
        pool = await asyncpg.create_pool(settings.database_url, ssl='require', min_size=1, max_size=1,
                                         timeout=10, command_timeout=15, statement_cache_size=0)
        created, probe = [], str(uuid4())
        try:
            async with pool.acquire() as conn:
                owners = [str(row['user_id']) for row in await conn.fetch('SELECT user_id FROM public.users ORDER BY user_id LIMIT 2')]
                assert len(owners) == 2
            a, b = owners
            engine = Engine()
            store = PostgresSessionStore(pool, engine=engine)
            repo = store.repository
            app = FastAPI()
            app.include_router(api.router)
            app.dependency_overrides[api.get_store] = lambda: store
            tokens = {owner: {'Authorization': 'Bearer '+create_access_token(UUID(owner), settings)} for owner in owners}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                for owner in owners:
                    response = await client.post('/api/research/chat/sessions', headers=tokens[owner])
                    assert response.status_code == 201
                    sid = response.json()['session_id']
                    created.append((owner, sid))
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE research_chat.conversations SET metadata=metadata||jsonb_build_object('_probe',$2::text) WHERE conversation_id=$1", UUID(sid), probe)
                sid_a, sid_b = created[0][1], created[1][1]
                path = '/api/research/chat/sessions/'+sid_a
                assert (await client.get(path)).status_code == 401
                for method, url, body in [('GET', path, None), ('POST', path+'/messages', {'text': 'x', 'revision': 0}),
                                          ('POST', path+'/resume', None), ('DELETE', path, None)]:
                    response = await client.request(method, url, json=body, headers=tokens[b])
                    assert response.status_code == 404, response.status_code
                assert engine.calls == 0
                forged = await client.post(path+'/messages', headers=tokens[a], json={'text': 'x', 'revision': 0, 'user_id': b})
                assert forged.status_code == 422
                sent = await client.post(path+'/messages', headers=tokens[a], json={'text': 'giá FPT bn', 'revision': 0})
                assert sent.status_code == 200
                saved = sent.json()
                assert saved['revision'] == 1 and len(saved['messages']) == 2
                assert (await PostgresSessionStore(pool, engine=engine).get(a, sid_a))['messages'] == saved['messages']
                stale = await client.post(path+'/messages', headers=tokens[a], json={'text': 'x', 'revision': 0})
                assert stale.status_code == 409 and engine.calls == 1
                listing = (await client.get('/api/research/chat/sessions?owner='+b, headers=tokens[a])).json()['items']
                assert sid_a in [item['session_id'] for item in listing]
                assert sid_b not in [item['session_id'] for item in listing]
                resumed = await client.post(path+'/resume', headers=tokens[a])
                assert resumed.status_code == 201
                fork = resumed.json()
                created.append((a, fork['session_id']))
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE research_chat.conversations SET metadata=metadata||jsonb_build_object('_probe',$2::text) WHERE conversation_id=$1", UUID(fork['session_id']), probe)
                assert fork['messages'] == saved['messages'] and fork['revision'] == 0

            # Prove DB isolation even when SQL accidentally omits WHERE user_id.
            for owner, own, other in ((a, sid_a, sid_b), (b, sid_b, sid_a)):
                async with repo.transaction(owner) as conn:
                    rows = await conn.fetch('SELECT conversation_id FROM research_chat.conversations WHERE conversation_id=ANY($1::uuid[])', [UUID(sid_a), UUID(sid_b)])
                    assert [str(row['conversation_id']) for row in rows] == [own]
                    assert await conn.execute("UPDATE research_chat.conversations SET preview='tamper' WHERE conversation_id=$1", UUID(other)) == 'UPDATE 0'
                    assert await conn.execute('DELETE FROM research_chat.conversations WHERE conversation_id=$1', UUID(other)) == 'DELETE 0'
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        async with conn.transaction():
                            await conn.execute('UPDATE research_chat.conversations SET user_id=$2 WHERE conversation_id=$1', UUID(own), UUID(b if owner == a else a))
                    with pytest.raises(asyncpg.ForeignKeyViolationError):
                        async with conn.transaction():
                            await conn.execute("INSERT INTO research_chat.messages(conversation_id,user_id,position,payload) VALUES($1,$2,1999,$3::jsonb)",
                                UUID(other), UUID(owner), json.dumps({'role': 'user', 'content': 'probe', 'timestamp': '2026-10-24T00:00:00+00:00'}))
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT current_setting('role')") in ('none', 'postgres')
                assert await conn.fetchval("SELECT current_setting('app.chat_user_id',true)") in (None, '')
                async with conn.transaction():
                    await conn.execute('SET LOCAL ROLE finmind_chat_runtime')
                    assert await conn.fetchval('SELECT count(*) FROM research_chat.conversations') == 0
                for role in ('anon', 'authenticated'):
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        async with conn.transaction():
                            await conn.execute('SET LOCAL ROLE '+role)
                            await conn.fetchval('SELECT count(*) FROM research_chat.conversations')
            # Keep only one pooled connection: a waiting model must not hold it.
            entered, release = asyncio.Event(), asyncio.Event()
            class BlockingEngine(Engine):
                async def answer(self, *args, **kwargs):
                    entered.set()
                    await release.wait()
                    return await super().answer(*args, **kwargs)
            waiting = PostgresSessionStore(pool, engine=BlockingEngine())
            pending = asyncio.create_task(waiting.send(a, sid_a, 'waiting probe', 1))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                async with pool.acquire(timeout=2) as conn:
                    assert await conn.fetchval('SELECT 1') == 1
                assert (await store.get(b, sid_b))['revision'] == 0
                with pytest.raises(ChatError) as conflict: await store.send(a, sid_a, 'duplicate probe', 1)
                assert conflict.value.status == 409
                release.set()
                await pending
            finally:
                release.set()
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
            # A DB error after updating the row must roll back both revision and messages.
            doc, lease = await repo.claim(a, sid_a, 2, 60)
            broken = await append_turn(doc, 'another probe', engine)
            broken['messages'][-1]['role'] = 'invalid'
            try:
                with pytest.raises(asyncpg.CheckViolationError): await repo.commit(a, sid_a, lease, 2, broken)
                unchanged = await repo.get(a, sid_a)
                assert unchanged['revision'] == 2 and len(unchanged['messages']) == 4
            finally: await repo.release(a, sid_a, lease)
            # Expired processing leases are recoverable; the old worker cannot save
            # a late answer or release the replacement worker's lease.
            doc, old_lease = await repo.claim(a, sid_a, 2, 60)
            async with pool.acquire() as conn:
                await conn.execute("UPDATE research_chat.conversations SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE conversation_id=$1 AND metadata->>'_probe'=$2", UUID(sid_a), probe)
            replacement_doc, replacement = await repo.claim(a, sid_a, 2, 60)
            try:
                late = await append_turn(doc, 'late probe', engine)
                with pytest.raises(ChatError): await repo.commit(a, sid_a, old_lease, 2, late)
                await repo.release(a, sid_a, old_lease)
                with pytest.raises(ChatError): await repo.claim(a, sid_a, 2, 60)
            finally: await repo.release(a, sid_a, replacement)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                path = '/api/research/chat/sessions/'+sid_a
                assert (await client.delete(path, headers=tokens[a])).status_code == 204
                assert (await client.get(path, headers=tokens[a])).status_code == 404
                async with pool.acquire() as conn:
                    assert await conn.fetchval('SELECT count(*) FROM research_chat.messages WHERE conversation_id=$1', UUID(sid_a)) == 0
            print({'db_persistence': 'PASS', 'jwt_api_isolation': 'PASS', 'rls_without_owner_filter': 'PASS',
                   'pool_identity_reset': 'PASS', 'no_connection_held_during_generation': 'PASS',
                   'atomic_rollback': 'PASS', 'expired_lease_guard': 'PASS', 'delete_cascade': 'PASS', 'json_writes': 0})
        finally:
            # Delete only UUIDs created by this probe, additionally bound to its marker.
            if created:
                async with pool.acquire() as conn:
                    await conn.execute("DELETE FROM research_chat.conversations WHERE conversation_id=ANY($1::uuid[]) AND metadata->>'_probe'=$2",
                                       [UUID(sid) for _, sid in created], probe)
            await pool.close()
    asyncio.run(run())
