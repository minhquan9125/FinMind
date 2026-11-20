import test from "node:test";
import assert from "node:assert/strict";
import { getOperations, localTime } from "./operationsApi.js";

test("operations uses authenticated API and preserves pagination filters", async () => {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "fixture-token" }) };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/admin/ingestion/audit?category=review&offset=30");
    assert.equal(options.headers.Authorization, "Bearer fixture-token");
    assert.equal(options.cache, "no-store");
    return { ok: true, json: async () => ({ items: [], total: 0 }) };
  };
  try { assert.deepEqual(await getOperations("/audit?category=review&offset=30"), { items: [], total: 0 }); }
  finally { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage; }
});

test("operations surfaces forbidden and network errors without mock data", async () => {
  const oldFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 403 });
    await assert.rejects(getOperations("/overview"), /không có quyền/);
    globalThis.fetch = async () => { throw new Error("network unavailable"); };
    await assert.rejects(getOperations("/overview"), /network unavailable/);
  } finally { globalThis.fetch = oldFetch; }
});

test("journal times use Vietnam timezone", () => {
  assert.match(localTime("2026-11-05T00:30:00Z"), /07:30:00/);
});

test("configuration PUT uses JSON and reports version conflicts", async () => {
  const oldFetch=globalThis.fetch;
  try {
    globalThis.fetch=async (url, options) => {
      assert.equal(url,"/api/v1/admin/ingestion/budget");
      assert.equal(options.method,"PUT");
      assert.equal(options.headers["Content-Type"],"application/json");
      assert.deepEqual(JSON.parse(options.body),{mode:"free"});
      return {ok:false,status:409};
    };
    await assert.rejects(getOperations("/budget",undefined,{method:"PUT",body:{mode:"free"}}),/người khác sửa/);
  } finally {globalThis.fetch=oldFetch;}
});
