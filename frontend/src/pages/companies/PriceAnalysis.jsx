// Price / volume / foreign-flow analysis. Every figure comes from the API as supplied;
// nothing financial is recomputed here.
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { getPriceAnalysis } from "./marketDataApi.js";

const WARNINGS = {
  unadjusted_prices: "Giá chưa điều chỉnh theo sự kiện doanh nghiệp.",
  stale_prices: "Giá đã lưu chưa cập nhật đến ngày yêu cầu.",
  incomplete_price_metrics: "Chưa đủ phiên để tính một số chỉ tiêu giá.",
  prices_source_not_approved: "Nguồn giá chưa được phê duyệt.",
  activity_source_not_approved: "Nguồn khối ngoại chưa được phê duyệt.",
  benchmark_source_not_approved: "Nguồn VNINDEX chưa được phê duyệt.",
  prices_missing_provenance: "Một số phiên giá thiếu thông tin truy nguồn.",
  activity_pending_latest_observation: "Số liệu khối ngoại gần nhất chưa được đối soát cuối ngày.",
  activity_incomplete_window: "Chưa đủ phiên khối ngoại/giá trị giao dịch đã đối soát để cộng theo kỳ.",
  activity_storage_unavailable: "Chưa có bảng lưu dữ liệu giao dịch theo ngày.",
  benchmark_incomplete_window: "VNINDEX thiếu phiên trùng ngày nên chưa so sánh được một số kỳ.",
};

function Num({ value, unit = "", digits = 2 }) {
  if (value == null) return <span className="font-normal text-slate-400">Chưa đủ dữ liệu</span>;
  // Display rounding only; the exact API figure stays in the tooltip.
  return <span title={`${value}${unit}`}>{Number(value).toLocaleString("vi-VN", { maximumFractionDigits: digits })}{unit}</span>;
}

function Item({ label, children, note }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-slate-900">{children}</dd>
      {note && <p className="mt-1 text-[11px] text-slate-500">{note}</p>}
    </div>
  );
}

function Section({ title, children }) {
  return <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>{children}</section>;
}

const TREND_LABELS = {
  UP: ["Tăng", "success"], DOWN: ["Giảm", "error"], SIDEWAYS: ["Đi ngang/tích lũy", "info"],
  UNCLEAR: ["Chưa rõ xu hướng", "neutral"], INSUFFICIENT_DATA: ["Chưa đủ dữ liệu", "neutral"],
};
const HORIZON_NAMES = { "20": "Ngắn hạn", "60": "Trung hạn", "200": "Dài hạn" };

function vnd(value, scale) {
  return `${(Number(value) * scale).toLocaleString("vi-VN", { maximumFractionDigits: 0 })} VND`;
}

export function TrendSection({ trend }) {
  if (!trend) return <p className="text-xs text-slate-500">Chưa tính được xu hướng giá từ dữ liệu đã lưu.</p>;
  const { context, source } = trend;
  return (
    <Section title={`Xu hướng giá · tính đến ${trend.as_of}`}>
      <dl className="grid gap-3 sm:grid-cols-3">
        {Object.entries(trend.horizons).map(([sessions, item]) => {
          const [label, tone] = TREND_LABELS[item.label] || TREND_LABELS.UNCLEAR;
          const actions = item.reasons.filter((code) => code.startsWith("possible_corporate_action:")).map((code) => code.split(":")[1]);
          return (
            <div key={sessions} className="rounded-lg border border-slate-200 p-3">
              <dt className="flex items-center justify-between gap-2 text-xs text-slate-500">
                <span>{HORIZON_NAMES[sessions] || `${sessions} phiên`} · {sessions} phiên</span>
                <StatusBadge tone={tone}>{label}</StatusBadge>
              </dt>
              {item.return_percent != null ? (
                <dd className="mt-2 space-y-1 text-xs text-slate-700">
                  <p>Lợi suất <Num value={item.return_percent} unit="%" /> · {trend.benchmark} {item.index_return_percent != null ? <Num value={item.index_return_percent} unit="%" /> : <span className="text-slate-400">chưa đủ dữ liệu</span>}</p>
                  <p>Giá so với SMA{sessions} <Num value={item.close_vs_sma_percent} unit="%" /> · độ dốc SMA <Num value={item.slope_percent} unit="%" /></p>
                  <p>Biên độ cao–thấp <Num value={item.range_percent} unit="%" /></p>
                  {actions.length > 0 && <p className="text-amber-700">Có ngày biến động vượt biên độ sàn ({actions.join(", ")}), có thể do chia tách/cổ tức cổ phiếu.</p>}
                </dd>
              ) : <dd className="mt-2 text-xs text-slate-500">Cần thêm phiên giao dịch để tính.</dd>}
            </div>
          );
        })}
      </dl>
      <p className="mt-2 text-[11px] text-slate-500">
        {context.high_52w != null && <>Đỉnh 52 tuần {vnd(context.high_52w, source.price_scale)} ({context.high_52w_date}) · đáy {vnd(context.low_52w, source.price_scale)} ({context.low_52w_date}) · </>}
        {context.rsi14 != null && <>RSI14 <Num value={context.rsi14} /> · </>}
        {context.volume20_vs_volume60 != null && <>KL TB20/TB60 <Num value={context.volume20_vs_volume60} unit=" lần" /> · </>}
        Mô tả từ dữ liệu giá đã lưu, không phải khuyến nghị.
      </p>
    </Section>
  );
}

