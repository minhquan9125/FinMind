import test from "node:test";
import { defaultGraphPositions } from "./graphModel.js";
import assert from "node:assert/strict";
import { createGraphApi } from "./api.js";
import { canExpand, getVisibleGraph, validateGraph, validateRelation, evidenceLink } from "./graphModel.js";
import { fixtureVersion, fixtureEvidence, fixtureRelation } from "./mock.js";
const query = { graph_version_id: fixtureVersion, entity_id: "fixture:company", hops: 2, limit: 50, relation_type: [], from: null, to: null };
const fake = mode => createGraphApi({ fixture: mode || "success" });

test("ELCOM initial layout keeps the Datanova–Smartek edge clear of the root and other spokes", () => {
  const peers = ["VFT", "ElcomPrime", "Datanova", "HaNoi", "BacKan", "Smartek", "ELCOMSoftware"];
  const nodes = ["ELCOM", ...peers].map(id => ({ id }));
  const edges = peers.map(target => ({ source: "ELCOM", target }));
  edges.push({ source: "Datanova", target: "Smartek" });
  const p = defaultGraphPositions(nodes, edges, "ELCOM");
  const a = p.get("Datanova"), b = p.get("Smartek");
  const distance = Math.abs(a.x*b.y-a.y*b.x)/Math.hypot(b.x-a.x,b.y-a.y);
  assert.ok(distance > 150, "peer edge must not pass through the central node");
  const cross = (a,b,c) => (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
  for (const id of peers.filter(id => !["Datanova", "Smartek"].includes(id))) {
    const c = p.get("ELCOM"), d = p.get(id);
    assert.equal(cross(a,b,c)*cross(a,b,d) < 0 && cross(c,d,a)*cross(c,d,b) < 0, false, id);
  }
  assert.deepEqual(defaultGraphPositions([...nodes].reverse(), [...edges].reverse(), "ELCOM"), p);
  assert.equal(p.size, nodes.length);
});

test("contract fixtures: Company, Person, Event, parallel temporal edges and bounded expansion", async () => {
  const graph = await fake().graph(query);
  assert.deepEqual(new Set(graph.nodes.map(n => n.type)), new Set(["Company", "Person", "Event"]));
  assert.equal(graph.edges.filter(e => e.type === "HAS_SUBSIDIARY").length, 2);
  let visible = getVisibleGraph(graph, query.entity_id, [query.entity_id]);
  assert.equal(visible.nodes.some(n => n.type === "Event"), false);
  assert.equal(canExpand(graph, visible, "fixture:person"), true);
  visible = getVisibleGraph(graph, query.entity_id, ["fixture:person", query.entity_id]);
  assert.equal(visible.nodes.find(n => n.type === "Event").id, "fixture:event");
  assert.equal(canExpand(graph, visible, "fixture:event"), false);
});

test("API uses GET, bearer token and exact version/filter parameters", async () => {
  const saved = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "test-access" }) };
  try {
    const graph = await fake().graph({...query, relation_type: ["HAS_SUBSIDIARY"], from: "2024-01-01", to: "2025-12-31"});
    const calls = [];
    const api = createGraphApi({ baseUrl: "http://backend", fetchImpl: async (url, options) => {
      calls.push({url, options}); return {ok: true, status: 200, json: async () => graph};
    }});
    const q = {...query, relation_type: ["HAS_SUBSIDIARY"], from: "2024-01-01", to: "2025-12-31"};
    assert.deepEqual(await api.graph(q), graph);
    const {url, options} = calls[0], params = new URL(url).searchParams;
    assert.equal(new URL(url).pathname, "/api/graph/neighborhood");
    assert.equal(params.get("graph_version_id"), fixtureVersion);
    assert.equal(params.get("entity_id"), query.entity_id);
    assert.deepEqual(params.getAll("relation_type"), ["HAS_SUBSIDIARY"]);
    assert.equal(params.get("from"), q.from); assert.equal(params.get("to"), q.to);
    assert.equal(options.headers.Authorization, "Bearer test-access");
    assert.equal(options.method || "GET", "GET");
    assert.equal(options.cache, "no-store");
  } finally { globalThis.localStorage = saved; }
});

test("relation detail preserves extraction, review, time, exact quotes and original locator", async () => {
  const g = await fake().graph(query), e = g.edges[0];
  const detail = await fake().relation(e.id, fixtureVersion, e);
  assert.deepEqual(detail, fixtureRelation(e.id));
  assert.equal(detail.relation.extraction.relation_id, e.id);
  assert.deepEqual(detail.evidence[0], fixtureEvidence[0]);
  let requestUrl;
  const api = createGraphApi({fetchImpl: async url => {
    requestUrl = url; return {ok: true, status: 200, json: async () => detail};
  }});
  assert.deepEqual(await api.relation(e.id, fixtureVersion, e), detail);
  assert.ok(requestUrl.includes("fixture%3Asubsidiary-2024"));
  assert.equal(new URL(requestUrl, "http://local").searchParams.get("graph_version_id"), fixtureVersion);
});

