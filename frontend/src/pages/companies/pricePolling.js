import { getSavedOhlcv, watchLivePrice, unwatchLivePrice, loadStockHistory } from "./marketDataApi.js";

// Each visible chart owns a lease; GETs never directly fetch from the provider.
export function startPricePolling({ symbol, onResult, onError, onChecked, onSettled, onHistoryLoading = () => {},
  document = globalThis.document, timers = globalThis,
  viewerId = globalThis.crypto.randomUUID(),
  api = { read: getSavedOhlcv, watch: watchLivePrice, unwatch: unwatchLivePrice, prepare: loadStockHistory } }) {
  let stopped = false;
  let timer;
  let controller;
  let etag = null;
  let failures = 0;
  let inFlight = false;
  let prepared = false;
  let historyError = null;

  const release = () => { api.unwatch(viewerId).catch(() => {}); };

  async function checkPrice() {
    if (stopped || document.hidden || inFlight) return;
    inFlight = true;
    controller = new AbortController();
    try {
      if (!prepared && api.prepare) {
        onHistoryLoading(true);
        // Show the saved chart immediately, then backfill before registering live quotes.
        try {
          const saved = await api.read(symbol, controller.signal, etag);
          if (stopped || document.hidden) return;
          if (!saved.unchanged) { etag = saved.etag; onResult(saved.data); }
        } catch (error) { if (error.name === "AbortError") throw error; }
        try { await api.prepare(symbol, controller.signal); }
        catch (error) {
          if (error.name === "AbortError") throw error;
          historyError = `Chưa tải đủ lịch sử: ${error.message}`;
        }
        if (stopped || document.hidden) return;
        prepared = true;
        onHistoryLoading(false);
      }
      // Renew together with each visible chart check; server leases expire if checks stop.
      // Failing lease registration must not prevent displaying saved history.
      let registrationError = null;
      await api.watch(viewerId, symbol, controller.signal).catch((error) => {
        if (error.name === "AbortError") throw error;
        registrationError = `Chưa bật được tự cập nhật giá: ${error.message}`;
      });
      if (stopped || document.hidden) return;
      const result = await api.read(symbol, controller.signal, etag);
      if (stopped || document.hidden) return;
      if (!result.unchanged) {
        etag = result.etag;
        onResult(result.data);
      }
      onChecked(new Date().toISOString());
      if (registrationError || historyError) onError(registrationError || historyError);
      failures = registrationError ? failures + 1 : 0;
    } catch (error) {
      if (stopped || error.name === "AbortError") return;
      onError(error.message);
      failures += 1;
    } finally {
      inFlight = false;
      if (!stopped) {
        onHistoryLoading(false);
        onSettled();
        if (!document.hidden) timer = timers.setTimeout(checkPrice, Math.min(30000, 5000 * (2 ** failures)));
      }
    }
  }

  function visibilityChanged() {
    timers.clearTimeout(timer);
    if (document.hidden) {
      controller?.abort();
      release();
    } else checkPrice();
  }

  document.addEventListener("visibilitychange", visibilityChanged);
  if (!document.hidden) checkPrice();
  return () => {
    stopped = true;
    timers.clearTimeout(timer);
    controller?.abort();
    release();
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}
