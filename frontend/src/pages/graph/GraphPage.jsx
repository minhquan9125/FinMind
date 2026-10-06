import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "../../app/router.jsx";
import { Button, Drawer, EmptyState, ErrorState, Select, Sidebar, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { researcherMock } from "../dashboard/mock.js";
import { getGraph } from "./api.js";
import GraphCanvas from "./GraphCanvas.jsx";
import { canExpand, getVisibleGraph, MAX_HOPS } from "./graphModel.js";
import { nodeTypes, rootOptions } from "./mock.js";

const menuPaths = {
  dashboard: "/dashboard", companies: "/companies", copilot: "/research",
  watchlist: "/watchlist", graph: "/graph",
};

export default function GraphPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryRoot = `company:${(params.get("company") || "FPT").toUpperCase()}`;
  const [rootId, setRootId] = useState(rootOptions.some((item) => item.value === queryRoot) ? queryRoot : rootOptions[0].value);
  const [graph, setGraph] = useState(null);
  const [expandedIds, setExpandedIds] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(rootId);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";

  useEffect(() => {
    if (fixture === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getGraph(fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setGraph(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fixture, retryCount]);

  const visible = useMemo(() => graph ? getVisibleGraph(graph, rootId, expandedIds) : null, [graph, rootId, expandedIds]);
  const selectedNode = graph?.nodes.find((node) => node.id === selectedNodeId);
  const selectedEdge = graph?.edges.find((edge) => edge.id === selectedEdgeId);
  const edgeSource = graph?.nodes.find((node) => node.id === selectedEdge?.source);
  const edgeTarget = graph?.nodes.find((node) => node.id === selectedEdge?.target);
  const selectedDepth = visible?.depths.get(selectedNodeId);
  const canExpandSelection = graph && visible && canExpand(graph, visible, selectedNodeId);

  function changeRoot(id) {
    setRootId(id);
    setSelectedNodeId(id);
    setSelectedEdgeId(null);
    setExpandedIds([]);
  }

  function expandSelection() {
    if (!canExpandSelection) return;
    setExpandedIds((current) => [...current, selectedNodeId]);
  }

  return (
    <div className="flex min-h-screen bg-[#FAF8FF] text-[#131B2E]">
      <Sidebar groups={userMenu} activeId="graph" onSelect={(id) => navigate(menuPaths[id])} profile={researcherMock}
        onProfile={() => navigate("/profile")} onLogout={() => navigate("/login")} />
      <main className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DAE2FD] bg-white px-4 py-4 sm:px-6">
          <div>
            <h1 className="text-xl font-bold">Đồ thị tri thức</h1>
            <p className="mt-0.5 text-xs text-slate-500">Khám phá doanh nghiệp, dataset, báo cáo, kỳ và chỉ tiêu mẫu.</p>
          </div>
          <div className="flex items-center gap-3"><StatusBadge tone="info">Mock · Tối đa {MAX_HOPS} hop</StatusBadge><Link className="text-xs font-semibold text-blue-700 hover:underline" to="/companies">← Doanh nghiệp</Link></div>
        </header>

        <div className="border-b border-[#DAE2FD] bg-white px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-end gap-3">
            <Select label="Chọn root" options={rootOptions} value={rootId} onChange={(event) => changeRoot(event.target.value)} className="min-w-56" />
            <Button onClick={expandSelection} disabled={!canExpandSelection}>
              {selectedDepth === MAX_HOPS ? "Đã đạt giới hạn 2 hop" : "Mở rộng từ node đang chọn"}
            </Button>
            <Button variant="secondary" onClick={() => changeRoot(rootId)}>Đặt lại góc nhìn</Button>
            <span className="text-xs text-slate-500">Bấm node để chọn; bấm đường nối để xem nguồn mẫu.</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-600">
            {nodeTypes.map((item) => <span key={item.type} className="inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2 py-1"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />{item.label}</span>)}
          </div>
        </div>

        <div className="grid gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_250px]">
          <section aria-label="Đồ thị mẫu" className="min-w-0">
            {loading ? <div className="rounded-xl border border-[#DAE2FD] bg-white p-6"><Skeleton rows={6} /></div> : error ? (
              <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
            ) : !graph?.nodes.length || !visible?.nodes.length ? (
              <EmptyState title="Chưa có đồ thị cho root này" description="Fixture graph hiện không có node để hiển thị." />
            ) : <GraphCanvas nodes={visible.nodes} edges={visible.edges} rootId={rootId}
              onNodeSelect={setSelectedNodeId} onEdgeSelect={setSelectedEdgeId} />}
          </section>

          <aside className="self-start rounded-xl border border-[#DAE2FD] bg-white p-4 shadow-sm">
            <h2 className="text-sm font-bold">Node đang chọn</h2>
            {selectedNode && visible?.nodes.some((node) => node.id === selectedNodeId) ? (
              <div className="mt-3 space-y-2 text-xs text-slate-600">
                <StatusBadge tone="info">{selectedNode.type}</StatusBadge>
                <p className="text-base font-semibold text-slate-900">{selectedNode.label}</p>
                <p>{selectedNode.detail}</p>
                <p>Khoảng cách từ root: <strong>{selectedDepth} hop</strong></p>
                <p>{canExpandSelection ? "Có thể mở rộng node này." : selectedDepth === MAX_HOPS ? "Đã chạm giới hạn 2 hop." : "Không còn node mới trong fixture."}</p>
              </div>
            ) : <p className="mt-3 text-xs text-slate-500">Chọn node trên đồ thị để xem chi tiết.</p>}
            <div className="mt-4 border-t border-slate-200 pt-4">
              <h3 className="text-xs font-bold">Quan hệ đang hiển thị</h3>
              {visible?.edges.length ? <div className="mt-2 space-y-1">
                {visible.edges.map((edge) => <button key={edge.id} type="button" onClick={() => setSelectedEdgeId(edge.id)}
                  className="block w-full rounded-lg border border-slate-200 p-2 text-left text-[11px] text-blue-700 hover:bg-blue-50">
                  {edge.type} · {graph.nodes.find((node) => node.id === edge.source)?.label} → {graph.nodes.find((node) => node.id === edge.target)?.label}
                </button>)}
              </div> : <p className="mt-2 text-xs text-slate-500">Mở rộng node để xem quan hệ và nguồn mẫu.</p>}
            </div>
          </aside>
        </div>
        <footer className="border-t border-[#DAE2FD] bg-white px-6 py-3 text-[11px] text-slate-500">Dữ liệu minh họa · Chưa kết nối Neo4j · Backend sẽ kiểm giới hạn hop khi nối thật.</footer>
      </main>

      <Drawer open={Boolean(selectedEdge)} title="Nguồn của quan hệ mẫu" onClose={() => setSelectedEdgeId(null)}>
        {selectedEdge && (
          <div className="space-y-3 text-xs">
            <StatusBadge tone="warning">{selectedEdge.provenance.kind}</StatusBadge>
            <p className="text-sm font-semibold text-slate-900">{edgeSource?.label} → {edgeTarget?.label}</p>
            <dl className="grid grid-cols-[105px_1fr] gap-x-3 gap-y-2 rounded-lg bg-slate-50 p-3">
              <dt>Quan hệ</dt><dd className="font-semibold">{selectedEdge.type}</dd>
              <dt>Dataset</dt><dd className="break-all">{selectedEdge.provenance.datasetId}</dd>
              <dt>Nguồn</dt><dd>{selectedEdge.provenance.source}</dd>
              <dt>Tệp nguồn</dt><dd className="break-all">{selectedEdge.provenance.sourceFile || "Chưa có trên quan hệ này"}</dd>
              <dt>JSON Pointer</dt><dd className="break-all">{selectedEdge.provenance.jsonPointer || "Chưa có trên quan hệ này"}</dd>
            </dl>
            <p className="text-slate-600">{selectedEdge.provenance.note}</p>
            <p className="text-slate-500">Đường dẫn mock:// chỉ mô tả fixture, không mở tệp hoặc nguồn chính thức.</p>
          </div>
        )}
      </Drawer>
    </div>
  );
}
