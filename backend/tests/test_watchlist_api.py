from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import watchlist as api
from src.auth.authorization import Principal, current_principal
from src.core.db import get_pool

USER = uuid4()
COMPANY = uuid4()


class Conn:
    def __init__(self, known):
        self.known, self.calls = known, []

    async def fetch(self, sql, *args):
        self.calls.append(('fetch', sql, args))
        return [{'ticker': 'FPT', 'name': 'FPT', 'sector': 'Công nghệ', 'exchange': 'HOSE'}]

    async def fetchval(self, sql, *args):
        self.calls.append(('fetchval', sql, args))
        return COMPANY if args[0] in self.known else None

    async def execute(self, sql, *args):
        self.calls.append(('execute', sql, args))


class Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        pool = self

        class Ctx:
            async def __aenter__(self): return pool.conn
            async def __aexit__(self, *exc): return False
        return Ctx()


def client(roles=('RESEARCHER',), known=('FPT',)):
    conn = Conn(known)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[current_principal] = lambda: Principal(USER, frozenset(roles))
    app.dependency_overrides[get_pool] = lambda: Pool(conn)
    return TestClient(app), conn


def test_list_is_scoped_to_the_signed_in_user():
    c, conn = client()
    body = c.get('/api/watchlist').json()
    assert body['items'][0]['ticker'] == 'FPT' and body['companies']
    assert conn.calls[0][2] == (USER,)


def test_follow_uppercases_and_inserts_for_the_user():
    c, conn = client()
    assert c.put('/api/watchlist/fpt').status_code == 204
    insert = conn.calls[-1]
    assert 'INSERT INTO public.watchlists' in insert[1] and insert[2] == (USER, COMPANY)


def test_unknown_company_is_404_and_writes_nothing():
    c, conn = client(known=())
    assert c.put('/api/watchlist/ZZZ').status_code == 404
    assert all(kind != 'execute' for kind, *_ in conn.calls)


def test_unfollow_deletes_only_the_users_row():
    c, conn = client()
    assert c.delete('/api/watchlist/FPT').status_code == 204
    assert 'DELETE FROM public.watchlists' in conn.calls[-1][1] and conn.calls[-1][2] == (USER, 'FPT')


def test_invalid_symbol_and_missing_role_are_rejected():
    c, _ = client()
    assert c.put('/api/watchlist/bad-symbol!').status_code == 422
    c, _ = client(roles=())
    assert c.get('/api/watchlist').status_code == 403
