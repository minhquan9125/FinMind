import test from "node:test";
import assert from "node:assert/strict";
import { createJobsApi } from "./jobsApi.js";

test("jobs API sends bearer header and paginated detail path", async () => {
  const previous = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "test-token" }) };
  try {
    let request;
    const api = createJobsApi({ fetchImpl: async (url, options) => {
      request = { url, options }; return { ok: true, json: async () => ({ items: [] }) };
    } });
    await api.detail("job-a", 50);
    assert.equal(request.url, "/api/v1/admin/jobs/job-a?offset=50&limit=50");
    assert.equal(request.options.headers.Authorization, "Bearer test-token");
    assert.equal(request.options.cache, "no-store");
  } finally { globalThis.localStorage = previous; }
});

test("forbidden and malformed responses cannot fall back to mock success", async () => {
  const api = createJobsApi({ fetchImpl: async () => ({ ok: false, status: 403 }) });
  await assert.rejects(api.list(), /không có quyền/);
  const broken = createJobsApi({ fetchImpl: async () => ({ ok: true, json: async () => ({}) }) });
  await assert.rejects(broken.list(), /không hợp lệ/);
});
