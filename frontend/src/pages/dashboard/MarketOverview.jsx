import { useEffect, useRef, useState } from "react";
import { Card, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getIndexHistory } from "../companies/marketDataApi.js";
import PriceHistory from "../companies/PriceHistory.jsx";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { loadMarketIndices, refreshIndex } from "./marketIndices.js";
import { Link } from "../../app/router.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";

const indices = [
  ["VNINDEX", "VN-INDEX"],
  ["VN30", "VN30"],
  ["HNXINDEX", "HNX-INDEX"],
  ["UPCOMINDEX", "UPCOM-INDEX"],
];
const api = {
  cached: (symbol, signal) => getIndexHistory(symbol, signal, { cached: true }),
  refresh: getIndexHistory,
};
const stamp = (value) =>
  value
    ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
    : "Chưa có bản lưu";

const number = (value) =>
  Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 2 });
function movement(bars = []) {
  const last = bars.at(-1),
    previous = bars.at(-2);
  if (
    !last ||
    !previous ||
    !Number.isFinite(Number(last.close)) ||
    !Number.isFinite(Number(previous.close)) ||
    Number(previous.close) === 0
  )
    return null;
  const change = Number(last.close) - Number(previous.close);
  return { change, percent: (change / Number(previous.close)) * 100 };
}
function Sparkline({ bars, positive }) {
  const values = bars
    .slice(-30)
    .map((bar) => Number(bar.close))
    .filter(Number.isFinite);
  if (values.length < 2) return null;
  const min = Math.min(...values),
    span = Math.max(...values) - min || 1;
  return (
    <svg
      className="approved-index-spark"
      viewBox="0 0 60 28"
      aria-hidden="true"
    >
      <polyline
        points={values
          .map(
            (value, i) =>
              `${(i / (values.length - 1)) * 60},${25 - ((value - min) / span) * 22}`,
          )
          .join(" ")}
        fill="none"
        stroke={positive ? "#149d83" : "#df5f79"}
        strokeWidth="1.5"
      />
    </svg>
  );
}
export default function MarketOverview({ watchlistCount = null }) {
  const { user } = useAuth();
  const [symbol, setSymbol] = useState("VNINDEX"),
    [data, setData] = useState({}),
    [errors, setErrors] = useState({}),
    [pending, setPending] = useState({});
  const selected = useRef(symbol),
    controller = useRef(null);
  selected.current = symbol;
  const callbacks = {
    onResult: (id, result) => setData((value) => ({ ...value, [id]: result })),
    onError: (id, error) =>
      setErrors((value) => ({ ...value, [id]: error?.message || null })),
    onPending: (id, status) =>
      setPending((value) => ({ ...value, [id]: status })),
  };
  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    setData({});
    setErrors({});
    setPending({});
    loadMarketIndices({
      symbols: indices.map(([id]) => id),
      getPriority: () => selected.current,
      api,
      signal: abort.signal,
      ...callbacks,
    });
    return () => abort.abort();
  }, [user?.id]);
  const current = data[symbol],
    busy = pending[symbol]?.loading,
    waiting = pending[symbol]?.waitSeconds;
  const hasBars = !!current?.bars?.length;
  const moves = indices.map(([id]) => movement(data[id]?.bars)).filter(Boolean);
  const rising = moves.filter((move) => move.change > 0).length,
    falling = moves.filter((move) => move.change < 0).length;
  const currentMove = movement(current?.bars);
  return (
    <section
      aria-label="Tổng quan thị trường"
      className="approved-market-overview"
    >
      <div className="approved-session">
        <div className="market-summary">
          <div className="market-summary-heading">
            <span className="market-summary-icon" aria-hidden="true">
              <AppIcon name="compare" />
            </span>
            <div>
              <h2>Tóm tắt phiên</h2>
              <p>
                Diễn biến chỉ số và biến động đáng chú ý trong danh sách theo
                dõi.
              </p>
            </div>
          </div>
          <div className="market-summary-breadth">
            <div className="market-breadth-counts">
              <span className="market-count-up">
                <i aria-hidden="true" />
                <strong>{moves.length ? rising : "—"}</strong> tăng
              </span>
              <span className="market-count-down">
                <i aria-hidden="true" />
                <strong>{moves.length ? falling : "—"}</strong> giảm
              </span>
            </div>
            <div className="market-breadth-track" aria-hidden="true">
              {moves.map((move, i) => (
                <i
                  key={i}
                  className={
                    move.change > 0 ? "up" : move.change < 0 ? "down" : "flat"
                  }
                />
              ))}
            </div>
          </div>
          <div className="market-summary-mover">
            <Link to="/watchlist">
              <span className="market-mover-copy">
                <small>Danh sách theo dõi của bạn</small>
                <span>
                  <strong>{watchlistCount ?? "—"}</strong>
                  <b>doanh nghiệp</b>
                </span>
              </span>
              <span className="market-mover-arrow">
                <AppIcon name="arrow" />
              </span>
            </Link>
          </div>
        </div>
        <div className="approved-index-grid">
          {indices.map(([id, name]) => {
            const bars = data[id]?.bars || [],
              last = bars.at(-1),
              move = movement(bars);
            return (
              <button
                key={id}
                type="button"
                aria-pressed={symbol === id}
                onClick={() => setSymbol(id)}
                className="approved-index-tile"
              >
                <span className="approved-index-name">{name}</span>
                <strong className="approved-index-value">
                  {last ? number(last.close) : "—"}
                </strong>
                <span
                  className={`approved-index-change ${move && move.change < 0 ? "negative" : "positive"}`}
                >
                  {move
                    ? `${move.change > 0 ? "+" : ""}${number(move.change)} (${move.percent > 0 ? "+" : ""}${number(move.percent)}%)`
                    : pending[id]?.loading
                      ? "Đang tải…"
                      : "Chưa đủ dữ liệu"}
                </span>
                <span className="approved-index-date">
                  {last ? `Phiên ${last.date}` : "Chưa có dữ liệu phiên"}
                  {last && pending[id]?.loading ? " · Cập nhật…" : ""}
                </span>
                <Sparkline bars={bars} positive={!move || move.change >= 0} />
              </button>
            );
          })}
        </div>
      </div>
      <Card
        className="approved-market-chart"
        title={`Diễn biến chỉ số · ${indices.find(([id]) => id === symbol)[1]}`}
      >
        {hasBars && (
          <div className="approved-chart-summary">
            <strong>{number(current.bars.at(-1).close)}</strong>
            {currentMove && (
              <span
                className={currentMove.change < 0 ? "negative" : "positive"}
              >
                {currentMove.percent > 0 ? "+" : ""}
                {number(currentMove.percent)}%
              </span>
            )}
          </div>
        )}
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <span>Nguồn cập nhật: {stamp(current?.fetched_at)}</span>
          <button
            type="button"
            disabled={busy || !controller.current}
            className="text-blue-700 disabled:opacity-50"
            onClick={() =>
              refreshIndex(symbol, {
                api,
                signal: controller.current.signal,
                ...callbacks,
              })
            }
          >
            {busy ? "Đang cập nhật…" : "Làm mới chỉ số"}
          </button>
        </div>
        {busy && (
          <p
            role="status"
            className="mb-3 rounded-lg bg-blue-50 p-3 text-xs text-blue-800"
          >
            {waiting
              ? `Nguồn đang giới hạn lượt gọi; tự thử lại sau ${waiting} giây.`
              : hasBars
                ? "Đang cập nhật ở nền, vẫn giữ biểu đồ đã lưu."
                : "Đang lấy dữ liệu lần đầu. Nguồn dùng chung được gọi lần lượt."}
          </p>
        )}
        {hasBars ? (
          <>
            {errors[symbol] && (
              <p
                role="status"
                className="mb-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800"
              >
                Chưa lấy được bản mới: {errors[symbol]} Đang giữ dữ liệu đã lưu,
                ngày {current.bars.at(-1).date}.
              </p>
            )}
            {!busy && current.refresh?.stale && !errors[symbol] && (
              <p className="mb-3 text-xs text-amber-800">
                Đang xem bản đã lưu; chưa xác nhận dữ liệu mới nhất.
              </p>
            )}
            <PriceHistory key={symbol} data={current} variant="area" compact />
          </>
        ) : busy || (!current && !errors[symbol]) ? (
          <Skeleton rows={4} />
        ) : (
          <ErrorState
            message={errors[symbol] || "Chưa có dữ liệu chỉ số."}
            onRetry={() =>
              refreshIndex(symbol, {
                api,
                signal: controller.current.signal,
                ...callbacks,
              })
            }
          />
        )}
      </Card>
    </section>
  );
}
