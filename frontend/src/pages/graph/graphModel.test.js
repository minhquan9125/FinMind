import test from "node:test";
import assert from "node:assert/strict";
import { getGraph } from "./api.js";
import { canExpand, getVisibleGraph, MAX_HOPS } from "./graphModel.js";
import { graphFixture, rootOptions } from "./mock.js";

test("mở rộng từ các root mẫu không hiển thị node quá hai hop", () => {
  for (const root of rootOptions) {
    let visible = getVisibleGraph(graphFixture, root.value);
    assert.deepEqual(visible.nodes.map((node) => node.id), [root.value]);

    const expanded = [root.value];
    visible = getVisibleGraph(graphFixture, root.value, expanded);
    for (const node of visible.nodes.filter((item) => visible.depths.get(item.id) === 1)) expanded.push(node.id);
    visible = getVisibleGraph(graphFixture, root.value, expanded);

    assert.ok(visible.nodes.every((node) => visible.depths.get(node.id) <= MAX_HOPS));
    for (const node of visible.nodes.filter((item) => visible.depths.get(item.id) === MAX_HOPS)) {
      assert.equal(canExpand(graphFixture, visible, node.id), false);
    }
  }
});

test("root FPT không mở Observation ở hop 3 dù yêu cầu mở rộng Report", () => {
  const visible = getVisibleGraph(graphFixture, "company:FPT", [
    "company:FPT", "dataset:FPT:demo", "report:FPT:2025-YEAR",
  ]);
  assert.ok(visible.nodes.some((node) => node.id === "report:FPT:2025-YEAR"));
  assert.ok(!visible.nodes.some((node) => node.id === "observation:FPT:assets"));
});

test("edge mẫu trỏ đúng nguồn và JSON Pointer của báo cáo", () => {
  const edge = graphFixture.edges.find((item) => item.id === "fpt-has-report");
  assert.equal(edge.provenance.datasetId, "FPT:demo");
  assert.equal(edge.provenance.sourceFile, "mock://fpt/financials.json");
  assert.equal(edge.provenance.jsonPointer, "/financial_data/balance_sheet/0");
});

test("API mock trả graph rỗng và lỗi rõ ràng", async () => {
  assert.deepEqual(await getGraph("empty"), { nodes: [], edges: [] });
  await assert.rejects(getGraph("error"), /Không thể tải đồ thị minh họa/);
});
