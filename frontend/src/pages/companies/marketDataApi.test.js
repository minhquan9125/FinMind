import test from "node:test";
import assert from "node:assert/strict";
import { getMarketNews, getSavedOhlcv } from "./marketDataApi.js";

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
