import test from "node:test";
import assert from "node:assert/strict";
import { createGraphApi } from "./api.js";

test("published legacy seed graphs are excluded while actual report graphs remain available", async () => {
  const real = { graph_version_id: "s4-bctn-b2550a0b-v4-20261102", status: "READY" };
  const api = createGraphApi({ fetchImpl: async () => ({ ok: true, json: async () => ({ versions: [
    { graph_version_id: "wbs08-smoke-20261030", status: "READY" }, real,
    { graph_version_id: "wbs08-smoke-20261030b", status: "READY" },
  ] }) }) });
  assert.deepEqual((await api.versions()).versions, [real]);
});

test("direct URLs cannot load entities, neighborhoods or relation evidence from a seed graph", async () => {
  const api = createGraphApi({ fetchImpl: async () => { assert.fail("Blocked graph must not be requested"); } });
  for (const graph_version_id of ["wbs08-smoke-20261030", "wbs08-smoke-20261030b"]) {
    const rejects = error => error.code === "TEST_GRAPH_BLOCKED";
    await assert.rejects(api.entities({ graph_version_id }), rejects);
    await assert.rejects(api.graph({ graph_version_id, entity_id: "company:alpha" }), rejects);
    await assert.rejects(api.relation("seed-edge", graph_version_id), rejects);
  }
});
