// Trang A05: Nhật ký kiểm toán (route /admin/audit).
// Tham số địa chỉ: ?event=AUD-... mở chi tiết sự kiện; ?trace= | ?config= | ?corpus= | ?source= lọc theo thành phần liên quan.
// Dữ liệu minh họa lấy từ ./auditMock.js; chuyển sang API thật chỉ cần đổi hàm getAuditEvents.

import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "../../app/router.jsx";
import { Button, Drawer, EmptyState, ErrorState, FilterBar, Modal, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { ACTION_TYPES, ACTORS, RESOURCE_TYPES, RESULTS, getAuditEvents } from "./auditMock.js";
import useToasts from "./useToasts.jsx";

// ─── Hằng số & hàm thuần ────────────────────────────────────────────────────

const NO_VALUE = "—";
const EMPTY_FILTERS = { q: "", time: "all", type: "all", actor: "all", result: "all", rtype: "all" };

const INBOUND = [
  { key: "trace", field: "trace", label: "Trace ID" },
  { key: "config", field: "config", label: "Configuration" },
  { key: "corpus", field: "corpus", label: "Corpus" },
  { key: "source", field: "source", label: "Source Adapter" },
];

const opts = (labelAll, values) => [{ value: "all", label: labelAll }, ...values.map((v) => ({ value: v, label: v }))];

const FILTER_FIELDS = [
  { key: "q", type: "text", label: "Tìm kiếm", placeholder: "Tìm theo Event ID hoặc Trace ID..." },
  { key: "time", type: "select", label: "Thời gian", options: [
    { value: "all", label: "Tất cả" }, { value: "in_retention", label: "Trong thời hạn lưu giữ" }, { value: "expired", label: "Ngoài thời hạn lưu giữ" },
  ] },
  { key: "type", type: "select", label: "Loại sự kiện", options: opts("Tất cả", ACTION_TYPES) },
  { key: "actor", type: "select", label: "Actor / Role", options: opts("Tất cả", ACTORS) },
  { key: "result", type: "select", label: "Kết quả", options: opts("Tất cả", RESULTS) },
  { key: "rtype", type: "select", label: "Resource", options: opts("Tất cả", RESOURCE_TYPES) },
];

// Bản ghi ngoài thời hạn lưu giữ không còn thuộc tính nào để lọc: chỉ khớp khi không lọc theo thuộc tính.
function matches(ev, f, inbound) {
  if (inbound && ev[inbound.field] !== inbound.value) return false;
  if (f.time === "in_retention" && ev.retentionExpired) return false;
  if (f.time === "expired" && !ev.retentionExpired) return false;
  const q = f.q.trim().toLowerCase();
  if (ev.retentionExpired) {
    if (f.type !== "all" || f.actor !== "all" || f.result !== "all" || f.rtype !== "all") return false;
    return !q || ev.id.toLowerCase().includes(q);
  }
  if (f.type !== "all" && ev.type !== f.type) return false;
  if (f.actor !== "all" && ev.actor !== f.actor) return false;
  if (f.result !== "all" && ev.result !== f.result) return false;
  if (f.rtype !== "all" && ev.rtype !== f.rtype) return false;
  return !q || ev.id.toLowerCase().includes(q) || Boolean(ev.trace?.toLowerCase().includes(q));
}

// ─── Thành phần nhỏ ─────────────────────────────────────────────────────────

const resultTone = (result) => (result === "Thành công" ? "success" : "error");
const Dash = () => <span className="text-slate-400">{NO_VALUE}</span>;

function Meta({ label, children, wide }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-0.5 text-[13px] font-medium text-slate-900">{children}</div>
    </div>
  );
}

function Related({ label, to, text }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-slate-500">{label}</span>
      {to ? <Link to={to} className="font-mono font-semibold text-blue-600 hover:underline">{text} ↗</Link> : <Dash />}
    </div>
  );
}

