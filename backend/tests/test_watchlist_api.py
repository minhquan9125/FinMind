"""Server-side watchlist on the throwaway test DB (127.0.0.1:15434, never production)."""
import asyncio
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api.routers import watchlist
from src.auth.authorization import Principal
from tests.financial_db_fixture import create_financial_db, drop_financial_db


@pytest.fixture
def db(monkeypatch):
    loop = asyncio.new_event_loop()
    admin, conn, name = loop.run_until_complete(create_financial_db())
    users = [Principal(uuid4(), frozenset({'RESEARCHER'})) for _ in range(2)]
    for user in users:
        loop.run_until_complete(conn.execute(
            "INSERT INTO users(user_id,email,username,password_hash,is_active) VALUES($1,$2,$3,'x',true)",
            user.user_id, f'{user.user_id.hex[:8]}@test.local', user.user_id.hex[:8]))
    for symbol, company in (('FPT', 'Công ty Cổ phần FPT'), ('VCB', 'Vietcombank')):
        loop.run_until_complete(conn.execute(
            "INSERT INTO companies(company_id,symbol,company_name,exchange,is_active) VALUES($1,$2,$3,'HOSE',true)",
            uuid4(), symbol, company))
    monkeypatch.setattr(watchlist, 'get_pool', lambda: conn)  # asyncpg connection has the pool's query methods
    yield lambda coro: loop.run_until_complete(coro), users
    loop.run_until_complete(drop_financial_db(admin, conn, name))
    loop.close()


def test_add_is_idempotent(db):
    run, (alice, _) = db
    run(watchlist.add_symbol('FPT', alice))
    body = run(watchlist.add_symbol('FPT', alice))
    assert [item['id'] for item in body] == ['FPT']
    assert body[0]['name'] == 'Công ty Cổ phần FPT' and body[0]['exchange'] == 'HOSE'


def test_unknown_symbol_404(db):
    run, (alice, _) = db
    with pytest.raises(HTTPException) as raised:
        run(watchlist.add_symbol('ZZZ', alice))
    assert raised.value.status_code == 404 and raised.value.detail == 'Không tìm thấy doanh nghiệp.'


def test_users_see_only_their_own_rows(db):
    run, (alice, bob) = db
    run(watchlist.add_symbol('FPT', alice))
    assert run(watchlist.list_watchlist(bob)) == []


def test_remove_is_a_no_op_when_absent(db):
    run, (alice, _) = db
    run(watchlist.add_symbol('VCB', alice))
    assert [i['id'] for i in run(watchlist.remove_symbol('FPT', alice))] == ['VCB']
    assert run(watchlist.remove_symbol('VCB', alice)) == []


def test_requires_login():
    app = FastAPI()
    app.include_router(watchlist.router)
    client = TestClient(app)
    assert client.get('/api/watchlist').status_code == 401
    assert client.put('/api/watchlist/FPT').status_code == 401
