import test from 'node:test';
import assert from 'node:assert/strict';
import { scopeChips, outcomeNotice, followUps } from './scopeView.js';

test('scope chips show only backend-resolved fields and hide private state', () => {
  const chips = scopeChips({ scope: { companies: ['FPT'], periods: ['2025-Q2'], metric_code: 'NET_REVENUE',
    source_type: 'BCTC', _pending_metric: 'X', _clarification_state: {} } });
  assert.deepEqual(chips.map(c => c.value), ['FPT', 'Quý 2/2025', 'Doanh thu thuần', 'Báo cáo tài chính']);
  assert.deepEqual(scopeChips(null), []);
  assert.deepEqual(scopeChips({ scope: { companies: [], periods: null } }), []);
});

test('latest-period marker and year are readable', () => {
  assert.equal(scopeChips({ scope: { periods: ['LATEST_AVAILABLE_PERIOD'] } })[0].value, 'Kỳ mới nhất');
  assert.equal(scopeChips({ scope: { periods: ['2025'] } })[0].value, 'Năm 2025');
});

test('price scope shows a readable day and metric instead of raw codes', () => {
  const chips = scopeChips({ scope: { companies: ['FPT'], periods: ['2026-11-12'], metric_code: 'LAST_PRICE', source_type: 'PRICE' } });
  assert.deepEqual(chips.map(c => c.value), ['FPT', '12/11/2026', 'Giá gần nhất', 'Giá cổ phiếu']);
});

test('unanswerable outcomes get a plain-language explanation, answers do not', () => {
  assert.match(outcomeNotice({ status: 'NO_DATA', reason_code: 'NO_DATA' }), /chưa có đoạn nguồn/);
  assert.match(outcomeNotice({ status: 'UNSUPPORTED', reason_code: 'SOURCE_NOT_AVAILABLE' }), /báo cáo thường niên/);
  assert.equal(outcomeNotice({ status: 'DRAFT_READY' }), null);
  assert.equal(outcomeNotice(null), null);
});

test('a specific no-data reason keeps the backend message instead of the generic notice', () => {
  assert.equal(outcomeNotice({ status: 'NO_DATA', reason_code: 'PRICE_UNIT_UNVERIFIED', scope: { source_type: 'PRICE' } }), null);
  assert.equal(outcomeNotice({ status: 'NO_DATA', reason_code: 'PRICE_UNAVAILABLE' }), null);
});

test('news with no matching articles gets a news-specific explanation', () => {
  const notice = outcomeNotice({ status: 'NO_DATA', reason_code: 'NO_DATA', scope: { source_type: 'NEWS' } });
  assert.match(notice, /Kho tin tức/);
  assert.doesNotMatch(notice, /chỉ tiêu/);
});

test('follow-ups come from the returned scope and are suppressed while choices are pending', () => {
  const result = { status: 'DRAFT_READY', scope: { companies: ['FPT'], source_type: 'BCTC' },
    evidence_pack: { items: [{}] } };
  assert.deepEqual(followUps(result).map(f => f.id), ['source', 'news', 'price']);
  assert.deepEqual(followUps(result, true), []);
  assert.deepEqual(followUps({ status: 'ASK_CLARIFICATION', scope: { companies: ['FPT'] } }), []);
  assert.deepEqual(followUps({ status: 'NO_DATA', scope: {} }), []);
});

test('no source follow-up for prices, no duplicate source-type follow-up', () => {
  const price = { status: 'EVIDENCE_READY', scope: { companies: ['VCB'], source_type: 'PRICE' },
    evidence_pack: { items: [{}] } };
  assert.deepEqual(followUps(price).map(f => f.id), ['news']);
});
