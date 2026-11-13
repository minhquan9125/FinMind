import { useEffect, useState } from "react";
import { Button, Card, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout from "./AdminLayout.jsx";
import AdminLimitsPanel from "./AdminLimitsPanel.jsx";
import BudgetUsage, { money } from "./BudgetUsage.jsx";
import { getOperations, localTime } from "./operationsApi.js";

// Hai nhóm này chưa có giá trị cấu hình tương ứng trong hệ thống: Evidence Gate B3 và Verifier đang tắt,
// còn giới hạn truy xuất là hằng số trong mã. Không hiển thị số mẫu; giới hạn Token đã chuyển sang bảng sửa được.
const READONLY_NOTES = [
  ["Ngưỡng bằng chứng (Evidence Gate / Verifier)", "Evidence Gate B3 và Answer Verification B3 đang tắt trong cấu hình nên chưa có ngưỡng để chỉnh. Việc kiểm tra nguồn của B1 (đoạn trích, số liệu, trích dẫn) luôn chạy và xem được ở từng truy vấn."],
  ["Truy xuất & hợp nhất", "Số ứng viên Vector, quan hệ Graph và hợp nhất kết quả là hằng số trong mã truy xuất, chưa có cấu hình nên chưa sửa được trên giao diện."],
];

export default function AdminConfigurationPage() {
  const [data, setData] = useState(null), [form, setForm] = useState(null), [reason, setReason] = useState("");
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setError("");
    getOperations("/budget", abort.signal).then(result => {
      if (!abort.signal.aborted) { setData(result); setForm(structuredClone(result.config)); }
    }).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [revision]);
  const set = (key, value) => setForm(f => ({ ...f, [key]: value }));
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await getOperations("/budget", undefined, { method: "PUT", body: { ...form, reason, expected_version: data.version } });
      setData(result); setForm(structuredClone(result.config)); setReason(""); setMessage("Đã lưu phiên bản cấu hình. Tổng quan sẽ cập nhật theo cấu hình này.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <AdminLayout>
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-xl font-bold">Ngưỡng & ngân sách API</h1><p className="mt-2 text-sm text-slate-500">Cấu hình ngân sách thật, đơn giá do admin cung cấp và lịch sử phiên bản trên máy này.</p></div>
      <Button variant="secondary" disabled={busy} onClick={() => { if (!form || confirm("Tải lại sẽ bỏ các chỉnh sửa chưa lưu. Tiếp tục?")) setRevision(v => v + 1); }}>Tải lại</Button></header>
    {error && <ErrorState message={error} />}{message && <p role="status" className="rounded-lg bg-green-50 p-4 text-green-800">{message}</p>}
    {!data && !error && <Skeleton rows={6} />}
    {data && form && <>
      <Card title="Cấu hình đang hoạt động"><p className="break-all text-sm">Phiên bản: {data.version || "Chưa lưu cấu hình"}</p><p className="mt-2 text-xs text-slate-500">Lưu tạo phiên bản mới và áp dụng ngay cho phần thống kê ước tính. Không thay đổi gói thanh toán hay khóa API của nhà cung cấp.</p></Card>
      <section id="budget"><BudgetUsage data={data} /></section>
      <form onSubmit={save} className="space-y-5 rounded-xl border bg-white p-5">
        <h2 className="font-semibold">Ngưỡng cảnh báo ngân sách</h2>
        <fieldset disabled={busy} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm">Chế độ<select className="mt-1 block w-full rounded border p-2" value={form.mode} onChange={e => setForm(f => ({ ...f, mode: e.target.value, rates: e.target.value === "paid" ? f.rates : [] }))}><option value="unconfigured">Chưa cấu hình</option><option value="free">Miễn phí — ước tính 0 USD</option><option value="paid">Trả phí — nhập đơn giá</option></select></label>
            <label className="text-sm">Kỳ ngân sách<select className="mt-1 block w-full rounded border p-2" value={form.period} onChange={e => set("period", e.target.value)}><option value="day">Ngày (giờ Việt Nam)</option><option value="month">Tháng (giờ Việt Nam)</option></select></label>
            <label className="text-sm">Ngân sách (USD)<input required type="number" min="0.000001" max="1000000" step="0.000001" className="mt-1 block w-full rounded border p-2" value={form.limit_usd} onChange={e => set("limit_usd", e.target.value)} /></label>
            <label className="text-sm">Cảnh báo khi dùng (%)<input required type="number" min="1" max="100" step="1" className="mt-1 block w-full rounded border p-2" value={form.warn_at} onChange={e => set("warn_at", Number(e.target.value))} /></label>
          </div>
          {form.mode === "paid" && <section className="space-y-3"><h3 className="text-sm font-semibold">Đơn giá USD / 1 triệu token</h3><p className="text-xs text-slate-500">Nhập đúng model và giá theo tài khoản của bạn. Giá đầu ra áp dụng cả token suy luận; chưa tính giá cache hoặc các chiết khấu riêng.</p>
            {form.rates.map((rate, index) => <div key={index} className="grid gap-3 rounded-lg border p-3 md:grid-cols-4">
              {[["model", "Tên model"], ["input_per_million", "Giá đầu vào"], ["output_per_million", "Giá đầu ra + suy luận"]].map(([key, label]) => <label key={key} className="text-xs">{label}<input required type={key === "model" ? "text" : "number"} min="0" max="1000000" step="0.000001" maxLength={key === "model" ? 100 : undefined} className="mt-1 block w-full rounded border p-2" value={rate[key]} onChange={e => set("rates", form.rates.map((r, i) => i === index ? { ...r, [key]: e.target.value } : r))} /></label>)}
              <Button variant="ghost" onClick={() => set("rates", form.rates.filter((_, i) => i !== index))}>Bỏ model</Button></div>)}
            <Button variant="secondary" disabled={form.rates.length >= 30} onClick={() => set("rates", [...form.rates, { model: "", input_per_million: "", output_per_million: "" }])}>Thêm model</Button>
          </section>}
          <label className="block text-sm">Lý do thay đổi<textarea required minLength="3" maxLength="1000" className="mt-1 block w-full rounded border p-3" value={reason} onChange={e => setReason(e.target.value)} /></label>
          <p className="text-xs text-slate-500">Chế độ hiện tại chỉ cảnh báo. Tùy chọn tự chặn AI khi vượt ngân sách chưa triển khai.</p>
          <Button type="submit" disabled={reason.trim().length < 3 || (form.mode === "paid" && !form.rates.length)}>Lưu phiên bản & áp dụng</Button>
        </fieldset>
      </form>
      <AdminLimitsPanel />
      <section className="grid items-start gap-5 lg:grid-cols-2">{READONLY_NOTES.map(([title, text]) => <Card key={title} title={title} action={<StatusBadge>Chưa có cấu hình</StatusBadge>}><p className="text-sm text-slate-600">{text}</p></Card>)}</section>
      <Card title="Lịch sử phiên bản cấu hình"><div className="space-y-3">{data.history.map((version, index) => <details key={version.id} className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">{localTime(version.created_at)} · {index === 0 ? "Đang áp dụng" : "Đã thay thế"} · {version.config.mode} · {money(version.config.limit_usd)}</summary><p className="mt-2 break-all text-xs text-slate-500">{version.id} · {version.actor}</p><p className="mt-2 text-sm">{version.reason}</p><pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(version.config, null, 2)}</pre></details>)}{!data.history.length && <p className="text-sm text-slate-500">Chưa có phiên bản đã lưu.</p>}</div></Card>
    </>}
  </AdminLayout>;
}
