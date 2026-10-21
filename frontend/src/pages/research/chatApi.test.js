// Node built‑in test runner for chatApi client
// This file validates the contract of the frontend API client (chatApi.js)
// No external dependencies are required; fetch and localStorage are stubbed.

import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Resolve module path relative to this test file
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const chatApi = await import('./chatApi.js');

// Helper to reset the environment between tests
function resetEnv() {
  // Clear mocked storage & fetch
  delete globalThis.fetch;
  delete globalThis.localStorage;
}

// Simple in‑memory localStorage mock
class SimpleStorage {
  constructor() { this.store = {}; }
  getItem(key) { return this.store[key] ?? null; }
  setItem(key, value) { this.store[key] = String(value); }
  removeItem(key) { delete this.store[key]; }
}

// ---------- Tests ----------

test('throws error when token is missing on any call', async (t) => {
  resetEnv();
  globalThis.localStorage = new SimpleStorage(); // no token stored
  globalThis.fetch = async () => { assert.fail('fetch should not be called'); };

  await assert.rejects(chatApi.createSession(), /đăng nhập/);
  await assert.rejects(chatApi.listSessions(), /đăng nhập/);
  await assert.rejects(chatApi.getSession('any-id'), /đăng nhập/);
  await assert.rejects(chatApi.sendMessage('any-id', 'text', 0), /đăng nhập/);
  await assert.rejects(chatApi.resumeSession('any-id'), /đăng nhập/);
});

test('creates session with correct POST request and headers', async (t) => {
  resetEnv();
  const token = 'test-token-123';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const mockResponse = { session_id: 'sess-1', revision: 0, messages: [], context: '' };
  let called = false;
  globalThis.fetch = async (url, opts) => {
    called = true;
    assert.equal(url, '/api/research/chat/sessions');
    assert.equal(opts.method, 'POST');
    assert.deepEqual(opts.headers, {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    });
    assert.ok(!opts.body, 'POST body should be empty for session creation');
    return { ok: true, json: async () => mockResponse };
  };

  const data = await chatApi.createSession();
  assert.ok(called, 'fetch was not called');
  assert.deepEqual(data, mockResponse);
});

test('lists sessions with GET and proper auth header', async (t) => {
  resetEnv();
  const token = 'list-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const mockData = { items: [{ session_id: 's1', preview: 'hello', turns: 2, saved_at: '2024-01-01' }] };
  globalThis.fetch = async (url, opts) => {
    assert.equal(url, '/api/research/chat/sessions');
    assert.equal(opts.method, 'GET');
    assert.equal(opts.headers.Authorization, `Bearer ${token}`);
    return { ok: true, json: async () => mockData };
  };

  const result = await chatApi.listSessions();
  assert.deepEqual(result, mockData);
});

test('gets a session with encoded ID', async (t) => {
  resetEnv();
  const token = 'get-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const sessionId = 'sess/with space';
  const encoded = encodeURIComponent(sessionId);
  const mockSession = { session_id: sessionId, messages: [], revision: 1, context: 'ctx' };
  globalThis.fetch = async (url, opts) => {
    assert.equal(url, `/api/research/chat/sessions/${encoded}`);
    assert.equal(opts.method, 'GET');
    return { ok: true, json: async () => mockSession };
  };

  const data = await chatApi.getSession(sessionId);
  assert.deepEqual(data, mockSession);
});

test('sends message with correct payload and revision', async (t) => {
  resetEnv();
  const token = 'msg-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const sessionId = 'abc-123';
  const text = 'What is profit?';
  const revision = 2;
  const mockResult = { messages: [{ role: 'assistant', content: 'Answer' }], revision: 3, context: '' };

  globalThis.fetch = async (url, opts) => {
    assert.equal(url, `/api/research/chat/sessions/${encodeURIComponent(sessionId)}/messages`);
    assert.equal(opts.method, 'POST');
    assert.equal(opts.headers.Authorization, `Bearer ${token}`);
    const body = JSON.parse(opts.body);
    assert.deepEqual(body, { text, revision });
    return { ok: true, json: async () => mockResult };
  };

  const result = await chatApi.sendMessage(sessionId, text, revision);
  assert.deepEqual(result, mockResult);
});

test('resumes a session via POST', async (t) => {
  resetEnv();
  const token = 'resume-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const sessionId = 'parent-xyz';
  const mockResume = { session_id: 'child-123', messages: [], revision: 0, context: '' };
  globalThis.fetch = async (url, opts) => {
    assert.equal(url, `/api/research/chat/sessions/${encodeURIComponent(sessionId)}/resume`);
    assert.equal(opts.method, 'POST');
    assert.equal(opts.headers.Authorization, `Bearer ${token}`);
    return { ok: true, json: async () => mockResume };
  };

  const data = await chatApi.resumeSession(sessionId);
  assert.deepEqual(data, mockResume);
});

test('converts non‑ok HTTP response into an Error with status and message', async (t) => {
  resetEnv();
  const token = 'error-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const errorJson = { detail: 'Invalid revision' };
  globalThis.fetch = async () => ({
    ok: false,
    status: 422,
    json: async () => errorJson,
  });

  await assert.rejects(chatApi.sendMessage('id', 'text', 0), (err) => {
    assert.equal(err.status, 422);
    assert.equal(err.message, 'Invalid revision');
    return true;
  });
});

test('propagates network errors from fetch', async (t) => {
  resetEnv();
  const token = 'net-token';
  const storage = new SimpleStorage();
  storage.setItem('finmind_auth_session', JSON.stringify({ token }));
  globalThis.localStorage = storage;

  const networkErr = new Error('Network down');
  globalThis.fetch = async () => { throw networkErr; };

  await assert.rejects(chatApi.listSessions(), (err) => {
    assert.equal(err.status, 0);
    assert.match(err.message, /Không kết nối/);
    return true;
  });
});

test('reports malformed successful JSON without fake data', async () => {
  globalThis.localStorage = new SimpleStorage();
  localStorage.setItem('finmind_auth_session', JSON.stringify({token:'test'}));
  globalThis.fetch = async () => ({ok:true,json:async()=>{throw new SyntaxError('broken')}});
  await assert.rejects(chatApi.listSessions(), error => error.status===502 && /không hợp lệ/.test(error.message));
});
test('rejects corrupt stored login before fetch', async () => {
  globalThis.localStorage = new SimpleStorage();
  localStorage.setItem('finmind_auth_session','not json');
  globalThis.fetch = async () => assert.fail('must not call unauthenticated');
  await assert.rejects(chatApi.createSession(), error => error.status===401);
});
