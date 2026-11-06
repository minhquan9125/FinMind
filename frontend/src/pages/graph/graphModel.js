export const MAX_HOPS = 2;

// Hop là số cạnh ngắn nhất từ root, tính cả chiều đi và chiều về để xem quan hệ.
// Hàm này chỉ giới hạn dữ liệu hiển thị; Cytoscape.js tự làm layout.
export function getDepths(graph, rootId) {
  if (!graph.nodes.some((node) => node.id === rootId)) return new Map();
  const depths = new Map([[rootId, 0]]);
  const queue = [rootId];
  for (const id of queue) {
    const depth = depths.get(id);
    if (depth >= MAX_HOPS) continue;
    for (const edge of graph.edges) {
      const other = edge.source === id ? edge.target : edge.target === id ? edge.source : null;
      if (other && !depths.has(other)) {
        depths.set(other, depth + 1);
        queue.push(other);
      }
    }
  }
  return depths;
}

export function getVisibleGraph(graph, rootId, expandedIds = []) {
  const depths = getDepths(graph, rootId);
  const visibleIds = new Set(depths.has(rootId) ? [rootId] : []);
  for (const id of [...expandedIds].sort((a, b) => depths.get(a) - depths.get(b))) {
    const depth = depths.get(id);
    if (depth === undefined || depth >= MAX_HOPS || !visibleIds.has(id)) continue;
    for (const edge of graph.edges) {
      const other = edge.source === id ? edge.target : edge.target === id ? edge.source : null;
      if (other && depths.get(other) === depth + 1) visibleIds.add(other);
    }
  }
  return {
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges: graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)),
    depths,
  };
}

export function canExpand(graph, visibleGraph, nodeId) {
  const depth = visibleGraph.depths.get(nodeId);
  if (depth === undefined || depth >= MAX_HOPS) return false;
  const visibleIds = new Set(visibleGraph.nodes.map((node) => node.id));
  return graph.edges.some((edge) => {
    const other = edge.source === nodeId ? edge.target : edge.target === nodeId ? edge.source : null;
    return other && visibleGraph.depths.get(other) === depth + 1 && !visibleIds.has(other);
  });
}

export const SOURCE_RELATION_TYPES = ["HOLDS_ROLE", "APPOINTS", "DISMISSES", "FORMER_ROLE", "RESIGNS", "REQUESTS_RESIGNATION"];
export const RELATION_TYPES = ["OWNS_SHARES", "HAS_SUBSIDIARY", "HAS_ASSOCIATE", "COOPERATES_WITH", "HOLDS_ROLE", "APPOINTS", "DISMISSES", "INVOLVES", "FORMER_ROLE", "RESIGNS", "REQUESTS_RESIGNATION"];
function reviewed(meta, edge) {
  if (meta.serving_scope === "SOURCE_DOCUMENT_ASSERTIONS") return edge.review?.status === "SOURCE_REVIEWED" &&
    SOURCE_RELATION_TYPES.includes(edge.type) && edge.attributes?.identity_scope === "SOURCE_OCCURRENCE" &&
    edge.attributes?.time_scope === "SOURCE_DOCUMENT_NOT_CURRENT_OFFICE" &&
    edge.attributes?.source_review_status === "APPROVED_IN_SOURCE_REPORT";
  return edge.review?.status === "APPROVED" && !["FORMER_ROLE", "RESIGNS", "REQUESTS_RESIGNATION"].includes(edge.type);
}

