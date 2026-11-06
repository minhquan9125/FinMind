// Trang A00: Tổng quan vận hành (route /admin và /admin/overview).
// Giữ đầy đủ bố cục ban đầu. Mục chưa có API được ghi rõ chưa triển khai.

import { useCallback, useEffect, useState } from "react";
import { Link } from "../../app/router.jsx";
import { Button, Card, DataTable, ErrorState, Skeleton, Stat, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { getOverview } from "./overviewData.js";
import { localTime, STATE_LABELS } from "./operationsApi.js";
import BudgetUsage from "./BudgetUsage.jsx";

const TEXT_TONE = { success: "text-emerald-600", warning: "text-amber-600", error: "text-rose-600" };

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
      <Link to={`${ADMIN_LINKS.traces}/${r.id}`} className="break-all text-xs font-medium text-blue-600 hover:underline">{r.id}</Link>
    ),
  },
  { key: "company", label: "Doanh nghiệp", render: (r) => <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 font-semibold text-slate-800">{r.company}</span> },
  { key: "status", label: "Trạng thái", render: (r) => <StatusBadge tone={r.tone}>{r.status}</StatusBadge> },
  { key: "gate", label: "Evidence Gate", render: (r) => <Verdict value={r.gate} /> },
  { key: "verifier", label: "Verifier", render: (r) => <Verdict value={r.verifier} /> },
  { key: "duration", label: "Thời gian xử lý", render: (r) => <span className="tabular-nums text-slate-500">{r.duration ?? "—"}</span> },
  { key: "tokens", label: "Token", render: (r) => <span className="tabular-nums text-slate-500">{r.tokens ?? "—"}</span> },
  { key: "model", label: "Model", render: (r) => <span className="text-xs text-slate-500">{r.model}</span> },
];

function SectionTitle({ children }) {
  return <h2 className="mb-3 text-base font-semibold text-slate-900">{children}</h2>;
}

function BudgetCard({ budget }) {
  return <><BudgetUsage data={budget} /><Link to={ADMIN_LINKS.configuration} className="mt-3 inline-block text-sm text-blue-600">Cấu hình ngưỡng & ngân sách API →</Link></>;
}

