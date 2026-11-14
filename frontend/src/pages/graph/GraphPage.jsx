import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams, useAuth } from "../../app/router.jsx";
import { Button, Drawer, EmptyState, ErrorState, Select, Sidebar, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { createGraphApi } from "./api.js";
import GraphCanvas from "./GraphCanvas.jsx";
import { canExpand, evidenceLink, getVisibleGraph, MAX_HOPS, RELATION_TYPES, SOURCE_RELATION_TYPES, watchGraphUpdates } from "./graphModel.js";
import { nodeTypes } from "./mock.js";

const menuPaths = { dashboard: "/dashboard", companies: "/companies", copilot: "/research", watchlist: "/watchlist", graph: "/graph" };
const fieldClass = "min-h-11 w-full min-w-0 rounded border border-slate-300 bg-white px-3 text-sm";
const unknown = "Chưa có thông tin";
function useRequest(load, key, enabled = true, refresh = 0) {
  const latest = useRef(load); latest.current = load;
  const [state, setState] = useState({ key: null, loading: false, data: null, error: null });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setState(previous => ({ key, loading: !(previous.key === key && previous.data), data: previous.key === key ? previous.data : null, error: null }));
    Promise.resolve().then(() => latest.current(controller.signal)).then(data => {
      if (!controller.signal.aborted) setState({ key, loading: false, data, error: null });
    }).catch(error => {
      if (!controller.signal.aborted) setState({ key, loading: false, data: null, error });
    });
    return () => controller.abort();
  }, [key, enabled, refresh]);
  return enabled && state.key === key ? state : { loading: enabled, data: null, error: null };
}
function Evidence({ item }) {
  const url = evidenceLink(item);
  const pdf = item.open?.kind === "PDF_PAGE" && item.doc_type !== "NEWS";
  return <article className="min-w-0 space-y-3 rounded-lg border border-slate-200 p-3">
    <h3 className="break-words font-semibold">{item.title || item.document_id}</h3>
    <p>{item.doc_type || "Nguồn"}{pdf && item.open.page != null ? ` · Trang ${item.open.page}` : ""}</p>
    <blockquote className="whitespace-pre-wrap break-words border-l-2 border-blue-300 pl-3">{item.quote}</blockquote>
    <dl className="space-y-2 break-all">
      <div><dt className="font-semibold">Document ID</dt><dd>{item.document_id}</dd></div>
      <div><dt className="font-semibold">Document version</dt><dd>{item.document_version || unknown}</dd></div>
      <div><dt className="font-semibold">Chunk ID</dt><dd>{item.chunk_id}</dd></div>
    </dl>
    <details><summary className="min-h-11 cursor-pointer py-3">Locator gốc</summary>
      <pre className="max-w-full whitespace-pre-wrap break-all rounded bg-slate-50 p-2">{JSON.stringify(item.locator, null, 2)}</pre>
    </details>
    {url ? <><a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center text-blue-700 underline">Mở nguồn gốc</a>
      <p className="text-slate-500">Nguồn ngoài có thể yêu cầu quyền truy cập. Đoạn trích và locator được giữ để đối chiếu.</p></> :
      <p role="status" className="text-amber-800">Không mở được nguồn gốc · {item.open?.reason || "URL nguồn không hợp lệ"}. Đoạn trích và locator vẫn được giữ nguyên.</p>}
  </article>;
}

