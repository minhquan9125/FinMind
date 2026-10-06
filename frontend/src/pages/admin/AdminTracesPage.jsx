// Trang A01: Theo dõi truy vấn & Trace (route /admin/traces và /admin/traces/:traceId).
// Chọn trace bằng :traceId hoặc ?trace=; ?state=telemetry hiện màn lỗi telemetry.
// Dữ liệu minh họa lấy từ ./tracesMock.js; chuyển sang API thật chỉ cần đổi hàm getTraces.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, FilterBar, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { ACTIVE_CONFIG, ACTIVE_CORPUS, STEP_NAMES, getTraces } from "./tracesMock.js";

const DEFAULT_TRACE_ID = "TRC-DEMO-004";

// ─── Hằng số hiển thị ───────────────────────────────────────────────────────

const STATUS_TONE = {
  "Thành công": "success",
  "Không đủ bằng chứng": "warning",
  "Xác minh không đạt": "error",
  "Lỗi vận hành": "error",
  "Đang xử lý": "info",
};
const GATE_TONE = { "Đạt": "success", "Đạt một phần": "warning", "Không đạt": "error" };

const TONE = {
  success: { box: "border-emerald-200 bg-emerald-50/40", title: "text-emerald-800", text: "text-emerald-700", bar: "bg-emerald-600", pill: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  warning: { box: "border-amber-200 bg-amber-50/40", title: "text-amber-800", text: "text-amber-700", bar: "bg-amber-500", pill: "bg-amber-50 text-amber-700 border-amber-200" },
  error: { box: "border-rose-200 bg-rose-50/40", title: "text-rose-800", text: "text-rose-700", bar: "bg-rose-600", pill: "bg-rose-50 text-rose-700 border-rose-200" },
  info: { box: "border-blue-200 bg-blue-50/40", title: "text-blue-800", text: "text-blue-700", bar: "bg-blue-600", pill: "bg-blue-50 text-blue-700 border-blue-200" },
  neutral: { box: "border-slate-200 bg-slate-50", title: "text-slate-700", text: "text-slate-600", bar: "bg-slate-400", pill: "bg-slate-50 text-slate-600 border-slate-200" },
};

const STEP_STATE = {
  done: { label: "Hoàn thành", tone: "success" },
  fail: { label: "Thất bại", tone: "error" },
  run: { label: "Đang chạy", tone: "info" },
  skip: { label: "Chưa chạy", tone: "neutral" },
};

const EMPTY_FILTERS = { q: "", time: "all", status: "all", company: "all", gate: "all", verifier: "all" };

const opts = (labelAll, values) => [{ value: "all", label: labelAll }, ...values.map((v) => ({ value: v, label: v }))];

const FILTER_FIELDS = [
  { key: "q", type: "text", label: "Trace ID", placeholder: "Tìm theo Trace ID..." },
  // Dữ liệu mẫu chỉ có giờ trong ngày nên bộ lọc thời gian chưa có tác dụng (giống mockup).
  { key: "time", type: "select", label: "Thời gian", options: [
    { value: "all", label: "Tất cả hôm nay" }, { value: "1h", label: "1 giờ qua" },
    { value: "6h", label: "6 giờ qua" }, { value: "24h", label: "24 giờ qua" },
  ] },
  { key: "status", type: "select", label: "Trạng thái", options: opts("Tất cả trạng thái", Object.keys(STATUS_TONE)) },
  { key: "company", type: "select", label: "Doanh nghiệp", options: opts("Tất cả mã", ["FPT", "VCB", "MBB", "TCB", "CMG", "BID", "CTG"]) },
  { key: "gate", type: "select", label: "Evidence Gate", options: opts("Tất cả", ["Đạt", "Đạt một phần", "Không đạt", "—"]) },
  { key: "verifier", type: "select", label: "Verifier", options: opts("Tất cả", ["Đạt", "Không đạt", "—"]) },
];

// ─── Hàm tính từ dữ liệu trace (không viết cứng số liệu) ─────────────────────

const fmtNum = (n) => (n == null ? "—" : n.toLocaleString("en-US"));
const fmtMs = (n) => (n == null ? "—" : `${fmtNum(n)}ms`);
const fmtPct = (n) => (Number.isInteger(n) ? `${n}%` : `${n.toFixed(1)}%`);

function totalRealMs(t) {
  return t.steps.reduce((sum, [ms, state]) => (state !== "skip" && ms > 0 ? sum + ms : sum), 0);
}

function verifierRate(t) {
  return t.ver?.run ? (t.ver.sup / t.ver.total) * 100 : null;
}

// "Đạt" | "Không đạt" | "—" (chưa chạy)
function verifierVerdict(t) {
  const rate = verifierRate(t);
  if (rate == null) return "—";
  return rate >= t.ver.thr ? "Đạt" : "Không đạt";
}

const gateLabel = (t) => (t.gate?.run ? t.gate.st : "—");

function tokenInfo(t) {
  const { in: inTok, out: outTok, limit } = t.tok;
  if (inTok == null && outTok == null) return null;
  const total = (inTok || 0) + (outTok || 0);
  return { inTok: inTok || 0, outTok: outTok || 0, total, limit, pct: (total / limit) * 100 };
}

function isApproved(t) {
  const gateOk = t.gate?.run && (t.gate.st === "Đạt" || t.gate.st === "Đạt một phần");
  const noFail = !t.steps.some(([, state]) => state === "fail");
  return Boolean(gateOk) && verifierVerdict(t) === "Đạt" && noFail;
}

function filterTraces(traces, f) {
  const q = f.q.trim().toLowerCase();
  return traces.filter((t) =>
    (q === "" || t.id.toLowerCase().includes(q)) &&
    (f.status === "all" || t.st === f.status) &&
    (f.company === "all" || t.co === f.company) &&
    (f.gate === "all" || gateLabel(t) === f.gate) &&
    (f.verifier === "all" || verifierVerdict(t) === f.verifier));
}

function buildReason(t) {
  const tone = STATUS_TONE[t.st] || "neutral";
  const rate = verifierRate(t);
  const base = { tone, label: null, value: null, gap: null, gapTone: tone };

  if (t.st === "Thành công") {
    return { ...base,
      main: `Tất cả các bước kiểm soát hợp lệ. Bằng chứng đáp ứng đầy đủ và xác minh luận điểm đạt ${fmtPct(rate)}.`,
      label: "So sánh tỷ lệ kiểm định:", value: `${t.ver.sup}/${t.ver.total} = ${fmtPct(rate)} ≥ ${t.ver.thr}%`,
      gap: `+${fmtPct(rate - t.ver.thr)} (Thừa điều kiện)`,
      impact: "Hệ quả: Phản hồi được phát hành an toàn với đầy đủ bằng chứng đối chiếu." };
  }
  if (t.st === "Không đủ bằng chứng") {
    const g = t.gate;
    return { ...base,
      main: `Chỉ tìm thấy ${g.have}/${g.req} ${g.unit} có nguồn dữ liệu kiểm toán hợp lệ, thấp hơn yêu cầu tối thiểu.`,
      label: "Chỉ số kỳ báo cáo:", value: `${g.have}/${g.req} ${g.unit} < ${g.req}`,
      gap: `Thiếu ${g.req - g.have} ${g.unit}`,
      impact: "Hệ quả: Dừng pipeline tại Evidence Gate. Phản hồi thông báo không đủ bằng chứng đến người dùng." };
  }
  if (t.st === "Xác minh không đạt") {
    return { ...base,
      main: `Chỉ ${t.ver.sup}/${t.ver.total} luận điểm được hỗ trợ bởi bằng chứng trích dẫn (tỷ lệ ${fmtPct(rate)}), thấp hơn ngưỡng yêu cầu tối thiểu ${t.ver.thr}%.`,
      label: "So sánh tỷ lệ kiểm định:", value: `${t.ver.sup}/${t.ver.total} = ${fmtPct(rate)} < ${t.ver.thr}%`,
      gap: `-${fmtPct(t.ver.thr - rate)}`,
      impact: "Hệ quả: Phản hồi bị chặn phát hành để bảo vệ tính chính xác theo quy chuẩn FinMind." };
  }
  if (t.st === "Lỗi vận hành" && t.cat === "D") {
    const tk = tokenInfo(t);
    return { ...base,
      main: `Tổng token sử dụng (${fmtNum(tk.total)}) đã chạm giới hạn ngân sách tối đa (${fmtNum(tk.limit)}).`,
      label: "So sánh ngân sách token:", value: `${fmtNum(tk.total)} / ${fmtNum(tk.limit)} = ${fmtPct(tk.pct)}`,
      gap: `${fmtNum(Math.max(0, tk.limit - tk.total))} token còn lại`,
      impact: "Hệ quả: Yêu cầu bị dừng theo chính sách an toàn ngân sách tính toán." };
  }
  if (t.st === "Lỗi vận hành") {
    const failStep = t.steps.findIndex(([, s]) => s === "fail");
    const failMs = failStep >= 0 ? t.steps[failStep][0] : null;
    return { ...base,
      main: "Dịch vụ Graph Retrieval không khả dụng do phản hồi quá thời gian cho phép.",
      label: "Dịch vụ gặp sự cố:", value: `Graph Service (${failMs != null ? `${failMs}ms` : "—"} timeout)`,
      impact: "Hệ quả: Ngắt pipeline an toàn, thông tin nhạy cảm đã được ẩn." };
  }
  return { ...base,
    main: "Truy vấn đang được duyệt trong đồ thị tri thức để liên kết các thực thể báo cáo tài chính.",
    label: "Tiến độ:", value: "Đang chạy tại bước Graph Retrieval",
    impact: "Hệ quả: Hệ thống đang tiếp tục tính toán và chưa có kết luận." };
}

function buildTaxonomy(t) {
  const rate = verifierRate(t);
  switch (t.cat) {
    case "B": return { tone: "warning", icon: "⚖", title: "Nhóm B: Sự cố bằng chứng (Evidence Gate)", desc: "Thiếu nguồn dữ liệu chính thức hoặc không đủ số kỳ báo cáo tài chính theo yêu cầu truy vấn." };
    case "C": return { tone: "error", icon: "✔", title: "Nhóm C: Xác minh không đạt (Verification Failure)", desc: `Tỷ lệ luận điểm có chứng cứ xác nhận (${fmtPct(rate)}) thấp hơn ngưỡng phê duyệt yêu cầu (${t.ver.thr}%).` };
    case "D": return { tone: "error", icon: "▣", title: "Nhóm D: Giới hạn ngân sách tài nguyên (Budget Exceeded)", desc: `Vượt giới hạn ${fmtNum(t.tok.limit)} token cho phép của một request đơn lẻ theo chính sách phòng vệ.` };
    case "E": return { tone: "error", icon: "▤", title: "Nhóm E: Lỗi hạ tầng vận hành (Operational Error)", desc: "Sự cố kết nối hoặc quá thời gian phản hồi từ dịch vụ đồ thị tri thức nội bộ." };
    default: return null;
  }
}

// ─── Thành phần nhỏ dùng trong trang ────────────────────────────────────────

function Pill({ tone = "neutral", children }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-semibold ${TONE[tone].pill}`}>
      {children}
    </span>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-xs">
      <span className="font-medium text-slate-500">{label}</span>
      <span className="text-right font-semibold text-slate-800">{children}</span>
    </div>
  );
}

function Bar({ pct, tone, label }) {
  const value = Math.round(Math.min(100, Math.max(0, pct)));
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}
      className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
      <div className={`h-2 rounded-full transition-all duration-300 ${TONE[tone].bar}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = async () => {
    try { await navigator.clipboard.writeText(text); } catch { /* clipboard bị chặn: bỏ qua */ }
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button type="button" onClick={copy} title="Sao chép vào clipboard"
      className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600 hover:bg-blue-100">
      {copied ? "Đã sao chép" : "Sao chép Trace ID"}
    </button>
  );
}

// ─── Danh sách bên trái ─────────────────────────────────────────────────────

const LIST_GRID = "sm:grid sm:grid-cols-[2.75rem_6.5rem_2.25rem_minmax(0,1fr)_4.75rem_4.25rem_2.5rem]";

function TraceList({ traces, total, selectedId, onSelect }) {
  return (
    <section aria-label="Danh sách truy vấn" className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-slate-200 p-4">
        <h2 className="text-sm font-bold text-slate-900">Danh sách truy vấn</h2>
        <span className="text-xs font-medium text-slate-500">({traces.length}/{total})</span>
      </div>
      <div className={`hidden gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2.5 text-[11px] font-semibold text-slate-500 ${LIST_GRID}`}>
        <span>Thời gian</span><span>Trace ID</span><span className="text-center">DN</span><span>Trạng thái</span>
        <span className="text-center">Gate</span><span className="text-center">Ver</span><span className="text-right">Xử lý</span>
      </div>
      {traces.length === 0 ? (
        <p className="p-8 text-center text-xs text-slate-400">Không tìm thấy bản ghi phù hợp bộ lọc.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {traces.map((t) => {
            const active = t.id === selectedId;
            const gate = gateLabel(t);
            const ver = verifierVerdict(t);
            return (
              <li key={t.id}>
                <button type="button" onClick={() => onSelect(t.id)} aria-current={active ? "true" : undefined}
                  className={`flex w-full flex-wrap items-center gap-x-2 gap-y-1 border-l-4 px-3 py-3 text-left text-xs ${LIST_GRID} ${active ? "border-l-blue-600 bg-blue-50/70" : "border-l-transparent hover:bg-slate-50"}`}>
                  <span className="font-mono text-[11px] text-slate-500">{t.s.slice(0, 5)}</span>
                  <span className={`font-mono text-[11px] font-bold ${active ? "text-blue-700" : "text-slate-900"}`}>{t.id}</span>
                  <span className="text-center text-[11px] font-bold text-slate-800">{t.co}</span>
                  <span><Pill tone={STATUS_TONE[t.st]}>{t.st}</Pill></span>
                  <span className="text-center">{gate === "—" ? <span className="text-slate-400">—</span> : <Pill tone={GATE_TONE[gate]}>{gate}</Pill>}</span>
                  <span className="text-center">{ver === "—" ? <span className="text-slate-400">—</span> : <Pill tone={ver === "Đạt" ? "success" : "error"}>{ver}</Pill>}</span>
                  <span className="text-right font-mono text-[11px] text-slate-500">{t.st === "Đang xử lý" ? "—" : `${(totalRealMs(t) / 1000).toFixed(1)}s`}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-400">Chọn một dòng để xem chi tiết trace · {total} bản ghi mẫu</p>
    </section>
  );
}

// ─── Chi tiết bên phải (9 khối) ─────────────────────────────────────────────

function TraceDetail({ t }) {
  const real = totalRealMs(t);
  const running = t.st === "Đang xử lý";
  const reason = buildReason(t);
  const taxonomy = buildTaxonomy(t);
  const tk = tokenInfo(t);
  const rate = verifierRate(t);
  const approved = isApproved(t);
  const tone = TONE[reason.tone];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-mono text-lg font-bold tracking-tight text-slate-900">{t.id}</h2>
            <CopyButton text={t.id} />
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <span className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-bold text-slate-900">{t.co}</span>
            <span aria-hidden="true">•</span>
            <span className="font-medium text-slate-700">{t.q}</span>
          </p>
        </div>
        <StatusBadge tone={STATUS_TONE[t.st]}>{t.st}</StatusBadge>
      </header>

      <Card title="(1) Tóm tắt trace">
        <div className="-my-1.5 divide-y divide-slate-100">
          <Row label="Thời gian bắt đầu:">{t.s}</Row>
          <Row label="Thời gian hoàn thành:">{t.e ?? "—"}</Row>
          <Row label="Tổng thời gian xử lý thực tế:"><span className="font-mono text-blue-700">{running ? "Đang xử lý..." : fmtMs(real)}</span></Row>
          <Row label="Doanh nghiệp:">{t.co}</Row>
          <Row label="Phiên bản cấu hình:">
            <Link to={`${ADMIN_LINKS.configuration}?cfg=${ACTIVE_CONFIG.replace("CFG ", "")}`} className="font-mono text-blue-600 hover:underline">{ACTIVE_CONFIG}</Link>
          </Row>
          <Row label="Phiên bản kho dữ liệu:">
            <Link to={`${ADMIN_LINKS.corpus}?corpus=${ACTIVE_CORPUS.replace("Corpus ", "")}`} className="font-mono text-blue-600 hover:underline">{ACTIVE_CORPUS}</Link>
          </Row>
          <Row label="Nhật ký kiểm toán:">
            <Link to={`${ADMIN_LINKS.audit}?trace=${t.id}`} className="text-blue-600 hover:underline">Xem nhật ký liên quan</Link>
          </Row>
          <Row label="Evidence Gate:">{t.gate?.run ? `${t.gate.st} (${t.gate.have}/${t.gate.req} ${t.gate.unit})` : "Chưa chạy"}</Row>
          <Row label="Verifier Result:">
            {rate == null ? "Chưa chạy" : `${t.ver.sup}/${t.ver.total} = ${fmtPct(rate)} ${rate >= t.ver.thr ? "≥" : "<"} ${t.ver.thr}% (${verifierVerdict(t)})`}
          </Row>
        </div>
      </Card>

      <section className={`space-y-2.5 rounded-xl border p-4 ${tone.box}`}>
        <h3 className={`text-xs font-bold uppercase tracking-wider ${tone.title}`}>(2) Lý do trạng thái</h3>
        <p className="text-xs font-semibold leading-relaxed text-slate-800">{reason.main}</p>
        <div className="rounded border border-slate-200/70 bg-white/80 p-2.5 text-xs">
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-500">{reason.label}</span>
            <span className="font-mono font-bold text-slate-800">{reason.value}</span>
          </div>
          {reason.gap && (
            <div className="mt-1 flex items-center justify-between gap-3 border-t border-slate-200/60 pt-1">
              <span className="text-slate-500">Độ lệch (Gap):</span>
              <span className={`font-mono font-bold ${TONE[reason.gapTone].text}`}>{reason.gap}</span>
            </div>
          )}
        </div>
        <p className="text-xs leading-relaxed text-slate-600">{reason.impact}</p>
      </section>

      <Card title="(3) Phân loại nguyên nhân">
        {taxonomy ? (
          <div className={`space-y-1 rounded-lg border p-2.5 text-xs ${TONE[taxonomy.tone].box}`}>
            <p className={`flex items-center gap-1.5 font-bold ${TONE[taxonomy.tone].title}`}><span aria-hidden="true">{taxonomy.icon}</span>{taxonomy.title}</p>
            <p className="text-[11px] text-slate-700">{taxonomy.desc}</p>
          </div>
        ) : (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-2.5 text-xs font-semibold text-emerald-800">
            <span aria-hidden="true">✓ </span>{running ? "Chưa ghi nhận lỗi (đang thực thi)" : "Không có lỗi (Thực thi thành công)"}
          </p>
        )}
      </Card>

      <Card title="(4) Tiến trình xử lý">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-y border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-500">
              <tr><th scope="col" className="px-3 py-2">Bước thực hiện</th><th scope="col" className="px-3 py-2">Trạng thái</th><th scope="col" className="px-3 py-2 text-right">Thời gian (ms)</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {t.steps.map(([ms, state], i) => {
                const s = STEP_STATE[state];
                return (
                  <tr key={STEP_NAMES[i]}>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{i + 1}. {STEP_NAMES[i]}</td>
                    <td className="px-3 py-2.5"><span className={state === "run" ? "animate-pulse" : ""}><StatusBadge tone={s.tone}>{s.label}</StatusBadge></span></td>
                    <td className="px-3 py-2.5 text-right font-mono text-slate-600">{state === "skip" || state === "run" ? "—" : `${ms}ms`}</td>
                  </tr>
                );
              })}
              <tr className="bg-slate-50/80">
                <td className="px-3 py-2.5 font-bold text-slate-900">8. Phát hành phản hồi</td>
                <td className="px-3 py-2.5">
                  <StatusBadge tone={t.st === "Thành công" ? "success" : running ? "info" : "error"}>
                    {t.st === "Thành công" ? "Đã phát hành" : running ? "Đang chờ xử lý" : "Không phát hành"}
                  </StatusBadge>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-400">—</td>
              </tr>
            </tbody>
            <tfoot className="border-t border-slate-200 bg-slate-50 text-xs font-bold text-slate-800">
              <tr>
                <td className="px-3 py-2.5">Tổng thực tế</td>
                <td className="px-3 py-2.5 font-normal text-slate-500">Các bước hoàn tất hợp lệ</td>
                <td className="px-3 py-2.5 text-right font-mono text-blue-700">{running ? "—" : fmtMs(real)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      <Card title="(5) Chi tiết truy xuất">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
              <span className="font-bold text-slate-800">Vector Retrieval</span>
              <Pill tone="success">Hoàn thành</Pill>
            </div>
            <Row label="Thời gian:"><span className="font-mono">{fmtMs(t.vec.ms)}</span></Row>
            <Row label="Tài liệu tìm thấy:">{t.vec.found} đoạn trích</Row>
            <Row label="Tài liệu giữ lại:">{t.vec.kept} đoạn trích</Row>
            <Row label="Bằng chứng chọn lọc:">{t.vec.sel != null ? `${t.vec.sel} đoạn chọn lọc` : "Chưa chọn lọc"}</Row>
          </div>
          <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50/50 p-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
              <span className="font-bold text-slate-800">Graph Retrieval</span>
              <Pill tone={t.gr.state === "Hoàn thành" ? "success" : t.gr.state === "Không khả dụng" ? "error" : "info"}>{t.gr.state}</Pill>
            </div>
            {t.gr.state === "Hoàn thành" && (
              <>
                <Row label="Thời gian:"><span className="font-mono">{fmtMs(t.gr.ms)}</span></Row>
                <Row label="Quan hệ tìm thấy:">{t.gr.found} quan hệ</Row>
                <Row label="Quan hệ hợp lệ:">{t.gr.valid} quan hệ thực thể</Row>
              </>
            )}
            {t.gr.state === "Không khả dụng" && (
              <>
                <Row label="Thời gian:"><span className="font-mono">{fmtMs(t.gr.ms)}</span></Row>
                <p role="alert" className="rounded border border-rose-200 bg-rose-50 p-2 text-[11px] leading-relaxed text-rose-700">{t.gr.err || "Không thể truy cập dịch vụ đồ thị."}</p>
              </>
            )}
            {t.gr.state === "Đang chạy" && <p className="font-medium text-blue-700">Đang thực hiện truy xuất...</p>}
          </div>
        </div>
      </Card>

      <Card title="(6) Evidence Gate">
        {!t.gate?.run ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center text-xs text-slate-500">Evidence Gate chưa chạy trong truy vấn này.</p>
        ) : (
          <div className="space-y-3 text-xs">
            <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold text-slate-700">Kỳ báo cáo đáp ứng:</span>
                <span className="font-mono font-bold text-slate-900">
                  {t.gate.have} / {t.gate.req} {t.gate.unit} ({Math.round((t.gate.have / t.gate.req) * 100)}%)
                </span>
              </div>
              <Bar pct={(t.gate.have / t.gate.req) * 100} tone={GATE_TONE[t.gate.st]} label="Kỳ báo cáo đáp ứng yêu cầu" />
              <div className="flex justify-between gap-3 text-[11px] text-slate-500">
                <span>Bằng chứng đủ điều kiện: <strong>{t.gate.elig}</strong> (Yêu cầu tối thiểu: {t.gate.minEv})</span>
                <span className={`font-semibold ${TONE[GATE_TONE[t.gate.st]].text}`}>{t.gate.st}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[["Nguồn tìm thấy:", `${t.gate.found} nguồn`], ["Nguồn hợp lệ:", `${t.gate.passed} nguồn`], ["Yêu cầu kỳ:", `${t.gate.req} ${t.gate.unit}`], ["Hiện có:", `${t.gate.have} ${t.gate.unit}`]].map(([k, v]) => (
                <div key={k} className="rounded border border-slate-200 bg-white p-2">
                  <span className="block text-[11px] text-slate-400">{k}</span>
                  <span className="font-semibold text-slate-800">{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title="(7) Xác minh câu trả lời (Verifier)">
        {rate == null ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-center text-xs text-slate-500">Verifier chưa chạy (bị bỏ qua do bước trước chưa đạt hoặc gián đoạn).</p>
        ) : (
          <div className="space-y-3 text-xs">
            <div className={`flex items-center justify-between gap-3 rounded-lg border p-3 ${verifierVerdict(t) === "Đạt" ? TONE.success.box : TONE.error.box}`}>
              <div>
                <p className="font-bold text-slate-900">{verifierVerdict(t) === "Đạt" ? "Đạt xác minh kiểm định" : "Không đạt xác minh kiểm định"}</p>
                <p className="mt-0.5 text-[11px] text-slate-600">So sánh: <strong>{t.ver.sup}/{t.ver.total} = {fmtPct(rate)}</strong> (Ngưỡng quy định: ≥ {t.ver.thr}%)</p>
              </div>
              <div className="text-right font-mono">
                <span className={`text-base font-bold ${verifierVerdict(t) === "Đạt" ? TONE.success.text : TONE.error.text}`}>{fmtPct(rate)}</span>
                <p className="text-[10px] text-slate-400">Tỷ lệ hỗ trợ</p>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <div className="flex justify-between border-b border-slate-200 bg-slate-50 px-3 py-2 font-semibold text-slate-700">
                <span>Chi tiết luận điểm ({t.ver.claims.length})</span>
                <span className="text-[11px] font-normal text-slate-400">Trích dẫn đối chiếu</span>
              </div>
              <ul className="divide-y divide-slate-100">
                {t.ver.claims.map((claim, i) => {
                  const cite = t.ver.cites[i];
                  const why = t.ver.why?.[i];
                  return (
                    <li key={claim} className={`flex items-start justify-between gap-3 p-2.5 ${cite ? "" : "bg-rose-50/40"}`}>
                      <div>
                        <p className="flex items-center gap-1.5 font-medium text-slate-800">
                          <span aria-hidden="true" className={cite ? "text-emerald-600" : "text-rose-600"}>{cite ? "✓" : "✕"}</span>
                          {claim}
                        </p>
                        {why && <p className="pl-5 text-[11px] text-rose-700">{why}</p>}
                      </div>
                      {cite
                        ? <span className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 font-mono text-[10px] font-semibold text-blue-700">{cite}</span>
                        : <span className="rounded bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700">Thiếu dẫn chứng</span>}
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        )}
      </Card>

      <Card title="(8) Mức sử dụng tài nguyên & Token">
        <div className="-my-1.5 divide-y divide-slate-100">
          <Row label="Input token:"><span className="font-mono">{fmtNum(tk?.inTok)}</span></Row>
          <Row label="Output token:"><span className="font-mono">{fmtNum(tk?.outTok)}</span></Row>
          <Row label="Tổng token:"><span className="font-mono">{fmtNum(tk?.total)}</span></Row>
          <Row label="Giới hạn phiên:"><span className="font-mono font-normal">{fmtNum(t.tok.limit)} max</span></Row>
        </div>
        <div className="mt-3 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <div className="flex justify-between gap-3">
            <span className="font-medium text-slate-700">Tỷ lệ tiêu thụ:</span>
            <span className="font-mono font-bold">{tk ? `${tk.pct.toFixed(1)}% (${fmtNum(tk.total)} / ${fmtNum(tk.limit)})` : "Đang giám sát"}</span>
          </div>
          <Bar pct={tk?.pct ?? 0} tone={!tk ? "neutral" : tk.pct >= 100 ? "error" : tk.pct >= 90 ? "warning" : "info"} label="Tỷ lệ tiêu thụ token" />
          <p className="text-[11px]">
            {!tk && <span className="text-slate-500">Chưa ghi nhận tiêu thụ token</span>}
            {tk && tk.pct >= 100 && <span className="font-bold text-rose-600">✕ Đã chạm giới hạn — Request dừng theo chính sách an toàn.</span>}
            {tk && tk.pct >= 90 && tk.pct < 100 && <span className="font-bold text-amber-700">⚠ Gần giới hạn (≥90%)</span>}
            {tk && tk.pct < 90 && <span className="text-slate-500">Trạng thái: An toàn (Dưới 90%)</span>}
          </p>
        </div>
      </Card>

      <FinalDecision t={t} approved={approved} running={running} rate={rate} tk={tk} />
    </div>
  );
}

function FinalDecision({ t, approved, running, rate, tk }) {
  const tone = approved ? "success" : running ? "info" : "error";
  const title = approved ? "PHÁT HÀNH CÂU TRẢ LỜI" : running ? "ĐANG XỬ LÝ" : "KHÔNG PHÁT HÀNH CÂU TRẢ LỜI";
  const reasons = {
    B: "Do Evidence Gate không đủ bằng chứng hoặc không đủ kỳ báo cáo tài chính theo yêu cầu.",
    C: rate != null ? `Do Verifier tỷ lệ hỗ trợ thấp hơn ngưỡng quy định (${fmtPct(rate)} < ${t.ver.thr}%). Luận điểm chưa đủ căn cứ xác minh.` : "",
    D: `Do đã chạm giới hạn ngân sách tài nguyên tối đa (${fmtNum(t.tok.limit)} token).`,
    E: "Do dịch vụ Graph không khả dụng trong lần chạy này.",
  };
  const body = approved
    ? "Đủ điều kiện bằng chứng và xác minh luận điểm vượt ngưỡng yêu cầu. Phản hồi được phê duyệt phát hành."
    : running
      ? "Truy vấn đang trong tiến trình thực thi, chưa có quyết định phát hành cuối cùng."
      : reasons[t.cat] || "Do không thỏa mãn tiêu chí kiểm soát chất lượng an toàn FinMind.";
  const budget = tk ? (tk.pct >= 100 ? "VƯỢT GIỚI HẠN" : "HỢP LỆ") : "CHƯA GHI NHẬN";

  return (
    <section className={`space-y-2 rounded-xl border p-4 ${TONE[tone].box}`}>
      <h3 className={`flex items-center gap-2 text-sm font-bold ${TONE[tone].title}`}>
        <span aria-hidden="true">{approved ? "✓" : running ? "⧖" : "✕"}</span>
        (9) QUYẾT ĐỊNH CUỐI: {title}
      </h3>
      <p className="text-xs leading-relaxed text-slate-700">{body}</p>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 font-mono text-[11px] text-slate-600">
        {running ? <span>Pipeline: ĐANG CHẠY</span> : (
          <>
            <span>Evidence Gate: {t.gate?.run ? t.gate.st.toUpperCase() : "CHƯA CHẠY"}</span>
            <span aria-hidden="true">•</span>
            <span>Verifier: {rate != null ? fmtPct(rate) : "CHƯA CHẠY"}</span>
            <span aria-hidden="true">•</span>
            <span>Ngân sách: {budget}</span>
          </>
        )}
      </p>
    </section>
  );
}

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminTracesPage() {
  const { traceId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [traces, setTraces] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  const selectedId = traceId || searchParams.get("trace") || DEFAULT_TRACE_ID;
  const telemetryDown = searchParams.get("state") === "telemetry";

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getTraces()
      .then(setTraces)
      .catch((e) => { setTraces(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = traces ? filterTraces(traces, filters) : [];
  const selected = traces?.find((t) => t.id === selectedId) ?? null;
  const detailPath = `${ADMIN_LINKS.traces}/${selectedId}`;

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200/70 pb-3 md:flex-row md:items-center">
        <div>
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link>
            <span aria-hidden="true" className="text-slate-300">/</span>
            <span className="font-medium text-slate-800">Theo dõi truy vấn</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Theo dõi truy vấn &amp; Trace</h1>
            <span className="rounded-md border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">Dữ liệu minh họa</span>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">Kiểm tra trạng thái thực thi, truy xuất bằng chứng, xác minh và mức sử dụng tài nguyên của từng truy vấn.</p>
        </div>
        <Link to={`${detailPath}?state=telemetry`} className="shrink-0 self-start rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-500 hover:border-slate-300 hover:text-blue-600">
          <span aria-hidden="true" className="text-amber-500">⚠ </span>Mô phỏng: telemetry không khả dụng
        </Link>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && traces && (
        <>
          <FilterBar filters={FILTER_FIELDS} values={filters}
            onChange={(key, value) => setFilters((f) => ({ ...f, [key]: value }))}
            onReset={() => setFilters(EMPTY_FILTERS)} />

          <div className="grid gap-6 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)] lg:items-start">
            <TraceList traces={visible} total={traces.length} selectedId={selectedId}
              onSelect={(id) => navigate(`${ADMIN_LINKS.traces}/${id}`)} />

            <div>
              {telemetryDown ? (
                <section role="alert" className="rounded-xl border border-amber-200 bg-amber-50/40 px-6 py-10 text-center">
                  <h2 className="mb-1.5 text-base font-bold text-slate-900">Không thể tải dữ liệu theo dõi</h2>
                  <p className="mx-auto mb-2 max-w-md text-xs leading-relaxed text-slate-600">Một phần thông tin vận hành telemetry hiện không khả dụng do gián đoạn kết nối máy chủ quản trị.</p>
                  <p className="inline-block rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">✓ Không ảnh hưởng đến dữ liệu nghiên cứu và kho dữ liệu đã lưu.</p>
                  <div className="mt-6">
                    <Button variant="secondary" onClick={() => navigate(detailPath)}>← Quay lại chi tiết trace</Button>
                  </div>
                </section>
              ) : selected ? (
                <TraceDetail t={selected} />
              ) : (
                <EmptyState title="Chưa chọn truy vấn nào" description="Chọn một dòng từ danh sách bên trái để kiểm tra chi tiết trace." />
              )}
            </div>
          </div>
        </>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-xs text-slate-500">
        Chỉ dùng cho quản trị vận hành FinMind. Dữ liệu minh họa.
      </footer>
    </AdminLayout>
  );
}
