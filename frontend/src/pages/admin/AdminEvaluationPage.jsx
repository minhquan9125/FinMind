// Trang Đánh giá RAG B0–B3 (route /evaluation, /evaluation/run, /evaluation/golden-test-set, /evaluation/traces/:traceId).
// Một component, 3 tab: Số đo | Lần chạy | Bộ câu hỏi (Golden Test Set). Địa chỉ quyết định tab và trace đang mở.
// Dữ liệu là DỮ LIỆU MINH HỌA từ ./evaluationMock.js; mọi thao tác (thêm, duyệt, đóng băng, chạy lại) chỉ giả lập trong bộ nhớ trang.
// Quy tắc: không bao giờ hiển thị điểm giả như kết quả thật, ô chưa có kết quả hiện "Chưa có".

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "../../app/router.jsx";
import { Button, Drawer, EmptyState, ErrorState, FilterBar, Input, Modal, Select, Skeleton, StatusBadge } from "../../shared/ui";
import { PATHS } from "../../shared/paths.js";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import {
  CATEGORIES, COMPANIES, FLAG_LABELS, ROLES, SPLITS, TARGET_CALIBRATION, TARGET_FINAL, TARGET_TOTAL, casesForRun, getEvaluationData,
} from "./evaluationMock.js";
import useToasts from "./useToasts.jsx";

// ─── Hằng số & hàm thuần ────────────────────────────────────────────────────

const RUN_TONE = { "Hoàn tất": "success", "Một phần": "warning", "Thiếu trace": "error", "Đang chạy": "info", "Lỗi": "error" };
const TYPE_TONE = { Gate: "info", Hypothesis: "warning", Report: "neutral" };
const REVIEW_TONE = { "Đã duyệt": "success", "Chờ review": "warning", "Tranh chấp": "error" };
const VERDICT_TONE = { "Đạt": "success", "Không đạt": "error", "Chưa chấm": "neutral" };
const TABS = [["metrics", "Số đo", PATHS.evaluation], ["runs", "Lần chạy", PATHS.evaluationRun], ["golden", "Bộ câu hỏi", PATHS.evaluationGoldenTestSet]];

const fmtNum = (n) => Number(n).toLocaleString("en-US");
function fmtMetric(kind, v) {
  if (kind === "seconds") return `${v.toFixed(1)} s`;
  if (kind === "token") return `${fmtNum(v)} token`;
  return v.toFixed(2);
}
const pad = (n) => String(n).padStart(2, "0");
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const byNewest = (a, b) => (b.startedAt > a.startedAt ? 1 : -1);
const latestCompleted = (runs, config, split) => [...runs].sort(byNewest).find((r) => r.config === config && r.split === split && r.status === "Hoàn tất") ?? null;
const gatePasses = (metric, v) => (metric.gate.op === ">=" ? v >= metric.gate.value : v < metric.gate.value);

function freezeChecks(questions) {
  const total = questions.length;
  const approved = questions.filter((x) => x.review.status === "Đã duyệt").length;
  const cal = questions.filter((x) => x.split === "calibration").length;
  const fin = questions.filter((x) => x.split === "final").length;
  const norm = questions.map((x) => x.text.trim().toLowerCase());
  const dups = norm.length - new Set(norm).size;
  return [
    { label: `Đủ ${TARGET_TOTAL} câu`, ok: total === TARGET_TOTAL, detail: `${total}/${TARGET_TOTAL}` },
    { label: "Tất cả câu đã được 2 người duyệt", ok: total > 0 && approved === total, detail: `${approved}/${total}` },
    { label: `Chia đúng ${TARGET_CALIBRATION} Hiệu chỉnh / ${TARGET_FINAL} Chốt cuối`, ok: cal === TARGET_CALIBRATION && fin === TARGET_FINAL, detail: `${cal} / ${fin}` },
    { label: "Không có câu trùng", ok: dups === 0, detail: `${dups} câu trùng` },
  ];
}

const EMPTY_FORM = { text: "", category: CATEGORIES[0], company: COMPANIES[0], period: "", answerable: "yes", split: "calibration", reference: "", canonical: "", locator: "" };
function validateForm(f) {
  const errors = {};
  if (f.text.trim().length < 10) errors.text = "Câu hỏi cần ít nhất 10 ký tự.";
  if (!f.period.trim()) errors.period = "Cần nhập kỳ (ví dụ FY2025, Q1/2026).";
  if (f.answerable === "yes") {
    if (!f.reference.trim()) errors.reference = "Câu trả lời được cần có đáp án chuẩn.";
    if (!f.locator.trim()) errors.locator = "Cần gắn vị trí nguồn (trang, bảng).";
  }
  return errors;
}

