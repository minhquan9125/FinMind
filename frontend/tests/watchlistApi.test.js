import test from "node:test";
import assert from "node:assert/strict";
import { createWatchlistApi } from "../src/pages/watchlist/watchlistApi.js";

function fakeServer(initial = []) {
  const rows = [...initial];
  const calls = [];
  const request = async (url, options = {}) => {
    const method = options.method || "GET";
    calls.push(`${method} ${url}`);
    const symbol = url.split("/").pop();
    if (method === "PUT" && symbol === "ZZZ") return new Response(JSON.stringify({ detail: "Không tìm thấy doanh nghiệp." }), { status: 404 });
    if (method === "PUT" && !rows.includes(symbol)) rows.push(symbol);
    if (method === "DELETE") rows.splice(0, rows.length, ...rows.filter((r) => r !== symbol));
    return new Response(JSON.stringify(rows.map((id) => ({ id, name: id }))), { status: 200 });
  };
  return { request, calls, rows };
}

function memoryStorage(entries = {}) {
  const data = { ...entries };
  return { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; }, removeItem: (k) => { delete data[k]; }, data };
}

test("local tickers move to the server once, then the local key is removed", async () => {
  const server = fakeServer(["VCB"]);
  const storage = memoryStorage({ finmind_watchlist: JSON.stringify(["FPT", "VCB"]) });
  const api = createWatchlistApi({ request: server.request, storage, base: "" });
  const first = await api.loadWatchlist();
  assert.deepEqual(first.map((i) => i.id), ["VCB", "FPT"]);
  assert.equal(storage.data.finmind_watchlist, undefined);
  server.calls.length = 0;
  await api.loadWatchlist();
  assert.deepEqual(server.calls, ["GET /api/watchlist"]);   // no second migration
});

test("removeFromWatchlist calls DELETE and returns the server list", async () => {
  const server = fakeServer(["FPT", "VCB"]);
  const api = createWatchlistApi({ request: server.request, storage: memoryStorage(), base: "" });
  const list = await api.removeFromWatchlist("FPT");
  assert.ok(server.calls.includes("DELETE /api/watchlist/FPT"));
  assert.deepEqual(list.map((i) => i.id), ["VCB"]);
});

test("an unknown ticker surfaces the server message", async () => {
  const api = createWatchlistApi({ request: fakeServer().request, storage: memoryStorage(), base: "" });
  await assert.rejects(api.addToWatchlist("ZZZ"), /Không tìm thấy doanh nghiệp/);
});

test("a server error during the move keeps the local list for the next load", async () => {
  const server = fakeServer(["VCB"]);
  const failing = async (url, options = {}) => (options.method === "PUT"
    ? new Response(JSON.stringify({ detail: "Lỗi máy chủ" }), { status: 500 }) : server.request(url, options));
  const storage = memoryStorage({ finmind_watchlist: JSON.stringify(["FPT"]) });
  const list = await createWatchlistApi({ request: failing, storage, base: "" }).loadWatchlist();
  assert.deepEqual(list.map((i) => i.id), ["VCB"]);                       // the server list still shows
  assert.equal(storage.data.finmind_watchlist, JSON.stringify(["FPT"]));  // nothing lost
});

test("an unknown ticker is dropped and the local key is cleared", async () => {
  const storage = memoryStorage({ finmind_watchlist: JSON.stringify(["ZZZ"]) });
  const list = await createWatchlistApi({ request: fakeServer().request, storage, base: "" }).loadWatchlist();
  assert.deepEqual(list, []);
  assert.equal(storage.data.finmind_watchlist, undefined);
});

test("local data that is not a list never breaks loading", async () => {
  const storage = memoryStorage({ finmind_watchlist: JSON.stringify({ broken: true }) });
  const list = await createWatchlistApi({ request: fakeServer(["FPT"]).request, storage, base: "" }).loadWatchlist();
  assert.deepEqual(list.map((i) => i.id), ["FPT"]);
  assert.equal(storage.data.finmind_watchlist, undefined);
});
