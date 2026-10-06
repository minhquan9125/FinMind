// Trang A00: Tổng quan vận hành (route /admin và /admin/overview).
// Dữ liệu minh họa lấy từ ./mock.js; chuyển sang API thật chỉ cần đổi hàm getOverview.

import { useCallback, useEffect, useState } from "react";
import { Link } from "../../app/router.jsx";
import { Button, Card, DataTable, ErrorState, Skeleton, Stat, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { getOverview } from "./mock.js";

const TEXT_TONE = { success: "text-emerald-600", warning: "text-amber-600", error: "text-rose-600" };

function budgetBarColor(pct, warnAt) {
  if (pct >= 100) return "bg-rose-600";
  if (pct >= warnAt) return "bg-amber-500";
  return "bg-blue-600";
}

function Verdict({ value }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return <span className={`font-semibold ${TEXT_TONE[value.tone] || "text-slate-600"}`}>{value.label}</span>;
}

const traceColumns = [
  { key: "time", label: "Thời gian", render: (r) => <span className="tabular-nums text-slate-500">{r.time}</span> },
  {
    key: "id",
    label: "Trace ID",
    render: (r) => (
      <Link to={`${ADMIN_LINKS.traces}?trace=${r.id}`} className="font-medium text-blue-600 hover:underline">{r.id}</Link>
    ),
  },
  { key: "company", label: "Doanh nghiệp", render: (r) => <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 font-semibold text-slate-800">{r.company}</span> },
  { key: "status", label: "Trạng thái", render: (r) => <StatusBadge tone={r.tone}>{r.status}</StatusBadge> },
  { key: "gate", label: "Evidence Gate", render: (r) => <Verdict value={r.gate} /> },
  { key: "verifier", label: "Verifier", render: (r) => <Verdict value={r.verifier} /> },
  { key: "duration", label: "Thời gian xử lý", render: (r) => <span className="tabular-nums text-slate-500">{r.duration ?? "—"}</span> },
  { key: "tokens", label: "Token", render: (r) => <span className="tabular-nums text-slate-500">{r.tokens ?? "—"}</span> },
];

function SectionTitle({ children }) {
  return <h2 className="mb-3 text-base font-semibold text-slate-900">{children}</h2>;
}

function BudgetCard({ budget }) {
  const pct = Math.round((budget.used / budget.limit) * 100);
  return (
    <Card title="Mức sử dụng ngân sách hiện tại">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-xl font-bold text-slate-800">Đã sử dụng {pct}%</span>
        <span className="text-[13px] text-slate-500">{budget.used} / {budget.limit} đơn vị · cảnh báo từ {budget.warnAt}%</span>
      </div>
      <div
        role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
        aria-label="Mức sử dụng ngân sách API"
        className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100"
      >
        <div className={`h-full rounded-full transition-all duration-300 ${budgetBarColor(pct, budget.warnAt)}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <p className="mt-2.5 text-xs text-slate-500">
        Thanh tiến độ chuyển sang màu hổ phách khi gần chạm giới hạn và màu đỏ khi vượt giới hạn.
      </p>
      <Link to={`${ADMIN_LINKS.configuration}?focus=budget`} className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-blue-600 hover:underline">
        Xem cấu hình ngưỡng &amp; ngân sách API →
      </Link>
    </Card>
  );
}

function AlertsCard({ alerts }) {
  return (
    <Card title="Cảnh báo vận hành" action={<span className="text-[11px] font-semibold text-slate-400">{alerts.length} cảnh báo</span>}>
      {alerts.length === 0 ? (
        <p className="text-sm text-slate-500">Không có cảnh báo nào.</p>
      ) : (
        <ul className="-my-2.5 divide-y divide-slate-100">
          {alerts.map((a) => (
            <li key={a.id} className="flex items-start justify-between gap-3 py-2.5">
              <div className="flex items-start gap-2 text-sm text-slate-700">
                <span aria-hidden="true" className={`mt-0.5 ${a.tone === "error" ? "text-rose-600" : "text-amber-600"}`}>{a.tone === "error" ? "●" : "▲"}</span>
                <span>{a.text}</span>
              </div>
              <Link to={a.to} className="mt-0.5 whitespace-nowrap text-xs font-medium text-blue-600 hover:underline">{a.linkLabel}</Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ActivityCard({ items, date }) {
  return (
    <Card title="Hoạt động quản trị gần đây" action={<span className="text-[11px] font-semibold text-slate-400">{date}</span>}>
      <ul className="-my-2.5 divide-y divide-slate-100">
        {items.map((a) => (
          <li key={a.id}>
            <Link to={`${ADMIN_LINKS.audit}?event=${a.id}`} className="-mx-2 flex items-center justify-between gap-3 rounded px-2 py-2.5 hover:bg-slate-50">
              <span className="flex items-center gap-3 text-sm text-slate-700">
                <span className="w-10 text-xs tabular-nums text-slate-400">{a.time}</span>
                {a.text}
              </span>
              <span className={`text-xs font-semibold ${a.ok ? "text-emerald-600" : "text-rose-600"}`}>{a.ok ? "Thành công" : "Thất bại"}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link to={ADMIN_LINKS.audit} className="mt-4 block text-[13px] font-medium text-blue-600 hover:underline">Xem toàn bộ trong Nhật ký kiểm toán →</Link>
    </Card>
  );
}

function ServicesCard({ services }) {
  return (
    <Card title="Dịch vụ cốt lõi" action={<span className="text-[11px] font-semibold text-slate-400">{services.length} dịch vụ</span>}>
      <ul className="-my-2.5 divide-y divide-slate-100">
        {services.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-2.5">
            <div>
              <p className="text-[13px] font-medium text-slate-800">{s.name}</p>
              <p className="text-xs text-slate-500">{s.desc}</p>
            </div>
            <StatusBadge tone={s.ok ? "success" : "error"}>{s.ok ? "Hoạt động" : "Gián đoạn"}</StatusBadge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function OverviewContent({ data }) {
  return (
    <>
      <section aria-labelledby="kpi-title">
        <h2 id="kpi-title" className="mb-3 text-base font-semibold text-slate-900">Tổng quan hoạt động</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          {data.kpis.map((k) => <Stat key={k.id} label={k.label} value={<span className="tabular-nums">{k.value}</span>} />)}
        </div>
      </section>

      <section><BudgetCard budget={data.budget} /></section>

      <section>
        <SectionTitle>Truy vấn gần đây</SectionTitle>
        <p className="-mt-2 mb-3 text-[13px] text-slate-500">{data.recentTraces.length} truy vấn gần nhất</p>
        <DataTable columns={traceColumns} rows={data.recentTraces} emptyMessage="Chưa có truy vấn nào" />
        <Link to={ADMIN_LINKS.traces} className="mt-3 inline-block text-[13px] font-medium text-blue-600 hover:underline">
          Xem toàn bộ lịch sử trong Theo dõi truy vấn →
        </Link>
      </section>

      <section className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <AlertsCard alerts={data.alerts} />
          <ActivityCard items={data.activities} date={data.activityDate} />
        </div>
        <ServicesCard services={data.services} />
      </section>

      <PageFooter />
    </>
  );
}

function PageFooter() {
  return (
    <footer className="mt-auto flex flex-col items-center justify-between gap-2 border-t border-slate-200 pb-6 pt-4 text-xs text-slate-500 sm:flex-row">
      <p>FinMind · Capstone CMU-SE 450 · 2026</p>
    </footer>
  );
}

export default function AdminOverviewPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getOverview()
      .then(setData)
      .catch((e) => { setData(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const healthy = data ? data.services.every((s) => s.ok) : null;

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-4 border-b border-slate-200/70 pb-2 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tổng quan vận hành</h1>
          <p className="mt-1 text-[13px] text-slate-500">Theo dõi tình trạng dịch vụ, truy vấn và mức sử dụng tài nguyên của FinMind.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          {healthy !== null && (
            <span className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[13px] font-medium ${healthy ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
              <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${healthy ? "bg-emerald-500" : "bg-rose-500"}`} />
              {healthy ? "Hệ thống hoạt động bình thường" : "Có dịch vụ gián đoạn"}
            </span>
          )}
          <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">Dữ liệu minh họa</span>
        </div>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}
      {!loading && data && <OverviewContent data={data} />}
    </AdminLayout>
  );
}
