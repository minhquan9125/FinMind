// Trang A02: Cấu hình nguồn dữ liệu (route /admin/sources và /admin/sources/:sourceId).
// Hiện hệ thống có đúng một nguồn thật là tin FireAnt. Trang này CHỈ ĐỌC cấu hình và các lần
// thu thập gần nhất; muốn sửa cấu hình hoặc thu thập, dùng trang Thu thập & duyệt.

import { useEffect, useState } from "react";
import { Link } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { STATE_LABELS, getOperations, localTime } from "./operationsApi.js";
import { pipelineResult } from "./ingestionPipeline.js";
import { automationNote, crawlRuns, runCounts, sourceRows } from "./sourceView.js";

const runTone = status => (status === "FAILED" ? "error" : status === "PARTIAL" ? "warning" : status === "COMPLETED" ? "success" : "neutral");

export default function AdminSourcesPage() {
  const [config, setConfig] = useState(null), [jobs, setJobs] = useState(null), [error, setError] = useState(""), [retry, setRetry] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setError("");
    Promise.all([getOperations("/source", abort.signal), getOperations("/jobs", abort.signal)])
      .then(([source, list]) => { if (!abort.signal.aborted) { setConfig(source); setJobs(list.items); } })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [retry]);
  const runs = crawlRuns(jobs);
  return <AdminLayout>
    <header className="space-y-1">
      <Link className="text-xs text-blue-600" to={ADMIN_LINKS.overview}>Tổng quan vận hành</Link>
      <h1 className="text-xl font-bold">Cấu hình nguồn dữ liệu</h1>
      <p className="text-sm text-slate-500">Dữ liệu thật, chỉ đọc. Hiện hệ thống thu thập tin từ một nguồn là FireAnt; các nguồn khác chưa được quản lý ở trang này.</p>
    </header>
    {error && <ErrorState message={error} onRetry={() => setRetry(v => v + 1)} />}
    {!config && !error && <Skeleton rows={6} />}
    {config && <Card title="FireAnt · tin tức theo mã" description={automationNote(config)}
      action={<Link to={ADMIN_LINKS.ingestion}><Button variant="secondary">Chỉnh sửa ở Thu thập & duyệt</Button></Link>}>
      <dl>{sourceRows(config).map(row => <div key={row.label} className="flex flex-wrap justify-between gap-3 border-b py-2 text-sm">
        <dt className="text-slate-500">{row.label}</dt><dd className="break-all text-right">{String(row.value)}</dd></div>)}</dl>
    </Card>}
    {config && <Card title="Các lần thu thập gần nhất">
      {runs.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead className="bg-slate-50"><tr><th className="p-2">Thời gian</th><th className="p-2">Trạng thái</th><th className="p-2">Lấy về</th><th className="p-2">Bài mới</th><th className="p-2">Trùng</th><th className="p-2">Lỗi</th><th className="p-2">Chạy nối tiếp</th></tr></thead>
        <tbody>{runs.map(job => { const counts = runCounts(job), chain = pipelineResult(job); return <tr key={job.id} className="border-t align-top">
          <td className="p-2">{localTime(job.created_at)}<p className="text-xs text-slate-400">{job.actor === "scheduler" ? "Lịch tự động" : "Bấm tay"}</p></td>
          <td className="p-2"><StatusBadge tone={runTone(job.status)}>{STATE_LABELS[job.status] || job.status}</StatusBadge></td>
          <td className="p-2">{counts.fetched ?? "—"}</td><td className="p-2">{counts.created ?? "—"}</td><td className="p-2">{counts.duplicates ?? "—"}</td>
          <td className="p-2">{counts.errors || "—"}</td><td className="max-w-xs p-2 text-xs text-slate-600">{chain ? chain.text : "—"}</td>
        </tr>; })}</tbody></table></div>
        : <EmptyState title="Chưa có lần thu thập nào" description="Bấm Cào ngay ở trang Thu thập & duyệt để chạy lần đầu." />}
    </Card>}
  </AdminLayout>;
}
