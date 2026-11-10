import { useEffect, useRef, useState } from "react";
import { Card, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getIndexHistory } from "../companies/marketDataApi.js";
import PriceHistory from "../companies/PriceHistory.jsx";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { loadMarketIndices, refreshIndex } from "./marketIndices.js";

const indices = [["VNINDEX", "VN-INDEX"], ["VN30", "VN30"], ["HNXINDEX", "HNX-INDEX"], ["UPCOMINDEX", "UPCOM-INDEX"]];
const api = { cached: (symbol, signal) => getIndexHistory(symbol, signal, { cached: true }), refresh: getIndexHistory };
const stamp = value => value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Chưa có bản lưu";

export default function MarketOverview() {
  const { user } = useAuth();
  const [symbol, setSymbol] = useState("VNINDEX"), [data, setData] = useState({}), [errors, setErrors] = useState({}), [pending, setPending] = useState({});
  const selected = useRef(symbol), controller = useRef(null); selected.current = symbol;
  const callbacks = {
    onResult: (id, result) => setData(value => ({ ...value, [id]: result })),
    onError: (id, error) => setErrors(value => ({ ...value, [id]: error?.message || null })),
    onPending: (id, status) => setPending(value => ({ ...value, [id]: status })),
  };
  useEffect(() => {
    const abort = new AbortController(); controller.current = abort;
    setData({}); setErrors({}); setPending({});
    loadMarketIndices({ symbols: indices.map(([id]) => id), getPriority: () => selected.current, api, signal: abort.signal, ...callbacks });
    return () => abort.abort();
  }, [user?.id]);
  const current = data[symbol], busy = pending[symbol]?.loading, waiting = pending[symbol]?.waitSeconds;
  const hasBars = !!current?.bars?.length;
  return <section aria-label="Tổng quan thị trường" className="space-y-4">
    <h2 className="text-sm font-bold">Tổng quan thị trường</h2>
    <p className="text-xs text-slate-500">Tự tải bản đã lưu khi mở trang, rồi cập nhật lần lượt từ vnstock/KBS. Dữ liệu ngày; không phải giá từng giao dịch.</p>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {indices.map(([id, name]) => { const last = data[id]?.bars?.at(-1); return <button key={id} type="button" aria-pressed={symbol === id}
        onClick={() => setSymbol(id)} className={`rounded-xl border p-4 text-left text-sm font-semibold ${symbol === id ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 bg-white hover:border-blue-300"}`}>
        {name}<span className="mt-2 block text-xs font-normal">{last ? `${Number(last.close).toLocaleString("vi-VN")} điểm` : pending[id]?.loading ? "Đang tải dữ liệu…" : "Chưa có dữ liệu"}</span>
        {last && <span className="mt-1 block text-[11px] font-normal text-slate-500">Ngày dữ liệu: {last.date}{pending[id]?.loading ? " · Đang cập nhật" : ""}</span>}
      </button>; })}
    </div>
    <Card title={`Biểu đồ ${indices.find(([id]) => id === symbol)[1]}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>Nguồn cập nhật: {stamp(current?.fetched_at)}</span>
        <button type="button" disabled={busy || !controller.current} className="text-blue-700 disabled:opacity-50" onClick={() => refreshIndex(symbol, { api, signal: controller.current.signal, ...callbacks })}>{busy ? "Đang cập nhật…" : "Làm mới chỉ số"}</button></div>
      {busy && <p role="status" className="mb-3 rounded-lg bg-blue-50 p-3 text-xs text-blue-800">{waiting ? `Nguồn đang giới hạn lượt gọi; tự thử lại sau ${waiting} giây.` : hasBars ? "Đang cập nhật ở nền, vẫn giữ biểu đồ đã lưu." : "Đang lấy dữ liệu lần đầu. Nguồn dùng chung được gọi lần lượt."}</p>}
      {hasBars ? <>
        {errors[symbol] && <p role="status" className="mb-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Chưa lấy được bản mới: {errors[symbol]} Đang giữ dữ liệu đã lưu, ngày {current.bars.at(-1).date}.</p>}
        {!busy && current.refresh?.stale && !errors[symbol] && <p className="mb-3 text-xs text-amber-800">Đang xem bản đã lưu; chưa xác nhận dữ liệu mới nhất.</p>}
        <PriceHistory key={symbol} data={current} />
      </> : busy || !current && !errors[symbol] ? <Skeleton rows={4} /> : <ErrorState message={errors[symbol] || "Chưa có dữ liệu chỉ số."} onRetry={() => refreshIndex(symbol, { api, signal: controller.current.signal, ...callbacks })} />}
    </Card>
  </section>;
}
