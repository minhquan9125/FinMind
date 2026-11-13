import { authorizedFetch } from "../../shared/api/authorization.js";
import { STORAGE_KEY } from "./mock.js";

const apiBase = (import.meta.env?.VITE_MARKET_DATA_API_URL || "").replace(/\/$/, "");

// The watchlist lives on the server (public.watchlists); the old browser-only list is moved there once.
export function createWatchlistApi({ request = authorizedFetch, storage = globalThis.localStorage, base = apiBase } = {}) {
  async function call(method, path = "") {
    const response = await request(`${base}/api/watchlist${path}`, method === "GET" ? {} : { method });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(body?.detail || `API trả lỗi ${response.status}.`);
    return body;
  }
  const getWatchlist = () => call("GET");
  const addToWatchlist = (ticker) => call("PUT", `/${encodeURIComponent(ticker)}`);
  const removeFromWatchlist = (ticker) => call("DELETE", `/${encodeURIComponent(ticker)}`);

  async function loadWatchlist() {
    let local = [];
    try { local = JSON.parse(storage?.getItem(STORAGE_KEY) || "[]"); } catch { local = []; }
    let list = await getWatchlist();
    for (const ticker of local) {
      if (!list.some((item) => item.id === ticker)) {
        try { list = await addToWatchlist(ticker); } catch { /* a ticker the server no longer knows is dropped */ }
      }
    }
    try { storage?.removeItem(STORAGE_KEY); } catch { /* storage may be unavailable */ }
    return list;
  }

  return { getWatchlist, addToWatchlist, removeFromWatchlist, loadWatchlist };
}

export const { getWatchlist, addToWatchlist, removeFromWatchlist, loadWatchlist } = createWatchlistApi();
