import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import { nodeTypes } from "./mock.js";

export default function GraphCanvas({ nodes, edges, rootId, onNodeSelect, onEdgeSelect }) {
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const callbacksRef = useRef({ onNodeSelect, onEdgeSelect });
  callbacksRef.current = { onNodeSelect, onEdgeSelect };

  useEffect(() => {
    const graph = cytoscape({
      container: containerRef.current,
      elements: [],
      minZoom: 0.45,
      maxZoom: 2.5,
      wheelSensitivity: 0.18,
      style: [
        { selector: "node", style: {
          label: "data(label)", "background-color": "#EFF6FF", color: "#0F172A",
          "font-size": 12, "font-weight": 600, "text-wrap": "wrap", "text-max-width": 115,
          "text-valign": "center", "text-halign": "center",
          width: 100, height: 66, shape: "round-rectangle",
          "border-color": "data(color)", "border-width": 2,
        } },
        { selector: "node:selected", style: { "border-width": 4, "background-opacity": 0.25 } },
        { selector: "edge", style: {
          label: "data(label)", width: 2, "line-color": "#94A3B8",
          "target-arrow-color": "#94A3B8", "target-arrow-shape": "triangle",
          "curve-style": "bezier", "font-size": 9, color: "#475569",
          "text-background-color": "#FFFFFF", "text-background-opacity": 0.9,
          "text-background-padding": 3, "text-rotation": "autorotate",
        } },
        { selector: "edge:selected", style: { "line-color": "#2563EB", "target-arrow-color": "#2563EB", width: 4 } },
      ],
    });
    graph.on("tap", "node", (event) => callbacksRef.current.onNodeSelect(event.target.id()));
    graph.on("tap", "edge", (event) => callbacksRef.current.onEdgeSelect(event.target.id()));
    graphRef.current = graph;
    return () => { graph.destroy(); graphRef.current = null; };
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.elements().remove();
    graph.add([
      ...nodes.map((node) => ({ data: {
        id: node.id, label: node.label,
        color: nodeTypes.find((item) => item.type === node.type)?.color || "#475569",
      } })),
      ...edges.map((edge) => ({ data: {
        id: edge.id, source: edge.source, target: edge.target, label: edge.type,
      } })),
    ]);
    graph.layout({
      name: "breadthfirst", roots: graph.getElementById(rootId),
      directed: false, circle: true, padding: 45, spacingFactor: 1.5, animate: false,
    }).run();
    if (graph.zoom() > 1.35) { graph.zoom(1.35); graph.center(); }
  }, [nodes, edges, rootId]);

  return (
    <div className="relative h-[540px] min-h-[380px] w-full overflow-hidden rounded-xl border border-[#DAE2FD] bg-[#FAF8FF]">
      <div ref={containerRef} className="h-full w-full" aria-label="Đồ thị tri thức minh họa" />
      <div className="absolute bottom-4 left-4 flex gap-1 rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
        <button type="button" aria-label="Phóng to" title="Phóng to" className="rounded px-2 py-1 text-sm hover:bg-slate-100" onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.2)}>＋</button>
        <button type="button" aria-label="Thu nhỏ" title="Thu nhỏ" className="rounded px-2 py-1 text-sm hover:bg-slate-100" onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.2)}>−</button>
        <button type="button" className="rounded px-2 py-1 text-xs hover:bg-slate-100" onClick={() => graphRef.current?.fit(undefined, 45)}>Căn giữa</button>
      </div>
      <span className="absolute right-4 top-4 rounded border border-slate-200 bg-white/95 px-2 py-1 text-[11px] text-slate-600">Dữ liệu minh họa</span>
    </div>
  );
}
