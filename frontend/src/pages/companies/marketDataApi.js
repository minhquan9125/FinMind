// This page reads the saved-data API. Change the URL when the same contract is served
// by the main FastAPI app or Supabase-backed repository; the UI does not change.
const apiBase = (import.meta.env.VITE_MARKET_DATA_API_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

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
