import test from 'node:test';
import assert from 'node:assert/strict';
import { docTypeLabel, corpusStatusLabel, indexStatusLabel, shortId, indexTone, typeBreakdown, servingFirst, pageLabel } from './corpusView.js';

test('labels are readable and unknown codes pass through instead of disappearing', () => {
  assert.equal(docTypeLabel('NEWS'), 'Tin tức');
  assert.equal(docTypeLabel('SOMETHING_NEW'), 'SOMETHING_NEW');
  assert.equal(docTypeLabel(null), 'Không rõ');
  assert.equal(corpusStatusLabel('FROZEN'), 'Đã đóng băng');
  assert.equal(indexStatusLabel('BUILDING'), 'Đang xây dựng');
  assert.equal(indexStatusLabel(null), 'Chưa có chỉ mục');
});

test('short id and tones tolerate missing values', () => {
  assert.equal(shortId('a530bc8a-e0f6-5003-9b9b-9c61b24dbcf1'), 'a530bc8a');
  assert.equal(shortId(undefined), '—');
  assert.equal(indexTone('ACTIVE'), 'success');
  assert.equal(indexTone('BUILDING'), 'warning');
  assert.equal(indexTone('FAILED'), 'error');
  assert.equal(indexTone(undefined), 'neutral');
});

test('type breakdown is sorted by count then label', () => {
  const rows = typeBreakdown({ NEWS: 192, FINANCIAL_STATEMENT: 1638, ANNUAL_REPORT: 20, COMPANY_PROFILE: 20 });
  assert.deepEqual(rows.map(r => r.type), ['FINANCIAL_STATEMENT', 'NEWS', 'ANNUAL_REPORT', 'COMPANY_PROFILE']);
  assert.equal(rows[0].count, 1638);
  assert.deepEqual(typeBreakdown(null), []);
});

test('the serving corpus is listed first and the input is not mutated', () => {
  const items = [{ id: 1 }, { id: 2, serving: true }, { id: 3 }];
  assert.deepEqual(servingFirst(items).map(i => i.id), [2, 1, 3]);
  assert.deepEqual(items.map(i => i.id), [1, 2, 3]);
  assert.deepEqual(servingFirst(null), []);
});

test('page label shows the visible range and the total', () => {
  assert.equal(pageLabel(null), '0 tài liệu');
  assert.equal(pageLabel({ total: 0, offset: 0, limit: 30 }), '0 tài liệu');
  assert.match(pageLabel({ total: 1875, offset: 30, limit: 30 }), /^31–60 \/ 1[.,]?875$/);
  assert.match(pageLabel({ total: 40, offset: 30, limit: 30 }), /^31–40 \/ 40$/);
});

test('actions follow the real state of the corpus', async () => {
  const { availableActions } = await import('./corpusView.js');
  const base = { corpus_version_id: 'a530bc8a-0000', status: 'FROZEN', servable: true, serving: false };
  assert.deepEqual(availableActions(base).map(a => a.id), ['serve', 'archive']);
  assert.deepEqual(availableActions({ ...base, serving: true }).map(a => a.id), []);
  assert.deepEqual(availableActions({ ...base, servable: false }).map(a => a.id), ['archive']);
  assert.deepEqual(availableActions({ ...base, status: 'ARCHIVED', servable: false }).map(a => a.id), ['restore']);
  assert.deepEqual(availableActions(null), []);
  assert.match(availableActions(base)[0].confirm, /a530bc8a/);
});

test('error and success messages are readable', async () => {
  const { actionErrorMessage, actionSuccessMessage } = await import('./corpusView.js');
  assert.match(actionErrorMessage('CORPUS_IN_USE', 409), /đang được Chat dùng/);
  assert.equal(actionErrorMessage('UNKNOWN', 401), 'Phiên đăng nhập hết hạn.');
  assert.equal(actionErrorMessage(undefined, 500), 'Thao tác không thành công.');
  assert.match(actionSuccessMessage('serve', { corpus_version_id: 'abcdefgh-1', warmed: false }), /chậm hơn/);
  assert.doesNotMatch(actionSuccessMessage('serve', { corpus_version_id: 'abcdefgh-1', warmed: true }), /chậm hơn/);
  assert.match(actionSuccessMessage('archive', { corpus_version_id: 'abcdefgh-1' }), /Đã lưu trữ phiên abcdefgh/);
  assert.match(actionSuccessMessage('restore', { corpus_version_id: 'abcdefgh-1' }), /Đã khôi phục/);
});
