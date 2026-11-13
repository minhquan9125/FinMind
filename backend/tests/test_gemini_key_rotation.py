"""Gemini key rotation: failover on quota/credential rejections only, never leaks a key."""
import asyncio
import json
import logging
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.b1_answering.core.policy import Limits
from src.b1_answering.providers import key_pool
from src.b1_answering.providers.gemini import GeminiError, GeminiProvider
from src.b1_answering.providers.key_pool import INVALID_COOLDOWN, MAX_QUOTA_COOLDOWN, QUOTA_COOLDOWN, KeyPool, parse_keys

K1, K2, K3 = 'AIza-secret-key-one', 'AIza-secret-key-two', 'AIza-secret-key-three'


class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now


def ok_response():
    payload = {'answer': 'x'}
    return httpx.Response(200, json={
        'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(payload)}]}}],
        'usageMetadata': {'promptTokenCount': 1, 'candidatesTokenCount': 1, 'totalTokenCount': 2}})


def provider(handler, keys=(K1, K2), clock=None):
    p = GeminiProvider(Limits(), api_keys=list(keys), free_tier_confirmed=True,
                       transport=httpx.MockTransport(handler))
    if clock is not None:
        p.pool = KeyPool(list(keys), clock=clock)
    return p


def generate(p):
    return asyncio.run(p.generate({'contents': []}))


def recorder(*responses):
    """A handler that answers with the given responses in order and records which key was used."""
    used, queue = [], list(responses)

    def handler(request):
        used.append(request.headers['x-goog-api-key'])
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception): raise item
        return item() if callable(item) else item
    return handler, used


# ---- pool ----------------------------------------------------------------------------------

def test_parse_keys_accepts_common_separators_and_removes_duplicates():
    assert parse_keys(' a , b;c\nd\r\ne ', 'b, f', None, '') == ['a', 'b', 'c', 'd', 'e', 'f']
    assert parse_keys(None, '') == []


def test_pool_is_round_robin():
    pool = KeyPool(['a', 'b', 'c'])
    assert [pool.acquire() for _ in range(6)] == ['a', 'b', 'c', 'a', 'b', 'c']


def test_quota_cooldown_grows_caps_and_expires():
    clock = Clock(); pool = KeyPool(['a', 'b'], clock=clock)
    pool.quota_exhausted('a')
    assert pool.acquire() == 'b' and pool.acquire() == 'b'    # key 1 skipped while cooling
    clock.now += QUOTA_COOLDOWN + 1
    assert 'a' in [pool.acquire() for _ in range(2)]
    fresh = KeyPool(['a'], clock=clock)
    fresh.quota_exhausted('a'); fresh.quota_exhausted('a')     # consecutive strikes double the wait
    assert fresh.status()[0]['retry_in_seconds'] == round(QUOTA_COOLDOWN * 2)
    for _ in range(12): fresh.quota_exhausted('a')
    assert fresh.status()[0]['retry_in_seconds'] == MAX_QUOTA_COOLDOWN
    fresh.success('a')                                         # a good call clears the penalty
    assert fresh.status()[0]['state'] == 'ready' and fresh.acquire() == 'a'


def test_invalid_key_is_parked_for_hours_and_everything_cooling_returns_none():
    clock = Clock(); pool = KeyPool(['a', 'b'], clock=clock)
    pool.invalid('a'); pool.quota_exhausted('b')
    assert pool.acquire() is None
    assert pool.status()[0]['state'] == 'invalid' and pool.status()[0]['retry_in_seconds'] == round(INVALID_COOLDOWN)
    assert pool.acquire(exclude=['a', 'b']) is None


def test_pool_never_exposes_key_material():
    pool = KeyPool([K1, K2])
    text = repr(pool) + json.dumps(pool.status())
    assert K1 not in text and K2 not in text and 'key 1' in text
    with pytest.raises(ValueError):
        KeyPool(['', '  '])


# ---- provider ------------------------------------------------------------------------------

def test_successful_calls_rotate_across_keys():
    handler, used = recorder(ok_response)
    p = provider(handler, keys=(K1, K2, K3))
    for _ in range(4): generate(p)
    assert used == [K1, K2, K3, K1]


def test_a_quota_rejection_moves_to_the_next_key_within_the_same_call():
    handler, used = recorder(httpx.Response(429, json={'error': {}}), ok_response)
    p = provider(handler)
    assert generate(p)['payload'] == {'answer': 'x'}
    assert used == [K1, K2]
    used.clear()
    generate(p)                                              # key 1 is cooling, so key 2 again
    assert used == [K2]


def test_every_key_out_of_quota_reports_rate_limited_once_per_key():
    handler, used = recorder(httpx.Response(429, json={'error': {}}))
    p = provider(handler, keys=(K1, K2, K3))
    with pytest.raises(GeminiError) as raised:
        generate(p)
    assert raised.value.code == 'RATE_LIMITED' and used == [K1, K2, K3]
    used.clear()
    with pytest.raises(GeminiError) as again:                # all cooling: fail fast without calling Google
        generate(p)
    assert again.value.code == 'RATE_LIMITED' and used == []


def test_recovered_key_is_used_again_after_its_cooldown():
    clock = Clock()
    handler, used = recorder(httpx.Response(429, json={'error': {}}), ok_response)
    p = provider(handler, clock=clock)
    generate(p)
    clock.now += QUOTA_COOLDOWN + 1
    used.clear()
    for _ in range(2): generate(p)
    assert K1 in used and K2 in used


