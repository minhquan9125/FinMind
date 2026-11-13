import test from "node:test";
import assert from "node:assert/strict";
import { createDashboardApi } from "../src/pages/dashboard/api.js";

const sessions = {
  items: [
    { session_id: "s1", preview: "phân tích fpt", saved_at: "2026-11-13T09:00:00Z", turns: 2 },
    { session_id: "s2", preview: "giá vcb", saved_at: "2026-11-12T09:00:00Z", turns: 1 },
    { session_id: "s3", preview: "tin mbb", saved_at: "2026-11-11T09:00:00Z", turns: 1 },
    { session_id: "s4", preview: "cũ", saved_at: "2026-11-10T09:00:00Z", turns: 1 },
  ],
};

test("dashboard joins the server watchlist and the 3 newest chat sessions", async () => {
  const api = createDashboardApi({ watchlist: async () => [{ id: "FPT", name: "FPT" }], sessions: async () => sessions });
  const data = await api.getDashboard();
  assert.deepEqual(data.watchlist.map((c) => c.id), ["FPT"]);
  assert.deepEqual(data.recentResearch.map((r) => r.id), ["s1", "s2", "s3"]);
  assert.equal(data.recentResearch[0].title, "phân tích fpt");
});

test("one failing source leaves the other section filled", async () => {
  const api = createDashboardApi({ watchlist: async () => { throw new Error("down"); }, sessions: async () => sessions });
  const data = await api.getDashboard();
  assert.deepEqual(data.watchlist, []);
  assert.equal(data.recentResearch.length, 3);
});
