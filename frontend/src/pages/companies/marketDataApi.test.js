import test from "node:test";
import assert from "node:assert/strict";
import { getIndexHistory, getMarketNews, getSavedOhlcv, loadStockHistory } from "./marketDataApi.js";

test("market news sends a bearer token and returns saved articles", async () => {
  const oldFetch=globalThis.fetch, oldStorage=globalThis.localStorage;
  globalThis.localStorage={getItem:()=>JSON.stringify({token:"fixture-token"})};
  globalThis.fetch=async (url,options)=>{
    assert.equal(url,"/api/market-data/news?limit=10");
    assert.equal(options.headers.get("Authorization"),"Bearer fixture-token");
    return {ok:true,status:200,json:async()=>({articles:[{id:"source-1",title:"Saved news"}]})};
  };
  try { assert.equal((await getMarketNews()).articles.length,1); }
  finally { globalThis.fetch=oldFetch;globalThis.localStorage=oldStorage; }
});

test("missing login remains an authentication error, not a backend connectivity error", async () => {
  const oldStorage=globalThis.localStorage;
  globalThis.localStorage={getItem:()=>null};
  try { await assert.rejects(getMarketNews(),e=>e.status===401 && /đăng nhập lại/.test(e.message)); }
  finally {globalThis.localStorage=oldStorage;}
});

test("conditional OHLCV requests retain the ETag while authenticating", async () => {
  const oldFetch=globalThis.fetch, oldStorage=globalThis.localStorage;
  globalThis.localStorage={getItem:()=>JSON.stringify({token:"fixture-token"})};
  globalThis.fetch=async (url,options)=>{
    assert.equal(options.headers.get("If-None-Match"),"etag-1");
    assert.equal(options.headers.get("Authorization"),"Bearer fixture-token");
    return {status:304};
  };
  try { assert.deepEqual(await getSavedOhlcv("BID",undefined,"etag-1"),{unchanged:true,etag:"etag-1"}); }
  finally {globalThis.fetch=oldFetch;globalThis.localStorage=oldStorage;}
});

test("index cached reads are explicit and fresh reads retain Retry-After", async () => {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "fixture-token" }) };
  const urls = [];
  globalThis.fetch = async url => {
    urls.push(url);
    if (url.endsWith('?cached=true')) return { ok: true, json: async () => ({ bars: [1] }) };
    return { ok: false, status: 429, headers: new Headers({ 'Retry-After': '7' }), json: async () => ({ detail: 'quota' }) };
  };
  try {
    assert.deepEqual(await getIndexHistory('VNINDEX', undefined, { cached: true }), { bars: [1] });
    await assert.rejects(getIndexHistory('VNINDEX'), error => error.status === 429 && error.retryAfter === '7');
    assert.deepEqual(urls, ['/api/market-data/indices/VNINDEX/ohlcv?cached=true', '/api/market-data/indices/VNINDEX/ohlcv']);
  } finally { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage; }
});

test('opening a company loads history through the authenticated read endpoint', async () => {
  const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: 'fixture-token' }) };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/market-data/stocks/ICT/history');
    assert.equal(options.method || 'GET', 'GET');
    assert.equal(options.headers.get('Authorization'), 'Bearer fixture-token');
    return { ok: true, status: 200, json: async () => ({ symbol: 'ICT', bars: [1] }) };
  };
  try { assert.equal((await loadStockHistory('ICT')).bars.length, 1); }
  finally { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage; }
});
