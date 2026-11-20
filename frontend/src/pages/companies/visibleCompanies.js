const openedKey = (userId) => `finmind_revealed_companies:${userId}`;
const normalizeTicker = (ticker) => typeof ticker === "string" ? ticker.trim().toUpperCase() : "";

export function visibleCompanies(catalog, revealed, followed) {
  const visibleTickers = new Set([...revealed, ...followed].map(normalizeTicker));
  return catalog.filter(({ id, latestPeriod }) => latestPeriod != null || visibleTickers.has(normalizeTicker(id)));
}

export function getRevealed(userId) {
  if (!userId) return [];
  try {
    const tickers = JSON.parse(localStorage.getItem(openedKey(userId)));
    return Array.isArray(tickers) ? [...new Set(tickers.map(normalizeTicker).filter(Boolean))] : [];
  } catch {
    return [];
  }
}

export function addRevealed(userId, ticker) {
  const id = normalizeTicker(ticker);
  if (!userId || !id) return;
  try {
    const tickers = getRevealed(userId);
    if (!tickers.includes(id)) localStorage.setItem(openedKey(userId), JSON.stringify([...tickers, id]));
  } catch {
    // The current page is still usable when storage is unavailable.
  }
}
