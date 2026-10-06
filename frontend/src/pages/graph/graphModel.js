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
  for (const id of expandedIds) {
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
