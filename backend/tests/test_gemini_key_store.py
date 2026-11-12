"""Gemini keys managed from the admin page: encrypted at rest, write-only, hot-reloaded."""
import asyncio
import json
import logging
import sqlite3
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.b1_answering.core.policy import Limits
from src.b1_answering.providers import gemini as gemini_module
from src.b1_answering.providers import key_pool, key_store
from src.b1_answering.providers.gemini import GeminiProvider, probe_key
from src.b1_answering.providers.key_pool import KeyPool
from src.b1_answering.providers.key_store import CachedKeys, KeyStore, fingerprint, validate_key

SECRET = 'a-long-enough-encryption-secret-123'
ENV_KEY = 'AIza' + 'E' * 35
K1 = 'AIza' + 'A' * 35
K2 = 'AIza' + 'B' * 35
K3 = 'AIza' + 'C' * 35


def ok_response():
    return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"a": 1}'}]}}],
                                     'usageMetadata': {'promptTokenCount': 1, 'candidatesTokenCount': 1, 'totalTokenCount': 2}})


# ---- the store -------------------------------------------------------------------------------

def test_a_key_is_encrypted_on_disk_and_never_listed(tmp_path):
    store = KeyStore(tmp_path, SECRET)
    item = store.add('Khóa của Huyền', K1, 'admin-1', verified=True)
    assert item['last4'] == K1[-4:] and item['enabled'] and item['verified'] and item['readable']
    assert K1 not in json.dumps(store.list())
    raw = (tmp_path / 'research-metrics.sqlite').read_bytes()
    assert K1.encode() not in raw and K1[4:].encode() not in raw           # nowhere in the file, not even a suffix
    with sqlite3.connect(tmp_path / 'research-metrics.sqlite') as conn:
        row = conn.execute('SELECT secret_enc, fingerprint FROM gemini_keys').fetchone()
    assert row[0].startswith('gAAAA') and row[1] == fingerprint(K1)


def test_active_keys_decrypt_only_enabled_ones_with_metadata(tmp_path):
    store = KeyStore(tmp_path, SECRET)
    first = store.add('Một', K1, 'a'); second = store.add('Hai', K2, 'a')
    store.set_enabled(second['id'], False)
    keys, meta = store.active_keys()
    assert keys == [K1] and meta == [{'label': 'Một', 'source': 'web', 'id': first['id']}]


def test_validation_duplicates_and_limits(tmp_path):
    store = KeyStore(tmp_path, SECRET)
    for bad in (None, '', 'AIza short', 'sk-' + 'x' * 40, 'AIza' + 'A' * 10 + ' ' + 'A' * 25, 'AIza' + 'A' * 100, 12345):
        with pytest.raises(ValueError, match='KEY_FORMAT_INVALID'):
            validate_key(bad)
    assert validate_key('  ' + K1 + '\r\n') == K1                       # whitespace around a pasted key is trimmed
    new_shape = 'AQ.' + 'x' * 8 + '_' + 'Y' * 20 + '-' + 'z' * 18                  # newer Google key shape, with a dot
    assert validate_key(new_shape) == new_shape
    for bad in ('AQ' + 'x' * 40, 'AQ. short', 'AQ.' + 'x' * 10 + ' ' + 'y' * 25, 'AQ.' + 'x' * 150, 'AX.' + 'x' * 40):
        with pytest.raises(ValueError, match='KEY_FORMAT_INVALID'):
            validate_key(bad)
    for label in ('', '   ', 'x' * 61, 'có\nxuống dòng', None):
        with pytest.raises(ValueError, match='KEY_LABEL_INVALID'):
            store.add(label, K1, 'a')
    store.add('Một', K1, 'a')
    with pytest.raises(ValueError, match='KEY_DUPLICATE'):
        store.add('Trùng', K1, 'a')
    with pytest.raises(ValueError, match='KEY_DUPLICATE'):                 # same key already set in .env
        store.add('Env', K2, 'a', extra_fingerprints={fingerprint(K2)})
    for n in range(key_store.MAX_KEYS - 1):
        store.add(f'k{n}', 'AIza' + f'{n:035d}', 'a')
    with pytest.raises(ValueError, match='KEY_LIMIT_REACHED'):
        store.add('Quá nhiều', 'AIza' + 'Z' * 35, 'a')


