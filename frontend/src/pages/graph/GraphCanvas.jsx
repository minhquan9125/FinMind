import { useEffect, useId, useRef, useState } from "react";
import NeoVis from "neovis.js";
import { defaultGraphPositions } from "./graphModel.js";

const colors = { Company: "#B7F0BE", Person: "#BFDBFE", Event: "#FED7AA" };
const relationLabels = {
  HAS_SUBSIDIARY: "Công ty con", HAS_ASSOCIATE: "Công ty liên kết", OWNS_SHARES: "Sở hữu cổ phần",
  COOPERATES_WITH: "Hợp tác", HOLDS_ROLE: "Giữ chức vụ", APPOINTS: "Bổ nhiệm",
  DISMISSES: "Miễn nhiệm", INVOLVES: "Có bên tham gia",
};
function compactLabel(node) {
  const short = node.ticker || node.aliases?.find(a => /^[A-Z0-9.-]{2,12}$/.test(a));
  if (short) return short;
  const words = node.label.split(/\s+/), lines = [];
  let line = "";
  for (const word of words) {
    if (line && line.length + word.length > 17) { lines.push(line); line = ""; }
    if (lines.length === 3) break;
    line += (line ? " " : "") + word;
  }
  if (line && lines.length < 3) lines.push(line);
  const label = lines.join("\n");
  return label.replace(/\n/g, " ").length < node.label.length ? label + "…" : label;
}
function tooltip(text) {
  const element = document.createElement("div");
  element.textContent = text;
  element.style.cssText = "max-width:280px;white-space:pre-wrap;overflow-wrap:anywhere;padding:6px";
  return element;
}
function edgeLabel(edge) {
  const time = edge.temporal || {};
  const period = time.as_of || (time.valid_from || time.valid_to ? `${time.valid_from || "…"} → ${time.valid_to || "…"}` : "");
  return `${relationLabels[edge.type] || edge.type}${period ? " · " + period : ""}`;
}
export default function GraphCanvas({ nodes, edges, rootId, fixture = false, onNodeSelect, onEdgeSelect }) {
  const id = "neo4j-graph-" + useId().replace(/:/g, "");
  const containerRef = useRef(null), graphRef = useRef(null);
  const callbacks = useRef({ onNodeSelect, onEdgeSelect });
  callbacks.current = { onNodeSelect, onEdgeSelect };
  const [renderError, setRenderError] = useState("");
  useEffect(() => {
    let disposed = false;
    let settleTimer;
    setRenderError("");
    const positions = defaultGraphPositions(nodes, edges, rootId);
    const grouped = new Map();
    edges.forEach(edge => {
      const key = JSON.stringify([edge.source, edge.target].sort());
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(edge.id);
    });
    // dataFunction disables Neovis's Bolt driver. Public datasets receive only
    // the existing API result; original entity/relation IDs stay unchanged.
    const viz = new NeoVis({
      containerId: id, dataFunction: () => [], groupAsLabel: false,
      visConfig: {
        autoResize: true,
        layout: { improvedLayout: false },
        nodes: { shape: "circle", margin: 10, borderWidth: 1.5,
          widthConstraint: { minimum: 82, maximum: 82 }, heightConstraint: { minimum: 82 },
          font: { size: 12, face: "Arial", color: "#172B22", multi: false, strokeWidth: 0 } },
        edges: { width: 1.4, color: { color: "#929CA4", highlight: "#2563EB", hover: "#2563EB", inherit: false },
          arrows: { to: { enabled: true, scaleFactor: 0.65 } },
          font: { size: 10, face: "Arial", color: "#64748B", align: "middle", strokeWidth: 4, strokeColor: "#F5F7F8" } },
        interaction: { hover: true, tooltipDelay: 180, dragNodes: true, dragView: true, zoomView: true, multiselect: false },
        physics: { enabled: false, solver: "forceAtlas2Based",
          forceAtlas2Based: { gravitationalConstant: -65, centralGravity: 0,
            springLength: 230, springConstant: 0.035, damping: 0.65, avoidOverlap: 1 },
          stabilization: { enabled: false }, minVelocity: 0.5 },
      },
    });
    let destroyed = false;
    function disposeNetwork() {
      const network = viz.network;
      if (!network || destroyed) return;
      network.destroy();
      // Neovis 2.1 schedules stopSimulation 10s after rendering without a
      // destroy API to cancel it. Keep that delayed call safe after unmount.
      network.stopSimulation = () => {};
      destroyed = true;
    }
    graphRef.current = viz;
    viz.registerOnEvent("completed", () => {
      if (disposed) { disposeNetwork(); return; }
      viz.nodes.add(nodes.map(node => {
        const color = colors[node.type] || "#E2E8F0";
        return { id: node.id, label: compactLabel(node), title: tooltip(node.label),
          color: { background: color, border: node.id === rootId ? "#65B976" : color,
            highlight: { background: color, border: "#2563EB" }, hover: { background: color, border: "#65B976" } },
          borderWidth: node.id === rootId ? 2.5 : 1.5,
          ...positions.get(node.id), fixed: false };
      }));
      viz.edges.add(edges.map(edge => {
        const group = grouped.get(JSON.stringify([edge.source, edge.target].sort()));
        const index = group.indexOf(edge.id);
        return { id: edge.id, from: edge.source, to: edge.target, label: edgeLabel(edge),
          title: tooltip(`${edge.type}\n${edge.id}\n${edgeLabel(edge)}`),
          arrows: { to: { enabled: edge.type !== "COOPERATES_WITH", scaleFactor: 0.65 } },
          smooth: group.length > 1 ? { enabled: true, type: index % 2 ? "curvedCCW" : "curvedCW",
            roundness: 0.16 + Math.floor(index / 2) * 0.14 } : false };
      }));
      const network = viz.network;
      network.fit({ animation: false });
      let dragging = false;
      let pinned = [];
      const freeze = () => {
        if (disposed || dragging) return;
        clearTimeout(settleTimer);
        network.setOptions({ physics: { enabled: false } });
      };
      network.on("dragStart", ({ nodes: dragged }) => {
        if (disposed || !dragged.length) return; // Panning leaves the layout alone.
        clearTimeout(settleTimer);
        dragging = true;
        if (pinned.length) viz.nodes.update(pinned.map(id => ({ id, fixed: false })));
        pinned = [];
        network.setOptions({ physics: { enabled: true } });
      });
      network.on("dragEnd", ({ nodes: dragged }) => {
        if (disposed || !dragged.length) return;
        dragging = false;
        // Keep the released node where the user placed it while neighbors settle.
        pinned = dragged;
        const current = network.getPositions(dragged);
        viz.nodes.update(dragged.map(id => ({ id, ...current[id], fixed: true })));
        settleTimer = setTimeout(freeze, 2000);
      });
      network.on("stabilized", freeze);
      containerRef.current?.setAttribute("aria-label", "Đồ thị Company, Person và Event");
    });
    viz.registerOnEvent("clickNode", ({ nodeId }) => { if (!disposed) callbacks.current.onNodeSelect(nodeId); });
    viz.registerOnEvent("clickEdge", ({ edgeId }) => { if (!disposed) callbacks.current.onEdgeSelect(edgeId); });
    viz.registerOnEvent("error", () => { if (!disposed) setRenderError("Không vẽ được đồ thị. Hãy tải lại trang."); });
    viz.render();
    const observer = new ResizeObserver(() => { if (!disposed) viz.network?.redraw(); });
    observer.observe(containerRef.current);
    return () => {
      disposed = true; observer.disconnect();
      clearTimeout(settleTimer);
      disposeNetwork();
      if (graphRef.current === viz) graphRef.current = null;
    };
  }, [id, nodes, edges, rootId]);
  function zoom(factor) {
    const network = graphRef.current?.network;
    if (network) network.moveTo({ scale: Math.max(0.15, Math.min(3, network.getScale() * factor)), animation: false });
  }
  return <div className="relative h-[65vh] min-h-[320px] max-h-[640px] w-full overflow-hidden rounded-xl border border-slate-200 bg-[#F5F7F8]">
    <div id={id} ref={containerRef} className="h-full w-full" aria-label="Đồ thị Company, Person và Event" />
    {renderError && <p role="alert" className="absolute inset-x-4 top-14 rounded bg-red-50 p-3 text-sm text-red-700">{renderError}</p>}
    <div className="absolute bottom-3 right-3 flex gap-1 rounded-lg border border-slate-300 bg-white p-1 shadow-sm">
      <button type="button" aria-label="Phóng to" className="min-h-10 min-w-10 rounded hover:bg-slate-100" onClick={() => zoom(1.2)}>＋</button>
      <button type="button" aria-label="Thu nhỏ" className="min-h-10 min-w-10 rounded hover:bg-slate-100" onClick={() => zoom(1 / 1.2)}>−</button>
      <button type="button" className="min-h-10 rounded px-2 text-xs hover:bg-slate-100" onClick={() => graphRef.current?.network?.fit({ animation: false })}>Căn giữa</button>
    </div>
    <span className="absolute right-3 top-3 rounded border bg-white/95 px-2 py-1 text-[11px] text-slate-600">Neovis.js · {fixture ? "Fixture kiểm thử" : "Kết quả API"}</span>
  </div>;
}
