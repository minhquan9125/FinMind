import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeMarket, selectFinancialEvidence } from './landingMarketData.js';

test('missing closes and a zero reference never produce fabricated movements', () => {
  for (const close of [null, undefined, '', ' ', false, true, 0, -1, 'invalid']) assert.equal(summarizeMarket({ bars: [{ close }] }), null);
  assert.equal(summarizeMarket({ bars: {} }), null);
  const single = summarizeMarket({ bars: [{ close: 44.5, date: '2026-11-26' }] });
  assert.equal(single.close, 44.5); assert.equal(single.change, null); assert.equal(single.percent, null);
  assert.equal(summarizeMarket({ bars: [{ close: 0 }, { close: 44.5 }] }).percent, null);
});
test('movement uses the previous actual close and retains the trading date', () => {
  const quote = summarizeMarket({ bars: [{ close: '46.05' }, { close: '44.5', date: '2026-11-26' }] });
  assert.ok(Math.abs(quote.change + 1.55) < 1e-8);
  assert.ok(quote.percent < 0); assert.equal(quote.date, '2026-11-26');
});
test('financial citation cannot attach a report from another period', () => {
  assert.equal(selectFinancialEvidence({ periods: [{ period: '2026-Q3' }], reports: [{ period: '2025-YEAR', url: 'https://example.org/report.pdf' }] }), null);
  const period = { period: '2026-Q3', facts: { netProfit: { value: 200, unit: 'VND' } } };
  const report = { period: '2026-Q3', url: 'https://example.org/report.pdf' };
  assert.deepEqual(selectFinancialEvidence({ periods: [period], reports: [report] }), { period, report, fact: period.facts.netProfit });
});
test('unknown money units and unsafe report links never become valid citations', () => {
  const period = { period: '2026-Q3', facts: { netProfit: { value: 200, unit: 'UNKNOWN' } } };
  assert.equal(selectFinancialEvidence({ periods: [period], reports: [{ period: period.period, url: 'javascript:alert(1)' }] }), null);
  assert.equal(selectFinancialEvidence({ periods: [period], reports: [{ period: period.period, url: 'https://example.org/report.pdf' }] }).fact, null);
});

test('source-native money keeps the same fact and partial verification used by the company page', () => {
  const period = { period: '2026-Q3', status: 'PARTIAL', facts: { netProfit: { value: 2729313537249, unit: 'SOURCE_NATIVE', status: 'PARTIAL' } } };
  const report = { period: period.period, url: 'https://example.org/report.pdf', status: 'PARTIAL' };
  const evidence = selectFinancialEvidence({ periods: [period], reports: [report] });
  assert.deepEqual(evidence.fact, period.facts.netProfit);
  assert.equal(evidence.period.status, 'PARTIAL');
});
