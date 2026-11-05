import { useEffect, useState } from "react";
import { Link, useParams } from "../../app/router.jsx";
import { Button, EmptyState, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { jobsApi } from "./jobsApi.js";

const LABELS = { PENDING_REVIEW: "Chờ duyệt", QUARANTINED: "Cần kiểm tra", NO_CANDIDATE: "Chưa tìm thấy ứng viên",
  ERROR: "Lỗi xử lý", MISSING_SOURCE: "Thiếu nguồn", UNPROCESSED: "Chưa xử lý" };
const CHECKS = { PASS: "Hai export khớp khóa", FAIL: "Hai export lệch khóa", NOT_READY: "Chưa có đủ export đối chiếu" };
const formatDate = value => new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

function useReport(id, offset) {
  const [state, setState] = useState({ loading: true });
  const [revision, reload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    const pending = id ? jobsApi.detail(id, offset, { signal: controller.signal }) : jobsApi.list(offset, { signal: controller.signal });
    pending.then(data => { if (!controller.signal.aborted) setState({ data }); })
      .catch(error => { if (!controller.signal.aborted) setState({ error: error.message || "Không kết nối được backend." }); });
    return () => controller.abort();
  }, [id, offset, revision]);
  return { ...state, reload: () => reload(n => n + 1) };
}

function Pager({ offset, limit, total, onChange }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
    <span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} / ${total}` : "0 kết quả"}</span>
    <div className="flex gap-2">
      <Button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Trước</Button>
      <Button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Sau</Button>
    </div>
  </div>;
}

function Result({ loading, error, children }) {
  if (loading) return <p role="status" className="rounded-xl border bg-white p-8 text-slate-600">Đang tải báo cáo…</p>;
  if (error) return <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">{error}</p>;
  return children;
}

function JobsList() {
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useReport(null, offset);
  return <>
    <div className="flex items-center justify-between gap-4"><div>
      <h1 className="text-2xl font-semibold text-slate-900">Job dữ liệu News</h1>
      <p className="mt-1 text-sm text-slate-500">Báo cáo WBS16 đã được lưu · {data?.total ?? "—"} job</p>
    </div><Button onClick={reload} disabled={loading}>Làm mới</Button></div>
    <p className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
      Trạng thái phản ánh lần xuất báo cáo gần nhất. Ứng viên còn chờ duyệt; xử lý xong đầu vào chưa có nghĩa đã nạp graph hoặc nghiệm thu.
    </p>
    <Result loading={loading} error={error}>
      {data?.items.length ? <>
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white"><table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500"><tr>{["Job", "Loại", "Đầu vào", "Cần theo dõi", "Trạng thái", "Báo cáo lúc"].map(x => <th className="p-4 font-medium" key={x}>{x}</th>)}</tr></thead>
          <tbody>{data.items.map(item => <tr key={item.job_id} className="border-t border-slate-100">
            <td className="p-4"><Link className="font-medium text-blue-700 hover:underline" to={`${ADMIN_LINKS.jobs}/${encodeURIComponent(item.job_id)}`}>{item.job_id}</Link></td>
            <td className="p-4">{item.mode ? <StatusBadge tone={item.mode === "fixture" ? "warning" : "neutral"}>{item.mode === "fixture" ? "Fixture" : "Toàn manifest"}</StatusBadge> : "—"}</td>
            <td className="p-4">{item.total_articles ?? "—"}</td>
            <td className="p-4">{item.counts ? Object.entries(item.counts).filter(([key]) => key !== "NO_CANDIDATE").reduce((sum, [, n]) => sum + n, 0) : "—"}</td>
            <td className="p-4"><StatusBadge tone={item.status === "STAGED" ? "neutral" : "warning"}>{item.status === "INVALID_REPORT" ? "Báo cáo lỗi" : item.status === "STAGED" ? "Đã xử lý đầu vào" : "Cần xử lý tiếp"}</StatusBadge></td>
            <td className="whitespace-nowrap p-4">{item.reported_at ? formatDate(item.reported_at) : "—"}</td>
          </tr>)}</tbody>
        </table></div>
        <Pager offset={offset} limit={20} total={data.total} onChange={setOffset} />
      </> : <EmptyState title="Chưa có báo cáo job" description="Báo cáo WBS16 sẽ xuất hiện sau khi runner ghi kết quả vào kho báo cáo của hệ thống." />}
    </Result>
  </>;
}

function JobDetail({ id }) {
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useReport(id, offset);
  return <>
    <Link to={ADMIN_LINKS.jobs} className="text-sm text-blue-700 hover:underline">← Danh sách job</Link>
    <div className="flex items-center justify-between gap-4"><h1 className="break-all text-2xl font-semibold text-slate-900">{id}</h1><Button onClick={reload} disabled={loading}>Làm mới</Button></div>
    <Result loading={loading} error={error}>{data && <>
      <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm">
        <div className="flex flex-wrap gap-3"><StatusBadge tone={data.mode === "fixture" ? "warning" : "neutral"}>{data.mode === "fixture" ? "Dữ liệu fixture" : "Toàn manifest"}</StatusBadge>
          <span>Chưa nghiệm thu</span><span>· {CHECKS[data.database_reconciliation]}</span></div>
        <dl className="mt-4 grid gap-3 text-slate-600"><div><dt className="font-medium">Corpus</dt><dd className="break-all font-mono">{data.corpus_version_id}</dd></div>
          <div><dt className="font-medium">Manifest SHA256</dt><dd className="break-all font-mono">{data.manifest_sha256}</dd></div>
          <div><dt className="font-medium">Báo cáo cập nhật</dt><dd>{formatDate(data.reported_at)} (giờ Việt Nam)</dd></div></dl>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">{Object.entries(LABELS).map(([status, label]) => <div key={status} className="rounded-xl border bg-white p-4"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-slate-900">{data.counts[status]}</p></div>)}</div>
      <section className="space-y-4"><h2 className="text-lg font-semibold text-slate-900">Các bài cần theo dõi</h2>
        <p className="text-sm text-slate-500">“Cần kiểm tra” là hàng đợi cục bộ của runner. Trang này chưa ghi quyết định duyệt hoặc quarantine vào DB.</p>
        {data.items.length ? <><div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr><th className="p-4">Article ID</th><th className="p-4">Trạng thái</th><th className="p-4">Mã lý do</th></tr></thead>
          <tbody>{data.items.map(item => <tr key={item.article_id} className="border-t"><td className="break-all p-4 font-mono">{item.article_id}</td><td className="p-4">{LABELS[item.status]}</td><td className="p-4">{item.reason || "—"}</td></tr>)}</tbody></table></div>
          <Pager offset={offset} limit={50} total={data.total_issues} onChange={setOffset} /></> : <EmptyState title="Không có bài trong danh sách cần theo dõi" description="Các bài chưa tìm thấy ứng viên được đếm riêng; kết quả này chưa xác nhận chất lượng trích xuất." />}
      </section>
    </>}</Result>
  </>;
}

export default function AdminJobsPage() {
  const { jobId } = useParams();
  return <AdminLayout>{jobId ? <JobDetail key={jobId} id={jobId} /> : <JobsList />}</AdminLayout>;
}
