// Real localhost HTTP + actual frontend modules; no browser/private storage access.
import assert from 'node:assert/strict';
import { isDeepStrictEqual } from 'node:util';
import { createSession, sendMessage } from '../src/pages/research/chatApi.js';
import { authorizedFetch } from '../src/shared/api/authorization.js';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const setup = JSON.parse(input);
const target = new URL(setup.base_url);
assert.equal(target.hostname, '127.0.0.1');
assert.equal(target.protocol, 'http:');
const nativeFetch = globalThis.fetch;
const storage = new Map();
globalThis.localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key),
};
let trace = [];
let phase = 'SETUP';
let lastState;
globalThis.fetch = async (url, options) => {
  const resolved = new URL(url, target);
  assert.equal(resolved.origin, target.origin);
  const response = await nativeFetch(resolved, { ...options, redirect: 'error' });
  trace.push({ endpoint: resolved.pathname.endsWith('/refresh') ? 'refresh'
    : resolved.pathname.endsWith('/messages') ? 'send-message' : 'session',
    status: response.status });
  return response;
};

async function scenario(seed, mode) {
  phase = `${mode}:create-session`;
  const makeSession = (token, expiresAtTimestamp) => ({
    user: { id: setup.owner, roles: ['RESEARCHER'] },
    token, refreshToken: seed.refresh_token, expiresAtTimestamp,
  });
  storage.set('finmind_auth_session', JSON.stringify(makeSession(setup.valid_access, Date.now() + 600_000)));
  let snapshot = await createSession();
  const postgres = setup.chat_store === 'postgres';
  phase = `${mode}:seed-conversation`;
  if (postgres) snapshot = await sendMessage(snapshot.session_id, 'Lợi nhuận sau thuế của BID năm 2025 là bao nhiêu?', snapshot.revision);
  const priorUserMessages = snapshot.messages.filter(item => item.role === 'user').length;
  storage.set('finmind_auth_session', JSON.stringify(makeSession(
    setup.expired_access, Date.now() + (mode === 'proactive' ? -60_000 : 600_000),
  )));
  trace = [];
  let status;
  const path = `/api/research/chat/sessions/${snapshot.session_id}/messages`;
  try {
    phase = `${mode}:expired-request`;
    if (mode === 'raw-chat') {
      await sendMessage(snapshot.session_id, 'Còn VCB thì sao?', snapshot.revision);
      status = 200;
    } else {
      status = (await authorizedFetch(path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Còn VCB thì sao?', revision: snapshot.revision }),
      })).status;
    }
  } catch (error) { status = error.status ?? 0; }
  const observed = [...trace];
  phase = `${mode}:read-persisted-session`;
  const response = await nativeFetch(new URL(`/api/research/chat/sessions/${snapshot.session_id}`, target), {
    headers: { Authorization: `Bearer ${setup.valid_access}` }, redirect: 'error',
  });
  assert.equal(response.status, 200);
  const after = await response.json();
  const state = {
    mode, status, trace: observed,
    refresh_calls: observed.filter(item => item.endpoint === 'refresh').length,
    message_attempts: observed.filter(item => item.endpoint === 'send-message').length,
    revision_delta: after.revision - snapshot.revision,
    user_messages: after.messages.filter(item => item.role === 'user').length,
    same_session_id: after.session_id === snapshot.session_id,
    prior_history_unchanged: isDeepStrictEqual(after.messages.slice(0, snapshot.messages.length), snapshot.messages),
  };
  state.user_message_delta = state.user_messages - priorUserMessages;
  lastState = state;
  phase = `${mode}:assert-persisted-state`;
  assert.equal(state.same_session_id, true);
  assert.equal(state.prior_history_unchanged, true);
  const refreshed = JSON.parse(storage.get('finmind_auth_session'));
  state.refresh_token_changed_in_memory = refreshed.refreshToken !== seed.refresh_token;
  if (mode === 'raw-chat' && !setup.expect_recovery) {
    assert.equal(status, 401);
    assert.equal(state.refresh_calls, 0);
    assert.equal(state.revision_delta, 0);
    assert.equal(state.user_message_delta, 0);
  } else {
    assert.equal(status, 200);
    assert.equal(state.refresh_calls, 1);
    assert.equal(state.revision_delta, 1);
    assert.equal(state.user_message_delta, 1);
    assert.equal(state.refresh_token_changed_in_memory, true);
    assert.equal(state.message_attempts, mode === 'proactive' ? 1 : 2);
    const replay = await nativeFetch(new URL('/api/v1/auth/refresh', target), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: seed.refresh_token }), redirect: 'error',
    });
    state.old_refresh_replay_status = replay.status;
    assert.equal(replay.status, 401);
    const check = await nativeFetch(new URL(`/api/research/chat/sessions/${snapshot.session_id}`, target), {
      headers: { Authorization: `Bearer ${refreshed.token}` }, redirect: 'error',
    });
    state.refreshed_access_accepted = check.status === 200;
    assert.equal(check.status, 200);
    if (postgres) {
      phase = `${mode}:assert-followup-scope`;
      const scope = after.messages.at(-1).result.scope;
      state.followup_scope = { companies: scope.companies, periods: scope.periods, metric_code: scope.metric_code };
      assert.deepEqual(state.followup_scope, { companies: ['VCB'], periods: ['2025'], metric_code: 'PROFIT_AFTER_TAX' });
    }
  }
  return state;
}

try {
  const cases = [];
  for (const mode of ['raw-chat', 'reactive', 'proactive']) cases.push(await scenario(setup.seeds[mode], mode));
  process.stdout.write(JSON.stringify({
    scope: setup.chat_store === 'postgres'
      ? 'ACTUAL_CLIENT_MODULES_REAL_LOCAL_HTTP_REAL_AUTH_AND_CHAT_DB_EMPTY_CORPUS_NOT_BROWSER'
      : 'ACTUAL_CLIENT_MODULES_REAL_LOCAL_HTTP_REAL_AUTH_DB_FIXTURE_CHAT_STORE_NOT_BROWSER',
    cases, raw_chat_bug_reproduced: !setup.expect_recovery,
    chat_recovery_accepted: setup.expect_recovery === true, recovery_control_passed: true,
    browser_timer_or_ui_tested: false, credentials_exported: false,
  }));
} catch (error) {
  // Never print request bodies, access tokens, refresh tokens or raw assertions.
  process.stdout.write(JSON.stringify({ status: 'HARNESS_FAILURE', error_type: error.name, phase, last_state: lastState }));
  process.exitCode = 1;
}