function AlertsCard({ alerts }) {
  return (
    <Card title="Cảnh báo vận hành" action={<span className="text-[11px] font-semibold text-slate-400">{alerts.length} cảnh báo</span>}>
      {alerts.length === 0 ? (
        <p className="text-sm text-slate-500">Không ghi nhận cảnh báo từ hàng đợi và kho dữ liệu trong lần kiểm tra này.</p>
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

function ActivityCard({ items, date, available }) {
  return (
    <Card title="Hoạt động quản trị gần đây" action={<span className="text-[11px] font-semibold text-slate-400">{date}</span>}>
      <ul className="-my-2.5 divide-y divide-slate-100">
        {items.map((a) => (
          <li key={a.id}>
            <Link to={ADMIN_LINKS.audit} className="-mx-2 block rounded px-2 py-2.5 hover:bg-slate-50">
              <span className="block text-xs tabular-nums text-slate-400">{a.time}</span>
              <span className="mt-1 block break-words text-sm text-slate-700">{a.text}</span>
              <span className="mt-1 block break-all text-xs text-slate-400">{a.resource}</span>
            </Link>
          </li>
        ))}
      </ul>
      {!items.length && <p className="text-sm text-slate-500">{available ? "Chưa có hoạt động quản trị được ghi nhận trên máy này." : "Chưa tải được nhật ký. Hãy làm mới để thử lại."}</p>}
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
            <StatusBadge tone={s.tone}>{s.label}</StatusBadge>
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
          {data.kpis.map((k) => <Stat key={k.id} label={k.label} note={k.note} value={<span className="tabular-nums">{k.value}</span>} />)}
        </div>
      </section>

      {data.telemetry && <Card title="Token sử dụng hôm nay" action={<StatusBadge tone={data.telemetry.unknown_calls ? "warning" : "success"}>{data.telemetry.unknown_calls ? "Có lần gọi chưa xác định" : "Đã kết nối"}</StatusBadge>}>
        <div className="grid gap-4 sm:grid-cols-3">{[["Đầu vào", data.telemetry.input_tokens], ["Đầu ra", data.telemetry.output_tokens], ["Tổng do model báo", data.telemetry.total_tokens]].map(([label, value]) => <div key={label}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold">{value.toLocaleString("vi-VN")}</p></div>)}</div>
        <p className="mt-4 text-xs text-slate-500">Chỉ tính các lần sinh câu trả lời Gemini trong Chat thật trên máy này. Bắt đầu ghi nhận: {localTime(data.telemetry.tracking_started_at)}; lịch sử trước đó chưa được cộng.</p>
        <p className="mt-2 text-xs text-slate-500">Tổng có thể gồm token suy luận ngoài đầu vào/đầu ra. Không gọi model: 0 token. Lần gọi không có số liệu: không xác định, không cộng thành 0.</p>
        {!!data.telemetry.unknown_calls && <p className="mt-3 text-sm text-amber-700">Có {data.telemetry.unknown_calls} lần gọi chưa nhận được số token. Các tổng đang hiển thị chỉ gồm phần đã biết.</p>}
        {data.telemetry.models.length > 0 && <div className="mt-4 divide-y border-t">{data.telemetry.models.map(model => <div key={model.model} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><span>{model.model}</span><span>{model.calls} lần gọi · {model.total_tokens.toLocaleString("vi-VN")} token đã biết{model.unknown_calls ? ` · ${model.unknown_calls} lần chưa xác định` : ""}</span></div>)}</div>}
      </Card>}

      <section><BudgetCard budget={data.budget} /></section>

      <section>
        <div className="mb-3 flex items-center gap-3"><SectionTitle>Truy vấn gần đây</SectionTitle><StatusBadge tone={data.telemetry ? "success" : "warning"}>{data.telemetry ? "Dữ liệu thật" : "Chưa đọc được thống kê"}</StatusBadge></div>
        <p className="-mt-2 mb-3 text-[13px] text-slate-500">Năm truy vấn Chat thật gần nhất. Evidence Gate và Verifier chưa nối phép đo nên để trống; “có câu trả lời” chưa đồng nghĩa với đã kiểm chứng toàn bộ nội dung.</p>
        <DataTable columns={traceColumns} rows={data.recentTraces} emptyMessage={data.telemetry ? "Chưa có truy vấn Chat thật kể từ khi bật thống kê" : "Chưa đọc được thống kê truy vấn"} />
      </section>

      <section className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <AlertsCard alerts={data.alerts} />
          <ActivityCard items={data.activities} date={data.activityDate} available={data.journalAvailable} />
        </div>
        <ServicesCard services={data.services} />
      </section>

      <DataOperations data={data.operations} />
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

function DataOperations({ data }) {
  return <>
    <section>
      <SectionTitle>Quản trị dữ liệu News</SectionTitle>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {["PENDING", "APPROVED", "INDEXED", "QUARANTINED", "REJECTED"].map(status =>
          <Stat key={status} label={STATE_LABELS[status]} value={data.counts[status] || 0} />)}
      </div>
    </section>
    <section className="grid gap-6 lg:grid-cols-2">
      <Card title="Thu thập News">
        <StatusBadge tone={data.schedule.enabled ? "success" : "neutral"}>{data.schedule.enabled ? "Đã bật lịch" : "Lịch tự động đang tắt"}</StatusBadge>
        <p className="mt-4 text-sm">FireAnt · {String(data.schedule.hour).padStart(2, "0")}:00 mỗi ngày, giờ Việt Nam · tối đa {data.schedule.limit} bài/lượt.</p>
        <p className="mt-2 text-sm text-slate-500">Duyệt tự động: {data.schedule.auto_approve ? "Đã bật" : "Đang tắt"}. Lịch chỉ chạy khi tiến trình scheduler đang mở.</p>
        <p className="mt-2 text-sm">Đang đợi/xử lý: {(data.job_counts.QUEUED || 0) + (data.job_counts.RUNNING || 0)} · Job thất bại trong lịch sử: {data.job_counts.FAILED || 0}</p>
        <Link to={ADMIN_LINKS.ingestion} className="mt-4 inline-block text-sm text-blue-600">Mở thu thập & duyệt →</Link>
      </Card>
      <Card title="Kho dữ liệu AI đang dùng">
        <p className="break-all text-sm">Phiên: {data.corpus_id || "Chưa cấu hình"}</p>
        {data.storage.status === "available" ? <p className="mt-3 text-sm">{data.storage.documents.toLocaleString("vi-VN")} tài liệu · {data.storage.chunks.toLocaleString("vi-VN")} chunk · {data.storage.index_status}</p>
          : <p className="mt-3 text-sm text-amber-700">Chưa đọc được phiên dữ liệu. Kiểm tra kết nối DB và cấu hình.</p>}
        <p className="mt-3 text-xs text-slate-500">Số liệu kho chung từ PostgreSQL; số bài và lịch sử duyệt từ hàng đợi trên máy này.</p>
      </Card>
    </section>
    <Card title="Các lần xử lý gần đây">
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-3">Thời gian</th><th>Loại</th><th>Trạng thái</th><th>Mã lần chạy</th></tr></thead>
        <tbody>{data.recent_jobs.map(job => <tr key={job.id} className="border-b"><td className="p-3 whitespace-nowrap">{localTime(job.created_at)}</td>
          <td>{({ CRAWL: "Cào dữ liệu", INDEX: "Tạo chunk & lưu", SHARED: "Nạp vào kho chung", OCR: "Đọc PDF/OCR", RECHECK: "Kiểm tra lại & OCR" })[job.kind] || job.kind}</td>
          <td><StatusBadge tone={job.status === "FAILED" ? "error" : job.status === "ACTIVE" ? "success" : "neutral"}>{STATE_LABELS[job.status] || job.status}</StatusBadge></td>
          <td className="break-all text-xs">{job.id}</td></tr>)}</tbody></table></div>
      {!data.recent_jobs.length && <p className="py-4 text-sm text-slate-500">Chưa có lần xử lý nào.</p>}
      <Link to={ADMIN_LINKS.ingestion} className="mt-4 inline-block text-sm text-blue-600">Xem tiến độ và xử lý lỗi →</Link>
    </Card>
  </>;
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
      .catch((e) => { setError(e.message); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const timer = setInterval(load, 30000); return () => clearInterval(timer); }, [load]);

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-4 border-b border-slate-200/70 pb-2 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tổng quan vận hành</h1>
          <p className="mt-1 text-[13px] text-slate-500">Theo dõi tình trạng dịch vụ, truy vấn và mức sử dụng tài nguyên của FinMind.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          <StatusBadge tone="info">Dữ liệu thật · Giám sát từng phần</StatusBadge>
          <Button variant="secondary" disabled={loading} onClick={load}>Làm mới</Button>
        </div>
      </header>

      {loading && !data && <Skeleton rows={6} />}
      {error && <ErrorState message={error} onRetry={load} />}
      {data && <><p className="text-xs text-slate-500">Cập nhật: {localTime(data.operations.observed_at)} · Tự cập nhật mỗi 30 giây{error ? " · Dữ liệu lần tải trước" : ""}</p><OverviewContent data={data} /></>}
    </AdminLayout>
  );
}
