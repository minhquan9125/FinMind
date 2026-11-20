import { emptyDashboardFixture, makeDashboardFixture } from "./mock.js";
import { getWatchlist, toView } from "../watchlist/api.js";
import { getCompanyCatalog } from "../companies/financials.js";

// Watchlist và danh mục doanh nghiệp lấy từ backend; các phần khác vẫn là mock.
// Lỗi của từng phần không làm hỏng cả Dashboard.
export async function getDashboard(fixture = "success") {
  if (fixture === "error") throw new Error("Không thể tải Dashboard minh họa.");
  if (fixture === "empty") return emptyDashboardFixture;
  const [watchlist, companies] = await Promise.allSettled([getWatchlist(), getCompanyCatalog()]);
  return {
    ...makeDashboardFixture(),
    watchlist: watchlist.status === "fulfilled" ? watchlist.value.items.map(toView) : [],
    watchlistError: watchlist.status === "rejected" ? watchlist.reason.message : "",
    companies: companies.status === "fulfilled" ? companies.value : [],
  };
}
