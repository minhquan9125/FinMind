import test from 'node:test';
import assert from 'node:assert/strict';
import { MAX_BYTES, parseUpload, launchErrorMessage, jobStatusView, hasRunning } from './jobLaunch.js';

const manifest = { corpus_version_id: 'c1', manifest_sha256: 'a'.repeat(64), manifest: { documents: [] } };

test('a valid manifest and article list are accepted', () => {
  assert.equal(parseUpload('manifest', JSON.stringify(manifest)).ok, true);
  assert.deepEqual(parseUpload('articles', JSON.stringify([{ article_id: 'a1', content: 'x' }])).value, [{ article_id: 'a1', content: 'x' }]);
});

test('invalid manifests are rejected with a specific reason', () => {
  assert.match(parseUpload('manifest', 'not json').error, /không phải JSON/);
  for (const bad of [{}, [], null, { ...manifest, manifest_sha256: 'xyz' }, { ...manifest, corpus_version_id: '' }, { ...manifest, manifest: null }]) {
    assert.equal(parseUpload('manifest', JSON.stringify(bad)).ok, false);
  }
});

test('article lists must be non-empty arrays of objects with an id and not too many', () => {
  assert.match(parseUpload('articles', '{}').error, /mảng JSON/);
  assert.match(parseUpload('articles', '[]').error, /rỗng/);
  assert.match(parseUpload('articles', JSON.stringify([{ content: 'no id' }])).error, /article_id/);
  assert.match(parseUpload('articles', JSON.stringify([null])).error, /article_id/);
  assert.match(parseUpload('articles', JSON.stringify(Array.from({ length: 5001 }, (_, i) => ({ article_id: String(i) })))).error, /Tối đa 5000/);
});

test('files over the size limit are refused before parsing', () => {
  assert.match(parseUpload('articles', '[]', MAX_BYTES + 1).error, /8 MB/);
});

test('launch errors are readable and unknown ones fall back by status', () => {
  assert.match(launchErrorMessage('JOB_ALREADY_RUNNING', 409), /Đang có một lần chạy khác/);
  assert.equal(launchErrorMessage('X', 403), 'Tài khoản không có quyền quản trị.');
  assert.equal(launchErrorMessage(undefined, 422), 'Dữ liệu gửi lên chưa đúng định dạng.');
  assert.equal(launchErrorMessage(undefined, 500), 'Không khởi chạy được.');
});

test('status view says what the job is and only links finished reports', () => {
  assert.deepEqual(jobStatusView({ status: 'STAGED' }), { label: 'Đã xử lý đầu vào', tone: 'neutral', linkable: true });
  assert.equal(jobStatusView({ status: 'ATTENTION' }).linkable, true);
  assert.equal(jobStatusView({ status: 'RUNNING' }).linkable, false);
  assert.match(jobStatusView({ status: 'LAUNCH_FAILED', reason: 'WORKER_STOPPED' }).label, /tiến trình đã dừng/);
  assert.equal(jobStatusView({ status: 'LAUNCH_FAILED' }).label, 'Lỗi');
  assert.equal(jobStatusView({ status: 'INVALID_REPORT' }).label, 'Báo cáo lỗi');
});

test('running detection', () => {
  assert.equal(hasRunning([{ status: 'STAGED' }, { status: 'RUNNING' }]), true);
  assert.equal(hasRunning([{ status: 'STAGED' }]), false);
  assert.equal(hasRunning(null), false);
});
