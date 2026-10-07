// Trang A02: Cấu hình nguồn dữ liệu (route /admin/sources và /admin/sources/:sourceId).
// Mở chi tiết bằng :sourceId hoặc ?source=. Dữ liệu minh họa lấy từ ./sourcesMock.js;
// mọi thay đổi (thêm/sửa/bật/tạm dừng/kiểm tra) chỉ lưu trong bộ nhớ trang, chưa gọi backend.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams, Link } from "../../app/router.jsx";
import { Button, Drawer, EmptyState, ErrorState, FilterBar, Input, Modal, Select, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { ACCESS_METHODS, SCHEDULES, SOURCE_STATUSES, SOURCE_TYPES, getIngestionRuns, getSources } from "./sourcesMock.js";

// ─── Hằng số & hàm thuần ────────────────────────────────────────────────────

const NO_DATA = "Chưa có dữ liệu";
const show = (v) => v || NO_DATA;

const STATUS_TONE = {
  "Hoạt động": "success", "Tạm dừng": "warning", "Chưa kiểm tra": "neutral",
  "Kiểm tra thất bại": "error", "Vô hiệu hóa": "neutral",
};
const TEST_BADGE = {
  passed: { tone: "success", label: "Đã kiểm tra" },
  failed: { tone: "error", label: "Thất bại" },
  none: { tone: "neutral", label: "Chưa kiểm tra" },
};
const TOAST_TONE = { info: "bg-slate-900", success: "bg-green-600", warning: "bg-amber-600", error: "bg-red-600" };

const EMPTY_FILTERS = { q: "", status: "ALL", type: "ALL", owner: "ALL" };
const withAll = (label, values) => [{ value: "ALL", label }, ...values.map((v) => ({ value: v, label: v }))];

const FILTER_FIELDS = [
  { key: "q", type: "text", label: "Tìm kiếm", placeholder: "Tìm nguồn dữ liệu..." },
  { key: "status", type: "select", label: "Trạng thái", options: withAll("Tất cả trạng thái", SOURCE_STATUSES) },
  { key: "type", type: "select", label: "Loại nguồn", options: withAll("Tất cả loại nguồn", SOURCE_TYPES) },
  { key: "owner", type: "select", label: "Chủ sở hữu", options: [
    { value: "ALL", label: "Tất cả chủ sở hữu" }, { value: "FinMind Admin", label: "FinMind Admin" }, { value: "NONE", label: NO_DATA },
  ] },
];

const FORM_FIELD_LABELS = [
  ["name", "Tên nguồn"], ["type", "Loại nguồn"], ["url", "URL"], ["access", "Phương thức truy cập"],
  ["schedule", "Lịch cập nhật"], ["owner", "Chủ sở hữu"], ["usage", "Mục đích sử dụng"],
  ["scope", "Phạm vi dữ liệu"], ["fallback", "Fallback"], ["terms", "Điều kiện sử dụng"],
];

const formFrom = (src) => ({
  name: src?.name ?? "", type: src?.type ?? "Website chính thức", url: src?.url ?? "",
  access: src?.access ?? "HTTP / Web", schedule: src?.schedule || "Hằng ngày", owner: src ? src.owner : "FinMind Admin",
  usage: src?.usage ?? "", scope: src?.scope ?? "", fallback: src?.fallback ?? "", terms: src?.terms ?? "",
});

function filterSources(list, f) {
  const q = f.q.trim().toLowerCase();
  return list.filter((s) =>
    (!q || [s.name, s.type, s.id].some((v) => v.toLowerCase().includes(q))) &&
    (f.status === "ALL" || s.status === f.status) &&
    (f.type === "ALL" || s.type === f.type) &&
    (f.owner === "ALL" || (f.owner === "NONE" ? !s.owner : s.owner === f.owner)));
}

function canEnable(s) {
  if (!s.testOk) return { ok: false, reason: "Không thể bật nguồn khi kiểm tra kết nối chưa đạt." };
  if (!(s.name && s.type && s.access && s.owner && s.usage)) return { ok: false, reason: "Không thể bật nguồn khi thông tin quản trị chưa đầy đủ." };
  return { ok: true, reason: "" };
}

function validate(form) {
  const errors = [];
  if (!form.name.trim()) errors.push("Thiếu tên nguồn");
  if ((form.access === "HTTP / Web" || form.access === "API") && !form.url.trim()) errors.push("Thiếu URL");
  if (!ACCESS_METHODS.includes(form.access)) errors.push("Phương thức truy cập không hợp lệ");
  if (!form.owner.trim()) errors.push("Thiếu chủ sở hữu");
  return errors;
}

function bumpVersion(v) {
  const m = /^v(\d+)\.(\d+)$/.exec(v);
  return m ? `v${m[1]}.${Number(m[2]) + 1}` : "v1.0";
}

const nowLabel = () => `${new Date().toTimeString().slice(0, 8)} Hôm nay`;

// ─── Thành phần nhỏ ─────────────────────────────────────────────────────────

function ToggleButton({ src, onPause, onEnable }) {
  if (src.status === "Hoạt động") {
    return <Button variant="secondary" className="min-h-8 px-2 py-1 text-xs" onClick={onPause}>⏸ Tạm dừng</Button>;
  }
  const check = canEnable(src);
  return (
    <Button variant="secondary" className="min-h-8 px-2 py-1 text-xs" disabled={!check.ok}
      title={check.ok ? "Bật nguồn dữ liệu" : check.reason} onClick={onEnable}>
      ▶ Bật
    </Button>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <span className="block text-[11px] text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{children}</span>
    </div>
  );
}

function SectionTitle({ children, extra }) {
  return (
    <div className="mb-2 flex items-center gap-1.5 border-b border-slate-100 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-500">
      <span>{children}</span>
      {extra && <span className="ml-auto normal-case tracking-normal">{extra}</span>}
    </div>
  );
}

function Toasts({ items }) {
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed bottom-12 left-1/2 z-[60] flex w-[min(90vw,32rem)] -translate-x-1/2 flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} className={`rounded-lg px-4 py-2.5 text-xs font-medium text-white shadow-xl ${TOAST_TONE[t.type]}`}>{t.message}</div>
      ))}
    </div>
  );
}

