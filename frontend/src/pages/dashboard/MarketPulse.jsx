// Ba khối "nhịp thị trường" cho trang Tổng quan (giao diện xanh biển & trắng):
//   <TickerTape />     băng giá chạy ngang, có nút tạm dừng
//   <SectorHeatmap />  bản đồ nhiệt 10 mã, ô to = vốn hóa lớn
//   <SessionRing />    vòng tiến độ phiên HOSE theo giờ thật (hỗ trợ ?fin-time=HH:MM)
// Dữ liệu giá là minh họa (pulseMock.js). Style nằm trong shared/ui/oceanTheme.css.
import { useEffect, useState } from "react";
import { Link } from "../../app/router.jsx";
import { finNow, getMarketStatus } from "../../components/mascot/timeTalk.js";
import { PULSE_SECTORS, pulseBreadth, pulseCompanies, pulseIndices } from "./pulseMock.js";

const num2 = new Intl.NumberFormat("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFmt = new Intl.NumberFormat("vi-VN");
const timeFmt = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" });

const tone = (change) => (change > 0 ? "up" : change < 0 ? "down" : "ref");
const arrow = (change) => (change > 0 ? "▲" : change < 0 ? "▼" : "■");
const signed = (change) => `${change > 0 ? "+" : change < 0 ? "−" : ""}${num2.format(Math.abs(change))}%`;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/* ---------------- Băng giá ---------------- */

export function TickerTape() {
  const [paused, setPaused] = useState(prefersReducedMotion);
  const items = [...pulseIndices, ...pulseCompanies];
  const row = (hidden) => items.map((item) => (
    <span className="ocean-tape-item" key={`${hidden ? "b" : "a"}-${item.code}`} aria-hidden={hidden || undefined}>
      <b translate="no">{item.code}</b>
      <span>{num2.format(item.price)}</span>
      <span className={`ocean-tape-${tone(item.change)}`}>{arrow(item.change)} {signed(item.change)}</span>
    </span>
  ));

  return (
    <div className="ocean-tape" role="region" aria-label="Băng giá (dữ liệu minh họa)">
      <div className="ocean-tape-view">
        <div className={`ocean-tape-track${paused ? " is-paused" : ""}`}>{row(false)}{row(true)}</div>
      </div>
      <button type="button" className="ocean-tape-btn" onClick={() => setPaused((value) => !value)}
        aria-pressed={paused} aria-label={paused ? "Chạy băng giá" : "Tạm dừng băng giá"}>
        {paused
          ? <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 5v14l12-7z" /></svg>
          : <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 5h4v14H7zM13 5h4v14h-4z" /></svg>}
      </button>
    </div>
  );
}

/* ---------------- Bản đồ nhiệt ---------------- */

function tileColor(change) {
  if (change >= 1.5) return { background: "#0B6E40", color: "#fff" };
  if (change >= 0.5) return { background: "#2E9E62", color: "#fff" };
  if (change > 0) return { background: "#BFE6CF", color: "#0B4D2E" };
  if (change === 0) return { background: "#FCEFC2", color: "#6B4E00" };
  if (change > -0.8) return { background: "#F6C9CC", color: "#7A1A20" };
  return { background: "#C8333B", color: "#fff" };
}

export function SectorHeatmap() {
  const [picked, setPicked] = useState(pulseCompanies[1].code);
  const current = pulseCompanies.find((company) => company.code === picked) || pulseCompanies[0];

  return (
    <section className="ocean-card ocean-heat-card" aria-labelledby="ocean-heat-title">
      <div className="ocean-card-head">
        <h2 id="ocean-heat-title">Bản đồ nhiệt</h2>
        <span>Ô to = vốn hóa lớn · minh họa</span>
      </div>
      <div className="ocean-heat" role="group" aria-label={`Bản đồ nhiệt ${pulseCompanies.length} mã`} translate="no">
        {pulseCompanies.map((company) => (
          <button type="button" key={company.code}
            className={`ocean-tile ${company.tile.split(" ").filter(Boolean).map((size) => `ocean-${size}`).join(" ")}`}
            style={tileColor(company.change)} aria-pressed={picked === company.code}
            aria-label={`${company.code} ${signed(company.change)}`} onClick={() => setPicked(company.code)}>
            <b>{company.code}</b>
            <small>{signed(company.change)}</small>
          </button>
        ))}
      </div>
      <div className="ocean-heat-pick" aria-live="polite">
        <span className="ocean-logo" translate="no">{current.code}</span>
        <div>
          <strong>{current.name} <em className={`ocean-${tone(current.change)}`}>{signed(current.change)}</em></strong>
          <span>{PULSE_SECTORS[current.sector]} · {current.note}</span>
        </div>
        <Link to={`/companies/${current.code}`}>Chi tiết</Link>
      </div>
    </section>
  );
}

/* ---------------- Nhịp phiên HOSE ---------------- */

const RING = 2 * Math.PI * 44;
const SESSION_TEXT = {
  weekend: "Cuối tuần, thị trường nghỉ",
  pre: "Trước giờ mở cửa (9:00)",
  ato: "Đang phiên ATO",
  open: "Đang giao dịch",
  lunch: "Đang nghỉ trưa",
  atc: "Đang phiên ATC",
  closed: "Phiên hôm nay đã kết thúc",
};

// Tỷ lệ thời gian giao dịch đã qua: 9:00–11:30 (150 phút) + 13:00–14:45 (105 phút)
function tradedRatio(date) {
  const day = date.getDay();
  if (day === 0 || day === 6) return 0;
  const minutes = date.getHours() * 60 + date.getMinutes();
  const morning = Math.max(0, Math.min(minutes, 690) - 540);
  const afternoon = Math.max(0, Math.min(minutes, 885) - 780);
  return Math.min(1, (morning + afternoon) / 255);
}

export function SessionRing() {
  const [now, setNow] = useState(finNow);
  useEffect(() => {
    const timer = setInterval(() => setNow(finNow()), 30_000);
    return () => clearInterval(timer);
  }, []);

  const status = getMarketStatus(now);
  const ratio = tradedRatio(now);
  const percent = Math.round(ratio * 100);
  const live = ["ato", "open", "atc"].includes(status.key);

  return (
    <section className="ocean-card ocean-session" aria-labelledby="ocean-session-title">
      <div className="ocean-card-head">
        <h2 id="ocean-session-title">Nhịp phiên HOSE</h2>
        <span className={`ocean-live${live ? " is-live" : ""}`}>{timeFmt.format(now)}</span>
      </div>
      <div className="ocean-session-body">
        <svg width="104" height="104" viewBox="0 0 104 104" role="img" aria-label={`Đã qua ${percent}% thời gian giao dịch`}>
          <circle cx="52" cy="52" r="44" fill="none" stroke="#EAF1FD" strokeWidth="12" />
          <circle cx="52" cy="52" r="44" fill="none" stroke="#0A5BD6" strokeWidth="12" strokeLinecap="round"
            strokeDasharray={`${(ratio * RING).toFixed(1)} ${RING.toFixed(1)}`} transform="rotate(-90 52 52)" />
          <text x="52" y="50" textAnchor="middle" fontSize="20" fontWeight="800" fill="#0B1B33">{percent}%</text>
          <text x="52" y="68" textAnchor="middle" fontSize="10" fill="#5B6B82">phiên</text>
        </svg>
        <div className="ocean-session-text">
          <strong>{SESSION_TEXT[status.key]}</strong>
          <span>Sáng 9:00 – 11:30</span>
          <span>Chiều 13:00 – 14:30 · ATC đến 14:45</span>
        </div>
      </div>
      <div className="ocean-breadth">
        <div className="ocean-breadth-up"><b>{intFmt.format(pulseBreadth.up)}</b><small>mã tăng</small></div>
        <div className="ocean-breadth-ref"><b>{intFmt.format(pulseBreadth.flat)}</b><small>đứng giá</small></div>
        <div className="ocean-breadth-down"><b>{intFmt.format(pulseBreadth.down)}</b><small>mã giảm</small></div>
      </div>
      <p className="ocean-footnote">Chưa trừ ngày nghỉ lễ · số mã tăng/giảm là minh họa</p>
    </section>
  );
}
