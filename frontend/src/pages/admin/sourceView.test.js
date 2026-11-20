import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceRows, automationNote, crawlRuns, runCounts } from './sourceView.js';

const config = { provider: 'fireant', enabled: true, hour: 7, limit: 100, max_pages: 5, symbols: ['FPT', 'VCB'],
  include_market: true, auto_approve: false, auto_index: false, auto_activate: false };

test('source rows describe the real config in order', () => {
  const rows = sourceRows(config);
  assert.equal(rows[0].value, 'FireAnt');
  assert.equal(rows[1].value, 'Bật, từ 07:00 (giờ Việt Nam)');
  assert.equal(rows.find(r => r.label === 'Mã theo dõi').value, 'FPT, VCB');
  assert.equal(rows.find(r => r.label === 'Tự động chuyển corpus cho Chat').value, 'Tắt');
  assert.deepEqual(sourceRows(null), []);
  assert.equal(sourceRows({ ...config, enabled: false })[1].value, 'Tắt');
  assert.equal(sourceRows({ ...config, symbols: [] }).find(r => r.label === 'Mã theo dõi').value, 'Không có');
});

test('automation note reflects the strongest enabled stage', () => {
  assert.match(automationNote({ ...config, enabled: false }), /chỉ thu thập khi bấm tay/);
  assert.match(automationNote(config), /duyệt và lưu database vẫn làm tay/);
  assert.match(automationNote({ ...config, auto_approve: true }), /tự duyệt/);
  assert.match(automationNote({ ...config, auto_index: true }), /chờ bấm Chuyển corpus/);
  assert.match(automationNote({ ...config, auto_index: true, auto_activate: true }), /tự chuyển corpus/);
  assert.equal(automationNote(undefined), '');
});

test('crawl runs keep only crawls, newest first, limited', () => {
  const jobs = [
    { id: 'a', kind: 'CRAWL', created_at: '2026-11-01T00:00:00Z' },
    { id: 'b', kind: 'INDEX', created_at: '2026-11-05T00:00:00Z' },
    { id: 'c', kind: 'CRAWL', created_at: '2026-11-03T00:00:00Z' },
  ];
  assert.deepEqual(crawlRuns(jobs).map(j => j.id), ['c', 'a']);
  assert.equal(crawlRuns(jobs, 1).length, 1);
  assert.deepEqual(crawlRuns(null), []);
});

test('run counts tolerate missing details', () => {
  assert.deepEqual(runCounts({ details: { fetched: 20, new_articles: 5, duplicates: 15, errors: [{}, {}] } }),
    { fetched: 20, created: 5, duplicates: 15, errors: 2 });
  assert.deepEqual(runCounts({}), { fetched: null, created: null, duplicates: null, errors: 0 });
});
