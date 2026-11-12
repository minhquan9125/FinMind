"""Admin overrides of the answering limits: bounded, versioned, applied per request."""
import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.b1_answering.core.policy import Limits
from src.b1_answering.providers.gemini import GeminiProvider
from src.documents.limit_overrides import EDITABLE, CachedLimits, LimitOverrides, effective_limits, validate
from src.retrieval_orchestration.live_research import LiveResearchService


def test_defaults_apply_until_something_is_saved(tmp_path):
    base = Limits.load()
    store = LimitOverrides(tmp_path)
    assert store.current() == (None, {})
    assert effective_limits(tmp_path) == base


def test_a_saved_override_changes_only_the_named_fields(tmp_path):
    base = Limits.load()
    store = LimitOverrides(tmp_path)
    version = store.save({'max_generation_calls': 5, 'max_output_tokens': 1024}, 'admin', 'Giảm để tiết kiệm', None)
    limits = effective_limits(tmp_path)
    assert (limits.max_generation_calls, limits.max_output_tokens) == (5, 1024)
    assert limits.max_input_tokens == base.max_input_tokens and limits.max_cost_usd == 0.0 and limits.model == base.model
    assert store.current()[0] == version and store.history()[0]['reason'] == 'Giảm để tiết kiệm'


def test_saving_requires_the_current_version_and_a_reason(tmp_path):
    store = LimitOverrides(tmp_path)
    first = store.save({'max_generation_calls': 5}, 'admin', 'Lần một', None)
    with pytest.raises(ValueError, match='LIMITS_CONFIG_CHANGED'):
        store.save({'max_generation_calls': 6}, 'admin', 'Người khác đã sửa', None)
    with pytest.raises(ValueError, match='LIMITS_REASON_REQUIRED'):
        store.save({'max_generation_calls': 6}, 'admin', ' ', first)
    store.save({}, 'admin', 'Quay về mặc định', first)           # an empty save is a recorded reset
    assert effective_limits(tmp_path) == Limits.load()


@pytest.mark.parametrize('values,code', [
    ({'max_cost_usd': 5}, 'LIMITS_FIELD_NOT_EDITABLE'),
    ({'model': 'x'}, 'LIMITS_FIELD_NOT_EDITABLE'),
    ({'max_generation_calls': 0}, 'LIMITS_OUT_OF_RANGE'),
    ({'max_generation_calls': 51}, 'LIMITS_OUT_OF_RANGE'),
    ({'max_output_tokens': True}, 'LIMITS_OUT_OF_RANGE'),
    ({'max_output_tokens': 1.5}, 'LIMITS_OUT_OF_RANGE'),
    ({'max_output_tokens': '2048'}, 'LIMITS_OUT_OF_RANGE'),
    ({'max_total_tokens': 1024, 'max_output_tokens': 4096}, 'LIMITS_INCONSISTENT'),
    ([], 'LIMITS_INVALID'),
])
def test_unsafe_values_are_refused(values, code):
    with pytest.raises(ValueError, match=code):
        validate(values)


def test_bounds_cover_exactly_the_five_token_and_call_fields():
    assert set(EDITABLE) == {'max_input_tokens', 'max_output_tokens', 'read_timeout_seconds',
                             'max_generation_calls', 'max_total_tokens'}
    assert validate({key: low for key, (low, _) in EDITABLE.items() if key != 'max_total_tokens'}) is not None


def test_cached_limits_pick_up_a_new_version_after_the_ttl(tmp_path):
    clock = [0.0]
    cached = CachedLimits(tmp_path, ttl=5.0, clock=lambda: clock[0])
    assert cached().max_generation_calls == 20
    LimitOverrides(tmp_path).save({'max_generation_calls': 3}, 'admin', 'Thử nghiệm', None)
    clock[0] = 1.0
    assert cached().max_generation_calls == 20                    # still cached
    clock[0] = 6.0
    assert cached().max_generation_calls == 3


def test_a_broken_override_store_never_blocks_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(LimitOverrides, 'current', lambda self: (_ for _ in ()).throw(RuntimeError('db locked')))
    assert effective_limits(tmp_path) == Limits.load()


def test_the_chat_service_uses_the_override_for_each_new_request(tmp_path):
    class Retriever:
        async def retrieve(self, *args): return {'items': []}

    seen = []
    service = LiveResearchService(Retriever(), limits_source=CachedLimits(tmp_path, ttl=0))

    async def run():
        from src.retrieval_orchestration import live_research
        real = live_research.LiveResearchService._answer_turn

        async def capture(self, *a, **k):
            seen.append((self.limits.max_generation_calls, self.budget.limits.max_generation_calls))
            return {'status': 'NO_DATA'}
        live_research.LiveResearchService._answer_turn = capture
        try:
            await service.answer('xin chào', 's')
            LimitOverrides(tmp_path).save({'max_generation_calls': 2}, 'admin', 'Giới hạn thấp', None)
            await service.answer('xin chào', 's')
        finally:
            live_research.LiveResearchService._answer_turn = real
    asyncio.run(run())
    assert seen == [(20, 20), (2, 2)]
    assert service.limits.max_generation_calls == 20             # the shared instance itself is untouched


def test_the_gemini_provider_timeout_follows_the_override(tmp_path):
    provider = GeminiProvider(Limits.load(), api_key='k', free_tier_confirmed=True)
    service = LiveResearchService(object(), provider=provider, limits_source=CachedLimits(tmp_path, ttl=0))
    LimitOverrides(tmp_path).save({'read_timeout_seconds': 45}, 'admin', 'Hạ thời gian chờ', None)
    service._current_limits()
    assert provider.limits.read_timeout_seconds == 45 and provider.limits.model == Limits.load().model


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(admin_ingestion_directory=tmp_path))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def test_api_requires_admin_and_round_trips_a_change(client):
    c, app = client
    path = '/api/v1/admin/ingestion/limits'
    assert c.get(path).status_code == 401 and c.put(path, json={}).status_code == 401
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))
    view = c.get(path).json()
    assert view['version'] is None and view['effective']['max_generation_calls'] == 20
    assert view['locked']['max_cost_usd'] == 0.0 and view['bounds']['max_generation_calls'] == {'min': 1, 'max': 50}
    saved = c.put(path, json={'values': {'max_generation_calls': 8}, 'reason': 'Giảm mức dùng', 'expected_version': None}).json()
    assert saved['effective']['max_generation_calls'] == 8 and saved['defaults']['max_generation_calls'] == 20
    assert saved['history'][0]['reason'] == 'Giảm mức dùng'
    stale = c.put(path, json={'values': {'max_generation_calls': 9}, 'reason': 'Bản cũ', 'expected_version': None})
    assert stale.status_code == 409 and stale.json()['detail'] == 'LIMITS_CONFIG_CHANGED'
    locked = c.put(path, json={'values': {'max_cost_usd': 1}, 'reason': 'Thử đổi khóa', 'expected_version': saved['version']})
    assert locked.status_code == 409 and locked.json()['detail'] == 'LIMITS_FIELD_NOT_EDITABLE'
    bad = c.put(path, json={'values': {'max_generation_calls': 999}, 'reason': 'Quá lớn', 'expected_version': saved['version']})
    assert bad.status_code == 409 and bad.json()['detail'] == 'LIMITS_OUT_OF_RANGE'
    assert c.put(path, json={'values': {}, 'reason': 'x', 'expected_version': saved['version']}).status_code == 422
