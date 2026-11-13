import test from "node:test";
import assert from "node:assert/strict";
import { getCompanies } from "../src/pages/companies/api.js";
import { getCompanyDetail } from "../src/pages/companies/detailApi.js";
import { AUTH_STORAGE_KEY } from "../src/shared/api/authSession.js";

const company = { id: "FPT", name: "Công ty Cổ phần FPT", sector: "Công nghệ", exchange: "HOSE", industry_type: "CORPORATE", has_financials: true };

function mockApi(t, routes, { signedIn = true } = {}) {
  const values = new Map(signedIn ? [[AUTH_STORAGE_KEY, JSON.stringify({ token: "company-access", expiresAtTimestamp: Date.now() + 60000 })]] : []);
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options = {}) => {
    calls.push({ url, options });
    assert.equal(options.headers.get("Authorization"), "Bearer company-access");
    const route = routes[url];
    assert.ok(route, `Unexpected request: ${url}`);
    if (route instanceof Error) throw route;
    const { status = 200, body } = route;
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  });
  const previous = globalThis.localStorage;
  globalThis.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  t.after(() => { globalThis.localStorage = previous; });
  return { calls, values };
}

test("company catalog uses authenticated API metadata and financial availability", async t => {
  const { calls } = mockApi(t, {
    "/api/companies": { body: [company, { id: "ZZT", name: "Doanh nghiệp chưa có BCTC", sector: null, exchange: null, industry_type: null, has_financials: false }] },
  });
  assert.deepEqual(await getCompanies(), [
    { id: "FPT", name: company.name, sector: "Công nghệ", exchange: "HOSE", status: "Có dữ liệu", tone: "success" },
    { id: "ZZT", name: "Doanh nghiệp chưa có BCTC", sector: "Chưa phân ngành", exchange: null, status: "Chưa có BCTC", tone: "neutral" },
  ]);
  assert.deepEqual(calls.map(call => call.url), ["/api/companies"]);
});

test("company detail maps actual periods, every fact, tỷ VNĐ and actual source pages", async t => {
  const facts = [
    { code: "TOTAL_ASSETS", label: "tổng tài sản", value_vnd: "80000000000000", status: "VERIFIED" },
    { code: "TOTAL_LIABILITIES", label: "tổng nợ phải trả", value_vnd: "42000000000000.125", status: "UNVERIFIED" },
    { code: "TOTAL_EQUITY", label: "tổng vốn chủ sở hữu", value_vnd: "38000000000000", status: "VERIFIED" },
    { code: "NET_REVENUE", label: "doanh thu thuần", value_vnd: "1234567890.125", status: "UNVERIFIED" },
    { code: "PROFIT_AFTER_TAX", label: "lợi nhuận sau thuế", value_vnd: null, status: "UNVERIFIED" },
    { code: "CASH_FLOW_OPERATING", label: "lưu chuyển tiền thuần từ hoạt động kinh doanh", value_vnd: "0", status: "VERIFIED" },
    { code: "TOTAL_OPERATING_INCOME", label: "tổng thu nhập hoạt động", value_vnd: "-1250000000", status: "UNVERIFIED" },
  ];
  const { calls } = mockApi(t, {
    "/api/companies/FPT": { body: company },
    "/api/companies/FPT/financials": { body: { symbol: "FPT", periods: [
      { period: "2026-Q3", facts, source: { title: "BCTC hợp nhất quý 3/2026", url: "https://static2.vietstock.vn/x.pdf", page: 12 } },
      { period: "2025-YEAR", facts: [], source: null },
    ] } },
  });
  const detail = await getCompanyDetail(" fpt ");
  assert.deepEqual(detail, {
    id: "FPT", name: company.name, sector: "Công nghệ", exchange: "HOSE",
    financials: [
      { period: "2026-Q3", label: "2026-Q3", facts: facts.map(fact => ({ id: fact.code, label: fact.label, value: fact.value_vnd === null ? null : Number(fact.value_vnd) / 1e9, status: fact.status })) },
      { period: "2025-YEAR", label: "2025-YEAR", facts: [] },
    ],
    reports: [{ id: "FPT-2026-Q3", title: "BCTC hợp nhất quý 3/2026", period: "2026-Q3", url: "https://static2.vietstock.vn/x.pdf", page: 12 }],
  });
  assert.equal(detail.financials[0].facts[0].value, 80000);
  assert.equal(detail.financials[0].facts[3].value, 1.234567890125);
  assert.equal(detail.financials[0].facts[4].value, null);
  assert.equal(detail.financials[0].facts[5].value, 0);
  assert.equal(detail.financials[0].facts[6].value, -1.25);
  assert.deepEqual(calls.map(call => call.url).sort(), ["/api/companies/FPT", "/api/companies/FPT/financials"]);
});

