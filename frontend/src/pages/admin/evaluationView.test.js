import test from 'node:test';
import assert from 'node:assert/strict';
import { levelView, runStatusLabel, passRate, percent, runSummaryText, progress, estimateNote, canStart, categories, filterQuestions, evaluationErrorMessage } from './evaluationView.js';

const summary = { total: 10, levels: { PASS: 6, PARTIAL: 1, FAIL: 1, MANUAL: 2 }, mean_score: 0.8123, mean_latency_ms: 4200 };

test('levels and statuses have readable labels and unknown values pass through', () => {
  assert.equal(levelView('PASS').label, 'Đạt'); assert.equal(levelView('ERROR').tone, 'error');
  assert.equal(levelView('X').label, 'X'); assert.equal(levelView(undefined).tone, 'neutral');
  assert.equal(runStatusLabel('INTERRUPTED'), 'Đã dừng'); assert.equal(runStatusLabel('?'), '?');
});

test('pass rate ignores the questions that need a human', () => {
  assert.equal(passRate(summary), 6 / 8);
  assert.equal(passRate({ total: 2, levels: { MANUAL: 2 } }), null);
  assert.equal(passRate(null), null);
  assert.equal(percent(0.75), '75%'); assert.equal(percent(null), '—');
});

test('run summary and progress are plain and safe on empty runs', () => {
  assert.match(runSummaryText({ summary }), /^Đạt 6\/10 · điểm trung bình 0,81 · 4,2 giây\/câu$/);
  assert.equal(runSummaryText({ summary: { total: 0 } }), 'Chưa có kết quả');
  assert.equal(runSummaryText(null), 'Chưa có kết quả');
  assert.equal(progress({ done: 3, total: 12 }), 25); assert.equal(progress({ done: 0, total: 0 }), 0); assert.equal(progress(null), 0);
});

test('the pre-run note says how many real chat requests will be made', () => {
  assert.match(estimateNote(10), /10 câu hỏi sẽ tạo 10 lượt Chat thật.*khoảng 3 phút/);
  assert.match(estimateNote(1), /khoảng 1 phút/);
});

test('starting is blocked with nothing selected or while a run is active', () => {
  assert.equal(canStart(['Q01'], []), true);
  assert.equal(canStart([], []), false);
  assert.equal(canStart(['Q01'], [{ status: 'RUNNING' }]), false);
  assert.equal(canStart(['Q01'], [{ status: 'COMPLETED' }]), true);
});

test('questions can be filtered by category, verification and text', () => {
  const items = [
    { id: 'Q01', question: 'Doanh thu FPT', category: 'bctc', verified: true },
    { id: 'Q02', question: 'Tin MSN', category: 'tin', verified: false },
    { id: 'Q03', question: 'Lợi nhuận VCB', category: 'bctc', verified: false },
  ];
  assert.deepEqual(categories(items), ['bctc', 'tin']);
  assert.deepEqual(filterQuestions(items, { category: 'bctc' }).map(i => i.id), ['Q01', 'Q03']);
  assert.deepEqual(filterQuestions(items, { verifiedOnly: true }).map(i => i.id), ['Q01']);
  assert.deepEqual(filterQuestions(items, { text: ' vcb ' }).map(i => i.id), ['Q03']);
  assert.deepEqual(filterQuestions(items, { text: 'q02' }).map(i => i.id), ['Q02']);
  assert.deepEqual(filterQuestions(null), []);
});

test('error codes map to readable messages', () => {
  assert.match(evaluationErrorMessage('EVALUATION_ALREADY_RUNNING', 409), /Đang có một lần chạy khác/);
  assert.equal(evaluationErrorMessage('X', 401), 'Phiên đăng nhập hết hạn.');
  assert.equal(evaluationErrorMessage(undefined, 500), 'Thao tác không thành công.');
});
