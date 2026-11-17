"""Token reproduction: real auth SQL/HTTP, fixture chat history, rollback-only user.

No browser storage, user credentials, live JWT secret or model/API calls are used.
Only the test app uses a random signing secret and pre-expired synthetic access.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import asyncpg
from fastapi import FastAPI
from pydantic import SecretStr
import uvicorn

from src.api.routers import auth, research_chat
from src.auth import repository
from src.auth.service import create_access_token, create_refresh_token, hash_password
from src.core.config import get_settings
from src.retrieval_orchestration.web_sessions import SessionStore


class SavepointConnection:
    """Actual SQL/RLS inside an outer rollback; not an isolation/concurrency test."""
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def transaction(self, **options):
        return self.connection.transaction()


class TransactionPool:
    """Share one rollback transaction across sequential test HTTP requests."""
    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        await self.connection.execute('RESET ROLE')
        try:
            yield SavepointConnection(self.connection)
        finally:
            await self.connection.execute('RESET ROLE')

    async def fetch(self, *args):
        return await self.connection.fetch(*args)

    async def execute(self, *args):
        return await self.connection.execute(*args)


async def run(result, chat_store='fixture', expect_recovery=False):
    runtime = get_settings()
    settings = runtime.model_copy(update={'jwt_secret_key': SecretStr(secrets.token_hex(32)),
                                          'access_token_minutes': 15})
    connection = await asyncpg.connect(runtime.database_url, timeout=10, command_timeout=15)
    transaction = connection.transaction()
    owner = None
    await transaction.start()
    try:
        await connection.execute("SET LOCAL statement_timeout = '15s'")
        role = await connection.fetchval("SELECT role_id FROM public.roles WHERE role_code='RESEARCHER'")
        if role is None:
            raise RuntimeError('Required existing test role missing; do not create grants')
        pool = TransactionPool(connection)
        account = await repository.create_user(pool, f's5wbs012-{secrets.token_hex(10)}@example.com',
                                               'S5 WBS012 rollback test', hash_password(secrets.token_urlsafe(32)))
        owner = account['user_id']
        seeds, hashes = {}, {}
        for mode in ('raw-chat', 'reactive', 'proactive'):
            token, digest = create_refresh_token()
            await repository.create_session(pool, owner, digest, settings.refresh_token_days)
            seeds[mode] = {'refresh_token': token}
            hashes[mode] = digest
        valid = create_access_token(owner, settings)
        expired = create_access_token(owner, settings.model_copy(update={'access_token_minutes': -1}))
        temporary_parent = ROOT / 'backend' / '.tmp'
        temporary_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='s5-wbs012-http-', dir=temporary_parent) as directory:
            app = FastAPI()
            app.include_router(auth.router)
            app.include_router(research_chat.router)
            if chat_store == 'postgres':
                from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
                from src.retrieval_orchestration.live_research import LiveResearchService

                class EmptyCorpus:
                    async def retrieve(self, query, scope):
                        return {'items': []}

                # Actual scope parsing, deliberately no facts/model/Google calls.
                store = PostgresSessionStore(pool, engine=LiveResearchService(EmptyCorpus()))
            else:
                store = SessionStore(Path(directory))
            app.dependency_overrides[research_chat.get_store] = lambda: store
            with patch.object(auth, 'get_pool', return_value=pool), \
                 patch.object(auth, 'get_settings', return_value=settings), \
                 patch.object(research_chat, 'get_settings', return_value=settings):
                listener = socket.socket()
                listener.bind(('127.0.0.1', 0))
                listener.listen(32)
                port = listener.getsockname()[1]
                config = uvicorn.Config(app, log_level='critical', access_log=False, lifespan='off')
                server = uvicorn.Server(config)
                task = asyncio.create_task(server.serve(sockets=[listener]))
                child = None
                try:
                    for _ in range(100):
                        if server.started:
                            break
                        if task.done():
                            await task
                            raise RuntimeError('Test HTTP server stopped')
                        await asyncio.sleep(0.02)
                    if not server.started:
                        raise TimeoutError('Test HTTP server startup')
                    child = await asyncio.create_subprocess_exec(
                        shutil.which('node') or 'node', str(ROOT / 'frontend/scripts/reproduce-s5-wbs012-http.mjs'),
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE, cwd=ROOT)
                    payload = dict(base_url=f'http://127.0.0.1:{port}', owner=str(owner),
                                   valid_access=valid, expired_access=expired, seeds=seeds, chat_store=chat_store,
                                   expect_recovery=expect_recovery)
                    stdout, _ = await asyncio.wait_for(child.communicate(json.dumps(payload).encode()), timeout=90)
                    client = json.loads(stdout)
                    result['client'] = client
                    if child.returncode != 0:
                        raise RuntimeError('Client harness assertions failed; inspect sanitized result')
                    unchanged = {}
                    for mode, digest in hashes.items():
                        unchanged[mode] = await connection.fetchval(
                            'SELECT count(*) FROM public.sessions WHERE user_id=$1 AND token_hash=$2', owner, digest)
                    result['auth_db'] = {
                        'raw_chat_refresh_still_valid': unchanged['raw-chat'] == 1,
                        'raw_chat_refresh_rotated': unchanged['raw-chat'] == 0,
                        'reactive_refresh_rotated': unchanged['reactive'] == 0,
                        'proactive_refresh_rotated': unchanged['proactive'] == 0,
                        'synthetic_sessions_in_transaction': await connection.fetchval(
                            'SELECT count(*) FROM public.sessions WHERE user_id=$1', owner),
                    }
                    assert result['auth_db']['raw_chat_refresh_still_valid'] is (not expect_recovery)
                    assert result['auth_db']['reactive_refresh_rotated']
                    assert result['auth_db']['proactive_refresh_rotated']
                    assert result['auth_db']['synthetic_sessions_in_transaction'] == 3
                    if chat_store == 'postgres':
                        async with pool.acquire() as chat_connection:
                            async with chat_connection.transaction():
                                await chat_connection.execute('SET LOCAL ROLE finmind_chat_runtime')
                                await chat_connection.fetchval("SELECT set_config('app.chat_user_id',$1,true)", str(owner))
                                conversations = await chat_connection.fetchval(
                                    'SELECT count(*) FROM research_chat.conversations WHERE user_id=$1', owner)
                                messages = await chat_connection.fetchval(
                                    'SELECT count(*) FROM research_chat.messages WHERE user_id=$1', owner)
                                user_messages = await chat_connection.fetchval(
                                    "SELECT count(*) FROM research_chat.messages WHERE user_id=$1 AND payload->>'role'='user'", owner)
                        assert (conversations, messages, user_messages) == ((3, 12, 6) if expect_recovery else (3, 10, 5))
                        result['chat_db'] = dict(conversations=conversations, message_rows=messages,
                                                 user_message_rows=user_messages, no_duplicate_writes=True)
                    result['status'] = ('PASS_CHAT_RECOVERY_AND_CONTROLS' if expect_recovery
                                        else 'PASS_REPRODUCTION_AND_RECOVERY_CONTROLS')
                finally:
                    if child is not None and child.returncode is None:
                        child.kill()
                        await child.communicate()
                    server.should_exit = True
                    await asyncio.wait_for(task, timeout=10)
                    listener.close()
    finally:
        try:
            await transaction.rollback()
            result['transaction_rolled_back'] = True
            if owner is not None:
                result['synthetic_user_absent_after_rollback'] = await connection.fetchval(
                    'SELECT count(*) FROM public.users WHERE user_id=$1', owner) == 0
                assert result['synthetic_user_absent_after_rollback']
                if chat_store == 'postgres':
                    async with connection.transaction():
                        await connection.execute('SET LOCAL ROLE finmind_chat_runtime')
                        await connection.fetchval("SELECT set_config('app.chat_user_id',$1,true)", str(owner))
                        result['synthetic_chat_absent_after_rollback'] = await connection.fetchval(
                            'SELECT count(*) FROM research_chat.conversations WHERE user_id=$1', owner) == 0
                        assert result['synthetic_chat_absent_after_rollback']
        finally:
            await connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--chat-store', choices=('fixture', 'postgres'), default='fixture')
    parser.add_argument('--expect', choices=('reproduction', 'recovery'), default='reproduction')
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Preserve prior evidence; choose a new output path')
    result = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  mode='REAL_LOCAL_HTTP_AUTH_ROUTER_POSTGRES_SQL_ROLLBACK_FIXTURE_CHAT_NOT_BROWSER',
                  expiry_method='Synthetic access issued already expired using random test-app signing secret',
                  production_settings_changed=False, browser_ui_or_timer_tested=False,
                  live_chat_postgres_store_tested=args.chat_store == 'postgres', external_ai_called=False,
                  credentials_exported=False)
    result['expectation'] = args.expect
    if args.chat_store == 'postgres':
        result['mode'] = 'REAL_LOCAL_HTTP_AUTH_AND_CHAT_POSTGRES_ROLLBACK_NOT_BROWSER'
        result['chat_engine'] = 'Real LiveResearchService scope parser; empty corpus; no model or source-quality claims'
        result['transaction_boundary'] = 'Sequential HTTP requests in one outer rollback with savepoints; not isolation/concurrency acceptance'
    try:
        asyncio.run(run(result, args.chat_store, args.expect == 'recovery'))
    except Exception as exc:
        result.update(status='FAIL', error_type=type(exc).__name__)
    watched = ['backend/src/api/routers/auth.py', 'backend/src/auth/repository.py',
               'backend/src/auth/service.py', 'frontend/src/pages/research/chatApi.js',
               'frontend/src/shared/api/authorization.js', 'frontend/src/shared/api/authSession.js']
    result['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in watched}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({'status': result['status'], 'error_type': result.get('error_type'),
                      'transaction_rolled_back': result.get('transaction_rolled_back'),
                      'synthetic_user_absent_after_rollback': result.get('synthetic_user_absent_after_rollback')}))
    sys.exit(0 if result['status'] in ('PASS_REPRODUCTION_AND_RECOVERY_CONTROLS', 'PASS_CHAT_RECOVERY_AND_CONTROLS') else 1)