test("registered company with no BCTC stays empty without invented financials", async t => {
  mockApi(t, { "/api/companies/ZZT": { body: { ...company, id: "ZZT", has_financials: false } }, "/api/companies/ZZT/financials": { body: { symbol: "ZZT", periods: [] } } });
  const detail = await getCompanyDetail("ZZT");
  assert.deepEqual(detail.financials, []);
  assert.deepEqual(detail.reports, []);
});

test("detail accepts only http(s) source links and never promotes missing verification", async t => {
  mockApi(t, {
    "/api/companies/FPT": { body: company },
    "/api/companies/FPT/financials": { body: { periods: [
      { period: "2026-Q3", facts: [{ code: "TOTAL_ASSETS", label: "tổng tài sản", value_vnd: null }], source: { title: "Invalid source", url: "javascript:alert(1)", page: null } },
      { period: "2026-Q2", facts: [], source: { title: "BCTC quý 2", url: "http://example.com/report.pdf", page: 5 } },
    ] } },
  });
  const detail = await getCompanyDetail("FPT");
  assert.equal(detail.financials[0].facts[0].status, "UNVERIFIED");
  assert.equal(detail.financials[0].facts[0].value, null);
  assert.equal(detail.reports[0].url, null);
  assert.equal(detail.reports[1].url, "http://example.com/report.pdf");
  assert.equal(detail.reports[1].page, 5);
});

test("unknown ticker returns null for 404 without a generated company placeholder", async t => {
  const { calls } = mockApi(t, { "/api/companies/ZZZ": { status: 404, body: { detail: "Không tìm thấy doanh nghiệp." } } });
  assert.equal(await getCompanyDetail("ZZZ"), null);
  assert.deepEqual(calls.map(call => call.url), ["/api/companies/ZZZ"]);
});

test("financials 404 returns null instead of stale or fixture data", async t => {
  mockApi(t, { "/api/companies/FPT": { body: company }, "/api/companies/FPT/financials": { status: 404, body: { detail: "Không tìm thấy doanh nghiệp." } } });
  assert.equal(await getCompanyDetail("FPT"), null);
});

test("company API failures preserve Vietnamese messages and status", async t => {
  mockApi(t, {
    "/api/companies": { status: 503, body: { detail: "Chưa kết nối được dữ liệu doanh nghiệp." } },
    "/api/companies/FPT": { body: company },
    "/api/companies/FPT/financials": { status: 403, body: { detail: "Tài khoản không có quyền xem dữ liệu." } },
  });
  await assert.rejects(getCompanies(), error => error.status === 503 && error.message === "Chưa kết nối được dữ liệu doanh nghiệp.");
  await assert.rejects(getCompanyDetail("FPT"), error => error.status === 403 && error.message === "Tài khoản không có quyền xem dữ liệu.");
});

test("network failures surface a Vietnamese API error", async t => {
  mockApi(t, { "/api/companies": new TypeError("Failed to fetch"), "/api/companies/FPT": new TypeError("Failed to fetch") });
  await assert.rejects(getCompanies(), /Không kết nối được API dữ liệu/);
  await assert.rejects(getCompanyDetail("FPT"), /Không kết nối được API dữ liệu/);
});

test("missing sessions propagate existing auth error and never send a request", async t => {
  const { calls } = mockApi(t, {}, { signedIn: false });
  await assert.rejects(getCompanies(), error => error.status === 401 && /đăng nhập lại/.test(error.message));
  await assert.rejects(getCompanyDetail("FPT"), error => error.status === 401 && /đăng nhập lại/.test(error.message));
  assert.equal(calls.length, 0);
});

test("rejected company token propagates session error and clears invalid session", async t => {
  const { values } = mockApi(t, { "/api/companies": { status: 401, body: { detail: "Unauthorized" } } });
  await assert.rejects(getCompanies(), error => error.status === 401 && /đăng nhập lại/.test(error.message));
  assert.equal(values.has(AUTH_STORAGE_KEY), false);
});

test("explicit preview empty and error fixtures do not fetch production data", async t => {
  const { calls } = mockApi(t, {}, { signedIn: false });
  assert.deepEqual(await getCompanies("empty"), []);
  assert.equal(await getCompanyDetail("FPT", "empty"), null);
  await assert.rejects(getCompanies("error"), /Không thể tải danh sách doanh nghiệp/);
  await assert.rejects(getCompanyDetail("FPT", "error"), /Không thể tải chi tiết doanh nghiệp/);
  assert.equal(calls.length, 0);
});
