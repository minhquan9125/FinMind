import test from "node:test";
import assert from "node:assert/strict";
import { overviewData } from "./overviewData.js";

const fixture = {
  counts: { PENDING: 38, APPROVED: 62, QUARANTINED: 3 }, job_counts: { FAILED: 2 },
  storage: { status: "available", corpus_status: "FROZEN", index_status: "ACTIVE" },
  initialization: { research: "ready", router: "ready" },
};

test("overview preserves original KPI slots without inventing telemetry or budgets", () => {
  const data = overviewData(fixture, { items: [] });
  assert.equal(data.kpis.length, 6);
  assert.ok(data.kpis.every(k => k.value === "—"));
  assert.equal(data.kpis[4].note,"Chưa đọc được thống kê");
  assert.equal(data.budget, null);
  assert.deepEqual(data.recentTraces, []);
  assert.equal(data.services.length, 7);
  assert.equal(data.services.find(s => s.id === "vector").label, "Đã kết nối");
  assert.equal(data.services.find(s => s.id === "graph").label, "Chưa có lượt hỏi nào được ghi nhận hôm nay");
  assert.equal(data.services.find(s => s.id === "verifier").tone, "neutral");
  assert.equal(data.alerts.length, 2);
});

test("real telemetry populates counters and keeps incomplete usage explicit", () => {
  const data=overviewData({...fixture,telemetry:{status:"available",total:3,outcomes:{SUCCESS:1,ERROR:1},
    total_tokens:120,unknown_calls:1,recent:[{id:"request-1",created_at:"2026-11-05T00:00:00Z",companies:["ICT"],
      outcome:"SUCCESS",duration_ms:1200,unknown_calls:1,known_total:120,calls:[{model:"gemini-test"}]}]}});
  assert.equal(data.kpis[0].value,"3");
  assert.equal(data.kpis[1].value,"1");
  assert.match(data.kpis[4].note,/chưa xác định/);
  assert.match(data.recentTraces[0].tokens,/chưa xác định/);
  assert.equal(data.recentTraces[0].model,"gemini-test");
  assert.equal(data.budget,null);
});

test("configured budget populates its KPI and warns on incomplete estimates", () => {
  const api_budget={config:{mode:"paid"},usage:{configured:true,used_usd:"8",limit_usd:"10",period:"month",percent:80,warning:true,exceeded:false,complete:false}};
  const data=overviewData({...fixture,api_budget});
  assert.equal(data.budget,api_budget);
  assert.match(data.kpis[5].note,/Chưa đầy đủ/);
  assert.notEqual(data.kpis[5].value,"—");
  assert.ok(data.alerts.some(a=>a.id==="api-budget"));
});

test("failed storage and journal remain explicit, review rejection is not a failed operation", () => {
  const unavailable = overviewData({ ...fixture, storage: { status: "unavailable" } });
  assert.equal(unavailable.journalAvailable, false);
  assert.ok(unavailable.alerts.some(a => a.id === "storage"));
  const reviewed = overviewData(fixture, { items: [{ id: "review:3", actor: "admin", action: "REJECTED", resource: "article-3", created_at: "2026-11-05T00:00:00Z" }] });
  assert.equal(reviewed.journalAvailable, true);
  assert.match(reviewed.activities[0].text, /Đã từ chối/);
  assert.equal(reviewed.activities[0].ok, undefined);
});

test("service cards use the measured pipeline numbers when telemetry carries them", () => {
  const pipeline = { requests_observed: 4, graph_calls: 2, vector_calls: 3, routes: { BOTH: 2, VECTOR: 2 },
    grounded_answers: 3, drafts_rejected_by_source_check: 1, b3: { b3_evidence_gate: false, b3_answer_verification: false } };
  const data = overviewData({ ...fixture, telemetry: { status: "available", total: 4, outcomes: {}, input_tokens: 0, output_tokens: 0,
    total_tokens: 0, unknown_calls: 0, models: [], recent: [], tracking_started_at: "2026-11-01T00:00:00Z", pipeline } }, { items: [] });
  assert.equal(data.services.find(s => s.id === "graph").label, "2 lần gọi graph hôm nay");
  assert.equal(data.services.find(s => s.id === "gate").label, "Tắt theo cấu hình");
});
