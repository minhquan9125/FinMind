import { useEffect, useMemo, useRef, useState } from "react";
import { CandlestickSeries, createChart, HistogramSeries } from "lightweight-charts";
import { EmptyState } from "../../shared/ui/index.js";

const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const statusLabels = {
  open: "Phiên đang mở",
  closed: "Phiên đã chốt",
  pending_reconciliation: "Chờ đối soát",
};

function validBar(bar) {
  if ([bar.open, bar.high, bar.low, bar.close].some((value) => value === null || value === undefined || value === "")) return false;
  const values = [bar.open, bar.high, bar.low, bar.close].map(Number);
  return values.every(Number.isFinite) && values[1] >= Math.max(values[0], values[3])
    && values[2] <= Math.min(values[0], values[3]);
}

function sameBar(first, second) {
  if (!first || !second) return false;
  return first.time === second.time && first.open === second.open && first.high === second.high
    && first.low === second.low && first.close === second.close && first.volume === second.volume;
}

export default function PriceHistory({ data }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candlesRef = useRef(null);
  const volumesRef = useRef(null);
  const shownRef = useRef([]);
  const barsRef = useRef([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [newerAvailable, setNewerAvailable] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const bars = useMemo(() => (data?.bars || []).filter(validBar), [data]);
  const hasBars = bars.length > 0;
  const selected = bars.find((bar) => bar.date === selectedDate) || bars.at(-1);
  const latest = bars.at(-1);

  useEffect(() => {
    if (!hasBars || !containerRef.current) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: { background: { color: "#ffffff" }, textColor: "#64748b", attributionLogo: false },
      grid: { vertLines: { color: "#f1f5f9" }, horzLines: { color: "#e2e8f0" } },
      timeScale: { borderColor: "#cbd5e1", timeVisible: false, rightOffset: 2 },
      rightPriceScale: { borderColor: "#cbd5e1" },
      crosshair: { mode: 0 },
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#0d9488", downColor: "#f43f5e", borderVisible: false,
      wickUpColor: "#0d9488", wickDownColor: "#f43f5e",
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.28 } });
    const volumes = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume", priceFormat: { type: "volume" },
      priceLineVisible: false, lastValueVisible: false,
    });
    volumes.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
    const selectBar = (point) => {
      if (!point.time) return;
      const date = typeof point.time === "string" ? point.time : `${point.time.year}-${String(point.time.month).padStart(2, "0")}-${String(point.time.day).padStart(2, "0")}`;
      if (barsRef.current.some((bar) => bar.date === date)) setSelectedDate(date);
    };
    chart.subscribeCrosshairMove(selectBar);
    chart.subscribeClick(selectBar);
    const resize = new ResizeObserver(() => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight }));
    resize.observe(container);
    chartRef.current = chart;
    candlesRef.current = candles;
    volumesRef.current = volumes;
    return () => {
      resize.disconnect();
      chart.unsubscribeCrosshairMove(selectBar);
      chart.unsubscribeClick(selectBar);
      chart.remove();
      chartRef.current = null;
      candlesRef.current = null;
      volumesRef.current = null;
      shownRef.current = [];
    };
  }, [hasBars]);

  useEffect(() => {
    if (!chartRef.current || !hasBars) return;
    barsRef.current = bars;
    const next = bars.map((bar) => ({
      time: bar.date, open: Number(bar.open), high: Number(bar.high),
      low: Number(bar.low), close: Number(bar.close), volume: Number(bar.volume) || 0,
    }));
    const old = shownRef.current;
    if (old.length === next.length && old.every((bar, index) => sameBar(bar, next[index]))) return;

    const scale = chartRef.current.timeScale();
    const visible = scale.getVisibleLogicalRange();
    const atLatest = !visible || visible.to >= old.length - 0.6;
    const prefixSame = old.length > 0 && old.slice(0, -1).every((bar, index) => sameBar(bar, next[index]));
    const append = next.length === old.length + 1 && old.every((bar, index) => sameBar(bar, next[index]));
    const updateLast = next.length === old.length && prefixSame && old.at(-1)?.time === next.at(-1)?.time;

    if (append || updateLast) {
      const last = next.at(-1);
      candlesRef.current.update(last);
      volumesRef.current.update({ time: last.time, value: last.volume, color: last.close >= last.open ? "rgba(13,148,136,.55)" : "rgba(244,63,94,.55)" });
    } else {
      candlesRef.current.setData(next);
      volumesRef.current.setData(next.map((bar) => ({ time: bar.time, value: bar.volume, color: bar.close >= bar.open ? "rgba(13,148,136,.55)" : "rgba(244,63,94,.55)" })));
    }
    shownRef.current = next;
    if (!old.length) {
      scale.setVisibleLogicalRange({ from: Math.max(0, next.length - 30) - 0.5, to: next.length - 0.5 });
    } else if (atLatest) {
      scale.scrollToRealTime();
      setNewerAvailable(false);
    } else {
      if (visible) scale.setVisibleLogicalRange(visible);
      if (!sameBar(old.at(-1), next.at(-1))) setNewerAvailable(true);
    }
  }, [bars, hasBars]);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event) => { if (event.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  function showRange(count) {
    const scale = chartRef.current?.timeScale();
    if (!scale) return;
    if (count === "all") scale.fitContent();
    else scale.setVisibleLogicalRange({ from: Math.max(0, bars.length - count) - 0.5, to: bars.length - 0.5 });
    setNewerAvailable(false);
  }

  function zoom(factor) {
    const scale = chartRef.current?.timeScale();
    const visible = scale?.getVisibleLogicalRange();
    if (!visible) return;
    const center = (visible.from + visible.to) / 2;
    const half = Math.max(2, ((visible.to - visible.from) * factor) / 2);
    scale.setVisibleLogicalRange({ from: center - half, to: center + half });
  }

  function goToLatest() {
    chartRef.current?.timeScale().scrollToRealTime();
    setNewerAvailable(false);
    setSelectedDate(null);
  }

  if (!data?.bars?.length) return <EmptyState title="Chưa có dữ liệu giá đã lưu cho mã này" />;
  if (!hasBars) return <EmptyState title="Chưa có nến OHLC hợp lệ để vẽ biểu đồ" />;

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-600">Nguồn: {latest.source || data.source || "Chưa rõ"} · Nến ngày 1D · {bars.length} phiên · Gần nhất: {latest.date}{data.price_unit === "points" ? " · Đơn vị: điểm chỉ số" : ""}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Giá đóng cửa gần nhất</p><strong className="text-lg">{number.format(Number(latest.close))}</strong></div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">Khối lượng ghi nhận</p><strong className="text-lg">{latest.volume == null ? "—" : number.format(Number(latest.volume))}</strong></div>
      </div>
      {expanded && <div className="fixed inset-0 z-40 bg-slate-900/60" onClick={() => setExpanded(false)} aria-hidden="true" />}
      <div className={expanded ? "fixed inset-3 z-50 flex flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-xl sm:inset-8" : "rounded-lg border border-slate-200 bg-white p-3"}>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => showRange(30)} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">30 phiên</button>
            <button type="button" onClick={() => showRange(90)} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">90 phiên</button>
            <button type="button" onClick={() => showRange("all")} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">Tất cả</button>
            <button type="button" onClick={() => zoom(0.75)} aria-label="Phóng to biểu đồ" className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">＋</button>
            <button type="button" onClick={() => zoom(1.3)} aria-label="Thu nhỏ biểu đồ" className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">－</button>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={goToLatest} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">{newerAvailable ? "Có dữ liệu mới · Về mới nhất" : "Về mới nhất"}</button>
            <button type="button" onClick={() => setExpanded((value) => !value)} className="rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50">{expanded ? "Thu gọn" : "Mở rộng"}</button>
          </div>
        </div>
        <div ref={containerRef} className={expanded ? "min-h-0 w-full flex-1" : "h-[420px] w-full"} aria-label={`Biểu đồ nến và khối lượng ${data.symbol}`} />
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700">
          <strong>{selected.date}</strong><span>{statusLabels[selected.status] || "Trạng thái chưa rõ"}</span>
          <span>Mở: {number.format(Number(selected.open))}</span><span>Cao: {number.format(Number(selected.high))}</span><span>Thấp: {number.format(Number(selected.low))}</span><span>Đóng: {number.format(Number(selected.close))}</span><span>KL: {selected.volume == null ? "—" : number.format(Number(selected.volume))}</span>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">Cuộn chuột để zoom, kéo ngang để xem lịch sử · TradingView Lightweight Charts™ · © 2025 <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer" className="underline">TradingView, Inc.</a></p>
      </div>
      <p className="text-xs text-amber-700">Dữ liệu đã lưu; trạng thái phiên gần nhất: {statusLabels[latest.status] || "Chưa rõ"}. Đơn vị và cơ sở điều chỉnh giá/khối lượng chưa được xác nhận. Không phải giá realtime từng giao dịch.</p>
    </div>
  );
}