function coverage(window) {
  return window.status === "complete" ? `Đủ ${window.required_sessions} phiên`
    : `Chưa đủ dữ liệu: ${window.available_sessions}/${window.required_sessions} phiên`;
}

export function PriceAnalysisResult({ data }) {
  if (!data || data.status === "no_data" || !data.metrics) return <EmptyState title="Chưa có dữ liệu giá đã lưu để phân tích" />;
  const { metrics, freshness, activity, benchmark } = data;
  const latest = activity?.latest_observation;
  const source = data.sources?.prices?.at(-1);
  const notes = [...new Set((data.warnings || []).map((code) => WARNINGS[code.split(":")[0]]).filter(Boolean))];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>Tính đến phiên <strong className="text-slate-900">{data.as_of}</strong> · {data.session_count} phiên từ {data.first_date} · Ngày yêu cầu {data.requested_as_of}</span>
        <StatusBadge tone={data.status === "ok" ? "success" : "warning"}>{data.status === "ok" ? "Đủ dữ liệu" : "Thiếu một phần dữ liệu"}</StatusBadge>
        {freshness?.stale && <StatusBadge tone="warning">Dữ liệu cũ {freshness.staleness_calendar_days} ngày</StatusBadge>}
        {metrics.is_adjusted === false && <StatusBadge>Giá chưa điều chỉnh</StatusBadge>}
      </div>

      <TrendSection trend={data.trend} />

      <Section title="Giá và khối lượng">
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Item label="Giá đóng cửa"><Num value={metrics.close_vnd} unit=" VND" digits={0} /></Item>
          <Item label="Lợi suất 1 phiên"><Num value={metrics.return_1_percent} unit="%" /></Item>
          <Item label="Lợi suất 5 phiên"><Num value={metrics.return_5_percent} unit="%" /></Item>
          <Item label="Lợi suất 20 phiên"><Num value={metrics.return_20_percent} unit="%" /></Item>
          <Item label="So với SMA20" note="Giá đóng cửa so với bình quân 20 phiên"><Num value={metrics.close_vs_sma20_percent} unit="%" /></Item>
          <Item label="Biên độ phiên" note="(Cao − thấp) / đóng cửa phiên trước"><Num value={metrics.intraday_range_percent} unit="%" /></Item>
          <Item label="Khối lượng phiên" note="Cổ phiếu"><Num value={metrics.volume} digits={0} /></Item>
          <Item label="So với TB 20 phiên trước" note="Không gồm phiên hiện tại"><Num value={metrics.volume_vs_prior20} unit=" lần" /></Item>
          <Item label="Biến động 20 phiên" note="Độ lệch chuẩn lợi suất ngày, chưa quy năm"><Num value={metrics.daily_volatility20_percent} unit="%" /></Item>
          <Item label="KL bình quân 5 phiên gần nhất"><Num value={metrics.average_volume_latest5} digits={0} /></Item>
          <Item label="KL bình quân 5 phiên trước đó"><Num value={metrics.average_volume_prior5} digits={0} /></Item>
        </dl>
      </Section>

      <Section title={`So với ${benchmark?.index_symbol || "VNINDEX"}`}>
        <dl className="grid gap-3 sm:grid-cols-3">
          {Object.entries(benchmark?.windows || {}).map(([sessions, window]) => (
            <Item key={sessions} label={`${sessions} phiên`} note={coverage(window)}>
              Cổ phiếu <Num value={window.stock_return_percent} unit="%" /> · Chỉ số <Num value={window.return_percent} unit="%" /> · Chênh <Num value={window.difference_percentage_points} unit=" điểm %" />
            </Item>
          ))}
        </dl>
      </Section>

      <Section title="Khối ngoại và giá trị giao dịch">
        {latest ? (
          <div className="mb-3 rounded-lg border border-slate-200 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>Quan sát gần nhất · ngày <strong className="text-slate-900">{latest.trade_date}</strong></span>
              <StatusBadge tone={latest.observation_status === "after_close" ? "info" : "warning"}>{latest.observation_status === "after_close" ? "Sau đóng cửa" : "Trong phiên"}</StatusBadge>
              <StatusBadge tone={latest.quality_status === "validated" ? "success" : "warning"}>{latest.quality_status === "validated" ? "Đã đối soát" : "Chờ đối soát"}</StatusBadge>
            </div>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Item label="Khối ngoại mua" note="Cổ phiếu"><Num value={latest.foreign_buy_volume} digits={0} /></Item>
              <Item label="Khối ngoại bán" note="Cổ phiếu"><Num value={latest.foreign_sell_volume} digits={0} /></Item>
              <Item label="Khối ngoại ròng" note="Mua − bán, cổ phiếu"><Num value={latest.foreign_net_volume} digits={0} /></Item>
              <Item label="Giá trị giao dịch" note={latest.value_basis === "unknown" ? "Chưa rõ gồm thỏa thuận hay không" : null}><Num value={latest.total_value_vnd} unit=" VND" digits={0} /></Item>
              <Item label="Giá trị khối ngoại ròng"><Num value={latest.foreign_net_value_vnd} unit=" VND" digits={0} /></Item>
            </dl>
            <p className="mt-2 text-[11px] text-slate-500">
              Nguồn {latest.source_name || "chưa rõ"}{latest.fetched_at ? ` · lấy lúc ${new Date(latest.fetched_at).toLocaleString("vi-VN")}` : ""}
              {latest.quality_status !== "validated" && " · Số tích lũy tại thời điểm lấy, chưa phải số chốt cuối ngày."}
            </p>
          </div>
        ) : <p className="mb-3 text-xs text-slate-500">Chưa có quan sát khối ngoại nào được lưu cho mã này.</p>}
        <dl className="grid gap-3 sm:grid-cols-3">
          {Object.entries(activity?.windows || {}).map(([sessions, window]) => (
            <Item key={sessions} label={`Cộng ${sessions} phiên đã đối soát`} note={coverage(window)}>
              Ròng <Num value={window.foreign_net_volume} unit=" cp" digits={0} /> · GTGD <Num value={window.total_value_vnd} unit=" VND" digits={0} />
            </Item>
          ))}
        </dl>
      </Section>

      <div className="space-y-1 rounded-lg bg-slate-50 p-3 text-[11px] text-slate-500">
        {source && <p>Nguồn giá: {source.source_name || "chưa rõ"} · {source.approval_status === "APPROVED" ? "Đã phê duyệt" : "Chưa phê duyệt"} · phiên {source.trade_date} · bản ghi gốc {source.payload_id || "chưa rõ"}</p>}
        {notes.map((note) => <p key={note}>• {note}</p>)}
        <p>Số liệu mô tả từ dữ liệu đã lưu, không phải khuyến nghị mua bán.</p>
      </div>
    </div>
  );
}

export default function PriceAnalysis({ symbol }) {
  const [state, setState] = useState({ symbol });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ symbol });
    getPriceAnalysis(symbol, undefined, controller.signal)
      .then((data) => setState({ symbol, data }))
      .catch((error) => { if (error.name !== "AbortError") setState({ symbol, error }); });
    return () => controller.abort();
  }, [symbol, retry]);

  // A late response for the previous ticker is never shown under the current one.
  const { data, error } = state.symbol === symbol ? state : {};
  if (error?.status === 404) return <EmptyState title="Chưa có dữ liệu giá đã lưu để phân tích" />;
  if (error) return <ErrorState message={error.message} onRetry={() => setRetry((count) => count + 1)} />;
  if (!data) return <Skeleton rows={3} />;
  return <PriceAnalysisResult data={data} />;
}
