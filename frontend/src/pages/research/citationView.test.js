import test from 'node:test';
import assert from 'node:assert/strict';
import { citationView, modeLabel, safeSourceUrl } from './citationView.js';

test('prices never show citation cards or source links', () => {
  assert.deepEqual(citationView({ execution_mode: 'LIVE', scope: { source_type: 'PRICE' },
    evidence_pack: { items: [{ evidence_id: 'price', source_type: 'PRICE', source_verified: true }] } }), []);
});

test('summaries show compact links only for articles used in the answer', () => {
  const item = { evidence_id: 'e1', source_type: 'NEWS', source_verified: true, title: 'Bài đã dùng',
    locator: { url: 'https://fireant.vn/bai-viet/tin/123' } };
  const result = { execution_mode: 'LIVE', presentation: { sources: 'USED_LINKS' },
    answering: { status: 'DRAFT_READY', citations: [{ evidence_id: 'e1', citation_number: 1 }] },
    evidence_pack: { items: [item, { ...item, evidence_id: 'unused' }] } };
  const sources = citationView(result);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].compact, true);
  assert.equal(sources[0].url, item.locator.url);
});

test('shows only verified live sources and distinguishes candidates from bound citations', () => {
  const item = { evidence_id: 'e1', passage: 'Nguồn thật', source_verified: true,
    title: 'Báo cáo FPT', locator: { source_table: 'financial_reports', section: 'Bảng cân đối', row_keys: ['r1'] } };
  assert.equal(citationView({ execution_mode: 'FIXTURE', evidence_pack: { items: [item] } }).length, 0);
  const result = { execution_mode: 'LIVE', evidence_pack: { items: [item, { ...item, evidence_id: 'e2', source_verified: false }] } };
  assert.equal(citationView(result).length, 1);
  assert.equal(citationView(result)[0].used, false);
  result.answering = { status: 'DRAFT_READY', citations: [{ evidence_id: 'e1' }] };
  assert.equal(citationView(result)[0].used, true);
  assert.equal(citationView(result)[0].location, 'Bảng cân đối');
});

test('source links reject executable schemes and credentials', () => {
  assert.equal(safeSourceUrl('javascript:alert(1)'), null);
  assert.equal(safeSourceUrl('data:text/html,hello'), null);
  assert.equal(safeSourceUrl('https://user:pass@example.com'), null);
  assert.equal(safeSourceUrl('https://cafef.vn/news.htm'), 'https://cafef.vn/news.htm');
});

test('mode label does not label live data as fixtures', () => {
  assert.match(modeLabel({ execution_mode: 'LIVE' }), /Nguồn dữ liệu thật/);
  assert.match(modeLabel({ execution_mode: 'FIXTURE' }), /Dữ liệu mẫu/);
});

test('citation numbers follow answer order instead of retrieval order', () => {
  const items = ['a', 'b', 'c'].map(id => ({ evidence_id: id, source_verified: true }));
  const view = citationView({ execution_mode: 'LIVE', evidence_pack: { items },
    answering: { status: 'DRAFT_READY', citations: [
      { evidence_id: 'b', citation_number: 1 }, { evidence_id: 'a', citation_number: 2 },
    ] } });
  assert.equal(view[0].citationNumber, 2);
  assert.equal(view[1].citationNumber, 1);
  assert.equal(view[2].citationNumber, null);
});