// ─── Bảng nguồn ─────────────────────────────────────────────────────────────

function SourceTable({ rows, activeId, testingIds, onOpen, onTest, onEdit, onPause, onEnable, onResetFilters }) {
  if (rows.length === 0) {
    return (
      <EmptyState title="Không tìm thấy nguồn dữ liệu phù hợp."
        description="Vui lòng điều chỉnh lại bộ lọc tìm kiếm hoặc từ khóa tra cứu."
        action={<Button variant="ghost" onClick={onResetFilters}>Đặt lại toàn bộ lọc</Button>} />
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-xs">
        <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-500">
          <tr>
            {["Tên nguồn", "Loại nguồn", "Phương thức truy cập", "Trạng thái", "Phiên bản", "Lần kiểm tra gần nhất", "Chủ sở hữu", "Thao tác"].map((h) => (
              <th key={h} scope="col" className={`whitespace-nowrap px-3 py-3 first:px-4 ${h === "Thao tác" ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 text-slate-900">
          {rows.map((s) => {
            const testing = testingIds.has(s.id);
            const test = TEST_BADGE[s.lastTest];
            return (
              <tr key={s.id} onClick={() => onOpen(s.id)} className={`cursor-pointer hover:bg-slate-50 ${activeId === s.id ? "bg-blue-50/50" : ""}`}>
                <td className="px-4 py-3">
                  <button type="button" onClick={(e) => { e.stopPropagation(); onOpen(s.id); }} className="text-left font-semibold hover:text-blue-600">{s.name}</button>
                  <div className="mt-0.5 font-mono text-[11px] text-slate-500">{s.id}</div>
                </td>
                <td className="px-3 py-3"><span className="whitespace-nowrap rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">{s.type}</span></td>
                <td className="px-3 py-3 text-slate-500">{s.access}</td>
                <td className="px-3 py-3"><StatusBadge tone={STATUS_TONE[s.status]}>{s.status}</StatusBadge></td>
                <td className="px-3 py-3 font-mono font-medium text-blue-600">{s.version}</td>
                <td className="px-3 py-3"><StatusBadge tone={test.tone}>{test.label}</StatusBadge></td>
                <td className="px-3 py-3 text-slate-500">{s.owner || <span className="italic text-slate-400">{NO_DATA}</span>}</td>
                <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                  <div className="inline-flex flex-wrap items-center justify-end gap-1.5">
                    <Button variant="ghost" className="min-h-8 px-2 py-1 text-xs" onClick={() => onOpen(s.id)}>Xem chi tiết</Button>
                    <Button variant="secondary" className="min-h-8 px-2 py-1 text-xs" disabled={testing} loading={testing} onClick={() => onTest(s.id)}>
                      {testing ? "Đang test..." : "Kiểm tra"}
                    </Button>
                    <Button variant="secondary" className="min-h-8 px-2 py-1 text-xs" onClick={() => onEdit(s.id)}>Sửa</Button>
                    <ToggleButton src={s} onPause={() => onPause(s.id)} onEnable={() => onEnable(s.id)} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Panel chi tiết ─────────────────────────────────────────────────────────

function TestResult({ src, testing }) {
  if (testing) {
    return <p className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs font-medium text-blue-700">Đang kiểm tra kết nối... (~1.2s)</p>;
  }
  if (src.lastTest === "passed") {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
        <p className="mb-1.5 font-bold text-emerald-700">✓ Kết nối thành công</p>
        <div className="grid grid-cols-2 gap-y-1 text-[11px] text-emerald-800">
          <div>Trạng thái: <strong className="text-emerald-700">Đạt</strong></div>
          <div>Thời gian phản hồi: <strong>320 ms</strong></div>
          <div>Access: <strong>Cho phép</strong></div>
          <div>Content type: <strong>Hợp lệ</strong></div>
        </div>
      </div>
    );
  }
  if (src.lastTest === "failed") {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-900">
        <p className="mb-1 font-bold text-red-700">✕ Không thể kết nối nguồn</p>
        <p className="text-[11px] text-red-800">Trạng thái: <strong>Không đạt</strong></p>
        <p className="mt-0.5 text-[11px] text-red-800">Lý do: <em>{src.failReason || "Thiếu trường cấu hình bắt buộc"}</em></p>
      </div>
    );
  }
  return null;
}

// ─── Lịch sử nạp dữ liệu (ingestion) của một nguồn ──────────────────────────

const RUN_TONE = { "Thành công": "success", "Thất bại": "error", "Đang chạy": "info" };

const pad = (n) => String(n).padStart(2, "0");
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fmtClock(iso) {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fmtDuration(start, end) {
  if (!end) return "—";
  const seconds = Math.max(0, Math.round((new Date(end) - new Date(start)) / 1000));
  return seconds < 60 ? `${seconds} giây` : `${Math.floor(seconds / 60)} phút ${seconds % 60} giây`;
}

function RunCard({ run }) {
  return (
    <li className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold text-blue-600">{run.id}</span>
        <StatusBadge tone={RUN_TONE[run.status]}>{run.status}</StatusBadge>
      </div>
      <p className="mt-1 text-[11px] text-slate-600">
        {run.trigger} · {fmtTime(run.startedAt)} → {run.finishedAt ? fmtTime(run.finishedAt) : "đang chạy"} · {fmtDuration(run.startedAt, run.finishedAt)}
      </p>
      <p className="mt-1 text-[11px] text-slate-700">
        Đạt: <strong className="text-emerald-700">{run.ok}</strong> bản ghi · Bị bỏ: <strong className={run.dropped ? "text-amber-700" : "text-slate-700"}>{run.dropped}</strong> bản ghi · Thử lại: <strong>{run.retries}</strong> lần
      </p>
      {run.error && <p role="alert" className="mt-1.5 rounded border border-red-200 bg-red-50 p-2 text-[11px] text-red-700">Lý do thất bại: {run.error}</p>}

      {(run.reasons.length > 0 || run.breakdown.length > 0) && (
        <details className="mt-1.5 text-[11px]">
          <summary className="cursor-pointer font-medium text-blue-600">Chi tiết lần chạy</summary>
          <div className="mt-1.5 space-y-2">
            {run.reasons.length > 0 && (
              <div>
                <p className="font-semibold text-slate-700">Lý do bản ghi bị bỏ</p>
                <ul className="mt-0.5 space-y-0.5 text-slate-600">
                  {run.reasons.map((r) => <li key={r.label}>• {r.label}: {r.count} bản ghi</li>)}
                </ul>
              </div>
            )}
            {run.breakdown.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="text-slate-500">
                    <tr><th scope="col" className="py-1 pr-2 font-semibold">Mã</th><th scope="col" className="py-1 pr-2 font-semibold">Loại báo cáo</th><th scope="col" className="py-1 pr-2 text-right font-semibold">Đạt</th><th scope="col" className="py-1 pr-2 text-right font-semibold">Bỏ</th><th scope="col" className="py-1 font-semibold">Ngày trang đăng</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-700">
                    {run.breakdown.map((b) => (
                      <tr key={`${b.co}-${b.type}`}>
                        <td className="py-1 pr-2 font-mono font-semibold">{b.co}</td><td className="py-1 pr-2">{b.type}</td>
                        <td className="py-1 pr-2 text-right tabular-nums">{b.ok}</td><td className="py-1 pr-2 text-right tabular-nums">{b.dropped}</td><td className="py-1">{b.published}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </details>
      )}
    </li>
  );
}

function SourceIngestionSection({ sourceId, sourceName, canRun, onNotify }) {
  const [runs, setRuns] = useState(null);
  const [refreshedAt, setRefreshedAt] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const timers = useRef(new Set());

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getIngestionRuns(sourceId)
      .then(({ runs: list, refreshedAt: at }) => { setRuns(list); setRefreshedAt(at); })
      .catch((e) => { setRuns(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, [sourceId]);
  useEffect(() => { load(); }, [load]);

  const closeConfirm = useCallback(() => setConfirmOpen(false), []);

  // Giả lập một lần chạy lại: hiện "Đang chạy" rồi hoàn thành sau 1,5 giây.
  function rerun() {
    const id = `JOB-LOCAL-${String((runs?.length ?? 0) + 1).padStart(3, "0")}`;
    const startedAt = new Date().toISOString();
    setRuns((list) => [{ id, trigger: "Thủ công", startedAt, finishedAt: null, ok: 0, dropped: 0, retries: 0, status: "Đang chạy", reasons: [], breakdown: [], error: null }, ...list]);
    setConfirmOpen(false);
    onNotify?.(`Đã bắt đầu chạy lại nguồn "${sourceName}".`, "info");
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      const finishedAt = new Date().toISOString();
      setRuns((list) => list.map((r) => (r.id === id ? { ...r, finishedAt, ok: 5, dropped: 0, status: "Thành công" } : r)));
      setRefreshedAt(finishedAt);
      onNotify?.(`Lần chạy ${id} hoàn tất: 5 bản ghi đạt, 0 bản ghi bị bỏ.`, "success");
    }, 1500);
    timers.current.add(timer);
  }

  const running = runs?.some((r) => r.status === "Đang chạy");

  return (
    <section aria-labelledby={`ingestion-${sourceId}`}>
      <div className="mb-2 flex items-center gap-1.5 border-b border-slate-100 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-500">
        <span id={`ingestion-${sourceId}`}>Lịch sử nạp dữ liệu</span>
        <span className="ml-auto normal-case tracking-normal font-normal text-slate-400">{refreshedAt ? `Làm mới lúc ${fmtClock(refreshedAt)}` : ""}</span>
      </div>

      {loading && <Skeleton rows={2} />}
      {!loading && error && <ErrorState title="Không thể tải lịch sử nạp dữ liệu" message={error} onRetry={load} />}

      {!loading && runs && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] text-slate-500">{runs.length} lần chạy gần đây</p>
            <div className="flex items-center gap-1.5">
              <Button variant="ghost" className="min-h-7 px-2 py-1 text-[11px]" onClick={load}>Làm mới</Button>
              <Button variant="secondary" className="min-h-7 px-2 py-1 text-[11px]" disabled={!canRun || running}
                title={canRun ? "Chạy lại nguồn này" : "Chỉ chạy lại được khi nguồn đang hoạt động."} onClick={() => setConfirmOpen(true)}>
                Chạy lại
              </Button>
            </div>
          </div>
          {runs.length === 0
            ? <p className="rounded-lg border border-dashed border-slate-300 bg-white p-4 text-center text-[11px] text-slate-500">Chưa có lần nạp dữ liệu nào cho nguồn này.</p>
            : <ul className="space-y-2">{runs.map((r) => <RunCard key={r.id} run={r} />)}</ul>}
        </div>
      )}

      {confirmOpen && (
        <div role="alertdialog" aria-label={`Xác nhận chạy lại nguồn ${sourceName}`} className="mt-2 space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="font-semibold">Chạy lại nguồn "{sourceName}"?</p>
          <p className="leading-relaxed text-amber-800">Hệ thống sẽ bắt đầu một lần nạp dữ liệu mới từ nguồn này. Bản ghi lỗi sẽ tự bị bỏ, dữ liệu đã có không bị xóa.</p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" className="min-h-8 px-2.5 py-1 text-xs" onClick={closeConfirm}>Hủy</Button>
            <Button className="min-h-8 px-2.5 py-1 text-xs" onClick={rerun}>Chạy lại</Button>
          </div>
        </div>
      )}
    </section>
  );
}

function DetailBody({ src, testing, onTest, onEdit, onPause, onEnable, onNotify }) {
  return (
    <div className="space-y-5 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <Button variant="secondary" className="min-h-8 px-2.5 py-1.5 text-xs" disabled={testing} loading={testing} onClick={onTest}>Kiểm tra kết nối</Button>
        <div className="flex items-center gap-1.5">
          <Button variant="secondary" className="min-h-8 px-2.5 py-1.5 text-xs" onClick={onEdit}>Chỉnh sửa</Button>
          <ToggleButton src={src} onPause={onPause} onEnable={onEnable} />
        </div>
      </div>

      <section>
        <SectionTitle>Tổng quan cấu hình</SectionTitle>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 rounded-lg border border-slate-200 bg-white p-3">
          <Field label="Tên nguồn">{src.name}</Field>
          <Field label="Loại nguồn">{src.type}</Field>
          <div className="col-span-2"><Field label="URL chính thức"><span className="break-all font-mono text-xs">{show(src.url)}</span></Field></div>
          <Field label="Phương thức truy cập">{src.access}</Field>
          <Field label="Lịch cập nhật">{show(src.schedule)}</Field>
          <Field label="Phiên bản hiện tại"><span className="font-mono font-semibold text-blue-600">{src.version}</span></Field>
          <Field label="Trạng thái"><StatusBadge tone={STATUS_TONE[src.status]}>{src.status}</StatusBadge></Field>
          <div className="col-span-2"><Field label="Lần kiểm tra gần nhất"><StatusBadge tone={TEST_BADGE[src.lastTest].tone}>{TEST_BADGE[src.lastTest].label}</StatusBadge></Field></div>
        </div>
      </section>

      <TestResult src={src} testing={testing} />

      <section>
        <SectionTitle>Thông tin quản trị nguồn</SectionTitle>
        <div className="space-y-2.5 rounded-lg border border-slate-200 bg-white p-3">
          <Field label="Chủ sở hữu nguồn">{show(src.owner)}</Field>
          <Field label="Mục đích sử dụng"><span className="font-normal leading-relaxed">{show(src.usage)}</span></Field>
          <Field label="Phạm vi dữ liệu"><span className="font-normal leading-relaxed">{show(src.scope)}</span></Field>
          <Field label="Phương án dự phòng (Fallback)">{show(src.fallback)}</Field>
          <Field label="Điều kiện sử dụng"><span className="font-normal">{show(src.terms)}</span></Field>
        </div>
      </section>

      <section>
        <SectionTitle>Trạng thái xác thực</SectionTitle>
        <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3">
          <span className="font-medium text-slate-900">Thông tin xác thực được lưu an toàn</span>
          <StatusBadge>{src.cred}</StatusBadge>
        </div>
      </section>

      <SourceIngestionSection key={src.id} sourceId={src.id} sourceName={src.name} canRun={src.status === "Hoạt động"} onNotify={onNotify} />

      <section>
        <SectionTitle extra={<Link to={`${ADMIN_LINKS.audit}?source=${src.id}`} className="text-[11px] font-medium text-blue-600 hover:underline">Xem nhật ký →</Link>}>
          Lịch sử phiên bản cấu hình
        </SectionTitle>
        {src.history.length === 0 ? (
          <p className="text-[11px] italic text-slate-400">Chưa có lịch sử phiên bản</p>
        ) : (
          <ul className="space-y-2">
            {src.history.map((h) => (
              <li key={`${h.v}-${h.at}`} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-blue-600">{h.v}</span>
                  <span className="text-[10px] text-slate-500">{h.at}</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-700">Người thực hiện: <strong>{h.by}</strong></p>
                <p className="mt-0.5 text-[11px] text-slate-500">Thay đổi: <span className="font-medium text-slate-800">{h.changed.join(", ")}</span></p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ─── Form thêm / sửa ────────────────────────────────────────────────────────

const textareaClass = "w-full rounded-lg border border-[#CBD5E1] bg-white px-3 py-2 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]";
const toOptions = (list) => list.map((v) => ({ value: v, label: v }));

function SourceForm({ form, errors, onChange, onSubmit }) {
  const set = (key) => (e) => onChange(key, e.target.value);
  return (
    <form id="source-form" onSubmit={onSubmit} noValidate className="space-y-4">
      {errors.length > 0 && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">
          <p className="mb-1 font-bold">✕ Không thể lưu cấu hình</p>
          <ul className="list-disc space-y-0.5 pl-5 text-[11px]">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      <Input label="Tên nguồn *" placeholder="Ví dụ: Báo cáo thường niên FPT" value={form.name} onChange={set("name")} />
      <Select label="Loại nguồn *" options={toOptions(SOURCE_TYPES)} value={form.type} onChange={set("type")} />
      <Input label="URL chính thức" placeholder={`Để trống hiển thị '${NO_DATA}'`} value={form.url} onChange={set("url")}
        hint="Lưu ý: Không tự ý sáng tạo URL. Nguồn HTTP / Web và API cần có URL để lưu." />
      <div className="grid grid-cols-2 gap-3">
        <Select label="Phương thức truy cập *" options={toOptions(ACCESS_METHODS)} value={form.access} onChange={set("access")} />
        <Select label="Lịch cập nhật" options={toOptions(SCHEDULES)} value={form.schedule} onChange={set("schedule")} />
      </div>
      <Input label="Chủ sở hữu nguồn *" placeholder="Ví dụ: FinMind Admin" value={form.owner} onChange={set("owner")} />
      <div>
        <label htmlFor="source-usage" className="mb-1 block text-xs font-semibold text-[#334155]">Mục đích sử dụng</label>
        <textarea id="source-usage" rows={2} className={textareaClass} value={form.usage} onChange={set("usage")}
          placeholder="Đối chiếu thông tin công bố niêm yết, tham chiếu báo cáo..." />
      </div>
      <Input label="Phạm vi dữ liệu" placeholder="Ví dụ: Công bố thông tin của doanh nghiệp niêm yết" value={form.scope} onChange={set("scope")} />
      <div className="grid grid-cols-2 gap-3">
        <Input label="Fallback" placeholder="Ví dụ: Nguồn HOSE" value={form.fallback} onChange={set("fallback")} />
        <Input label="Điều kiện sử dụng" placeholder={NO_DATA} value={form.terms} onChange={set("terms")} />
      </div>
      <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div>
          <p className="text-xs font-medium text-slate-900">Thông tin xác thực được lưu an toàn</p>
          <p className="text-[11px] text-slate-500">Không nhập hoặc lưu mật mã trực tiếp</p>
        </div>
        <StatusBadge>Chưa cấu hình</StatusBadge>
      </div>
    </form>
  );
}

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminSourcesPage() {
  const { sourceId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [testingIds, setTestingIds] = useState(() => new Set());
  const [editing, setEditing] = useState(null); // null | { id: string | null }
  const [form, setForm] = useState(formFrom(null));
  const [formErrors, setFormErrors] = useState([]);
  const [confirm, setConfirm] = useState(null); // null | { kind: "pause" | "enable", id }
  const [toasts, setToasts] = useState([]);

  const timers = useRef(new Set());
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  // Khi form sửa hoặc hộp xác nhận đang mở, phím Esc chỉ đóng lớp trên cùng, không đóng panel chi tiết bên dưới.
  const overlayOpen = useRef(false);
  overlayOpen.current = editing !== null || confirm !== null;

  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const later = useCallback((fn, ms) => {
    const id = setTimeout(() => { timers.current.delete(id); fn(); }, ms);
    timers.current.add(id);
  }, []);

  const toast = useCallback((message, type = "info") => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((t) => [...t, { id, message, type }]);
    later(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, [later]);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getSources()
      .then(setSources)
      .catch((e) => { setSources(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const patchSource = useCallback((id, patch) => {
    setSources((list) => list.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }, []);

  const activeId = sourceId || searchParams.get("source");
  const active = sources?.find((s) => s.id === activeId) ?? null;
  const rows = sources ? filterSources(sources, filters) : [];
  const confirmSrc = confirm ? sources?.find((s) => s.id === confirm.id) : null;

  const openDetail = useCallback((id) => navigateRef.current(`${ADMIN_LINKS.sources}/${id}`), []);
  const closeDetail = useCallback(() => {
    if (overlayOpen.current) return;
    navigateRef.current(ADMIN_LINKS.sources);
  }, []);
  const closeEdit = useCallback(() => setEditing(null), []);
  const closeConfirm = useCallback(() => setConfirm(null), []);

  function openForm(id) {
    setForm(formFrom(id ? sources.find((s) => s.id === id) : null));
    setFormErrors([]);
    setEditing({ id });
  }

  function testConnection(id) {
    const src = sources.find((s) => s.id === id);
    if (!src || testingIds.has(id)) return;
    setTestingIds((set) => new Set(set).add(id));
    toast(`Đang kiểm tra kết nối đến nguồn ${src.name}...`, "info");

    later(() => {
      setTestingIds((set) => { const next = new Set(set); next.delete(id); return next; });
      if (src.willPassTest) {
        patchSource(id, { testOk: true, lastTest: "passed", ...(src.status === "Kiểm tra thất bại" ? { status: "Chưa kiểm tra" } : {}) });
        toast(`Kết nối thành công tới ${src.name}: Trạng thái Đạt`, "success");
      } else {
        patchSource(id, { testOk: false, lastTest: "failed", status: "Kiểm tra thất bại" });
        toast(`Không thể kết nối nguồn ${src.name}: ${src.failReason || "Thiếu trường cấu hình bắt buộc"}`, "error");
      }
    }, 1200);
  }

  function askPause(id) { setConfirm({ kind: "pause", id }); }
  function askEnable(id) {
    const check = canEnable(sources.find((s) => s.id === id));
    if (!check.ok) toast(check.reason, "error");
    else setConfirm({ kind: "enable", id });
  }

  function doConfirm() {
    if (!confirmSrc) return;
    if (confirm.kind === "pause") {
      patchSource(confirmSrc.id, { status: "Tạm dừng" });
      toast(`Đã tạm dừng nguồn "${confirmSrc.name}". Không chạy ingestion mới. Lịch sử và các phiên bản trước được giữ nguyên. Dữ liệu đã có không bị xóa.`, "warning");
    } else {
      patchSource(confirmSrc.id, { status: "Hoạt động" });
      toast(`Đã bật nguồn dữ liệu "${confirmSrc.name}" thành công.`, "success");
    }
    setConfirm(null);
  }

  function submitForm(e) {
    e.preventDefault();
    const errors = validate(form);
    setFormErrors(errors);
    if (errors.length > 0) return;

    const values = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim()]));
    const at = nowLabel();

    if (editing.id) {
      const src = sources.find((s) => s.id === editing.id);
      const changed = FORM_FIELD_LABELS.filter(([key]) => (src[key] ?? "") !== values[key]).map(([, label]) => label);
      const version = bumpVersion(src.version);
      patchSource(src.id, {
        ...values, version,
        history: [{ v: version, by: "Quản trị viên", at, changed: changed.length ? changed : ["Cập nhật thông tin quản trị"] }, ...src.history],
      });
      setEditing(null);
      toast(`Đã tạo phiên bản cấu hình mới ${version}`, "success");
    } else {
      const nextNumber = Math.max(0, ...sources.map((s) => Number(s.id.replace("src-", "")) || 0)) + 1;
      const id = `src-${nextNumber}`;
      setSources((list) => [...list, {
        ...values, id, status: "Chưa kiểm tra", version: "v1.0", lastTest: "none", testOk: false, willPassTest: true, cred: "Chưa cấu hình",
        history: [{ v: "v1.0", by: "Quản trị viên", at, changed: ["Tạo cấu hình"] }],
      }]);
      setEditing(null);
      toast(`Đã thêm nguồn dữ liệu mới ${id} (phiên bản v1.0)`, "success");
      openDetail(id);
    }
  }

  const confirmText = confirmSrc && (confirm.kind === "pause"
    ? `Tạm dừng nguồn "${confirmSrc.name}"? Không chạy ingestion mới. Lịch sử và các phiên bản trước được giữ nguyên.`
    : `Bật nguồn "${confirmSrc.name}"?`);

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200/70 pb-3 md:flex-row md:items-center">
        <div>
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link>
            <span aria-hidden="true" className="text-slate-300">/</span>
            <span className="font-medium text-slate-900">Cấu hình nguồn</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Cấu hình nguồn dữ liệu</h1>
            <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">Dữ liệu minh họa</span>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">Quản lý các nguồn dữ liệu được phép kết nối và sử dụng trong FinMind.</p>
        </div>
        <Button className="shrink-0 self-start text-xs" disabled={!sources} onClick={() => openForm(null)}>＋ Thêm nguồn dữ liệu</Button>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && sources && (
        <section className="space-y-4">
          <FilterBar filters={FILTER_FIELDS} values={filters}
            onChange={(key, value) => setFilters((f) => ({ ...f, [key]: value }))}
            onReset={() => setFilters(EMPTY_FILTERS)} />
          <SourceTable rows={rows} activeId={active?.id} testingIds={testingIds}
            onOpen={openDetail} onTest={testConnection} onEdit={openForm}
            onPause={askPause} onEnable={askEnable} onResetFilters={() => setFilters(EMPTY_FILTERS)} />
          <p className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
            <span>Hiển thị {rows.length} nguồn dữ liệu</span>
            <span className="text-[11px]">Chọn một dòng để xem thông tin chi tiết</span>
          </p>
        </section>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-xs text-slate-500">
        Chỉ dùng cho quản trị vận hành FinMind. Dữ liệu minh họa.
      </footer>

      <Drawer open={Boolean(active)} onClose={closeDetail} title={active ? active.name : ""}
        footer={active && (
          <div className="flex w-full items-center justify-between text-[11px] text-slate-500">
            <span>Mã định danh: <span className="font-mono text-slate-900">{active.id}</span></span>
            <Button variant="ghost" onClick={closeDetail}>Đóng panel</Button>
          </div>
        )}>
        {active && (
          <DetailBody src={active} testing={testingIds.has(active.id)}
            onTest={() => testConnection(active.id)} onEdit={() => openForm(active.id)}
            onPause={() => askPause(active.id)} onEnable={() => askEnable(active.id)} onNotify={toast} />
        )}
      </Drawer>

      <Drawer open={editing !== null} onClose={closeEdit}
        title={editing?.id ? `Chỉnh sửa nguồn: ${sources?.find((s) => s.id === editing.id)?.name ?? ""}` : "Thêm nguồn dữ liệu mới"}
        footer={<><Button variant="secondary" onClick={closeEdit}>Hủy</Button><Button type="submit" form="source-form">Lưu cấu hình</Button></>}>
        <SourceForm form={form} errors={formErrors} onSubmit={submitForm}
          onChange={(key, value) => setForm((f) => ({ ...f, [key]: value }))} />
      </Drawer>

      <Modal open={Boolean(confirmSrc)} onClose={closeConfirm} title={confirm?.kind === "pause" ? "Tạm dừng nguồn" : "Bật nguồn"}
        footer={<><Button variant="secondary" onClick={closeConfirm}>Hủy</Button><Button onClick={doConfirm}>{confirm?.kind === "pause" ? "Tạm dừng" : "Bật"}</Button></>}>
        {confirmText}
      </Modal>

      <Toasts items={toasts} />
    </AdminLayout>
  );
}