def test_without_a_proper_secret_the_store_is_disabled(tmp_path):
    for secret in (None, '', 'too-short'):
        store = KeyStore(tmp_path, secret)
        assert store.usable is False
        with pytest.raises(ValueError, match='KEY_STORE_DISABLED'):
            store.add('x', K1, 'a')
        assert store.active_keys() == ([], [])


def test_a_changed_secret_makes_old_keys_unreadable_not_crashing(tmp_path):
    KeyStore(tmp_path, SECRET).add('Cũ', K1, 'a')
    other = KeyStore(tmp_path, 'a-completely-different-secret-value')
    assert other.list()[0]['readable'] is False
    assert other.active_keys() == ([], []) and other.secret(other.list()[0]['id']) is None


def test_toggle_and_delete_report_missing_keys(tmp_path):
    store = KeyStore(tmp_path, SECRET)
    item = store.add('Một', K1, 'a')
    assert store.set_enabled(item['id'], False)['enabled'] is False
    assert store.delete(item['id']) == 'Một' and store.list() == []
    for call in (lambda: store.set_enabled(item['id'], True), lambda: store.delete(item['id'])):
        with pytest.raises(ValueError, match='KEY_NOT_FOUND'):
            call()


# ---- hot reload ---------------------------------------------------------------------------------

def test_sync_keeps_cooldowns_of_staying_keys_and_adopts_changes():
    clock = [0.0]
    pool = KeyPool(['a', 'b'], clock=lambda: clock[0])
    pool.quota_exhausted('a')
    assert pool.sync(['a', 'b', 'c'], [None, None, {'label': 'Mới', 'source': 'web', 'id': 'i'}]) is True
    assert pool.acquire() == 'b' and pool.acquire() == 'c' and pool.acquire() == 'b'      # 'a' is still cooling
    assert [s['state'] for s in pool.status()][0] == 'quota' and pool.status()[2]['label'] == 'Mới'
    assert pool.sync(['b', 'c']) is True and pool.position('a') == 0 and len(pool) == 2
    assert pool.sync([]) is False and len(pool) == 2                                       # an empty list is ignored
    assert pool.sync(['b', 'c']) is False


def test_status_never_contains_key_material():
    pool = KeyPool([K1, K2], meta=[None, {'label': 'Hai', 'source': 'web', 'id': 'x'}])
    text = json.dumps(pool.status()) + repr(pool)
    assert K1 not in text and K2 not in text and 'Hai' in text


def test_the_cached_source_merges_env_and_web_keys_without_duplicates(tmp_path):
    clock = [0.0]
    store = KeyStore(tmp_path, SECRET)
    source = CachedKeys([ENV_KEY], store, ttl=5, clock=lambda: clock[0])
    assert source()[0] == [ENV_KEY]
    store.add('Web', K1, 'a')
    assert source()[0] == [ENV_KEY]                                    # cached
    clock[0] = 6
    keys, meta = source()
    assert keys == [ENV_KEY, K1] and [m['source'] for m in meta] == ['env', 'web']
    store.add('Env lại', ENV_KEY[:-1] + 'F', 'a')
    source.refresh()
    assert len(source()[0]) == 3


def test_a_running_provider_uses_a_key_added_later_and_stops_using_a_removed_one(tmp_path):
    store, used = KeyStore(tmp_path, SECRET), []

    def handler(request):
        used.append(request.headers['x-goog-api-key'])
        return ok_response()
    source = CachedKeys([ENV_KEY], store, ttl=0)
    provider = GeminiProvider(Limits.load(), api_keys=[ENV_KEY], key_source=source, free_tier_confirmed=True,
                              transport=httpx.MockTransport(handler))
    run = lambda: asyncio.run(provider.generate({'contents': []}))
    run(); run()
    assert set(used) == {ENV_KEY}
    item = store.add('Web', K1, 'a')
    for _ in range(4): run()
    assert K1 in used
    store.delete(item['id']); used.clear()
    for _ in range(3): run()
    assert set(used) == {ENV_KEY}


