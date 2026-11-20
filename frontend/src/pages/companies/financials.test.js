import test from "node:test";
import assert from "node:assert/strict";
import { formatFact, getCompanyFinancials, toPeriodCode, verification } from "./financials.js";

test("money is shown in tỷ đồng only for confirmed VND; ratios as percent", () => {
  const n = (text) => text.replace(/\s/g, " ");
  assert.equal(n(formatFact({ value: 70112825100710, unit: "VND" }, "money")), "70.113 tỷ đồng");
  // Vietcap money tagged SOURCE_NATIVE is dong, continuous with the VND periods: show it the same way.
  assert.equal(n(formatFact({ value: 13754159003395, unit: "SOURCE_NATIVE" }, "money")), "13.754 tỷ đồng");
  assert.equal(formatFact({ value: 0.2829, unit: "SOURCE_NATIVE" }, "percent"), "28,3%");
  assert.equal(formatFact({ value: 0.1156, unit: "RATIO" }, "growth"), "+11,6%");
  assert.equal(formatFact(undefined, "money"), "—");
});

test("old period links map to API period codes", () => {
  assert.equal(toPeriodCode("FY2025"), "2025-YEAR");
  assert.equal(toPeriodCode("Q2/2026"), "2026-Q2");
  assert.equal(toPeriodCode("2026-Q3"), "2026-Q3");
  assert.equal(toPeriodCode("bad"), "");
  assert.equal(verification(null).tone, "neutral");
  assert.equal(verification("MISMATCH").tone, "error");
});

test("unknown company is null, other errors keep their status", async () => {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "fixture-token" }) };
  try {
    globalThis.fetch = async (url) => { assert.equal(url, "/api/companies/ZZZ"); return { ok: false, status: 404 }; };
    assert.equal(await getCompanyFinancials("ZZZ"), null);
    globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    await assert.rejects(getCompanyFinancials("FPT"), (e) => e.status === 503);
  } finally { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage; }
});