// ─── Thành phần nhỏ ─────────────────────────────────────────────────────────

function Bar({ value, total, label }) {
  const pct = total ? Math.min(100, Math.round((value / total) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-slate-600">{label}</span><span className="font-mono font-semibold text-slate-800">{value}/{total}</span></div>
      <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={value} className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Rows({ rows }) {
  return (
    <div className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-slate-50 px-4 text-xs">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-3 py-2.5"><span className="text-slate-500">{label}</span><span className="text-right font-medium text-slate-900">{value}</span></div>
      ))}
    </div>
  );
}

const Heading = ({ children }) => <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">{children}</h3>;
const NotAllowed = ({ children }) => <p className="text-xs text-slate-500">{children}</p>;

// ─── Tab 1: Số đo ───────────────────────────────────────────────────────────

function MetricCell({ metric, config, split, runs }) {
  const done = latestCompleted(runs, config, split);
  if (!done) {
    const other = runs.find((r) => r.config === config && r.split === split);
    return <span className="text-slate-400">{other ? `Chưa có (${other.status})` : "Chưa chạy"}</span>;
  }
  const v = done.metrics?.[metric.key];
  if (v == null) return <span className="text-slate-400">Chưa có</span>;
  // Đạt / Không đạt chỉ áp dụng cho cột B3 trên tập Chốt cuối.
  const judged = metric.gate && config === "B3" && split === "final";
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className="font-mono font-semibold text-slate-900">{fmtMetric(metric.kind, v)}</span>
      <span className="rounded bg-slate-100 px-1 text-[10px] text-slate-500">mẫu</span>
      {judged && <StatusBadge tone={gatePasses(metric, v) ? "success" : "error"}>{gatePasses(metric, v) ? "Đạt" : "Không đạt"}</StatusBadge>}
    </span>
  );
}