function EventDetail({ ev }) {
  if (ev.retentionExpired) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Event ID</div>
            <div className="mt-0.5 font-mono text-base font-bold text-slate-900">{ev.id}</div>
          </div>
          <StatusBadge>Ngoài thời hạn lưu giữ</StatusBadge>
        </div>
        <div role="note" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
          <p className="text-[13px] font-semibold">Bản ghi không còn được lưu theo chính sách lưu giữ.</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-700">Dữ liệu chi tiết đã được làm sạch và xoá vĩnh viễn khỏi bộ nhớ theo quy chuẩn tuân thủ bảo mật nội bộ.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 text-[13px]">
      <div className="grid grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <Meta label="Thời gian"><span className="font-mono">{ev.time}</span></Meta>
        <Meta label="Kết quả"><StatusBadge tone={resultTone(ev.result)}>{ev.result}</StatusBadge></Meta>
        <Meta label="Actor">{ev.actor}</Meta>
        <Meta label="Role">{ev.role}</Meta>
        <Meta label="Action">{ev.action}</Meta>
        <Meta label="Resource Type">{ev.rtype}</Meta>
        <Meta label="Resource ID" wide><span className="font-mono">{ev.resource}</span></Meta>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-slate-900">Thành phần liên quan</h3>
        <div className="divide-y divide-slate-100 text-xs">
          <Related label="Related Trace ID" to={ev.trace && `${ADMIN_LINKS.traces}/${ev.trace}`} text={ev.trace} />
          <Related label="Related Configuration" to={ev.config && `${ADMIN_LINKS.configuration}?cfg=${ev.config}`} text={`CFG ${ev.config}`} />
          <Related label="Related Corpus" to={ev.corpus && `${ADMIN_LINKS.corpus}?corpus=${ev.corpus}`} text={`Corpus ${ev.corpus}`} />
          <Related label="Source Adapter" to={ev.source && `${ADMIN_LINKS.sources}?source=${ev.source}`} text={ev.source} />
        </div>
      </section>

      {ev.reason && (
        <section role="alert" className="space-y-1.5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
          <h3 className="text-[13px] font-semibold">Lý do (đã làm sạch)</h3>
          <p className="text-xs leading-relaxed text-red-700">{ev.reason}</p>
        </section>
      )}

      {ev.sanitized && (
        <section className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-[13px] font-semibold text-slate-900">Dữ liệu đã làm sạch</h3>
          <div className="divide-y divide-slate-100">
            {Object.entries(ev.sanitized).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between py-1.5">
                <span className="text-xs text-slate-500">{key}</span>
                <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-medium text-slate-600">{value}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const EXPORT_FIELDS = ["Thời gian", "Event ID", "Actor", "Hành động", "Resource", "Kết quả", "Trace ID"];

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminAuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast, toastNode } = useToasts(3000);

  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [exportOpen, setExportOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getAuditEvents()
      .then(setEvents)
      .catch((e) => { setEvents(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  // Địa chỉ là nguồn sự thật cho bộ lọc đến từ trang khác và cho sự kiện đang mở.
  const inboundDef = INBOUND.find((d) => searchParams.get(d.key));
  const inbound = inboundDef ? { field: inboundDef.field, value: searchParams.get(inboundDef.key), label: `${inboundDef.label} = ${searchParams.get(inboundDef.key)}` } : null;
  const eventId = searchParams.get("event");
  const selected = events?.find((e) => e.id === eventId) ?? null;

  const updateParams = useCallback((mutate) => {
    setSearchParams((current) => { const next = new URLSearchParams(current); mutate(next); return next; });
  }, [setSearchParams]);
  const clearInbound = () => updateParams((p) => INBOUND.forEach((d) => p.delete(d.key)));
  const openEvent = (id) => updateParams((p) => p.set("event", id));
  const closeEvent = useCallback(() => updateParams((p) => p.delete("event")), [updateParams]);
  const closeExport = useCallback(() => setExportOpen(false), []);

  const rows = events ? events.filter((e) => matches(e, filters, inbound)) : [];

  return (
    <AdminLayout>
      <header className="flex flex-col gap-2 border-b border-slate-200/70 pb-3">
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-slate-500">
          <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link>
          <span aria-hidden="true">/</span>
          <span className="font-medium text-slate-900">Nhật ký kiểm toán</span>
        </nav>
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[22px] font-bold tracking-tight text-slate-900">Nhật ký kiểm toán</h1>
            <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">Dữ liệu minh họa</span>
          </div>
          <Button variant="secondary" className="shrink-0 text-[13px]" disabled={!events} onClick={() => setExportOpen(true)}>⬇ Xuất nhật ký (đã làm sạch)</Button>
        </div>
        <p className="text-[13px] text-slate-500">Theo dõi các sự kiện quản trị và vận hành đã được ghi nhận trong FinMind.</p>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && events && (
        <section className="space-y-4">
          {inbound && (
            <div role="status" className="flex items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-[13px] text-blue-800">
              <span>Đang lọc theo: <strong className="font-semibold text-blue-700">{inbound.label}</strong></span>
              <button type="button" onClick={clearInbound} className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline">✕ Xóa lọc</button>
            </div>
          )}

          <FilterBar filters={FILTER_FIELDS} values={filters}
            onChange={(key, value) => setFilters((f) => ({ ...f, [key]: value }))}
            onReset={() => { setFilters(EMPTY_FILTERS); clearInbound(); }} />

          <div className="flex items-center gap-3">
            <h2 className="text-[15px] font-bold text-slate-900">Danh sách sự kiện kiểm toán</h2>
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">({rows.length}/{events.length})</span>
          </div>

          {rows.length === 0 ? (
            <EmptyState title="Không tìm thấy sự kiện kiểm toán phù hợp." description="Thử thay đổi bộ lọc hoặc từ khóa tìm kiếm của bạn." />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="w-full border-collapse text-left text-[13px]">
                <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-500">
                  <tr>
                    {["Thời gian", "Event ID", "Actor", "Hành động", "Resource", "Kết quả", "Trace ID", "Thao tác"].map((h) => (
                      <th key={h} scope="col" className={`whitespace-nowrap px-4 py-3 ${h === "Thao tác" ? "text-right" : ""}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-800">
                  {rows.map((ev) => (
                    <tr key={ev.id} onClick={() => openEvent(ev.id)} className={`cursor-pointer hover:bg-slate-50 ${eventId === ev.id ? "bg-blue-50/50" : ""}`}>
                      {ev.retentionExpired ? (
                        <>
                          <td className="whitespace-nowrap px-4 py-3.5"><StatusBadge>Ngoài thời hạn lưu giữ</StatusBadge></td>
                          <td className="whitespace-nowrap px-4 py-3.5 font-mono font-medium text-slate-900">{ev.id}</td>
                          {[1, 2, 3, 4, 5].map((i) => <td key={i} className="whitespace-nowrap px-4 py-3.5"><Dash /></td>)}
                        </>
                      ) : (
                        <>
                          <td className="whitespace-nowrap px-4 py-3.5 font-mono text-xs text-slate-600">{ev.time}</td>
                          <td className="whitespace-nowrap px-4 py-3.5 font-mono font-semibold text-slate-900">{ev.id}</td>
                          <td className="whitespace-nowrap px-4 py-3.5 font-medium">{ev.actor}</td>
                          <td className="whitespace-nowrap px-4 py-3.5 font-medium text-slate-700">{ev.action}</td>
                          <td className="whitespace-nowrap px-4 py-3.5">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="rounded border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">{ev.rtype}</span>
                              <span className="font-medium text-slate-900">{ev.resource}</span>
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-4 py-3.5"><StatusBadge tone={resultTone(ev.result)}>{ev.result}</StatusBadge></td>
                          <td className="whitespace-nowrap px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                            {ev.trace ? <Link to={`${ADMIN_LINKS.traces}/${ev.trace}`} className="font-mono font-medium text-blue-600 hover:underline">{ev.trace}</Link> : <Dash />}
                          </td>
                        </>
                      )}
                      <td className="whitespace-nowrap px-4 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                        <button type="button" onClick={() => openEvent(ev.id)} className="text-xs font-semibold text-blue-600 hover:underline">Xem chi tiết</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-center text-xs text-slate-500">Chỉ dùng cho quản trị vận hành FinMind.</footer>

      <Drawer open={Boolean(selected)} onClose={closeEvent} title="Chi tiết sự kiện kiểm toán"
        footer={<Button variant="secondary" onClick={closeEvent}>Đóng</Button>}>
        {selected && (
          <div className="space-y-4">
            <p className="font-mono text-xs text-slate-500">{selected.id}</p>
            <EventDetail ev={selected} />
          </div>
        )}
      </Drawer>

      <Modal open={exportOpen} onClose={closeExport} title="Xuất nhật ký kiểm toán"
        footer={<>
          <Button variant="secondary" onClick={closeExport}>Hủy</Button>
          <Button onClick={() => { closeExport(); toast("Đã chuẩn bị tệp xuất (minh họa)", "success"); }}>Xuất</Button>
        </>}>
        <div className="space-y-4 text-[13px] text-slate-700">
          <p className="rounded-lg border border-blue-200 bg-blue-50 p-3.5 leading-relaxed text-blue-800">
            Chỉ xuất các trường đã được làm sạch và được phép hiển thị. Không xuất secret hoặc raw payload.
          </p>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Các trường thông tin sẽ xuất:</p>
            <ul className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              {EXPORT_FIELDS.map((f) => <li key={f}><span aria-hidden="true" className="text-emerald-500">✓ </span>{f}</li>)}
            </ul>
          </div>
          <p className="text-xs text-slate-500">Định dạng tệp: <strong>CSV (UTF-8, Sanitized)</strong></p>
        </div>
      </Modal>

      {toastNode}
    </AdminLayout>
  );
}
