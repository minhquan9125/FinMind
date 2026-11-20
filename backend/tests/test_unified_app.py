from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from src import main


@pytest.mark.parametrize('fail_market', [False, True])
def test_combined_lifecycle_and_cleanup(monkeypatch, fail_market):
    events = []

    async def connect(): events.append('db-open')
    async def disconnect(): events.append('db-close')
    async def warmup(app):
        events.append('warmup')
        app.state.research_warmup = {'status': 'ready'}

    @asynccontextmanager
    async def market(app):
        events.append('market-open')
        if fail_market:
            raise RuntimeError('collector unavailable')
        try:
            app.state.live = None
            app.state.news = None
            yield
        finally:
            events.append('market-close')

    monkeypatch.setattr(main, 'connect', connect)
    monkeypatch.setattr(main, 'disconnect', disconnect)
    monkeypatch.setattr(main, 'market_lifespan', market)
    monkeypatch.setattr(main, 'warmup_research', warmup, raising=False)
    if fail_market:
        with pytest.raises(RuntimeError, match='collector unavailable'):
            with TestClient(main.app): pass
        assert events == ['db-open', 'market-open', 'db-close']
    else:
        with TestClient(main.app) as client:
            assert client.get('/api/health').status_code == 200
            assert client.get('/api/health').json()['research_warmup']['status'] == 'ready'
            paths = client.get('/openapi.json').json()['paths']
            assert '/api/v1/auth/login' in paths
            assert '/api/market-data/news' in paths
            assert '/api/market-data/live/viewers/{viewer_id}' in paths
        assert events == ['db-open', 'market-open', 'warmup', 'market-close', 'db-close']
