// Per-user watchlist stored in the backend (public.watchlists).
import { authorizedFetch } from "../../shared/api/authorization.js";

async function call(path = "", method = "GET") {
  const response = await authorizedFetch(`/api/watchlist${path}`, { method, cache: "no-store" });
  if (!response.ok) {
    let body = null;
    try { body = await response.json(); } catch { /* API may return an empty error body. */ }
    throw Object.assign(new Error(body?.detail && typeof body.detail === "string"
      ? body.detail : `Không cập nhật được danh sách theo dõi (lỗi ${response.status}).`), { status: response.status });
  }
  return response.status === 204 ? null : response.json();
}

export const getWatchlist = () => call();
export const followCompany = (ticker) => call(`/${encodeURIComponent(ticker)}`, "PUT");
export const unfollowCompany = (ticker) => call(`/${encodeURIComponent(ticker)}`, "DELETE");

// Missing company fields are shown as placeholders, never as made-up values.
export const toView = (company) => ({
  ticker: company.ticker,
  name: company.name || company.ticker,
  sector: company.sector || "Khác",
  exchange: company.exchange || "Chưa có dữ liệu",
});
