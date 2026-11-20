import test from 'node:test';
import assert from 'node:assert/strict';
import { loadMarketIndices } from './marketIndices.js';

function setup(api, extra = {}) {
  const results = [], errors = [], pending = [];
  return { symbols: ['VNINDEX', 'VN30'], signal: new AbortController().signal, api,
    onResult: (symbol, data) => results.push([symbol, data]), onError: (...args) => errors.push(args),
    onPending: (...args) => pending.push(args), results, errors, pending, ...extra };
}

test('saved charts arrive before provider finishes and fresh calls stay sequential', async () => {
  let release, active = 0, maximum = 0;
  const gate = new Promise(resolve => { release = resolve; });
  const options = setup({ cached: async () => ({ bars: [1], refresh: { needed: true } }),
    refresh: async () => { active++; maximum = Math.max(maximum, active); await gate; active--; return { bars: [2] }; } });
  const run = loadMarketIndices(options);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(options.results.length, 2);
  assert.equal(active, 1);
  release(); await run;
  assert.equal(maximum, 1); assert.equal(options.results.length, 4);
});

test('fresh cache avoids quota, selected index gets priority and Retry-After is honored', async () => {
  const calls = [], waits = []; let count = 0;
  const options = setup({ cached: async symbol => ({ bars: [1], refresh: { needed: symbol !== 'VNINDEX' } }),
    refresh: async symbol => { calls.push(symbol); if (!count++) throw Object.assign(Error('quota'), { status: 429, retryAfter: 7 }); return { bars: [2] }; }
  }, { getPriority: () => 'VN30', wait: async ms => waits.push(ms) });
  await loadMarketIndices(options);
  assert.deepEqual(calls, ['VN30', 'VN30']); assert.deepEqual(waits, [7000]);
  assert.equal(options.errors.filter(([, error]) => error).length, 0);
});

test('provider failure preserves saved data and abort stops remaining updates', async () => {
  const abort = new AbortController(); let calls = 0;
  const options = setup({ cached: async () => ({ bars: [1] }), refresh: async () => { calls++; throw Error('offline'); } });
  await loadMarketIndices(options);
  assert.equal(options.results.length, 2); assert.equal(options.errors.length, 2);
  const cancelled = setup({ cached: async () => { abort.abort(); return { bars: [1] }; }, refresh: async () => { calls++; } }, { signal: abort.signal });
  await loadMarketIndices(cancelled);
  assert.equal(cancelled.results.length, 0); assert.equal(calls, 2);
});
