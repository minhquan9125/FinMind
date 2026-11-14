import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import * as api from "../src/pages/companies/marketDataApi.js";

const root = fileURLToPath(new URL("..", import.meta.url));

test("analysis client sends authorized dated read and cancellation signal", async () => {
  assert.equal(typeof api.getPriceAnalysis, "function");
  const originalFetch = globalThis.fetch;
  const originalStorage = globalThis.localStorage;
  const signal = new AbortController().signal;
  const calls = [];
  globalThis.localStorage = { getItem: () => JSON.stringify({ token: "test-session" }) };
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ symbol: "FPT", status: "partial" }) };
  };
  try {
    assert.deepEqual(await api.getPriceAnalysis("F/PT", "2026-10-29", signal), { symbol: "FPT", status: "partial" });
    assert.equal(calls[0].url, "/api/market-data/stocks/F%2FPT/analysis?as_of=2026-10-29");
    assert.equal(calls[0].options.signal, signal);
    assert.equal(calls[0].options.headers.Authorization, "Bearer test-session");
    await api.getPriceAnalysis("MBB", undefined, signal);
    assert.equal(calls[1].url, "/api/market-data/stocks/MBB/analysis");
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.localStorage = originalStorage;
  }
});

test("analysis client preserves no-data, auth, unavailable, and abort distinctions", async () => {
  assert.equal(typeof api.getPriceAnalysis, "function");
  const originalFetch = globalThis.fetch;
  try {
    for (const status of [404, 401, 503]) {
      globalThis.fetch = async () => ({ ok: false, status, json: async () => ({ detail: "Không thể đọc dữ liệu" }) });
      await assert.rejects(api.getPriceAnalysis("FPT"), (error) => error.status === status && error.message === "Không thể đọc dữ liệu");
    }
    globalThis.fetch = async () => { throw Object.assign(new Error("cancelled"), { name: "AbortError" }); };
    await assert.rejects(api.getPriceAnalysis("FPT"), { name: "AbortError" });
  } finally { globalThis.fetch = originalFetch; }
});

test("analysis renders supplied metrics, incomplete windows and pending snapshot separately", async () => {
  assert.ok(existsSync(`${root}/src/pages/companies/PriceAnalysis.jsx`), "analysis component must exist");
  const server = await createServer({ root, configFile: false, server: { middlewareMode: true }, esbuild: { jsx: "automatic" } });
  try {
    const { PriceAnalysisResult, default: PriceAnalysis } = await server.ssrLoadModule("/src/pages/companies/PriceAnalysis.jsx");
    const data = {
      symbol: "FPT", status: "partial", requested_as_of: "2026-11-11", as_of: "2026-10-29", first_date: "2026-10-01", session_count: 21,
      freshness: { stale: true, staleness_calendar_days: 13 },
      metrics: { close_vnd: "120000.0000", close: "120.0000", price_scale: 1000, is_adjusted: false,
        return_1_percent: "0.8403", return_5_percent: "4.3478", return_20_percent: "20.0000", sma20: "110.5000",
        close_vs_sma20_percent: "8.5973", volume: 200, average_volume_prior20: "100.0000", volume_vs_prior20: "2.0000",
        average_volume_latest5: "120.0000", average_volume_prior5: "100.0000", intraday_range_percent: "1.6807", daily_volatility20_percent: "0.0498" },
      activity: {
        latest_observation: { trade_date: "2026-11-11", observation_status: "intraday", quality_status: "pending_reconciliation",
          total_value_vnd: "105048970000.0000", foreign_buy_volume: 368405, foreign_sell_volume: 515600, foreign_net_volume: -147195,
          foreign_buy_value_vnd: null, foreign_sell_value_vnd: null, fetched_at: "2026-11-11T03:00:00+00:00", source_name: "vnstock_kbs", value_basis: "unknown" },
        windows: { "1": { required_sessions: 1, available_sessions: 0, missing_dates: ["2026-10-29"], status: "incomplete", total_value_vnd: null, foreign_net_value_vnd: null } },
      },
      benchmark: { index_symbol: "VNINDEX", windows: { "20": { required_sessions: 21, available_sessions: 21, missing_dates: [], return_percent: "10.0000", stock_return_percent: "20.0000", difference_percentage_points: "10.0000", status: "complete" } } },
      coverage: { price_sessions: 21, required_price_sessions: 21, missing_metrics: ["foreign_net_value_vnd"] },
      warnings: ["unadjusted_prices"],
      sources: { prices: [{ trade_date: "2026-10-29", price_id: "price-1", payload_id: "raw-1", source_id: "source-1", source_name: "vnstock_kbs", approval_status: "PENDING", price_scale: 1000, is_adjusted: false }], activity: [], benchmark: [] },
    };
    const html = renderToStaticMarkup(React.createElement(PriceAnalysisResult, { data }));
    for (const text of ["2026-10-29", "2026-11-11", "13", "20.0000%", "2.0000", "VNINDEX", "10.0000", "Chưa đủ dữ liệu", "Trong phiên", "Chờ đối soát", "raw-1", "vnstock_kbs", "Chưa phê duyệt", "2026-10-29", "105048970000.0000"]) assert.ok(html.includes(text), text);
    assert.ok(!html.includes("null"));
    assert.ok(!html.includes("undefined"));
    const loading = renderToStaticMarkup(React.createElement(PriceAnalysis, { symbol: "MBB" }));
    assert.ok(loading.includes("Đang tải"));
    assert.ok(!loading.includes("120000"));
    const empty = renderToStaticMarkup(React.createElement(PriceAnalysisResult, { data: { symbol: "FPT", status: "no_data" } }));
    assert.ok(empty.includes("Chưa có dữ liệu"));
    const pendingAuxiliary = renderToStaticMarkup(React.createElement(PriceAnalysisResult, { data: {
      ...data, sources: { ...data.sources, prices: data.sources.prices.map(row => ({ ...row, approval_status: "APPROVED" })) },
      warnings: ["activity_source_not_approved:2026-11-11", "benchmark_source_not_approved:2026-11-11"],
    } }));
    assert.ok(pendingAuxiliary.includes("Nguồn khối ngoại chưa được phê duyệt."));
    assert.ok(pendingAuxiliary.includes("Nguồn VNINDEX chưa được phê duyệt."));
  } finally { await server.close(); }
});

