import test from "node:test";
import assert from "node:assert/strict";
import { addRevealed, getRevealed, visibleCompanies } from "./visibleCompanies.js";

const covered = ["BID", "CMG", "CTG", "ELC", "FPT", "ICT", "ITD", "MBB", "TCB", "VCB"];
const catalog = [
  ...covered.map((id) => ({ id, latestPeriod: "2026-Q3" })),
  { id: "HPG", latestPeriod: null },
  { id: "VIC", latestPeriod: null },
];
const ids = (companies) => companies.map(({ id }) => id);

function mockStorage(t, descriptor) {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, ...descriptor });
  t.after(() => {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else delete globalThis.localStorage;
  });
}

test("catalog shows companies with reports by default", () => {
  assert.deepEqual(ids(visibleCompanies(catalog, [], [])), covered);
});

test("opened and followed tickers add only known companies without duplicates", () => {
  assert.deepEqual(ids(visibleCompanies(catalog, ["HPG"], [])), [...covered, "HPG"]);
  assert.deepEqual(ids(visibleCompanies(catalog, [], ["VIC"])), [...covered, "VIC"]);
  assert.deepEqual(ids(visibleCompanies(catalog, ["CII", "hpg"], ["HPG", "VIC"])), [...covered, "HPG", "VIC"]);
});

test("opened tickers are uppercase, unique, and isolated per account", (t) => {
  const storage = new Map();
  mockStorage(t, { value: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) } });

  addRevealed("alice", "hpg");
  addRevealed("alice", "HPG");
  addRevealed("alice", "vic");
  addRevealed(null, "FPT");
  assert.deepEqual(getRevealed("alice"), ["HPG", "VIC"]);
  assert.deepEqual(getRevealed("bob"), []);
  assert.deepEqual(JSON.parse(storage.get("finmind_revealed_companies:alice")), ["HPG", "VIC"]);
  assert.equal(storage.size, 1);
});

test("invalid or inaccessible storage is treated as empty", (t) => {
  mockStorage(t, { value: {
    getItem: () => "{broken json",
    setItem: () => { throw new Error("quota exceeded"); },
  } });
  assert.deepEqual(getRevealed("alice"), []);
  assert.doesNotThrow(() => addRevealed("alice", "HPG"));

  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("blocked"); } });
  assert.deepEqual(getRevealed("alice"), []);
  assert.doesNotThrow(() => addRevealed("alice", "HPG"));
});
