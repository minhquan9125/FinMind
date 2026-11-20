import test from "node:test";
import assert from "node:assert/strict";
import { followCompany, getWatchlist, toView, unfollowCompany } from "./api.js";

function withFetch(handler, run) {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "fixture-token" }) };
  globalThis.fetch = handler;
  return run().finally(() => { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage; });
}

test("watchlist calls send the token and use the right method per action", async () => {
  const seen = [];
  await withFetch(async (url, options) => {
    seen.push([url, options.method, options.headers.get("Authorization")]);
    return url === "/api/watchlist"
      ? { ok: true, status: 200, json: async () => ({ items: [], companies: [] }) }
      : { ok: true, status: 204 };
  }, async () => {
    assert.deepEqual(await getWatchlist(), { items: [], companies: [] });
    assert.equal(await followCompany("FPT"), null);
    await unfollowCompany("FPT");
  });
  assert.deepEqual(seen, [
    ["/api/watchlist", "GET", "Bearer fixture-token"],
    ["/api/watchlist/FPT", "PUT", "Bearer fixture-token"],
    ["/api/watchlist/FPT", "DELETE", "Bearer fixture-token"],
  ]);
});

test("API errors keep the status and the backend message", async () => {
  await withFetch(async () => ({ ok: false, status: 404, json: async () => ({ detail: "Không tìm thấy doanh nghiệp." }) }),
    () => assert.rejects(followCompany("ZZZ"), (e) => e.status === 404 && e.message === "Không tìm thấy doanh nghiệp."));
});

test("missing company fields become placeholders", () => {
  assert.deepEqual(toView({ ticker: "ABC", name: null, sector: null, exchange: null }),
    { ticker: "ABC", name: "ABC", sector: "Khác", exchange: "Chưa có dữ liệu" });
});