test("mismatched version/root/filter, disconnected data and stale detail are rejected", async () => {
  const graph = await fake().graph(query);
  for (const mutate of [
    g => g.meta.graph_version_id = "wrong", g => g.meta.status = "BUILDING",
    g => g.meta.root_id = "wrong", g => g.meta.hops = 1,
    g => g.meta.filters.from = "2020-01-01", g => g.edges[0].review.status = "REJECTED",
    g => g.edges[0].source = "missing", g => g.nodes.push({id: "outside", type: "Company", label: "Outside"}),
  ]) { const bad = structuredClone(graph); mutate(bad); assert.throws(() => validateGraph(bad, query)); }
  const detail = fixtureRelation(graph.edges[0].id);
  assert.throws(() => validateRelation(detail, "other-version", detail.relation.id, graph.edges[0]));
  const changed = structuredClone(detail); changed.relation.temporal.as_of = "2026-01-01";
  assert.throws(() => validateRelation(changed, fixtureVersion, changed.relation.id, graph.edges[0]));
});

test("PDF opens at supplied page; News preserves URL and original locator, unavailable never gets a link", async () => {
  assert.equal(evidenceLink(fixtureEvidence[0]), "https://example.com/report.pdf#page=12");
  const news = structuredClone(fixtureEvidence[1]);
  const original = structuredClone(news);
  assert.equal(evidenceLink(news), "https://example.com/article");
  assert.deepEqual(news, original);
  news.open.url = "javascript:alert(1)"; assert.equal(evidenceLink(news), null);
  const data = await fake("source-unavailable").relation("fixture:role", fixtureVersion);
  assert.equal(evidenceLink(data.evidence[0]), null);
  assert.ok(data.evidence[0].quote); assert.ok(data.evidence[0].locator);
});

test("all structured API failures propagate without a mock fallback", async () => {
  for (const [status, code] of [[401, ""], [403, ""], [404, "ENTITY_NOT_FOUND"], [404, "RELATION_NOT_FOUND"],
    [404, "GRAPH_VERSION_NOT_FOUND"], [409, "GRAPH_VERSION_NOT_READY"], [503, "GRAPH_UNAVAILABLE"], [504, "GRAPH_TIMEOUT"]]) {
    const api = createGraphApi({fetchImpl: async () => ({ok: false, status, json: async () => ({detail: {code, message: "Backend error"}})})});
    await assert.rejects(api.graph(query), e => e.status === status && e.code === code && e.message === "Backend error");
  }
  await assert.rejects(createGraphApi({fetchImpl: async () => {throw new TypeError("network");}}).versions(), /Không kết nối/);
  await assert.rejects(createGraphApi({fetchImpl: async () => ({ok: true, status: 200, json: async () => {throw new Error("html");}})}).versions(), /không hợp lệ/);
});

test("empty and truncated states, exact entity search and version selection", async () => {
  const empty = await fake("empty").graph(query);
  assert.equal(empty.nodes.length, 1); assert.deepEqual(empty.edges, []);
  assert.equal((await fake("truncated").graph(query)).meta.truncated, true);
  const limited = await fake().graph({...query, limit: 1});
  assert.equal(limited.meta.truncated, true); assert.equal(limited.edges.length, 1);
  const versions = await fake().versions(); assert.equal(versions.versions.length, 2);
  const people = await fake().entities({graph_version_id: "fixture:news", q: "mẫu", type: "Person"});
  assert.equal(people.meta.graph_version_id, "fixture:news");
  assert.equal(people.items.length, 1); assert.equal(people.items[0].type, "Person");
});

test("entity dropdown can load a version without a keyword and filter by type", async () => {
  const companies = await fake().entities({graph_version_id: fixtureVersion, q: "", type: "Company", limit: 50});
  assert.equal(companies.items.length, 2);
  assert.ok(companies.items.every(n => n.type === "Company"));
  assert.equal(companies.meta.graph_version_id, fixtureVersion);
  let request;
  const api = createGraphApi({fetchImpl: async url => { request = new URL(url, "http://local");
    return {ok: true, status: 200, json: async () => companies};
  }});
  await api.entities({graph_version_id: fixtureVersion, q: "", type: "Company", limit: 50});
  assert.equal(request.searchParams.get("graph_version_id"), fixtureVersion);
  assert.equal(request.searchParams.has("q"), false);
});

test("abort and timeout do not return data", async () => {
  const controller = new AbortController();
  const loading = fake("loading").graph(query, {signal: controller.signal});
  controller.abort(); await assert.rejects(loading, {name: "AbortError"});
  const api = createGraphApi({timeoutMs: 5, fetchImpl: async (url, {signal}) => new Promise((resolve, reject) =>
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))))});
  await assert.rejects(api.versions(), e => e.code === "GRAPH_TIMEOUT");
});
