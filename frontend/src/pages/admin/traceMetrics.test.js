import test from 'node:test';
import assert from 'node:assert/strict';
import { routeLabel, routingView, groundingView, b3View } from './traceMetrics.js';

const details = {
  router: { route: 'BOTH', adapters: ['GRAPH', 'CONTENT', 'NEW'], graph_calls: 1, vector_calls: 2 },
  evidence_types: { NEWS: 1, BCTN: 3 },
  grounding: { status: 'DRAFT_READY', reason_code: 'OK', citations: 2, response_mode: 'NATURAL',
    checks: { citation_binding: true, support_quote_check: true, numeric_source_check: false },
    draft_rejected_reason: 'UNSUPPORTED_NUMBER' },
  b3: { b3_evidence_gate: false, b3_answer_verification: false },
};

test('routing view names the route, adapters and sorts evidence types by count', () => {
  const view = routingView(details);
  assert.equal(view.route, 'Đồ thị rồi tìm nội dung');
  assert.deepEqual(view.adapters, ['Graph', 'Nội dung (vector)', 'NEW']);
  assert.equal(view.graphCalls, 1); assert.equal(view.vectorCalls, 2);
  assert.deepEqual(view.evidenceTypes.map(t => t.type), ['BCTN', 'NEWS']);
  assert.equal(routeLabel('SOMETHING'), 'SOMETHING');
  assert.equal(routeLabel(null), 'Không xác định');
});

test('older requests without the new details give null, not made-up values', () => {
  assert.equal(routingView({}), null);
  assert.equal(routingView(undefined), null);
  assert.equal(groundingView({}), null);
  assert.deepEqual(b3View({}), []);
  assert.deepEqual(b3View(undefined), []);
});

test('grounding view lists only checks the backend reported and the rejected draft reason', () => {
  const view = groundingView(details);
  assert.equal(view.status, 'DRAFT_READY'); assert.equal(view.citations, 2);
  assert.deepEqual(view.checks.map(c => [c.key, c.enabled]),
    [['citation_binding', true], ['support_quote_check', true], ['numeric_source_check', false]]);
  assert.equal(view.rejectedReason, 'UNSUPPORTED_NUMBER');
  assert.equal(groundingView({ grounding: { status: 'X' } }).rejectedReason, null);
});

test('B3 components are reported as disabled when the manifest says so', () => {
  const view = b3View(details);
  assert.deepEqual(view.map(v => [v.label, v.enabled]), [['Evidence Gate (B3)', false], ['Answer Verification (B3)', false]]);
});

test('overview service cards show measured pipeline numbers and say when nothing was recorded', async () => {
  const { pipelineServices } = await import('./traceMetrics.js');
  const empty = pipelineServices(null);
  assert.deepEqual(empty.map(s => s.id), ['graph', 'gate', 'verifier']);
  assert.equal(empty[0].label, 'Chưa có lượt hỏi nào được ghi nhận hôm nay');
  assert.equal(empty[1].tone, 'neutral');
  const day = pipelineServices({ requests_observed: 5, graph_calls: 3, vector_calls: 4, routes: { BOTH: 2, VECTOR: 3 },
    grounded_answers: 4, drafts_rejected_by_source_check: 1, b3: { b3_evidence_gate: false, b3_answer_verification: false } });
  assert.equal(day[0].label, '3 lần gọi graph hôm nay'); assert.equal(day[0].tone, 'success');
  assert.match(day[0].desc, /BOTH 2, VECTOR 3/);
  assert.equal(day[1].label, 'Tắt theo cấu hình'); assert.match(day[1].desc, /4 câu trả lời có nguồn, 1 bản nháp Gemini bị bác/);
  assert.match(day[2].desc, /tắt trong cấu hình/);
  assert.equal(pipelineServices({ requests_observed: 1, graph_calls: 0, vector_calls: 1, routes: {}, b3: { b3_evidence_gate: true } })[1].label, 'Đang bật');
  assert.equal(pipelineServices({ requests_observed: 2, graph_calls: 0, vector_calls: 0, routes: {} })[0].tone, 'neutral');
});
