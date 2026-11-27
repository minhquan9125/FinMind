import test from "node:test";
import assert from "node:assert/strict";
import routes from "../src/app/routes.js";
import { getProfile } from "../src/pages/profile/api.js";
import { PATHS } from "../src/shared/paths.js";

test("public routes and workspace routes require their intended access", () => {
  const publicPaths = [PATHS.home, PATHS.login, PATHS.register, PATHS.forgotPassword, PATHS.resetPassword];
  assert.deepEqual(routes.filter((route) => !route.auth).map((route) => route.path).sort(), publicPaths.sort());
  for (const path of [PATHS.dashboard, PATHS.companies, PATHS.research, PATHS.watchlist, PATHS.graph, PATHS.profile]) {
    const route = routes.find((entry) => entry.path === path);
    assert.equal(route?.auth, true, path);
    assert.deepEqual(route.roles, ["user", "admin"], path);
  }
});

test("every admin route requires the admin role and routes have unique paths", () => {
  const adminRoutes = routes.filter((route) => route.path === "/admin" || route.path.startsWith("/admin/"));
  assert.ok(adminRoutes.length > 1);
  assert.equal(new Set(routes.map((route) => route.path)).size, routes.length);
  for (const route of adminRoutes) {
    assert.equal(route.auth, true, route.path);
    assert.deepEqual(route.roles, ["admin"], route.path);
  }
});

test("research, graph and audit links keep Unicode and reserved query characters", () => {
  const question = "Doanh thu FPT & kế hoạch?";
  const research = new URL(PATHS.researchQuery({ company: "FPT", period: "FY2025", question, autosubmit: true }), "https://example.test");
  assert.equal(research.pathname, PATHS.research);
  assert.deepEqual(Object.fromEntries(research.searchParams), { company: "FPT", period: "FY2025", question, autosubmit: "1" });
  assert.equal(PATHS.researchQuery(), PATHS.research);
  const graph = new URL(PATHS.graphQuery("Mã & tên"), "https://example.test");
  assert.equal(graph.searchParams.get("company"), "Mã & tên");
  const audit = new URL(PATHS.adminAuditQuery({ trace: "trace/a&b", event: "duyệt" }), "https://example.test");
  assert.deepEqual(Object.fromEntries(audit.searchParams), { trace: "trace/a&b", event: "duyệt" });
});

test("profile fixture returns an account summary for the default state", async () => {
  const profile = await getProfile();
  assert.ok(profile.name);
  assert.ok(profile.role);
  assert.equal(profile.avatarUrl, null);
});

test("profile fixture represents a missing profile with null", async () => {
  assert.equal(await getProfile("empty"), null);
});

test("profile fixture rejects when loading the account fails", async () => {
  await assert.rejects(getProfile("error"), /Không thể tải hồ sơ/);
});
