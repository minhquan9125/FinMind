import { retryRateLimited, waitForRetry } from "../companies/companyData.js";

export async function refreshIndex(symbol, { api, signal, onResult, onError, onPending, wait = waitForRetry }) {
  if (signal.aborted) return;
  onPending(symbol, { loading: true, waitSeconds: 0 });
  try {
    const data = await retryRateLimited(async () => {
      try { return await api.refresh(symbol, signal); }
      catch (error) {
        if (!signal.aborted && error.status === 429) onPending(symbol, { loading: true, waitSeconds: Number(error.retryAfter) || 5 });
        throw error;
      }
    }, signal, wait);
    if (!signal.aborted) { onResult(symbol, data); onError(symbol, null); }
  } catch (error) {
    if (!signal.aborted && error.name !== "AbortError") onError(symbol, error);
  } finally { if (!signal.aborted) onPending(symbol, { loading: false, waitSeconds: 0 }); }
}

export async function loadMarketIndices({ symbols, getPriority, api, signal, onResult, onError, onPending, wait }) {
  const snapshots = new Map(); let denied = false;
  symbols.forEach(symbol => onPending(symbol, { loading: true, waitSeconds: 0 }));
  // These requests only read disk/memory. They do not spend provider quota.
  await Promise.all(symbols.map(async symbol => {
    try {
      const data = await api.cached(symbol, signal);
      if (!signal.aborted) { snapshots.set(symbol, data); onResult(symbol, data); }
    } catch (error) {
      if ([401, 403].includes(error.status)) denied = true;
      if (!signal.aborted && error.name !== "AbortError") onError(symbol, error);
    }
  }));
  if (signal.aborted) return;
  if (denied) { symbols.forEach(symbol => onPending(symbol, { loading: false, waitSeconds: 0 })); return; }
  const remaining = new Set(symbols);
  while (remaining.size && !signal.aborted) {
    const priority = getPriority?.();
    const symbol = remaining.has(priority) ? priority : remaining.values().next().value;
    remaining.delete(symbol);
    const cached = snapshots.get(symbol);
    if (cached?.bars?.length && cached.refresh?.needed === false) {
      onPending(symbol, { loading: false, waitSeconds: 0 }); continue;
    }
    // Fresh provider calls are sequential, including any Retry-After wait.
    await refreshIndex(symbol, { api, signal, onResult, onError, onPending, wait });
  }
}