@pytest.mark.parametrize('rejection', [
    httpx.Response(403, json={'error': {'status': 'PERMISSION_DENIED'}}),
    httpx.Response(401, json={'error': {}}),
    httpx.Response(400, json={'error': {'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'API_KEY_INVALID'}]}}),
])
def test_revoked_or_invalid_keys_fail_over_and_are_parked(rejection):
    handler, used = recorder(rejection, ok_response)
    p = provider(handler)
    assert generate(p)['payload'] == {'answer': 'x'}
    assert used == [K1, K2]
    assert p.pool.status()[0]['state'] == 'invalid'


@pytest.mark.parametrize('failure,code', [
    (httpx.ReadTimeout('slow'), 'GEMINI_TIMEOUT'),
    (httpx.Response(500, json={'error': {'message': 'boom'}}), 'GEMINI_UNAVAILABLE'),
    (httpx.Response(200, content=b'not json'), 'INVALID_GEMINI_RESPONSE'),
])
def test_timeouts_server_errors_and_bad_bodies_never_trigger_failover(failure, code):
    handler, used = recorder(failure, ok_response)
    p = provider(handler)
    with pytest.raises(GeminiError) as raised:
        generate(p)
    assert raised.value.code == code and used == [K1]        # no second billable attempt


def test_a_single_key_keeps_the_previous_behaviour():
    handler, used = recorder(httpx.Response(429, json={'error': {}}))
    p = GeminiProvider(Limits(), api_key=K1, free_tier_confirmed=True, transport=httpx.MockTransport(handler))
    with pytest.raises(GeminiError) as raised:
        generate(p)
    assert raised.value.code == 'RATE_LIMITED' and used == [K1]
    assert len(p.pool) == 1


def test_error_details_and_logs_never_contain_a_key(caplog):
    leaky = httpx.Response(500, json={'error': {'status': 'INTERNAL', 'message': f'bad key {K2} here'}})
    handler, _ = recorder(httpx.Response(429, json={'error': {}}), leaky)
    p = provider(handler)
    with caplog.at_level(logging.DEBUG), pytest.raises(GeminiError):
        generate(p)
    assert K1 not in caplog.text and K2 not in caplog.text and 'key 1/2' in caplog.text
    assert K1 not in repr(p) and K2 not in repr(p)


@pytest.mark.parametrize('keys', [[], ['  '], ['a,b'], ['a\nb'], ['a;b']])
def test_invalid_key_lists_are_refused(keys):
    with pytest.raises(GeminiError) as raised:
        GeminiProvider(Limits(), api_keys=keys, free_tier_confirmed=True)
    assert raised.value.code == 'MISSING_API_KEY'


def test_free_tier_confirmation_is_still_required():
    with pytest.raises(GeminiError) as raised:
        GeminiProvider(Limits(), api_keys=[K1, K2], free_tier_confirmed=False)
    assert raised.value.code == 'FREE_TIER_NOT_CONFIRMED'


# ---- admin status ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    secret = SimpleNamespace(get_secret_value=lambda: '')
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        admin_ingestion_directory=tmp_path, gemini_keys_secret=secret, gemini_api_key=secret, gemini_api_keys=secret))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app
    key_pool.set_active(None)


def test_status_endpoint_requires_admin_and_hides_keys(client):
    c, app = client
    assert c.get('/api/v1/admin/ingestion/gemini-keys').status_code == 401
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))
    empty = c.get('/api/v1/admin/ingestion/gemini-keys').json()
    assert empty['keys'] == [] and empty['configured'] is False
    pool = KeyPool([K1, K2]); pool.quota_exhausted(K1); key_pool.set_active(pool)
    body = c.get('/api/v1/admin/ingestion/gemini-keys')
    assert body.json()['configured'] is True and body.json()['keys'][0]['state'] == 'quota'
    assert K1 not in body.text and K2 not in body.text


# ---- model busy (HTTP 503): ask again, never rotate or cool the key ------------------------------

def busy():
    return httpx.Response(503, json={'error': {'status': 'UNAVAILABLE', 'message': 'This model is currently experiencing high demand.'}})


def no_wait(p):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
    p._sleep = sleep
    return waits


def test_a_busy_model_is_asked_again_and_the_answer_is_returned(monkeypatch):
    monkeypatch.setattr('src.b1_answering.providers.gemini.RETRY_DELAY_SECONDS', 0)
    handler, used = recorder(busy(), ok_response)
    p = provider(handler, keys=(K1, K2))
    assert generate(p)['payload'] == {'answer': 'x'}
    assert len(used) == 2
    assert [item['state'] for item in p.pool.status()] == ['ready', 'ready']   # no key was cooled or blamed


def test_a_model_that_stays_busy_stops_after_one_retry(monkeypatch):
    monkeypatch.setattr('src.b1_answering.providers.gemini.RETRY_DELAY_SECONDS', 0)
    handler, used = recorder(busy())
    p = provider(handler, keys=(K1, K2))
    with pytest.raises(GeminiError) as caught:
        generate(p)
    assert caught.value.code == 'GEMINI_UNAVAILABLE'
    assert len(used) == 2
    assert [item['state'] for item in p.pool.status()] == ['ready', 'ready']


def test_other_server_errors_are_still_not_retried():
    handler, used = recorder(httpx.Response(500, json={'error': {'message': 'boom'}}))
    p = provider(handler)
    waits = []
    with pytest.raises(GeminiError) as caught:
        generate(p)
    assert caught.value.code == 'GEMINI_UNAVAILABLE'
    assert len(used) == 1 and waits == []


def test_a_busy_model_never_leaks_the_key_in_logs(caplog):
    leaky = httpx.Response(503, json={'error': {'status': 'UNAVAILABLE', 'message': f'busy for {K1}'}})
    handler, _ = recorder(leaky)
    p = provider(handler, keys=(K1,))
    no_wait(p)
    with caplog.at_level(logging.DEBUG), pytest.raises(GeminiError):
        generate(p)
    assert K1 not in caplog.text
