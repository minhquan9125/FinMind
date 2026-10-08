// Read saved history with the shared live-price overlay. Change the URL when served
// by the main FastAPI app or Supabase-backed repository; the UI does not change.
import { retryRateLimited } from "./companyData.js";
const apiBase = (import.meta.env?.VITE_MARKET_DATA_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

async function readJson(path, signal) {
  let response;
  try {
    response = await fetch(`${apiBase}${path}`, { signal });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Không kết nối được API dữ liệu đã lưu. Hãy kiểm tra server ở cổng 8001.");
  }
  if (!response.ok) {
    let body = null;
    try { body = await response.json(); } catch { /* API may return an empty error body. */ }
    throw new Error(body?.detail || `API trả lỗi ${response.status}.`);
  }
  return response.json();
}

export async function getSavedOhlcv(symbol, signal, etag) {
  let response;
  try {
    response = await fetch(`${apiBase}/api/market-data/stocks/${encodeURIComponent(symbol)}/ohlcv?limit=250`, {
      signal,
      cache: "no-store",
      headers: etag ? { "If-None-Match": etag } : {},
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Không kết nối được API dữ liệu đã lưu. Hãy kiểm tra server ở cổng 8001.");
  }
  if (response.status === 304) return { unchanged: true, etag };
  if (!response.ok) {
    let body = null;
    try { body = await response.json(); } catch { /* API may return an empty error body. */ }
    throw new Error(body?.detail || `API trả lỗi ${response.status}.`);
  }
  return { unchanged: false, etag: response.headers.get("ETag"), data: await response.json() };
}

export function getSavedNews(symbol, signal) {
  return readJson(`/api/market-data/companies/${encodeURIComponent(symbol)}/news?limit=10`, signal);
}

export function getMarketNews(signal) {
  return readJson("/api/market-data/news?limit=10", signal);
}

export function getIndexHistory(symbol, signal) {
  return readJson(`/api/market-data/indices/${encodeURIComponent(symbol)}/ohlcv`, signal);
}

async function liveRequest(path, options) {
  const response = await fetch(`${apiBase}/api/market-data${path}`, { cache: "no-store", ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(body?.detail || "Chưa cập nhật được dữ liệu; vui lòng thử lại sau.");
    error.status = response.status;
    error.retryAfter = response.headers.get("Retry-After");
    throw error;
  }
  return response.json();
}

export function watchLivePrice(viewerId, symbol, signal) {
  return liveRequest(`/live/viewers/${viewerId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }), signal,
  });
}

export function unwatchLivePrice(viewerId) {
  return liveRequest(`/live/viewers/${viewerId}`, { method: "DELETE", keepalive: true });
}

export function refreshLivePrice(symbol) {
  return liveRequest(`/stocks/${encodeURIComponent(symbol)}/refresh`, { method: "POST" });
}

export function loadStockHistory(symbol, signal) {
  return retryRateLimited(() => liveRequest(`/stocks/${encodeURIComponent(symbol)}/history`, { method: "POST", signal }), signal);
}

export function refreshCompanyNews(symbol, signal) {
  return retryRateLimited(() => liveRequest(`/companies/${encodeURIComponent(symbol)}/news/refresh`, { method: "POST", signal }), signal);
}
