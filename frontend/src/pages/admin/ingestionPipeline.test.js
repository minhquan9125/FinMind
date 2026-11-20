import test from 'node:test';
import assert from 'node:assert/strict';
import { withPipelineFlag, pipelineSummary, canActivate, pipelineResult } from './ingestionPipeline.js';

test('turning off DB indexing also turns off automatic corpus switching', () => {
  const on = { auto_index: true, auto_activate: true };
  assert.deepEqual(withPipelineFlag(on, 'auto_index', false), { auto_index: false, auto_activate: false });
  assert.equal(withPipelineFlag(on, 'auto_activate', false).auto_index, true);
});

test('turning on automatic corpus switching also turns on DB indexing', () => {
  const next = withPipelineFlag({ auto_index: false, auto_activate: false }, 'auto_activate', true);
  assert.deepEqual(next, { auto_index: true, auto_activate: true });
});

test('flag updates never mutate the source object', () => {
  const source = { auto_index: true, auto_activate: true };
  withPipelineFlag(source, 'auto_index', false);
  assert.deepEqual(source, { auto_index: true, auto_activate: true });
});

test('summary lists only the enabled steps in order', () => {
  assert.equal(pipelineSummary({}), 'Thu thập');
  assert.equal(pipelineSummary({ auto_approve: true, auto_index: true }),
    'Thu thập → duyệt tự động → tạo chunk/vector và lưu vào database');
  assert.match(pipelineSummary({ auto_approve: true, auto_index: true, auto_activate: true }), /chuyển corpus cho Chat$/);
});

test('only a stored but not yet activated index job offers the switch button', () => {
  const job = { kind: 'INDEX', status: 'INDEXED', details: { manifest_sha256: 'abc' } };
  assert.equal(canActivate(job), true);
  assert.equal(canActivate({ ...job, status: 'ACTIVE' }), false);
  assert.equal(canActivate({ ...job, kind: 'CRAWL' }), false);
  assert.equal(canActivate({ ...job, details: {} }), false);
  assert.equal(canActivate({ ...job, details: { manifest_sha256: 'abc', recovery_job_id: 'x' } }), false);
  assert.equal(canActivate(null), false);
});

test('pipeline result is described for each outcome and absent for manual crawls', () => {
  assert.equal(pipelineResult({ details: {} }), null);
  assert.equal(pipelineResult({ details: { pipeline: { error: 'RuntimeError' } } }).tone, 'error');
  assert.match(pipelineResult({ details: { pipeline: { skipped: 'NO_APPROVED_ARTICLES' } } }).text, /Không có bài đã duyệt/);
  assert.match(pipelineResult({ details: { pipeline: { skipped: 'SOMETHING_NEW' } } }).text, /SOMETHING_NEW/);
  const active = pipelineResult({ details: { pipeline: { index_status: 'ACTIVE', articles: 7 } } });
  assert.equal(active.tone, 'success');
  assert.match(active.text, /7 bài.*chuyển corpus/);
  assert.equal(pipelineResult({ details: { pipeline: { index_status: 'INDEXED', articles: 3 } } }).tone, 'warning');
});

test('delete message reports the count and groups the skipped reasons', async () => {
  const { deleteResultMessage } = await import('./ingestionPipeline.js');
  assert.equal(deleteResultMessage({ deleted: ['a', 'b'], skipped: [] }), 'Đã xóa 2 bài.');
  assert.equal(deleteResultMessage({ deleted: [], skipped: [] }), 'Không xóa được bài nào.');
  const text = deleteResultMessage({ deleted: ['a'], skipped: [
    { id: 'b', reason: 'IN_INDEX_JOB' }, { id: 'c', reason: 'IN_INDEX_JOB' }, { id: 'd', reason: 'WHATEVER' }] });
  assert.match(text, /^Đã xóa 1 bài\. Bỏ qua: 2 bài đang nằm trong lần lưu database chưa chuyển corpus; 1 bài WHATEVER\.$/);
  assert.equal(deleteResultMessage(null), 'Không xóa được bài nào.');
});
