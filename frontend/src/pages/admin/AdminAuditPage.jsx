import { useEffect, useState } from "react";
import AdminLayout from "./AdminLayout.jsx";
import { Button, ErrorState, Skeleton } from "../../shared/ui";
import { getOperations, localTime, STATE_LABELS } from "./operationsApi.js";

const ACTIONS = { SOURCE_CONFIG: "Cập nhật cấu hình nguồn", RETRY_INDEX: "Thử nạp lại", INTERRUPT: "Ngắt lần xử lý", BUDGET_CONFIG: "Cập nhật ngân sách API", RECOVER_STOPPED_JOB: "Phục hồi hàng đợi sau khi worker dừng", RETRY_JOB: "Tiếp tục job" };

export default function AdminAuditPage() {
  const [category, setCategory] = useState(""), [offset, setOffset] = useState(0), [refresh, setRefresh] = useState(0);
  const [data, setData] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(""); setData(null);
    getOperations(`/audit?offset=${offset}&limit=30${category ? `&category=${category}` : ""}`, controller.signal)
      .then(d => { if (!controller.signal.aborted) setData(d); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [category, offset, refresh]);
  return <AdminLayout>
    <header className="flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-2xl font-bold">Nhật ký kiểm toán</h1>
      <p className="mt-2 text-sm text-slate-500">Lịch sử duyệt bài và thao tác nguồn dữ liệu trên máy này, gồm quyết định tự động và thủ công.</p></div>
      <Button variant="secondary" disabled={loading} onClick={() => setRefresh(v => v + 1)}>Làm mới</Button></header>
    <nav className="flex gap-3" aria-label="Loại nhật ký">{[["", "Tất cả"], ["review", "Quyết định duyệt"], ["operation", "Thao tác quản trị"]].map(([key, text]) =>
      <Button key={key} variant={category === key ? "primary" : "secondary"} onClick={() => { setCategory(key); setOffset(0); }}>{text}</Button>)}</nav>
    {loading && <Skeleton rows={6} />}
    {error && <ErrorState message={error} onRetry={() => setRefresh(v => v + 1)} />}
    {data && <>
      <p className="text-sm text-slate-500">{data.total} sự kiện · Thời gian theo giờ Việt Nam</p>
      <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th className="p-4">Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th className="p-4">Đối tượng / Ghi chú</th></tr></thead>
        <tbody>{data.items.map(e => <tr key={e.id} className="border-b align-top"><td className="p-4 whitespace-nowrap">{localTime(e.created_at)}</td>
          <td className="max-w-56 break-words py-4 pr-4">{e.actor}</td><td className="py-4 pr-4">{ACTIONS[e.action] || STATE_LABELS[e.action] || e.action}</td>
          <td className="max-w-xl break-words p-4"><p className="text-xs text-slate-500">{e.resource}</p>{e.note && <p className="mt-2 whitespace-pre-wrap">{e.note}</p>}</td></tr>)}</tbody></table>
        {!data.items.length && <p className="p-8 text-center text-slate-500">Chưa có sự kiện trong mục này.</p>}</div>
      <div className="flex items-center gap-4"><Button variant="secondary" disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 30))}>Trang trước</Button>
        <span>Trang {Math.floor(offset / 30) + 1}</span><Button variant="secondary" disabled={offset + 30 >= data.total} onClick={() => setOffset(v => v + 30)}>Trang sau</Button></div>
    </>}
  </AdminLayout>;
}
