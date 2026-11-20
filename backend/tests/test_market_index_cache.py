import json
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from uuid import uuid4
from backend.src.api.routers.market_data import router, get_market_data_repository
from backend.src.auth.authorization import Principal, current_principal
from backend.src.market_data.repository import FileMarketDataRepository
from backend.src.market_data.history import normalize_index_history
from backend.src.market_data.live import LiveCoordinator
from backend.tests.test_market_indices import snapshot


def test_cache_survives_restart_and_does_not_spend_provider_quota(tmp_path):
    repo = FileMarketDataRepository(tmp_path)
    fetch = Mock(return_value=snapshot())
    service = LiveCoordinator(Mock(), lambda _: False, repo, history_fetch=fetch)
    service.index_history('VNINDEX')
    new_service = LiveCoordinator(Mock(), lambda _: False, repo, history_fetch=fetch)
    saved = new_service.saved_index_history('VNINDEX')
    assert saved['bars'][0]['close'] == '1710.5'
    assert saved['refresh']['stale'] is True
    fetch.assert_called_once()


def test_legacy_points_and_malformed_cache_fallback(tmp_path):
    repo = FileMarketDataRepository(tmp_path)
    legacy = tmp_path / 'data_pipeline/ScrapersOHLCV/data/stocks/VNINDEX/data.json'
    legacy.parent.mkdir(parents=True)
    raw = snapshot()
    legacy.write_text(json.dumps({'provenance': {'instrument_type': 'index', 'price_units': 'points', 'fetched_at': raw['fetched_at']},
        'bars': [{**r, 'symbol': 'VNINDEX', 'trade_date': r['time']} for r in raw['rows']]}))
    runtime = repo.index_history_path('VNINDEX'); runtime.parent.mkdir(parents=True)
    runtime.write_text('[]')
    assert repo.read_index_history('VNINDEX')['bars'][0]['close'] == '1710.5'
    legacy.write_text(json.dumps({'provenance': {'instrument_type': 'index', 'price_units': 'VND'}, 'bars': []}))
    assert repo.read_index_history('VNINDEX')['bars'] == []
    with pytest.raises(ValueError): repo.read_index_history('../FPT')


def test_cached_http_remains_available_when_shared_quota_is_busy_or_collector_off(tmp_path):
    repo = FileMarketDataRepository(tmp_path)
    repo.write_index_history('VNINDEX', normalize_index_history('VNINDEX', snapshot()))
    fetch = Mock(return_value=snapshot())
    service = LiveCoordinator(Mock(), lambda _: False, repo, history_fetch=fetch)
    service.index_history('HNXINDEX')
    app = FastAPI(); app.include_router(router); app.state.live = service
    app.dependency_overrides[get_market_data_repository] = lambda: repo
    app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset({'ADMINISTRATOR'}))
    with TestClient(app) as client:
        url = '/api/market-data/indices/VNINDEX/ohlcv'
        busy = client.get(url)
        assert busy.status_code == 429 and int(busy.headers['retry-after']) > 0
        saved = client.get(url + '?cached=true')
        assert saved.status_code == 200 and saved.json()['bars'][0]['close'] == '1710.5'
        app.state.live = None
        assert client.get(url + '?cached=true').status_code == 200
    fetch.assert_called_once()
