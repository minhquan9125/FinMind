export function waitForRetry(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException("Đã hủy", "AbortError")); };
    if (signal?.aborted) return reject(new DOMException("Đã hủy", "AbortError"));
    const timer = setTimeout(() => { signal?.removeEventListener("abort", abort); resolve(); }, milliseconds);
    signal?.addEventListener("abort", abort, { once: true });
  });
}

export async function retryRateLimited(action, signal, wait = waitForRetry) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (signal?.aborted) throw new DOMException("Đã hủy", "AbortError");
    try { return await action(); } catch (error) {
      if (error.status !== 429 || attempt === 3) throw error;
      const seconds = Number(error.retryAfter) || 5;
      if (seconds > 60) throw error;
      await wait(Math.max(1, seconds) * 1000, signal);
    }
  }
}

export async function loadCompanyNews({ symbol, signal, api, onResult, onError, onSettled }) {
  try {
    try {
      const saved = await api.read(symbol, signal);
      if (signal.aborted) return;
      onResult(saved);
    } catch (error) {
      if (signal.aborted || error.name === "AbortError") return;
    }
    const fresh = await api.refresh(symbol, signal);
    if (signal.aborted) return;
    onResult(fresh);
    if (fresh.refresh?.stale) onError(fresh.refresh.error);
  } catch (error) {
    if (!signal.aborted && error.name !== "AbortError") onError(error.message);
  } finally {
    if (!signal.aborted) onSettled();
  }
}