def test_a_broken_key_source_never_blocks_requests():
    def broken(): raise RuntimeError('db locked')
    provider = GeminiProvider(Limits.load(), api_keys=[K1], key_source=broken, free_tier_confirmed=True,
                              transport=httpx.MockTransport(lambda r: ok_response()))
    assert asyncio.run(provider.generate({'contents': []}))['payload'] == {'a': 1}


# ---- probing a key -------------------------------------------------------------------------------

@pytest.mark.parametrize('response,expected', [
    (httpx.Response(200, json={'totalTokens': 3}), 'OK'),
    (httpx.Response(429, json={'error': {}}), 'QUOTA'),
    (httpx.Response(403, json={'error': {}}), 'INVALID'),
    (httpx.Response(400, json={'error': {'details': [{'reason': 'API_KEY_INVALID'}]}}), 'INVALID'),
    (httpx.Response(500, json={'error': {}}), 'UNAVAILABLE'),
])
def test_probe_key_classifies_the_answer_without_generating_anything(response, expected):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return response
    assert asyncio.run(probe_key(K1, transport=httpx.MockTransport(handler))) == expected
    assert seen and seen[0].endswith(':countTokens')


# ---- the admin API --------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    def secret(value): return SimpleNamespace(get_secret_value=lambda: value)
    settings = SimpleNamespace(admin_ingestion_directory=tmp_path, gemini_keys_secret=secret(SECRET),
                               gemini_api_key=secret(ENV_KEY), gemini_api_keys=secret(''))
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    outcome = {'value': 'OK'}

    async def fake_probe(key, *args, **kwargs):
        outcome['seen'] = key
        return outcome['value']
    monkeypatch.setattr(gemini_module, 'probe_key', fake_probe)
    key_pool.set_active(None); key_store.set_key_source(None)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))
    with TestClient(app) as c:
        yield c, app, outcome, settings
    key_pool.set_active(None); key_store.set_key_source(None)


BASE = '/api/v1/admin/ingestion/gemini-keys'


def test_every_key_endpoint_requires_an_administrator(client):
    c, app, _, _ = client
    app.dependency_overrides.clear()
    for call in (lambda: c.get(BASE), lambda: c.post(BASE, json={}), lambda: c.post(f'{BASE}/{UUID(int=1)}/test'),
                 lambda: c.patch(f'{BASE}/{UUID(int=1)}', json={'enabled': False}), lambda: c.delete(f'{BASE}/{UUID(int=1)}')):
        assert call().status_code == 401


def test_adding_a_key_returns_no_secret_and_audits_without_it(client, tmp_path, caplog):
    c, _, outcome, _ = client
    with caplog.at_level(logging.DEBUG):
        response = c.post(BASE, json={'label': 'Khóa của Huyền', 'key': K1})
    assert response.status_code == 201 and outcome['seen'] == K1
    body = response.json()
    assert body['item']['label'] == 'Khóa của Huyền' and body['item']['last4'] == K1[-4:] and body['verification'] == 'OK'
    assert body['restart_needed'] is True                                    # no chat provider is running in this test
    listing = c.get(BASE)
    assert listing.json()['managed'][0]['id'] == body['item']['id'] and listing.json()['store']['usable'] is True
    audit = json.dumps(api.queue().audit_page(category='operation')['items'])
    for text in (response.text, listing.text, audit, caplog.text):
        assert K1 not in text and K1[4:] not in text
    assert 'GEMINI_KEY_ADD' in audit


