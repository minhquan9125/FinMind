import { emptyDashboardFixture } from "./mock.js";
import { getWatchlist } from "../watchlist/watchlistApi.js";
import { listSessions } from "../research/chatApi.js";

// Market cards and news are loaded by their own components (MarketOverview, MarketNews).
// Here: the account's watchlist and its newest chat sessions; one failing source empties only its section.
export function createDashboardApi({ watchlist = getWatchlist, sessions = listSessions } = {}) {
  async function getDashboard(fixture = "success") {
    if (fixture === "error") throw new Error("Không thể tải Dashboard.");
    if (fixture === "empty") return emptyDashboardFixture;
    const [companies, history] = await Promise.allSettled([watchlist(), sessions()]);
    const items = history.status === "fulfilled" ? history.value?.items || [] : [];
    return {
      ...emptyDashboardFixture,
      watchlist: companies.status === "fulfilled" ? companies.value : [],
      recentResearch: [...items]
        .sort((a, b) => String(b.saved_at).localeCompare(String(a.saved_at)))
        .slice(0, 3)
        .map((item) => ({ id: item.session_id, ticker: "", title: item.preview, time: item.saved_at })),
    };
  }
  return { getDashboard };
}

export const { getDashboard } = createDashboardApi();
