import test from "node:test";
import assert from "node:assert/strict";
import { AUTH_STORAGE_KEY, readAuthSession, refreshStoredSession } from "./authSession.js";
import { authorizedFetch } from "./authorization.js";

function storage(session) {
  const values = new Map(session ? [[AUTH_STORAGE_KEY, JSON.stringify(session)]] : []);
  return { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v), removeItem: k => values.delete(k) };
}
function session() { return { user: { id: "user-1", roles: ["RESEARCHER"] }, token: "old-access", refreshToken: "old-refresh", expiresAtTimestamp: Date.now() + 60000 }; }
const fresh = { access_token: "new-access", refresh_token: "new-refresh", expires_in: 900 };

test("StrictMode and concurrent refresh callers share one token rotation", async () => {
  const original = session(), store = storage(original); let calls = 0, release;
  const ready = new Promise(resolve => { release = resolve; });
  const refresh = async () => { calls++; await ready; return fresh; };
  const options = { storage: store, refresh, notify() {}, locks: null };
  const first = refreshStoredSession(original, options), second = refreshStoredSession(original, options);
  release();
  const results = await Promise.all([first, second]);
  assert.equal(calls, 1); assert.equal(results[0].token, "new-access");
  assert.equal(readAuthSession(store).refreshToken, "new-refresh");
  await refreshStoredSession(original, options);
  assert.equal(calls, 1, "an old timer must reuse the already rotated session");
});

test("a late refresh cannot undo logout or erase a newer login", async () => {
  const original = session(), store = storage(original); let release;
  const response = new Promise(resolve => { release = resolve; });
  const pending = refreshStoredSession(original, { storage: store, refresh: () => response, notify() {}, locks: null });
  store.removeItem(AUTH_STORAGE_KEY); release(fresh);
  await assert.rejects(pending, error => error.status === 401);
  assert.equal(readAuthSession(store), null);
  store.setItem(AUTH_STORAGE_KEY, JSON.stringify(original));
  let fail;
  const failure = new Promise((resolve, reject) => { fail = reject; });
  const stale = refreshStoredSession(original, { storage: store, refresh: () => failure, notify() {}, locks: null });
  store.setItem(AUTH_STORAGE_KEY, JSON.stringify({ ...original, token: "other-access", refreshToken: "other-refresh" }));
  fail(Object.assign(new Error("expired"), { status: 401 }));
  await assert.rejects(stale);
  assert.equal(readAuthSession(store).token, "other-access");
});

test("profile-only legacy storage cannot send anonymous authenticated requests", async () => {
  const oldStorage = globalThis.localStorage, oldFetch = globalThis.fetch;
  globalThis.localStorage = storage({ user: { id: "user-1" }, expiresAtTimestamp: Date.now() + 60000 });
  let sent = false; globalThis.fetch = async () => { sent = true; };
  try {
    await assert.rejects(authorizedFetch("/api/market-data/news"), error => error.status === 401 && /đăng nhập lại/.test(error.message));
    assert.equal(sent, false);
  } finally { globalThis.localStorage = oldStorage; globalThis.fetch = oldFetch; }
});

test("market requests refresh once on 401 and retain conditional headers", async () => {
  const oldStorage = globalThis.localStorage, oldFetch = globalThis.fetch;
  globalThis.localStorage = storage(session()); let rotations = 0, requests = 0;
  globalThis.fetch = async (url, options) => {
    if (url === "/api/v1/auth/refresh") { rotations++; return { ok: true, status: 200, json: async () => ({ data: fresh }) }; }
    requests++;
    assert.equal(options.headers.get("If-None-Match"), "etag-1");
    return options.headers.get("Authorization") === "Bearer new-access" ? { status: 200, ok: true } : { status: 401, ok: false };
  };
  try {
    const responses = await Promise.all([authorizedFetch("/api/market-data/news", { headers: { "If-None-Match": "etag-1" } }), authorizedFetch("/api/market-data/news", { headers: { "If-None-Match": "etag-1" } })]);
    assert.ok(responses.every(r => r.status === 200)); assert.equal(rotations, 1); assert.equal(requests, 4);
  } finally { globalThis.localStorage = oldStorage; globalThis.fetch = oldFetch; }
});

test("403 does not refresh tokens or sign out the user", async () => {
  const oldStorage = globalThis.localStorage, oldFetch = globalThis.fetch;
  globalThis.localStorage = storage(session()); let requests = 0;
  globalThis.fetch = async () => { requests++; return { status: 403, ok: false }; };
  try {
    assert.equal((await authorizedFetch("/api/market-data/news")).status, 403);
    assert.equal(requests, 1); assert.equal(readAuthSession().token, "old-access");
  } finally { globalThis.localStorage = oldStorage; globalThis.fetch = oldFetch; }
});
