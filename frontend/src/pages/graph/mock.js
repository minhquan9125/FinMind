// Explicit graph-viewer-v1 UI fixtures. Not live extraction data or a fallback.
export const nodeTypes = [
  { type: "Company", label: "Doanh nghiệp", color: "#B7F0BE" },
  { type: "Person", label: "Nhân sự", color: "#BFDBFE" },
  { type: "Event", label: "Sự kiện", color: "#FED7AA" },
];
export const fixtureVersion = "fixture:annual";
const nodes = [
  { id: "fixture:company", type: "Company", label: "Doanh nghiệp mẫu", detail: "Fixture", attributes: {} },
  { id: "fixture:subsidiary", type: "Company", label: "Công ty con mẫu", detail: "Fixture", attributes: {} },
  { id: "fixture:person", type: "Person", label: "Nhân sự mẫu", detail: null, attributes: {} },
  { id: "fixture:event", type: "Event", label: "Sự kiện mẫu", detail: "Fixture", attributes: { event_type: "appointment" } },
];
const review = { status: "APPROVED", reviewer: "Người duyệt fixture", reviewed_at: "2026-11-02T17:13:40+07:00" };
const edge = (id, source, target, type, as_of) => ({ id, source, target, type, attributes: {},
  temporal: { as_of, valid_from: null, valid_to: null }, review, evidence_count: 1 });
const edges = [
  edge("fixture:subsidiary-2024", nodes[0].id, nodes[1].id, "HAS_SUBSIDIARY", "2024-12-31"),
  edge("fixture:subsidiary-2025", nodes[0].id, nodes[1].id, "HAS_SUBSIDIARY", "2025-12-31"),
  edge("fixture:role", nodes[2].id, nodes[0].id, "HOLDS_ROLE", "2025-12-31"),
  edge("fixture:involves", nodes[3].id, nodes[2].id, "INVOLVES", "2025-12-31"),
];
export const graphFixture = { nodes, edges };
export const rootOptions = nodes.map(n => ({ value: n.id, label: n.label }));
export const emptyGraphFixture = { nodes: [nodes[0]], edges: [] };
export const fixtureEvidence = [
  { document_id: "fixture:report", document_version: "fixture:snapshot", chunk_id: "fixture:pdf",
    title: "BCTN mẫu", doc_type: "ANNUAL_REPORT", quote: "Đoạn nguồn PDF minh họa.\nGiữ nguyên xuống dòng.",
    locator: { kind: "db_text_span", page: 12, char_start: 0, char_end: 42 },
    open: { status: "AVAILABLE", kind: "PDF_PAGE", url: "https://example.com/report.pdf", page: 12, reason: null } },
  { document_id: "fixture:article", document_version: "fixture:web-snapshot", chunk_id: "fixture:news",
    title: "Tin mẫu", doc_type: "NEWS", quote: "Đoạn tin minh họa sự kiện.",
    locator: { kind: "db_text_span", page: 1, json_pointer: "/content", article_id: "fixture:article" },
    open: { status: "AVAILABLE", kind: "WEB_ARTICLE", url: "https://example.com/article", page: null, reason: null } },
];
export function fixtureRelation(id, version = fixtureVersion) {
  const e = edges.find(item => item.id === id);
  if (!e) throw Object.assign(new Error("Không tìm thấy quan hệ fixture."), { status: 404, code: "RELATION_NOT_FOUND" });
  return { meta: { graph_version_id: version, status: "READY" },
    relation: { ...e, source: nodes.find(n => n.id === e.source), target: nodes.find(n => n.id === e.target),
      extraction: { relation_id: id, source_batch_id: "fixture:batch", corpus_id: "fixture:corpus", index_version_id: "fixture:index" } },
    evidence: [structuredClone(fixtureEvidence[id === "fixture:involves" ? 1 : 0])] };
}
export async function fixtureResponse(path, params, mode, signal) {
  if (!["success", "empty", "error", "loading", "truncated", "source-unavailable"].includes(mode)) throw new Error("Fixture không hợp lệ.");
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  if (mode === "loading") return new Promise((resolve, reject) =>
    signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true }));
  if (mode === "error") throw Object.assign(new Error("Lỗi tải graph fixture."), { status: 503, code: "GRAPH_UNAVAILABLE" });
  const version = params.graph_version_id || fixtureVersion;
  if (path === "/versions") return { versions: [fixtureVersion, "fixture:news"].map(graph_version_id =>
    ({ graph_version_id, status: "READY", corpus_id: "fixture:corpus", index_version_id: "fixture:index", relation_count: edges.length })) };
  const meta = { graph_version_id: version, status: "READY", corpus_id: "fixture:corpus", index_version_id: "fixture:index" };
  if (path === "/entities") return { meta, items: mode === "empty" ? [] : nodes.filter(n =>
    (!params.type || n.type === params.type) && (n.label.toLowerCase().includes(params.q.toLowerCase()) || n.id.includes(params.q))),
    truncated: mode === "truncated" };
  if (path === "/neighborhood") {
    const root = nodes.find(n => n.id === params.entity_id);
    if (!root) throw Object.assign(new Error("Không tìm thấy thực thể fixture."), { code: "ENTITY_NOT_FOUND", status: 404 });
    let selected = mode === "empty" ? [] : edges.filter(e =>
      (!params.relation_type?.length || params.relation_type.includes(e.type)) &&
      (!params.from || e.temporal.as_of >= params.from) && (!params.to || e.temporal.as_of <= params.to));
    const depths = new Map([[root.id, 0]]);
    for (let i = 0; i < params.hops; i++) for (const e of selected) {
      const a = depths.get(e.source), b = depths.get(e.target);
      if (a !== undefined && a < params.hops && !depths.has(e.target)) depths.set(e.target, a + 1);
      if (b !== undefined && b < params.hops && !depths.has(e.source)) depths.set(e.source, b + 1);
    }
    selected = selected.filter(e => depths.has(e.source) && depths.has(e.target));
    const truncated = mode === "truncated" || selected.length > params.limit;
    selected = selected.slice(0, params.limit);
    return structuredClone({ meta: { ...meta, root_id: root.id, hops: params.hops, filters: {
      relation_type: params.relation_type || [], from: params.from || null, to: params.to || null },
      limit: params.limit, truncated },
      nodes: nodes.filter(n => n.id === root.id || selected.some(e => e.source === n.id || e.target === n.id)),
      edges: selected });
  }
  const data = fixtureRelation(decodeURIComponent(path.slice("/relations/".length)), version);
  if (mode === "source-unavailable") data.evidence[0].open = { ...data.evidence[0].open, status: "UNAVAILABLE", url: null, reason: "DOCUMENT_NOT_FOUND" };
  return data;
}
