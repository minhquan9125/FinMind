import { useEffect, useState } from "react";
import { Card, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getIndexHistory } from "../companies/marketDataApi.js";
import PriceHistory from "../companies/PriceHistory.jsx";

const indices = [["VNINDEX", "VN-INDEX"], ["VN30", "VN30"], ["HNXINDEX", "HNX-INDEX"], ["UPCOMINDEX", "UPCOM-INDEX"]];

export default function MarketOverview() {
  const [symbol, setSymbol] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!symbol) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setData(null);
    getIndexHistory(symbol, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setData(result); })
      .catch((caught) => { if (!controller.signal.aborted) setError(caught.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [symbol, retry]);
  return <section aria-label="Tổng quan thị trường" className="space-y-4">
    <h2 className="text-sm font-bold">Tổng quan thị trường</h2>
    <p className="text-xs text-slate-500">Bấm một chỉ số để tải biểu đồ thật. Dữ liệu ngày từ vnstock/KBS; không tự cập nhật từng giao dịch.</p>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {indices.map(([id, name]) => <button key={id} type="button" aria-pressed={symbol === id}
        onClick={() => setSymbol(id)} className={`rounded-xl border p-4 text-left text-sm font-semibold ${symbol === id ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 bg-white hover:border-blue-300"}`}>
        {name}<span className="mt-2 block text-xs font-normal">{data?.symbol === id && symbol === id ? `${Number(data.bars.at(-1)?.close).toLocaleString("vi-VN")} điểm` : "Xem biểu đồ →"}</span>
      </button>)}
    </div>
    {symbol && <Card title={`Biểu đồ ${indices.find(([id]) => id === symbol)[1]}`}>
      {error ? <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} /> : loading || data?.symbol !== symbol ? <Skeleton rows={4} /> : <>
        <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
          <span>Nguồn cập nhật: {data?.fetched_at ? new Date(data.fetched_at).toLocaleString("vi-VN") : "—"}</span>
          <button type="button" className="text-blue-700" onClick={() => setRetry((value) => value + 1)}>Làm mới chỉ số</button>
        </div>
        <PriceHistory key={symbol} data={data} />
      </>}
    </Card>}
  </section>;
}
