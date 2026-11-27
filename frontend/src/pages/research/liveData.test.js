import test from "node:test";
import assert from "node:assert/strict";
import { getSession } from "./chatApi.js";
import { createGraphApi } from "../graph/api.js";

test("chat refuses fixture sessions and mixed histories from the server", async () => {
  const previous = globalThis.fetch;
  const previousStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "unit-test-token" }), removeItem: () => {} };
  try {
    for (const payload of [
      { session_id: "s", execution_mode: "FIXTURE", messages: [] },
      { session_id: "s", execution_mode: "LIVE", messages: [{ result: { execution_mode: "FIXTURE" } }] },
    ]) {
      globalThis.fetch = async () => ({ ok: true, json: async () => payload });
      await assert.rejects(getSession("s"), error => error.status === 503);
    }
    const live = { session_id: "s", execution_mode: "LIVE", messages: [] };
    globalThis.fetch = async () => ({ ok: true, json: async () => live });
    assert.deepEqual(await getSession("s"), live);
  } finally { globalThis.fetch = previous; globalThis.localStorage = previousStorage; }
});

test("legacy fixture option cannot bypass the graph API", async () => {
  let calls = 0;
  const api = createGraphApi({ fixture: "success", fetchImpl: async url => {
    calls++;
    assert.equal(url, "/api/graph/versions");
    return { ok: true, json: async () => ({ versions: [] }) };
  } });
  assert.deepEqual(await api.versions(), { versions: [] });
  assert.equal(calls, 1);
});
