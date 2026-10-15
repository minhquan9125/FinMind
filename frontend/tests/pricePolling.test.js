import assert from "node:assert/strict";
import test from "node:test";
import { startPricePolling } from "../src/pages/companies/pricePolling.js";

const flush = () => new Promise((resolve) => setImmediate(resolve));

function setup(overrides = {}) {
  const events = new Map();
  const timers = new Map();
  const calls = { watch: [], read: [], unwatch: [], result: [], errors: [], status: null };
  const document = { hidden: false, addEventListener: (key, fn) => events.set(key, fn),
    removeEventListener: (key) => events.delete(key) };
  const api = {
    watch: async (...args) => { calls.watch.push(args); },
    read: async (...args) => { calls.read.push(args); return { etag: '"one"', data: { symbol: "FPT" } }; },
    unwatch: async (id) => { calls.unwatch.push(id); }, ...overrides,
  };
  const stop = startPricePolling({ symbol: "FPT", viewerId: "viewer-one", document, api,
    timers: { setTimeout: (fn, delay) => { timers.set(fn, delay); return fn; }, clearTimeout: (fn) => timers.delete(fn) },
    onResult: (data) => calls.result.push(data), onError: (error) => { calls.errors.push(error); calls.status = error; },
    onChecked: () => { calls.status = null; }, onSettled: () => {},
  });
  return { calls, events, timers, stop, document };
}

test("visible chart renews one lease, reuses ETag and releases on cleanup", async () => {
  const s = setup();
  await flush();
  assert.equal(s.calls.watch.length, 1);
  assert.equal(s.calls.read.length, 1);
  const [next, delay] = [...s.timers][0];
  assert.equal(delay, 5000);
  s.timers.clear();
  await next();
  assert.equal(s.calls.read[1][2], '"one"');
  s.stop();
  assert.deepEqual(s.calls.unwatch, ["viewer-one"]);
  assert.equal(s.events.size, 0);
  assert.equal(s.timers.size, 0);
});

test("history completes before watching and only runs once per chart", async () => {
  const order = [];
  const s = setup({ prepare: async () => { order.push("history"); },
    watch: async () => { order.push("watch"); } });
  await flush();
  assert.deepEqual(order, ["history", "watch"]);
  const [next] = [...s.timers][0];
  s.timers.clear();
  await next();
  assert.deepEqual(order, ["history", "watch", "watch"]);
  s.stop();
});

test("history failure keeps saved chart and reports missing history", async () => {
  const s = setup({ prepare: async () => { throw new Error("source unavailable"); } });
  await flush();
  assert.ok(s.calls.result.length > 0);
  assert.match(s.calls.status, /Chưa tải đủ lịch sử/);
  s.stop();
});

test("hidden tab releases lease and resumes when visible", async () => {
  const s = setup();
  await flush();
  s.document.hidden = true;
  s.events.get("visibilitychange")();
  assert.equal(s.calls.unwatch.length, 1);
  assert.equal(s.timers.size, 0);
  s.document.hidden = false;
  s.events.get("visibilitychange")();
  await flush();
  assert.equal(s.calls.watch.length, 2);
  s.stop();
});

test("a pending request cannot overlap or update an unmounted chart", async () => {
  let resolve;
  const s = setup({ read: () => new Promise((done) => { resolve = done; }) });
  await flush();
  s.events.get("visibilitychange")();
  assert.equal(s.calls.watch.length, 1);
  s.stop();
  resolve({ etag: "late", data: { symbol: "VCB" } });
  await flush();
  assert.equal(s.calls.result.length, 0);
  assert.equal(s.timers.size, 0);
});

test("saved history remains available when collector is disabled", async () => {
  const s = setup({ watch: async () => { throw new Error("disabled"); } });
  await flush();
  assert.equal(s.calls.result.length, 1);
  assert.match(s.calls.status, /disabled/);
  s.stop();
});

test("lease registration failure is visible, then clears when renewal recovers", async () => {
  let unavailable = true;
  const s = setup({ watch: async () => { if (unavailable) throw new Error("API 404"); } });
  await flush();
  assert.equal(s.calls.result.length, 1);
  assert.match(s.calls.status, /API 404/);
  unavailable = false;
  const [next] = [...s.timers][0];
  s.timers.clear();
  await next();
  assert.equal(s.calls.status, null);
  s.stop();
});