function MetricsTab({ configs, metrics, runs, split, onSplit, selected, onToggle }) {
  const cols = configs.filter((c) => selected.includes(c.id));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tập câu hỏi">
        <span className="text-xs font-semibold text-slate-600">Tập câu hỏi:</span>
        {Object.entries(SPLITS).map(([id, label]) => (
          <button key={id} type="button" aria-pressed={split === id} onClick={() => onSplit(id)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${split === id ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>
            {label} ({id === "final" ? TARGET_FINAL : TARGET_CALIBRATION}){id === "final" ? " 🔒" : ""}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {configs.map((c) => {
          const on = selected.includes(c.id);
          return (
            <button key={c.id} type="button" aria-pressed={on} onClick={() => onToggle(c.id)}
              className={`rounded-xl border p-3 text-left ${on ? "border-blue-600 bg-blue-50/50" : "border-slate-200 bg-white hover:bg-slate-50"}`}>
              <div className="flex items-center justify-between"><span className="text-sm font-bold text-slate-900">{c.id}</span><span className="text-[11px] text-slate-500">{on ? "Đang so sánh" : "Bỏ qua"}</span></div>
              <p className="text-xs font-medium text-slate-700">{c.name}</p>
              <p className="mt-0.5 text-[11px] text-slate-500">{c.purpose}</p>
              <ul className="mt-2 flex flex-wrap gap-1">
                {Object.entries(FLAG_LABELS).map(([k, label]) => (
                  <li key={k} className={`rounded px-1.5 py-0.5 text-[10px] ${c.flags[k] ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-400 line-through"}`}>{label}</li>
                ))}
              </ul>
            </button>
          );
        })}
      </div>

      {cols.length === 0 ? <EmptyState title="Chọn ít nhất một cấu hình để so sánh" /> : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-3">Số đo</th><th scope="col" className="px-3 py-3">Loại</th><th scope="col" className="px-3 py-3">Ngưỡng</th>
                {cols.map((c) => <th key={c.id} scope="col" className="px-3 py-3">{c.id}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {metrics.map((m) => (
                <tr key={m.key}>
                  <td className="px-4 py-3 font-medium text-slate-900">{m.label}</td>
                  <td className="px-3 py-3"><StatusBadge tone={TYPE_TONE[m.type]}>{m.type}</StatusBadge></td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-500">{m.rule}</td>
                  {cols.map((c) => <td key={c.id} className="whitespace-nowrap px-3 py-3"><MetricCell metric={m} config={c.id} split={split} runs={runs} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[11px] leading-relaxed text-slate-500">
        {split === "calibration"
          ? "Tập Hiệu chỉnh chỉ dùng để chỉnh ngưỡng, kết quả không được báo cáo là hiệu năng cuối, nên không hiện Đạt hoặc Không đạt."
          : "Đạt hoặc Không đạt chỉ áp dụng cho cột B3 trên tập Chốt cuối, khi lần chạy đã Hoàn tất. Số liệu hiện tại là mẫu."}
      </p>
    </div>
  );
}

// ─── Tab 2: Lần chạy ────────────────────────────────────────────────────────

function RunsTab({ runs, canWrite, onOpen, onRerun }) {
  const sorted = [...runs].sort(byNewest);
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">Hoàn tất = đủ câu và đủ trace · Một phần = còn câu chưa chạy · Thiếu trace = có câu chưa có dấu vết truy vấn.</p>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full border-collapse text-left text-xs">
          <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-600">
            <tr>{["Run ID", "Cấu hình", "Tập", "Trạng thái", "Số câu", "Số trace", "Bắt đầu", "Kết thúc", "Thao tác"].map((h) => <th key={h} scope="col" className="whitespace-nowrap px-3 py-3 first:px-4">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((r) => {
              const locked = r.split === "final";
              const reason = !canWrite ? "Chỉ Evaluator được chạy lại." : locked ? "Tập Chốt cuối chỉ chạy theo kế hoạch đã duyệt, không chạy lại để chỉnh ngưỡng." : r.status === "Đang chạy" ? "Lần chạy đang diễn ra." : "";
              return (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3"><button type="button" onClick={() => onOpen(r.id)} className="font-mono font-semibold text-blue-600 hover:underline">{r.id}</button></td>
                  <td className="px-3 py-3 font-bold text-slate-900">{r.config}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-600">{SPLITS[r.split]}{locked ? " 🔒" : ""}</td>
                  <td className="whitespace-nowrap px-3 py-3"><StatusBadge tone={RUN_TONE[r.status]}>{r.status}</StatusBadge></td>
                  <td className="px-3 py-3 font-mono text-slate-600">{r.done}/{r.total}</td>
                  <td className={`px-3 py-3 font-mono ${r.traces < r.total && r.status !== "Đang chạy" && r.status !== "Một phần" ? "font-semibold text-rose-600" : "text-slate-600"}`}>{r.traces}/{r.total}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-500">{fmtTime(r.startedAt)}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-500">{fmtTime(r.finishedAt)}</td>
                  <td className="whitespace-nowrap px-3 py-3">
                    <div className="inline-flex gap-1.5">
                      <Button variant="ghost" className="min-h-8 px-2 py-1 text-xs" onClick={() => onOpen(r.id)}>Xem</Button>
                      <Button variant="secondary" className="min-h-8 px-2 py-1 text-xs" disabled={Boolean(reason)} title={reason || "Chạy lại cấu hình này (giả lập)"} onClick={() => onRerun(r.id)}>Chạy lại</Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunBody({ run, metrics, cases, questions, onOpenTrace }) {
  return (
    <div className="space-y-5 text-xs">
      <p className="flex flex-wrap items-center gap-2"><StatusBadge tone={RUN_TONE[run.status]}>{run.status}</StatusBadge><span className="text-slate-500">{run.config} · {SPLITS[run.split]} · dữ liệu mẫu</span></p>
      {run.error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">Lỗi: {run.error}</p>}
      <section><Heading>Manifest lần chạy</Heading><Rows rows={[["Phiên bản corpus", run.corpus], ["Phiên bản cấu hình", run.cfg], ...Object.entries(run.manifest)]} /></section>
      <section>
        <Heading>Số đo của lần chạy</Heading>
        {run.metrics ? (
          <ul className="grid grid-cols-2 gap-2">
            {metrics.map((m) => (
              <li key={m.key} className="rounded border border-slate-200 bg-white p-2"><span className="block text-[11px] text-slate-500">{m.label}</span><span className="font-mono font-semibold text-slate-900">{fmtMetric(m.kind, run.metrics[m.key])}</span> <span className="text-[10px] text-slate-400">mẫu</span></li>
            ))}
          </ul>
        ) : <NotAllowed>Chưa có số đo: lần chạy chưa hoàn tất.</NotAllowed>}
      </section>
      <section>
        <Heading>Các câu trong lần chạy ({cases.length})</Heading>
        <ul className="space-y-1.5">
          {cases.map((c) => (
            <li key={c.questionId} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2">
              <span className="min-w-0"><span className="font-mono font-semibold text-slate-800">{c.questionId}</span> <span className="text-slate-500">{questions.find((x) => x.id === c.questionId)?.text.slice(0, 48)}…</span></span>
              <span className="flex shrink-0 items-center gap-2">
                <StatusBadge tone={VERDICT_TONE[c.verdict]}>{c.verdict}</StatusBadge>
                {c.traceId ? <button type="button" onClick={() => onOpenTrace(c.traceId)} className="font-semibold text-blue-600 hover:underline">Trace</button> : <span className="font-semibold text-rose-600">Thiếu trace</span>}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function TraceBody({ info }) {
  const { run, caseItem, question } = info;
  return (
    <div className="space-y-4 text-xs">
      <Rows rows={[["Trace ID", <span key="t" className="font-mono">{caseItem.traceId}</span>], ["Lần chạy", run.id], ["Cấu hình", run.config], ["Tập", SPLITS[run.split]], ["Câu hỏi", caseItem.questionId], ["Kết quả chấm", <StatusBadge key="v" tone={VERDICT_TONE[caseItem.verdict]}>{caseItem.verdict}</StatusBadge>]]} />
      <section><Heading>Câu hỏi</Heading><p className="rounded-lg border border-slate-200 bg-white p-3 text-slate-800">{question?.text}</p></section>
      <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-800">Chưa có nội dung câu trả lời và các bước truy xuất: dữ liệu này sẽ có khi nối backend. Không hiển thị điểm hoặc câu trả lời giả.</p>
    </div>
  );
}

// ─── Tab 3: Bộ câu hỏi ──────────────────────────────────────────────────────

const opts = (all, list) => [{ value: "all", label: all }, ...list.map((v) => ({ value: v, label: v }))];
const GOLDEN_FILTERS = [
  { key: "q", type: "text", label: "Tìm câu hỏi", placeholder: "Tìm theo nội dung hoặc mã câu..." },
  { key: "category", type: "select", label: "Loại câu hỏi", options: opts("Tất cả loại", CATEGORIES) },
  { key: "company", type: "select", label: "Doanh nghiệp", options: opts("Tất cả mã", COMPANIES) },
  { key: "split", type: "select", label: "Tập", options: [{ value: "all", label: "Tất cả tập" }, ...Object.entries(SPLITS).map(([value, label]) => ({ value, label }))] },
  { key: "answerable", type: "select", label: "Trả lời được?", options: [{ value: "all", label: "Tất cả" }, { value: "yes", label: "Có" }, { value: "no", label: "Không" }] },
  { key: "review", type: "select", label: "Review", options: opts("Tất cả", ["Chờ review", "Đã duyệt", "Tranh chấp"]) },
];
const EMPTY_FILTERS = { q: "", category: "all", company: "all", split: "all", answerable: "all", review: "all" };

function GoldenTab({ questions, datasets, ver, onVer, frozen, canWrite, onAdd, onOpen, onFreeze }) {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const rows = questions.filter((x) => {
    const t = filters.q.trim().toLowerCase();
    return (!t || x.text.toLowerCase().includes(t) || x.id.toLowerCase().includes(t)) &&
      (filters.category === "all" || x.category === filters.category) && (filters.company === "all" || x.company === filters.company) &&
      (filters.split === "all" || x.split === filters.split) && (filters.answerable === "all" || (filters.answerable === "yes") === x.answerable) &&
      (filters.review === "all" || x.review.status === filters.review);
  });
  const cal = questions.filter((x) => x.split === "calibration").length;
  const fin = questions.filter((x) => x.split === "final").length;
  const approved = questions.filter((x) => x.review.status === "Đã duyệt").length;

  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-end">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Phiên bản bộ đề" className="min-w-52" value={ver} onChange={(e) => onVer(e.target.value)} options={datasets.map((d) => ({ value: d.v, label: `${d.v} (${d.state})` }))} />
          <StatusBadge tone={frozen ? "success" : "warning"}>{frozen ? "🔒 Đã đóng băng, chỉ đọc" : "Bản nháp"}</StatusBadge>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" className="text-xs" disabled={frozen || !canWrite} title={frozen ? "Bộ đề đã đóng băng." : !canWrite ? "Chỉ Evaluator được thêm ca mẫu." : ""} onClick={onAdd}>＋ Thêm ca mẫu</Button>
          <Button className="text-xs" disabled={frozen || !canWrite} title={frozen ? "Bộ đề đã đóng băng." : !canWrite ? "Chỉ Evaluator được đóng băng." : ""} onClick={onFreeze}>Đóng băng (Freeze)</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4">
        <Bar label="Đã soạn" value={questions.length} total={TARGET_TOTAL} />
        <Bar label="Hiệu chỉnh" value={cal} total={TARGET_CALIBRATION} />
        <Bar label="Chốt cuối" value={fin} total={TARGET_FINAL} />
        <Bar label="Đã duyệt" value={approved} total={questions.length || 1} />
      </div>
      <p className="text-[11px] text-slate-500">Đây là 12 câu mẫu trích từ bản nháp, không phải đủ 120 câu. Đáp án chuẩn và vị trí nguồn sẽ lấy từ tài liệu thật.</p>

      <FilterBar filters={GOLDEN_FILTERS} values={filters} onChange={(k, v) => setFilters((f) => ({ ...f, [k]: v }))} onReset={() => setFilters(EMPTY_FILTERS)} />

      {rows.length === 0 ? <EmptyState title="Không có câu hỏi phù hợp bộ lọc" /> : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-600">
              <tr>{["Mã", "Câu hỏi", "Loại", "Mã DN", "Kỳ", "Trả lời được?", "Tập", "Review"].map((h) => <th key={h} scope="col" className="whitespace-nowrap px-3 py-3">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((x) => (
                <tr key={x.id} onClick={() => onOpen(x.id)} className="cursor-pointer hover:bg-slate-50">
                  <td className="whitespace-nowrap px-3 py-3 font-mono font-semibold text-slate-900">{x.id}</td>
                  <td className="max-w-md px-3 py-3"><button type="button" onClick={(e) => { e.stopPropagation(); onOpen(x.id); }} className="text-left text-slate-800 hover:text-blue-600">{x.text}</button></td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-600">{x.category}</td>
                  <td className="px-3 py-3 font-mono font-bold text-slate-700">{x.company}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-600">{x.period}</td>
                  <td className="px-3 py-3 text-slate-600">{x.answerable ? "Có" : "Không"}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-600">{SPLITS[x.split]}{x.split === "final" ? " 🔒" : ""}</td>
                  <td className="whitespace-nowrap px-3 py-3"><StatusBadge tone={REVIEW_TONE[x.review.status]}>{x.review.status}</StatusBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function QuestionDetail({ x, frozen, canWrite, onApprove, onDispute }) {
  const hideRef = frozen && x.split === "final";
  const editable = !frozen && canWrite && x.review.status !== "Đã duyệt";
  return (
    <div className="space-y-5 text-xs">
      <p className="rounded-lg border border-slate-200 bg-white p-3 text-[13px] leading-relaxed text-slate-900">{x.text}</p>
      <Rows rows={[
        ["Loại", x.category], ["Doanh nghiệp", x.company], ["Kỳ", x.period], ["Trả lời được?", x.answerable ? "Có" : "Không (phải từ chối)"],
        ["Tập", `${SPLITS[x.split]}${x.split === "final" ? " 🔒" : ""}`],
        ["Đáp án chuẩn", hideRef ? "Ẩn (khóa)" : x.reference || "—"], ["Giá trị số chuẩn", hideRef ? "Ẩn (khóa)" : x.canonical || "—"], ["Vị trí nguồn", hideRef ? "Ẩn (khóa)" : x.locator || "—"],
      ]} />
      <section>
        <Heading>Review (cần 2 người)</Heading>
        <p className="mb-2 flex items-center gap-2"><StatusBadge tone={REVIEW_TONE[x.review.status]}>{x.review.status}</StatusBadge><span className="text-slate-500">{x.review.reviewers.length ? x.review.reviewers.join(", ") : "Chưa có người duyệt"}</span></p>
        {editable ? (
          <div className="flex gap-2"><Button className="min-h-8 px-3 py-1 text-xs" onClick={onApprove}>Duyệt</Button><Button variant="secondary" className="min-h-8 px-3 py-1 text-xs" onClick={onDispute}>Đánh dấu tranh chấp</Button></div>
        ) : <NotAllowed>{frozen ? "Bộ đề đã đóng băng, không thể sửa review." : !canWrite ? "Chỉ Evaluator được review." : "Câu này đã được duyệt đủ."}</NotAllowed>}
      </section>
    </div>
  );
}

function QuestionForm({ form, errors, onChange, onSubmit }) {
  const set = (k) => (e) => onChange(k, e.target.value);
  const answerable = form.answerable === "yes";
  return (
    <form id="question-form" onSubmit={onSubmit} noValidate className="space-y-4">
      <Input label="Câu hỏi *" value={form.text} onChange={set("text")} error={errors.text} placeholder="Ví dụ: Doanh thu của FPT năm 2025 là bao nhiêu?" />
      <div className="grid grid-cols-2 gap-3">
        <Select label="Loại câu hỏi *" options={CATEGORIES.map((v) => ({ value: v, label: v }))} value={form.category} onChange={set("category")} />
        <Select label="Doanh nghiệp *" options={COMPANIES.map((v) => ({ value: v, label: v }))} value={form.company} onChange={set("company")} />
        <Input label="Kỳ *" value={form.period} onChange={set("period")} error={errors.period} placeholder="FY2025, Q1/2026" />
        <Select label="Tập *" options={Object.entries(SPLITS).map(([value, label]) => ({ value, label }))} value={form.split} onChange={set("split")} />
      </div>
      <Select label="Trả lời được từ corpus? *" options={[{ value: "yes", label: "Có (có đáp án)" }, { value: "no", label: "Không (hệ thống phải từ chối)" }]} value={form.answerable} onChange={set("answerable")} />
      <Input label={`Đáp án chuẩn${answerable ? " *" : ""}`} value={form.reference} onChange={set("reference")} error={errors.reference} disabled={!answerable} />
      <Input label="Giá trị số chuẩn (nếu có)" value={form.canonical} onChange={set("canonical")} disabled={!answerable} hint="Ví dụ: 1.250 tỷ VND, kỳ FY2025." />
      <Input label={`Vị trí nguồn${answerable ? " *" : ""}`} value={form.locator} onChange={set("locator")} error={errors.locator} disabled={!answerable} hint="Tài liệu, trang, bảng hoặc mục." />
    </form>
  );
}

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminEvaluationPage() {
  const { traceId } = useParams();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { toast, toastNode } = useToasts();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [role, setRole] = useState("Evaluator");
  const [split, setSplit] = useState("calibration");
  const [selected, setSelected] = useState(["B0", "B1", "B2", "B3"]);
  const [ver, setVer] = useState("v0.3");
  const [runId, setRunId] = useState(null);
  const [questionId, setQuestionId] = useState(null);
  const [rerunId, setRerunId] = useState(null);
  const [adding, setAdding] = useState(false);
  const [freezing, setFreezing] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState({});

  const tab = pathname.startsWith(PATHS.evaluationGoldenTestSet) ? "golden" : pathname.startsWith(PATHS.evaluationRun) || traceId ? "runs" : "metrics";
  const canWrite = role === "Evaluator";

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getEvaluationData().then(setData).catch((e) => { setData(null); setError(e.message); }).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const questions = data?.questions[ver] ?? [];
  const allQuestions = data?.questions["v0.3"] ?? [];
  const dataset = data?.datasets.find((d) => d.v === ver);
  const frozen = dataset?.state === "Đã đóng băng";
  const runs = data?.runs ?? [];

  const runItem = runs.find((r) => r.id === runId) ?? null;
  const questionItem = questions.find((x) => x.id === questionId) ?? null;
  const rerunItem = runs.find((r) => r.id === rerunId) ?? null;
  const checks = useMemo(() => freezeChecks(questions), [questions]);

  // Trace mở bằng địa chỉ: tìm trong các lần chạy.
  const traceInfo = useMemo(() => {
    if (!traceId || !data) return null;
    for (const r of data.runs) {
      const caseItem = casesForRun(r, allQuestions).find((c) => c.traceId === traceId);
      if (caseItem) return { run: r, caseItem, question: allQuestions.find((x) => x.id === caseItem.questionId) };
    }
    return null;
  }, [traceId, data, allQuestions]);

  const closeRun = useCallback(() => setRunId(null), []);
  const closeQuestion = useCallback(() => setQuestionId(null), []);
  const closeAdd = useCallback(() => setAdding(false), []);
  const closeFreeze = useCallback(() => setFreezing(false), []);
  const closeRerun = useCallback(() => setRerunId(null), []);
  const closeTrace = useCallback(() => navigate(PATHS.evaluationRun), [navigate]);

  const patchQuestions = (fn) => setData((d) => ({ ...d, questions: { ...d.questions, [ver]: fn(d.questions[ver]) } }));

  function approve(id) {
    patchQuestions((list) => list.map((x) => {
      if (x.id !== id || x.review.reviewers.length >= 2) return x;
      const reviewers = [...x.review.reviewers, `Reviewer ${x.review.reviewers.length ? "B" : "A"}`];
      return { ...x, review: { status: reviewers.length === 2 ? "Đã duyệt" : "Chờ review", reviewers } };
    }));
    toast("Đã ghi nhận lượt duyệt (giả lập).", "success");
  }
  const dispute = (id) => { patchQuestions((list) => list.map((x) => (x.id === id ? { ...x, review: { ...x.review, status: "Tranh chấp" } } : x))); toast("Đã đánh dấu tranh chấp, cần thống nhất trước khi chia tập.", "warning"); };

  function openAdd() { setForm(EMPTY_FORM); setFormErrors({}); setAdding(true); }
  function submitQuestion(e) {
    e.preventDefault();
    const errors = validateForm(form);
    setFormErrors(errors);
    if (Object.keys(errors).length) return;
    const next = Math.max(0, ...allQuestions.map((x) => Number(x.id.slice(1)) || 0)) + 1;
    const answerable = form.answerable === "yes";
    const id = `Q${String(next).padStart(3, "0")}`;
    patchQuestions((list) => [...list, {
      id, text: form.text.trim(), category: form.category, company: form.company, period: form.period.trim(), answerable, split: form.split,
      review: { status: "Chờ review", reviewers: [] }, reference: answerable ? form.reference.trim() : "", canonical: answerable ? form.canonical.trim() : "", locator: answerable ? form.locator.trim() : "",
    }]);
    setAdding(false);
    toast(`Đã thêm ca mẫu ${id}, đang chờ review.`, "success");
  }

  function freeze() {
    if (!checks.every((c) => c.ok)) return;
    setData((d) => ({ ...d, datasets: d.datasets.map((x) => (x.v === ver ? { ...x, state: "Đã đóng băng" } : x)) }));
    setFreezing(false);
    toast(`Đã đóng băng bộ đề ${ver}. Từ giờ chỉ đọc.`, "success");
  }

  function rerun() {
    if (!rerunItem) return;
    const n = runs.filter((r) => r.id.startsWith("RUN-LOCAL")).length + 1;
    const id = `RUN-LOCAL-${String(n).padStart(3, "0")}`;
    setData((d) => ({ ...d, runs: [{ ...rerunItem, id, status: "Đang chạy", done: 0, traces: 0, startedAt: new Date().toISOString(), finishedAt: null, metrics: null, error: null }, ...d.runs] }));
    setRerunId(null);
    toast(`Đã gửi yêu cầu chạy lại ${rerunItem.config} (giả lập). Kết quả sẽ có khi nối backend.`, "info");
  }

  const openTrace = (id) => { setRunId(null); navigate(PATHS.evaluationTraceDetail(id)); };

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200/70 pb-3 md:flex-row md:items-start">
        <div>
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link><span aria-hidden="true">/</span><span className="font-medium text-slate-900">Đánh giá RAG</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Đánh giá RAG (B0–B3)</h1>
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">Dữ liệu minh họa</span>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">Quản lý bộ câu hỏi kiểm thử, theo dõi các lần chạy đánh giá và so sánh số đo giữa các cấu hình.</p>
        </div>
        <Select label="Xem với vai trò (minh họa)" className="w-full md:w-52" value={role} onChange={(e) => setRole(e.target.value)} options={ROLES.map((r) => ({ value: r, label: r }))} />
      </header>

      <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
        Mọi con số trong trang này là dữ liệu mẫu, không phải kết quả đánh giá thật của hệ thống. Ô chưa có kết quả hiện "Chưa có".
      </p>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && data && role === "Researcher" && (
        <EmptyState title="Bạn không có quyền truy cập khu vực đánh giá" description="Khu vực này dành cho vai trò Evaluator và Data Operator." />
      )}

      {!loading && data && role !== "Researcher" && (
        <>
          <div role="tablist" className="flex gap-8 border-b border-slate-200">
            {TABS.map(([id, label, path]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => navigate(path)}
                className={`-mb-px whitespace-nowrap border-b-2 pb-3 text-sm ${tab === id ? "border-blue-600 font-semibold text-blue-600" : "border-transparent font-medium text-slate-500 hover:text-slate-700"}`}>{label}</button>
            ))}
          </div>

          {tab === "metrics" && (
            <MetricsTab configs={data.configs} metrics={data.metrics} runs={runs} split={split} onSplit={setSplit} selected={selected}
              onToggle={(id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))} />
          )}
          {tab === "runs" && <RunsTab runs={runs} canWrite={canWrite} onOpen={setRunId} onRerun={setRerunId} />}
          {tab === "golden" && (
            <GoldenTab questions={questions} datasets={data.datasets} ver={ver} onVer={setVer} frozen={frozen} canWrite={canWrite}
              onAdd={openAdd} onOpen={setQuestionId} onFreeze={() => setFreezing(true)} />
          )}
        </>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-xs text-slate-500">Chỉ dùng cho quản trị vận hành FinMind. Dữ liệu minh họa.</footer>

      <Drawer open={Boolean(runItem)} onClose={closeRun} title={runItem ? `Lần chạy ${runItem.id}` : ""} footer={<Button variant="secondary" onClick={closeRun}>Đóng</Button>}>
        {runItem && <RunBody run={runItem} metrics={data.metrics} cases={casesForRun(runItem, allQuestions)} questions={allQuestions} onOpenTrace={openTrace} />}
      </Drawer>

      <Drawer open={Boolean(traceInfo)} onClose={closeTrace} title="Chi tiết trace" footer={<Button variant="secondary" onClick={closeTrace}>Đóng</Button>}>
        {traceInfo && <TraceBody info={traceInfo} />}
      </Drawer>

      <Drawer open={Boolean(questionItem)} onClose={closeQuestion} title={questionItem ? `Câu hỏi ${questionItem.id}` : ""} footer={<Button variant="secondary" onClick={closeQuestion}>Đóng</Button>}>
        {questionItem && <QuestionDetail x={questionItem} frozen={frozen} canWrite={canWrite} onApprove={() => approve(questionItem.id)} onDispute={() => dispute(questionItem.id)} />}
      </Drawer>

      <Drawer open={adding} onClose={closeAdd} title="Thêm ca mẫu"
        footer={<><Button variant="secondary" onClick={closeAdd}>Hủy</Button><Button type="submit" form="question-form">Lưu ca mẫu</Button></>}>
        <QuestionForm form={form} errors={formErrors} onChange={(k, v) => setForm((f) => ({ ...f, [k]: v }))} onSubmit={submitQuestion} />
      </Drawer>

      <Modal open={freezing} onClose={closeFreeze} title={`Đóng băng bộ đề ${ver}?`}
        footer={<><Button variant="secondary" onClick={closeFreeze}>Hủy</Button><Button disabled={!checks.every((c) => c.ok)} onClick={freeze}>Đóng băng</Button></>}>
        <p className="mb-3 text-xs">Đóng băng xong thì không thể thêm hay sửa câu hỏi. Tập Chốt cuối sẽ ẩn đáp án khỏi runtime. Điều kiện cần đạt:</p>
        <ul className="space-y-1.5 text-xs">
          {checks.map((c) => (
            <li key={c.label} className={`flex items-center justify-between rounded-lg border p-2 ${c.ok ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
              <span><span aria-hidden="true">{c.ok ? "✓ " : "✕ "}</span>{c.label}</span><span className="font-mono">{c.detail}</span>
            </li>
          ))}
        </ul>
      </Modal>

      <Modal open={Boolean(rerunItem)} onClose={closeRerun} title={rerunItem ? `Chạy lại ${rerunItem.config} trên tập ${SPLITS[rerunItem.split]}?` : ""}
        footer={<><Button variant="secondary" onClick={closeRerun}>Hủy</Button><Button onClick={rerun}>Chạy lại</Button></>}>
        Hệ thống sẽ tạo một lần chạy mới cùng cấu hình. Lần chạy cũ được giữ nguyên. Đây là giả lập, chưa gọi backend.
      </Modal>

      {toastNode}
    </AdminLayout>
  );
}
