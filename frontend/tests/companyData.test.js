import test from "node:test";
import assert from "node:assert/strict";
import { loadCompanyNews, retryRateLimited, waitForRetry } from "../src/pages/companies/companyData.js";

test("news displays saved then refreshed articles", async () => {
  const result = [];
  await loadCompanyNews({ symbol: "CTR", signal: new AbortController().signal,
    api: { read: async () => ({ articles: ["old"] }), refresh: async () => ({ articles: ["new"] }) },
    onResult: (value) => result.push(value), onError: () => assert.fail(), onSettled: () => {} });
  assert.deepEqual(result.map((value) => value.articles), [["old"], ["new"]]);
});
test("navigation discards late news and does not start a crawl", async () => {
  const controller = new AbortController();
  let complete;
  let refreshed = false;
  const pending = loadCompanyNews({ symbol: "CTR", signal: controller.signal,
    api: { read: () => new Promise((resolve) => { complete = resolve; }), refresh: async () => { refreshed = true; } },
    onResult: () => assert.fail(), onError: () => assert.fail(), onSettled: () => assert.fail() });
  controller.abort();
  complete({ articles: [] });
  await pending;
  assert.equal(refreshed, false);
});
test("rate-limit retries honor delay and stop after four attempts", async () => {
  let attempts = 0;
  const waits = [];
  const action = async () => { attempts += 1; throw Object.assign(new Error("busy"), { status: 429, retryAfter: 7 }); };
  await assert.rejects(retryRateLimited(action, null, async (ms) => waits.push(ms)), /busy/);
  assert.equal(attempts, 4);
  assert.deepEqual(waits, [7000, 7000, 7000]);
  const controller = new AbortController();
  const pending = waitForRetry(60000, controller.signal);
  controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
});

test("already aborted delay returns a rejected promise without throwing synchronously", async () => {
  const controller = new AbortController();
  controller.abort();
  let pending;
  assert.doesNotThrow(() => { pending = waitForRetry(60000, controller.signal); });
  await assert.rejects(pending, { name: "AbortError" });
});

test("late refresh response cannot replace another ticker's news", async () => {
  const controller = new AbortController();
  let finish;
  const results = [];
  const pending = loadCompanyNews({ symbol: "CTR", signal: controller.signal,
    api: { read: async () => ({ symbol: "CTR", articles: [] }),
      refresh: () => new Promise((resolve) => { finish = resolve; }) },
    onResult: (value) => results.push(value), onError: () => assert.fail(), onSettled: () => assert.fail() });
  await new Promise((resolve) => setImmediate(resolve));
  controller.abort();
  finish({ symbol: "CTR", articles: ["late"] });
  await pending;
  assert.equal(results.length, 1);
});
