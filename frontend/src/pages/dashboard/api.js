import { getWatchlist, toView } from "../watchlist/api.js";

export async function getDashboard() {
  const watchlist = await getWatchlist();
  return { watchlist: watchlist.items.map(toView) };
}