const trendHorizon = (label, extra = {}) => ({ label, sessions: 20, lookback: 5, sma: "52.1000", slope_percent: "-1.5000",
  return_percent: "-10.8581", range_percent: "12.0000", close_vs_sma_percent: "-6.1145", index_return_percent: "2.4653",
  reasons: ["close_below_sma", "sma_falling", "negative_return"], ...extra });

test("trend renders three horizons, labels, reasons and disclaimer", async () => {
  const server = await createServer({ root, configFile: false, server: { middlewareMode: true }, esbuild: { jsx: "automatic" } });
  try {
    const { TrendSection } = await server.ssrLoadModule("/src/pages/companies/PriceAnalysis.jsx");
    const trend = { as_of: "2026-11-11", benchmark: "VNINDEX",
      source: { name: "ENTRADE", approval_status: "PENDING", is_adjusted: false, price_scale: 1000 },
      horizons: { "20": trendHorizon("DOWN"), "60": trendHorizon("SIDEWAYS"),
        "200": trendHorizon("UNCLEAR", { reasons: ["possible_corporate_action:2026-06-12", "mixed_signals"] }) },
      context: { high_52w: "68.0000", high_52w_date: "2026-01-05", low_52w: "49.8000", low_52w_date: "2026-11-05",
        from_high_percent: "-25.1471", from_low_percent: "2.2088", rsi14: "30.9877", volume20_vs_volume60: "0.8500" },
      warnings: ["prices_source_not_approved", "unadjusted_prices", "possible_corporate_action:2026-06-12"] };
    const html = renderToStaticMarkup(React.createElement(TrendSection, { trend }));
    for (const text of ["Xu hướng giá", "Ngắn hạn", "Trung hạn", "Dài hạn", "Giảm", "Đi ngang/tích lũy", "Chưa rõ xu hướng",
      "-10,86%", "VNINDEX", "2,47%", "2026-06-12", "68.000", "30,99", "2026-11-11", "không phải khuyến nghị"]) assert.ok(html.includes(text), text);
    assert.ok(!html.includes("null") && !html.includes("undefined"));
    const missing = renderToStaticMarkup(React.createElement(TrendSection, { trend: null }));
    assert.ok(missing.includes("Chưa tính được xu hướng giá"));
  } finally { await server.close(); }
});

test("missing trend shows unavailable note without breaking metrics", async () => {
  const server = await createServer({ root, configFile: false, server: { middlewareMode: true }, esbuild: { jsx: "automatic" } });
  try {
    const { PriceAnalysisResult } = await server.ssrLoadModule("/src/pages/companies/PriceAnalysis.jsx");
    const html = renderToStaticMarkup(React.createElement(PriceAnalysisResult, { data: {
      symbol: "FPT", status: "partial", requested_as_of: "2026-11-11", as_of: "2026-11-11", first_date: "2026-10-14", session_count: 21,
      metrics: { close_vnd: "50900.0000", is_adjusted: false }, warnings: ["trend_unavailable"], trend: null } }));
    assert.ok(html.includes("Chưa tính được xu hướng giá"));
    assert.ok(html.includes("50.900"));
  } finally { await server.close(); }
});
