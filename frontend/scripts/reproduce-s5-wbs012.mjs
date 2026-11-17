// Transport reproduction with real client modules and controlled HTTP responses.
// No real credentials, browser storage, database or application source changes.
import { sendMessage } from '../src/pages/research/chatApi.js';
import { authorizedFetch } from '../src/shared/api/authorization.js';

class Storage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

async function scenario(useSharedFetch) {
  const storage = new Storage();
  storage.setItem('finmind_auth_session', JSON.stringify({
    user: { id: 'synthetic-owner', roles: ['RESEARCHER'] },
    token: 'synthetic-expired-access', refreshToken: 'synthetic-valid-refresh',
    // Metadata can lag server expiry; exercise the reactive HTTP-401 path.
    expiresAtTimestamp: Date.now() + 120_000,
  }));
  globalThis.localStorage = storage;
  const trace = [];
  let acceptedWrites = 0;
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/v1/auth/refresh') {
      trace.push({ endpoint: 'refresh', status: 200 });
      return { ok: true, status: 200, json: async () => ({ data: {
        access_token: 'synthetic-fresh-access', refresh_token: 'synthetic-rotated-refresh', expires_in: 900,
      } }) };
    }
    const headers = new Headers(options.headers);
    const accepted = headers.get('Authorization') === 'Bearer synthetic-fresh-access';
    const status = accepted ? 200 : 401;
    if (accepted) acceptedWrites++;
    trace.push({ endpoint: 'send-message', status });
    return { ok: accepted, status, json: async () => accepted
      ? { session_id: 'synthetic-session', revision: 1, messages: [] }
      : { detail: 'Token không hợp lệ hoặc đã hết hạn.' } };
  };
  let outcome;
  try {
    if (useSharedFetch) {
      const response = await authorizedFetch('/api/research/chat/sessions/synthetic-session/messages', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'Còn VCB thì sao?', revision: 0 }),
      });
      outcome = { status: response.status };
    } else {
      await sendMessage('synthetic-session', 'Còn VCB thì sao?', 0);
      outcome = { status: 200 };
    }
  } catch (error) { outcome = { status: error.status, message: error.message }; }
  return { outcome, trace, refreshCalls: trace.filter(r => r.endpoint === 'refresh').length,
    sendAttempts: trace.filter(r => r.endpoint === 'send-message').length,
    acceptedWritesInMock: acceptedWrites };
}

const saved = { storage: globalThis.localStorage, fetch: globalThis.fetch };
try {
  const chat = await scenario(false);
  const sharedControl = await scenario(true);
  // These assertions verify the reproduction, not a claim that the bug is fixed.
  if (chat.outcome.status !== 401 || chat.refreshCalls !== 0 || chat.sendAttempts !== 1)
    throw new Error('OBSERVED_CHAT_BEHAVIOR_CHANGED_REVIEW_REPRODUCTION');
  if (sharedControl.outcome.status !== 200 || sharedControl.refreshCalls !== 1 || sharedControl.acceptedWritesInMock !== 1)
    throw new Error('CONTROL_REFRESH_PATH_FAILED');
  console.log(JSON.stringify({ case_id: 'S5-WBS01.2-TOKEN-CLIENT', mode: 'CONTROLLED_TRANSPORT_NOT_BROWSER_E2E',
    expected: 'Refresh once on 401 with valid refresh, retry once, accept one message',
    chat, sharedControl, symptomReproduced: true, productSourceChanged: false }, null, 2));
} finally {
  if (saved.storage === undefined) delete globalThis.localStorage;
  else globalThis.localStorage = saved.storage;
  globalThis.fetch = saved.fetch;
}