def test_invalid_input_never_echoes_the_submitted_key(client):
    c, _, _, _ = client
    for payload in ({'label': 'x', 'key': 'AIza-not-valid-' + 'Q' * 40 + '!'}, {'label': 'x', 'key': 12345},
                    {'label': '', 'key': K1}, {'key': K1}, ['AIza' + 'Q' * 35]):
        response = c.post(BASE, json=payload)
        assert response.status_code == 422
        assert 'Q' * 20 not in response.text and K1 not in response.text
    assert c.post(BASE, content='not json', headers={'Content-Type': 'application/json'}).status_code == 422


def test_a_key_google_refuses_is_not_stored(client):
    c, _, outcome, _ = client
    outcome['value'] = 'INVALID'
    response = c.post(BASE, json={'label': 'Hỏng', 'key': K1})
    assert response.status_code == 409 and response.json()['detail'] == 'KEY_REJECTED'
    assert c.get(BASE).json()['managed'] == []


@pytest.mark.parametrize('verdict,verified', [('QUOTA', True), ('UNAVAILABLE', False)])
def test_a_valid_but_exhausted_or_unverifiable_key_is_still_saved(client, verdict, verified):
    c, _, outcome, _ = client
    outcome['value'] = verdict
    response = c.post(BASE, json={'label': 'Một', 'key': K1}).json()
    assert response['verification'] == verdict and response['item']['verified'] is verified


def test_duplicates_including_the_env_key_are_refused(client):
    c, _, _, _ = client
    assert c.post(BASE, json={'label': 'Một', 'key': K1}).status_code == 201
    assert c.post(BASE, json={'label': 'Lại', 'key': K1}).json()['detail'] == 'KEY_DUPLICATE'
    assert c.post(BASE, json={'label': 'Env', 'key': ENV_KEY}).json()['detail'] == 'KEY_DUPLICATE'


def test_without_an_encryption_secret_adding_is_refused_and_says_why(client):
    c, _, _, settings = client
    settings.gemini_keys_secret = SimpleNamespace(get_secret_value=lambda: '')
    response = c.post(BASE, json={'label': 'Một', 'key': K1})
    assert response.status_code == 503 and response.json()['detail'] == 'KEY_STORE_DISABLED'
    assert c.get(BASE).json()['store']['usable'] is False


def test_test_toggle_and_delete_work_by_id(client):
    c, _, outcome, _ = client
    item = c.post(BASE, json={'label': 'Một', 'key': K1}).json()['item']
    outcome['value'] = 'INVALID'
    assert c.post(f"{BASE}/{item['id']}/test").json() == {'result': 'INVALID'} and outcome['seen'] == K1
    assert c.get(BASE).json()['managed'][0]['verified'] is False
    assert c.patch(f"{BASE}/{item['id']}", json={'enabled': False}).json()['item']['enabled'] is False
    assert c.patch(f"{BASE}/{item['id']}", json={'enabled': 'no'}).status_code == 422
    assert c.delete(f"{BASE}/{item['id']}").json() == {'deleted': True}
    missing = f'{BASE}/{UUID(int=9)}'
    assert c.post(missing + '/test').status_code == 404 and c.delete(missing).status_code == 404
    assert c.patch(missing, json={'enabled': True}).status_code == 404
    actions = [r['action'] for r in api.queue().audit_page(category='operation')['items']]
    assert {'GEMINI_KEY_ADD', 'GEMINI_KEY_DISABLE', 'GEMINI_KEY_DELETE'} <= set(actions)


def test_a_change_reaches_the_running_chat_without_a_restart(client, tmp_path):
    c, _, _, _ = client
    source = CachedKeys([ENV_KEY], KeyStore(tmp_path, SECRET), ttl=3600)
    key_store.set_key_source(source)
    assert source()[0] == [ENV_KEY]                                          # cached for an hour
    key_pool.set_active(KeyPool([ENV_KEY]))
    response = c.post(BASE, json={'label': 'Một', 'key': K1}).json()
    assert response['restart_needed'] is False and source()[0] == [ENV_KEY, K1]
