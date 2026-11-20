import { Card, StatusBadge } from "../../shared/ui";
import { localTime } from "./operationsApi.js";

export const money = value => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 6 }).format(Number(value || 0));

export default function BudgetUsage({ data }) {
  const u = data?.usage;
  if (!u?.configured) return <Card title="Mức sử dụng ngân sách hiện tại" action={<StatusBadge>Chưa cấu hình</StatusBadge>}>
    <p className="text-sm text-slate-500">Chọn chế độ miễn phí hoặc nhập đơn giá model và ngân sách tại Ngưỡng & ngân sách API.</p>
  </Card>;
  const percent = Math.max(0, Math.min(100, u.percent));
  return <Card title="Mức sử dụng ngân sách hiện tại" action={<StatusBadge tone={u.exceeded ? "error" : u.warning || !u.complete ? "warning" : "success"}>{u.exceeded ? "Đạt/vượt ngân sách" : u.warning ? "Gần chạm ngân sách" : !u.complete ? "Số liệu chưa đầy đủ" : "Trong ngân sách"}</StatusBadge>}>
    <div className="flex flex-wrap justify-between gap-3"><strong className="text-xl">{money(u.used_usd)} / {money(u.limit_usd)}</strong><span className="text-sm">{u.percent.toFixed(2)}% · {u.period === "month" ? "Theo tháng" : "Theo ngày"}</span></div>
    <div role="progressbar" aria-label="Ngân sách API ước tính" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100"><div style={{ width: `${percent}%` }} className={`h-full ${u.exceeded ? "bg-red-600" : u.warning ? "bg-amber-500" : "bg-blue-600"}`} /></div>
    <p className="mt-3 text-xs text-slate-500">Kỳ: {localTime(u.starts_at)} → {localTime(u.ends_at)} · Cảnh báo từ {u.warn_at}%.</p>
    {!u.complete && <p className="mt-3 text-sm text-amber-800">Chỉ gồm chi phí đã tính được: {u.unknown_calls} lần thiếu token, {u.unpriced_calls} lần chưa có giá model. Chi phí thực tế có thể cao hơn phần đang hiển thị.</p>}
    <p className="mt-3 text-xs text-slate-500">{data.config.mode === "free" ? "Ước tính 0 USD theo chế độ miễn phí do admin chọn. " : "Ước tính theo đơn giá hiện tại, áp dụng lại cho token đã ghi trong kỳ. "}Chỉ tính Chat trên máy này, không phải hóa đơn nhà cung cấp. Cảnh báo chưa tự chặn AI.</p>
  </Card>;
}