export default function GraphPage() {
  const navigate = useNavigate(), { user, logout } = useAuth();
  const [params, setParams] = useSearchParams();
  const search = params.toString(), fixture = params.get("fixture") || "";
  const version = params.get("graph_version_id") || "", rootId = params.get("entity_id") || "";
  const relationId = params.get("relation_id") || "";
  const api = useMemo(() => createGraphApi({ fixture }), [fixture]);
  const [retry, setRetry] = useState(0), [searchTask, setSearchTask] = useState(null);
  const [searchText, setSearchText] = useState(params.get("company") || "");
  const [entityType, setEntityType] = useState("");
  const [expandedIds, setExpandedIds] = useState([]), [selectedNodeId, setSelectedNodeId] = useState(rootId);
  const [notice, setNotice] = useState(""), [filterError, setFilterError] = useState("");
  const [draft, setDraft] = useState({ type: "", from: "", to: "", hops: "2", limit: "50" });
  const query = {
    graph_version_id: version, entity_id: rootId, hops: Number(params.get("hops") || 2),
    limit: Number(params.get("limit") || 50), relation_type: params.getAll("relation_type"),
    from: params.get("from") || null, to: params.get("to") || null,
  };
  const validQuery = [1, 2].includes(query.hops) && Number.isInteger(query.limit) && query.limit >= 1 && query.limit <= 100 &&
    query.relation_type.every(t => RELATION_TYPES.includes(t)) &&
    [query.from, query.to].every(d => !d || (/^\d{4}-\d{2}-\d{2}$/.test(d) && Number.isFinite(Date.parse(d)) && new Date(d).toISOString().slice(0, 10) === d)) &&
    !(query.from && query.to && query.from > query.to);
  const graphKey = JSON.stringify([fixture, query]);
  const versions = useRequest(signal => api.versions({ signal }), JSON.stringify([fixture]), true, retry);
  useEffect(() => fixture ? undefined : watchGraphUpdates(() => setRetry(n => n + 1)), [fixture]);
  const activeSearch = searchTask?.version === version ? searchTask.q : "";
  const results = useRequest(signal => api.entities({ graph_version_id: version, q: activeSearch, type: entityType || null, limit: 50 }, { signal }),
    JSON.stringify([fixture, version, activeSearch, entityType, searchTask?.nonce]), Boolean(version), retry);
  const graphRequest = useRequest(signal => api.graph(query, { signal }), graphKey, Boolean(version && rootId && validQuery), retry);
  const graph = graphRequest.data;
  const selectedEdge = graph?.edges.find(e => e.id === relationId);
  const detailKey = JSON.stringify([graphKey, relationId]);
  const detail = useRequest(signal => api.relation(relationId, version, selectedEdge, { signal }), detailKey, Boolean(selectedEdge), retry);
  const visible = useMemo(() => graph ? getVisibleGraph(graph, rootId, expandedIds) : null, [graph, rootId, expandedIds]);
  const selectedNode = graph?.nodes.find(n => n.id === selectedNodeId);
  const canExpandSelection = graph && visible && canExpand(graph, visible, selectedNodeId);
  function change(values, clearSelection = true) {
    setParams(previous => {
      const next = new URLSearchParams(previous);
      if (clearSelection) next.delete("relation_id");
      for (const [key, value] of Object.entries(values)) {
        next.delete(key);
        for (const v of Array.isArray(value) ? value : [value]) if (v !== null && v !== undefined && v !== "") next.append(key, String(v));
      }
      return next;
    });
    setNotice("");
  }
  useEffect(() => {
    if (!version && !relationId && versions.data?.versions.length) {
      setParams(previous => {
        if (previous.get("graph_version_id")) return previous;
        const next = new URLSearchParams(previous);
        next.set("graph_version_id", versions.data.versions[0].graph_version_id);
        if (fixture && !next.get("entity_id")) next.set("entity_id", "fixture:company");
        return next;
      }, { replace: true });
    }
  }, [versions.data, version, relationId, fixture, setParams]);
  useEffect(() => {
    const p = new URLSearchParams(search);
    setDraft({ type: p.get("relation_type") || "", from: p.get("from") || "", to: p.get("to") || "", hops: p.get("hops") || "2", limit: p.get("limit") || "50" });
    setFilterError("");
  }, [search]);
  useEffect(() => { setExpandedIds([rootId]); setSelectedNodeId(rootId); setNotice(""); }, [graphKey, rootId]);
  useEffect(() => { setSearchText(""); setSearchTask(null); }, [version]);
  useEffect(() => {
    if (graph && relationId && graph.edges.some(e => e.id === relationId)) setExpandedIds(graph.nodes.map(n => n.id));
  }, [graph, relationId]);
  const authError = [versions.error, results.error, graphRequest.error, detail.error].find(e => e?.status === 401 || e?.status === 403);
  useEffect(() => {
    if (authError) void logout().then(() => navigate("/login", { state: { from: { pathname: "/graph", search: "?" + search } } }));
  }, [authError, logout, navigate, search]);
  useEffect(() => {
    if (detail.error?.code === "RELATION_NOT_FOUND") {
      setNotice(detail.error.message);
      setParams(previous => { const next = new URLSearchParams(previous); next.delete("relation_id"); return next; }, { replace: true });
    }
  }, [detail.error, setParams]);
  function findEntity(event) {
    event.preventDefault();
    setSearchTask({ version, q: searchText.trim(), nonce: Date.now() });
  }
  function applyFilters(event) {
    event.preventDefault();
    if (draft.from && draft.to && draft.from > draft.to) { setFilterError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc."); return; }
    change({ relation_type: draft.type ? [draft.type] : [], from: draft.from, to: draft.to, hops: draft.hops, limit: draft.limit });
  }
  const versionOptions = versions.data?.versions.map(v => ({ value: v.graph_version_id, label: `${v.serving_scope === "SOURCE_DOCUMENT_ASSERTIONS" ? "Nhân sự theo nguồn · " : ""}${v.graph_version_id} · ${v.relation_count} quan hệ` })) || [];
  if (!versionOptions.some(v => v.value === version)) versionOptions.unshift({ value: version, label: version || "Chọn phiên graph" });
  const relation = detail.data?.relation;
  const sourceVersion = versions.data?.versions.find(v => v.graph_version_id === version)?.serving_scope === "SOURCE_DOCUMENT_ASSERTIONS";
  const availableTypes = sourceVersion ? SOURCE_RELATION_TYPES : RELATION_TYPES.filter(t => !["FORMER_ROLE", "RESIGNS", "REQUESTS_RESIGNATION"].includes(t));
  const entityOptions = [{ value: "", label: "Chọn thực thể để xem đồ thị" }, ...(results.data?.items || []).map(n => ({
    value: n.id, label: `${n.label} · ${n.type}${n.relation_count != null ? ` · ${n.relation_count} quan hệ` : ""}`,
  }))];
  if (rootId && !entityOptions.some(o => o.value === rootId)) entityOptions.push({ value: rootId, label: graph?.nodes.find(n => n.id === rootId)?.label || rootId });
  const displayName = user?.name?.trim() || "Người dùng";
  return <div className="flex min-h-screen bg-[#FAF8FF] text-[#131B2E]">
    <Sidebar groups={userMenu} activeId="graph" onSelect={id => navigate(menuPaths[id])}
      profile={{ name: displayName, initials: displayName.slice(0, 2).toUpperCase(), role: user?.role === "admin" ? "Quản trị viên" : "Nhà nghiên cứu" }}
      onProfile={() => navigate("/profile")} onLogout={() => { void logout().then(() => navigate("/login")); }} />
    <main className="min-w-0 flex-1">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white p-4 sm:px-6">
        <div><h1 className="text-xl font-bold">Đồ thị tri thức</h1><p className="text-xs text-slate-600">Doanh nghiệp, nhân sự, sự kiện và bằng chứng của quan hệ.</p></div>
        <div className="flex flex-wrap items-center gap-3"><StatusBadge tone={fixture ? "warning" : "info"}>{fixture ? "Fixture · Không phải dữ liệu thật" : "API graph · Tối đa 2 hop"}</StatusBadge><Link to="/research" className="text-sm text-blue-700 underline">Chat</Link></div>
      </header>
      <div className="space-y-4 border-b bg-white p-4 sm:px-6">
        {!fixture && <div className="flex items-center gap-3 text-xs text-slate-600"><p>Tự cập nhật mỗi 30 giây và khi quay lại trang; giữ nguyên phiên đang xem. Phiên mới xuất hiện trong danh sách.</p><Button variant="secondary" onClick={() => setRetry(n => n + 1)}>Cập nhật ngay</Button></div>}
        {sourceVersion && <p role="status" className="text-sm text-amber-800">Nhân sự theo nguồn tài liệu: danh tính theo từng lần xuất hiện, không khẳng định chức vụ đương nhiệm. Chưa xác nhận ngày hiệu lực; lọc theo ngày sẽ không trả các quan hệ này.</p>}
        {versions.loading ? <p role="status" className="text-sm">Đang tải phiên graph…</p> : versions.error ? <ErrorState message={versions.error.message} onRetry={() => setRetry(n => n + 1)} /> : !versions.data?.versions.length && !version ?
          <EmptyState title="Chưa có phiên graph được công bố" description="Backend chưa có phiên READY để xem." /> : null}
        <Select label="Phiên graph" options={versionOptions} value={version} disabled={versions.loading}
          className="min-w-0 [&_select]:max-w-full" onChange={e => change({ graph_version_id: e.target.value, entity_id: null, relation_type: [] })} />
        {relationId && !version && <p role="alert" className="text-sm text-amber-800">Liên kết thiếu phiên graph. Hãy chọn đúng phiên trước khi mở quan hệ.</p>}
        <form onSubmit={findEntity} className="grid min-w-0 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_160px_auto]">
          <label className="min-w-0 text-xs font-semibold">Lọc theo mã, ID hoặc tên (để trống: tất cả)<input aria-label="Tìm thực thể" className={fieldClass + " mt-1"} value={searchText} maxLength={100} onChange={e => setSearchText(e.target.value)} /></label>
          <Select label="Loại thực thể" value={entityType} onChange={e => setEntityType(e.target.value)} options={[{ value: "", label: "Tất cả" }, ...nodeTypes.map(t => ({ value: t.type, label: t.label }))]} />
          <Button type="submit" disabled={!version || results.loading}>Tìm thực thể</Button>
        </form>
        {results.loading ? <p role="status">Đang tìm thực thể…</p> : results.error ? <ErrorState message={results.error.message} onRetry={() => setRetry(n => n + 1)} /> : results.data ? <div>
          {!results.data.items.length ? <p role="status" className="text-sm text-slate-600">Không tìm thấy thực thể. Hãy đổi từ khóa hoặc loại.</p> :
            <Select label="Thực thể trong phiên đang chọn" options={entityOptions} value={rootId}
              className="min-w-0 [&_select]:max-w-full" onChange={e => change({ entity_id: e.target.value })} />}
          {results.data.truncated && <p role="status" className="mt-2 text-sm text-amber-800">Có nhiều kết quả. Hãy nhập tên cụ thể hơn.</p>}
        </div> : null}
        <form onSubmit={applyFilters} className="grid min-w-0 items-end gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Select label="Loại quan hệ" options={[{ value: "", label: "Tất cả" }, ...availableTypes.map(value => ({ value, label: value }))]} value={draft.type} onChange={e => setDraft(d => ({ ...d, type: e.target.value }))} />
          <label className="min-w-0 text-xs font-semibold">Từ ngày<input type="date" className={fieldClass + " mt-1"} value={draft.from} onChange={e => setDraft(d => ({ ...d, from: e.target.value }))} /></label>
          <label className="min-w-0 text-xs font-semibold">Đến ngày<input type="date" className={fieldClass + " mt-1"} value={draft.to} onChange={e => setDraft(d => ({ ...d, to: e.target.value }))} /></label>
          <Select label="Số hop" options={[{ value: "1", label: "1" }, { value: "2", label: "2" }]} value={draft.hops} onChange={e => setDraft(d => ({ ...d, hops: e.target.value }))} />
          <label className="min-w-0 text-xs font-semibold">Giới hạn đường kết quả<input type="number" min="1" max="100" required className={fieldClass + " mt-1"} value={draft.limit} onChange={e => setDraft(d => ({ ...d, limit: e.target.value }))} /></label>
          <Button type="submit" disabled={!rootId}>Áp dụng bộ lọc</Button>
          {filterError && <p role="alert" className="text-sm text-red-700">{filterError}</p>}
        </form>
      </div>
      {notice && <p role="alert" className="p-4 text-sm text-amber-800">{notice}</p>}
      <div className="grid gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <section className="min-w-0" aria-label="Graph Viewer">
          {!validQuery ? <ErrorState message="Bộ lọc trong URL không hợp lệ. Hop phải là 1–2, giới hạn 1–100 và khoảng ngày hợp lệ." /> :
            graphRequest.loading ? <Skeleton rows={6} /> : graphRequest.error?.code === "ENTITY_NOT_FOUND" ? <EmptyState title="Thực thể không có trong phiên graph" description="Tìm lại thực thể trong phiên đang chọn." /> :
            graphRequest.error ? <ErrorState message={graphRequest.error.message + (graphRequest.error.status === 504 ? " Hãy giảm hop hoặc thu hẹp bộ lọc." : "")} onRetry={() => setRetry(n => n + 1)} /> :
            !graph ? <EmptyState title="Chọn thực thể để xem graph" description="Tìm và chọn Company, Person hoặc Event trong phiên graph." /> :
            <div className="space-y-3">
              <div className="space-y-1 break-all text-xs text-slate-600"><p>Graph: {graph.meta.graph_version_id} · {graph.meta.status}</p><p>Corpus: {graph.meta.corpus_id} · Index: {graph.meta.index_version_id}</p><p>Root: {graph.meta.root_id} · Hop: {graph.meta.hops} · {graph.nodes.length} node / {graph.edges.length} cạnh</p></div>
              {graph.meta.truncated && <p role="status" className="text-sm text-amber-800">Đang hiển thị một phần, hãy lọc theo loại quan hệ/thời gian.</p>}
              {relationId && !selectedEdge && <p role="alert" className="text-sm text-amber-800">Quan hệ được truyền không có trong phạm vi kết quả này. Không mở quan hệ hoặc phiên khác thay thế.</p>}
              {!graph.edges.length && <EmptyState title="Không có quan hệ khớp bộ lọc" description="Root vẫn có trong phiên. Hãy đổi bộ lọc để tìm quan hệ khác." />}
              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={() => setExpandedIds(ids => [...ids, selectedNodeId])} disabled={!canExpandSelection}>Mở rộng node đang chọn</Button>
                <Button variant="secondary" onClick={() => { setExpandedIds([rootId]); setSelectedNodeId(rootId); change({ relation_id: null }, false); }}>Đặt lại góc nhìn</Button>
                {nodeTypes.map(t => <span key={t.type} className="flex items-center gap-1 text-xs"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: t.color }} />{t.label}</span>)}
              </div>
              <GraphCanvas nodes={visible.nodes} edges={visible.edges} rootId={rootId} fixture={Boolean(fixture)}
                onNodeSelect={setSelectedNodeId} onEdgeSelect={id => change({ relation_id: id }, false)} />
            </div>}
        </section>
        <aside className="min-w-0 self-start rounded-xl border bg-white p-4">
          <h2 className="font-semibold">Thực thể đang chọn</h2>
          {selectedNode ? <div className="mt-2 space-y-2 break-all text-xs"><StatusBadge tone="info">{selectedNode.type}</StatusBadge><p className="text-sm font-semibold">{selectedNode.label}</p><p>{selectedNode.detail}</p><p>ID: {selectedNode.id}</p><p>{visible?.depths.get(selectedNode.id)} hop từ root</p></div> :
            <p className="mt-2 text-sm text-slate-600">Bấm node để xem định danh.</p>}
          <h2 className="mt-4 border-t pt-4 font-semibold">Quan hệ trong phạm vi</h2>
          <div className="mt-2 max-h-[60vh] space-y-2 overflow-y-auto">{graph?.edges.map(e => <button key={e.id} type="button" onClick={() => change({ relation_id: e.id }, false)}
            className="min-h-11 w-full break-words rounded border p-2 text-left text-xs text-blue-800 hover:bg-blue-50">
            <span className="block font-semibold">{e.type}</span>{graph.nodes.find(n => n.id === e.source)?.label} → {graph.nodes.find(n => n.id === e.target)?.label}
            <span className="block">{e.temporal.as_of || e.temporal.valid_from || "Chưa có mốc thời gian"}</span><span className="block break-all text-slate-500">{e.id}</span>
          </button>)}</div>
        </aside>
      </div>
    </main>
    <Drawer open={Boolean(selectedEdge)} title="Bằng chứng của quan hệ" onClose={() => change({ relation_id: null }, false)}>
      {detail.loading ? <Skeleton rows={5} /> : detail.error ? <ErrorState message={detail.error.message} onRetry={() => setRetry(n => n + 1)} /> : relation ? <div className="min-w-0 space-y-4 text-xs">
        <p className="break-words text-sm font-semibold">{relation.source.label} → {relation.target.label}</p>
        <dl className="space-y-2 break-all">{Object.entries({
          "Loại quan hệ": relation.type, "Relation ID": relation.id, "Graph version": detail.data.meta.graph_version_id,
          "Trạng thái": relation.review.status, "Người duyệt": relation.review.reviewer || unknown, "Lúc duyệt": relation.review.reviewed_at || unknown,
          "As of": relation.temporal.as_of || unknown, "Valid from": relation.temporal.valid_from || unknown, "Valid to": relation.temporal.valid_to || unknown,
        }).map(([label, value]) => <div key={label}><dt className="font-semibold">{label}</dt><dd>{value}</dd></div>)}</dl>
        <details><summary className="min-h-11 cursor-pointer py-3">Extraction</summary><pre className="whitespace-pre-wrap break-all">{JSON.stringify(relation.extraction, null, 2)}</pre></details>
        <details><summary className="min-h-11 cursor-pointer py-3">Thuộc tính</summary><pre className="whitespace-pre-wrap break-all">{JSON.stringify(relation.attributes, null, 2)}</pre></details>
        {detail.data.evidence.length ? detail.data.evidence.map((item, i) => <Evidence key={i} item={item} />) : <p>Backend chưa trả bằng chứng cho quan hệ.</p>}
      </div> : null}
    </Drawer>
  </div>;
}