// No version IDs are cached or pinned. Refresh only while the page is visible.
export function watchGraphUpdates(refresh, win = window, doc = document) {
  const update = () => { if (doc.visibilityState === "visible") refresh(); };
  const timer = win.setInterval(update, 30000);
  win.addEventListener("focus", update);
  doc.addEventListener("visibilitychange", update);
  return () => {
    win.clearInterval(timer);
    win.removeEventListener("focus", update);
    doc.removeEventListener("visibilitychange", update);
  };
}
const fail = () => { throw new Error("Dữ liệu graph sai contract hoặc không khớp phạm vi/phiên đang xem."); };
const hasText = value => typeof value === "string" && value.trim().length > 0;
const sorted = value => Array.isArray(value) ? [...value].sort() : [];
const canonical = value => JSON.stringify(value, (key, item) => item && typeof item === "object" && !Array.isArray(item)
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
function versionMeta(data, version) {
  if (!data?.meta || data.meta.graph_version_id !== version || data.meta.status !== "READY") fail();
}
export function validateGraph(data, query) {
  versionMeta(data, query.graph_version_id);
  if (data.meta.root_id !== query.entity_id || data.meta.hops !== query.hops || data.meta.limit !== query.limit ||
      !Array.isArray(data.nodes) || !Array.isArray(data.edges) || typeof data.meta.truncated !== "boolean") fail();
  const filters = data.meta.filters;
  if (!filters || canonical(sorted(filters.relation_type)) !== canonical(sorted(query.relation_type)) ||
      (filters.from || null) !== (query.from || null) || (filters.to || null) !== (query.to || null)) fail();
  const ids = new Set(), edgeIds = new Set();
  for (const node of data.nodes) {
    if (!hasText(node.id) || ids.has(node.id) || !["Company", "Person", "Event"].includes(node.type) || !hasText(node.label)) fail();
    ids.add(node.id);
  }
  if (!ids.has(query.entity_id)) fail();
  for (const edge of data.edges) {
    if (!hasText(edge.id) || edgeIds.has(edge.id) || !ids.has(edge.source) || !ids.has(edge.target) ||
        !RELATION_TYPES.includes(edge.type) || !reviewed(data.meta, edge) || !edge.temporal || !edge.attributes) fail();
    if (query.relation_type?.length && !query.relation_type.includes(edge.type)) fail();
    const t = edge.temporal;
    if (!t.valid_from && !t.valid_to) {
      if ((query.from || query.to) && !t.as_of) fail();
      if ((query.from && t.as_of < query.from) || (query.to && t.as_of > query.to)) fail();
    } else if ((query.from && t.valid_to && t.valid_to < query.from) || (query.to && t.valid_from && t.valid_from > query.to)) fail();
    edgeIds.add(edge.id);
  }
  const depths = getDepths(data, query.entity_id);
  if (data.nodes.some(n => !depths.has(n.id) || depths.get(n.id) > query.hops)) fail();
  return data;
}
export function validateRelation(data, version, id, expectedEdge) {
  versionMeta(data, version);
  const r = data.relation;
  if (r?.id !== id || !RELATION_TYPES.includes(r.type) || !reviewed(data.meta, r) ||
      !r.source?.id || !r.target?.id || !r.temporal || !r.attributes || !r.extraction || !Array.isArray(data.evidence)) fail();
  if (r.extraction.relation_id !== id) fail();
  if (expectedEdge && (r.source.id !== expectedEdge.source || r.target.id !== expectedEdge.target || r.type !== expectedEdge.type ||
      canonical(r.temporal) !== canonical(expectedEdge.temporal) || canonical(r.attributes) !== canonical(expectedEdge.attributes) ||
      canonical(r.review) !== canonical(expectedEdge.review))) fail();
  for (const e of data.evidence) {
    if (![e.document_id, e.chunk_id, e.quote].every(hasText) || !e.locator || typeof e.locator !== "object" ||
        Array.isArray(e.locator) || !["AVAILABLE", "UNAVAILABLE"].includes(e.open?.status)) fail();
  }
  return data;
}
export function evidenceLink(evidence) {
  const open = evidence.open;
  if (open?.status !== "AVAILABLE") return null;
  try {
    const url = new URL(open.url);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    // A web source keeps its URL and never acquires a fabricated PDF page.
    if (open.kind === "PDF_PAGE" && evidence.doc_type !== "NEWS") {
      if (Number.isInteger(open.page) && open.page > 0) url.hash = "page=" + open.page;
    } else if (open.kind !== "WEB_ARTICLE") return null;
    return url.href;
  } catch { return null; }
}
// Keep connected peers together, then minimize chord crossings before drawing.
// Physics stays disabled so it cannot undo this initial arrangement.
export function defaultGraphPositions(nodes, edges, rootId) {
  const ids = nodes.map(n => n.id).filter(id => id !== rootId).sort();
  const adjacent = new Map(ids.map(id => [id, new Set()]));
  for (const { source, target } of edges) {
    if (adjacent.has(source) && adjacent.has(target) && source !== target) {
      adjacent.get(source).add(target);
      adjacent.get(target).add(source);
    }
  }
  const order = [], seen = new Set();
  function visit(id) {
    if (seen.has(id)) return;
    seen.add(id); order.push(id);
    [...adjacent.get(id)].sort().forEach(visit);
  }
  ids.forEach(visit);
  const radius = Math.max(250, ids.length * 180 / (2 * Math.PI));
  function positions(sequence) {
    return new Map([[rootId, { x: 0, y: 0 }], ...sequence.map((id, i) => {
      const angle = i * 2 * Math.PI / sequence.length - Math.PI / 2;
      return [id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) }];
    })]);
  }
  const unique = new Map();
  edges.forEach(e => {
    if (e.source !== e.target) unique.set(JSON.stringify([e.source, e.target].sort()), e);
  });
  const links = [...unique.values()];
  const cross = (a, b, c) => (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
  function score(sequence) {
    const p = positions(sequence);
    let total = 0;
    links.forEach((e, i) => {
      const a = p.get(e.source), b = p.get(e.target);
      if (!a || !b) return;
      for (const [id, c] of p) {
        if (id === e.source || id === e.target) continue;
        const length2 = (b.x-a.x)**2 + (b.y-a.y)**2;
        const t = length2 ? Math.max(0, Math.min(1, ((c.x-a.x)*(b.x-a.x)+(c.y-a.y)*(b.y-a.y))/length2)) : 0;
        if (Math.hypot(c.x-a.x-t*(b.x-a.x), c.y-a.y-t*(b.y-a.y)) < 75) total += 10;
      }
      for (const f of links.slice(i+1)) {
        if ([e.source, e.target].some(id => id === f.source || id === f.target)) continue;
        const c = p.get(f.source), d = p.get(f.target);
        if (c && d && cross(a,b,c)*cross(a,b,d) < -0.001 && cross(c,d,a)*cross(c,d,b) < -0.001) total++;
      }
    });
    return total;
  }
  let best = score(order);
  // Bound work for large API results; never block interaction on a hard layout.
  if (order.length <= 24 && links.length <= 60) {
    for (let pass = 0; pass < 4 && best > 0; pass++) {
      let improved = false;
      for (let i = 0; i < order.length; i++) for (let j = i+1; j < order.length; j++) {
        [order[i], order[j]] = [order[j], order[i]];
        const candidate = score(order);
        if (candidate < best) { best = candidate; improved = true; }
        else [order[i], order[j]] = [order[j], order[i]];
      }
      if (!improved) break;
    }
  }
  return positions(order);
}
