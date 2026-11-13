"""The committed JWT default must never sign tokens, and search endpoints need a signed-in reader."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import search
from src.core.config import LEAKED_JWT_SECRETS, Settings, check_jwt_secret

app = FastAPI()
app.include_router(search.router)
anonymous = TestClient(app)


@pytest.mark.parametrize('path', ['/api/search/price', '/api/search/filtered'])
def test_search_price_and_filtered_require_login(path):
    assert anonymous.post(path, json={}).status_code == 401


@pytest.mark.parametrize('secret', ['', 'short-secret', 'replace-with-a-long-random-secret',
                                    *sorted(LEAKED_JWT_SECRETS)])
def test_startup_rejects_missing_short_or_committed_secret(monkeypatch, secret):
    monkeypatch.setenv('JWT_SECRET_KEY', secret)
    with pytest.raises(RuntimeError, match='JWT_SECRET_KEY'):
        check_jwt_secret(Settings(_env_file=None))


def test_a_long_private_secret_is_accepted(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'x' * 48)
    check_jwt_secret(Settings(_env_file=None))
