"""Exercise every protected route through HTTP, including direct calls by a low-privilege user."""

import asyncio
from uuid import UUID, uuid4

import pytest

from src.auth.service import create_access_token, create_password_reset_token
from src.core.config import get_settings
from src.main import app


USER_ID = uuid4()
READ = [
    ("GET", "/api/documents/doc-1/chunks"),
    ("GET", "/api/documents/doc-1/vocab"),
    ("POST", "/api/search"),
    ("GET", "/api/market-data/stocks/FPT/ohlcv"),
    ("GET", "/api/market-data/indices/VNINDEX/ohlcv"),
    ("GET", "/api/market-data/news"),
    ("GET", "/api/market-data/companies/FPT/news"),
    ("GET", "/api/market-data/live/status"),
    ("PUT", f"/api/market-data/live/viewers/{uuid4()}"),
    ("DELETE", f"/api/market-data/live/viewers/{uuid4()}"),
]
WRITE = [
    ("POST", "/api/documents"),
    ("POST", "/api/documents/json"),
    ("POST", "/api/documents/import-symbol/FPT"),
    ("POST", "/api/market-data/stocks/FPT/refresh"),
    ("POST", "/api/market-data/stocks/FPT/history"),
    ("POST", "/api/market-data/companies/FPT/news/refresh"),
]


@pytest.fixture
def role_client(monkeypatch):
    assigned = ["RESEARCHER"]

    async def find_user(pool, user_id: UUID):
        return {"user_id": user_id, "is_active": True}

    async def roles(pool, user_id: UUID):
        return assigned

    monkeypatch.setattr("src.auth.authorization.get_pool", lambda: object())
    monkeypatch.setattr("src.auth.repository.find_user_by_id", find_user)
    monkeypatch.setattr("src.auth.repository.get_user_roles", roles)
    return assigned


def request(method, path, bearer_token=None):
    """Invoke the real ASGI router without opening a network listener."""
    async def run():
        response = []
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.Event().wait()

        async def send(message):
            response.append(message)

        headers = [(b"host", b"testserver")]
        if bearer_token is not None:
            headers.append((b"authorization", f"Bearer {bearer_token}".encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                 "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
                 "query_string": b"", "root_path": "", "headers": headers,
                 "client": ("127.0.0.1", 1234), "server": ("testserver", 80)}
        await app(scope, receive, send)
        return next(message["status"] for message in response if message["type"] == "http.response.start")

    return asyncio.run(run())


def token(roles=("RESEARCHER",)):
    return create_access_token(USER_ID, get_settings(), list(roles))


@pytest.mark.parametrize("method,path", READ + WRITE)
def test_missing_and_invalid_token_denied(role_client, method, path):
    assert request(method, path) == 401
    assert request(method, path, "invalid") == 401


@pytest.mark.parametrize("method,path", WRITE)
def test_researcher_direct_write_denied(role_client, method, path):
    assert request(method, path, token()) == 403


@pytest.mark.parametrize("method,path", READ)
def test_account_without_granted_role_denied(role_client, method, path):
    role_client.clear()
    assert request(method, path, token()) == 403


def test_server_roles_override_stale_jwt_claims(role_client):
    assigned = role_client
    claimed_admin = token(("ADMINISTRATOR",))
    assert request("POST", "/api/documents/import-symbol/FPT", claimed_admin) == 403
    assigned[:] = ["DATA_ENGINEER"]
    # Once the server grants the role, the route reaches its handler (which has no fixture file).
    assert request("POST", "/api/documents/import-symbol/NOTFOUND", token()) == 404


def test_inactive_and_reset_token_denied(role_client, monkeypatch):
    async def inactive(pool, user_id):
        return {"user_id": user_id, "is_active": False}
    monkeypatch.setattr("src.auth.repository.find_user_by_id", inactive)
    assert request("GET", "/api/market-data/news", token()) == 401
    reset = create_password_reset_token(USER_ID, None, get_settings())
    assert request("GET", "/api/market-data/news", reset) == 401
