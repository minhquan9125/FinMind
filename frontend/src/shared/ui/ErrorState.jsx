import Button from "./Button.jsx";

export default function ErrorState({ title = "Không thể tải dữ liệu", message, onRetry }) {
  return (
    <div role="alert" className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-6 py-8 text-center">
      <p className="text-sm font-semibold text-[#B91C1C]">{title}</p>
      {message && <p className="mt-1 text-xs text-[#7F1D1D]">{message}</p>}
      {onRetry && <Button variant="secondary" className="mt-4" onClick={onRetry}>Thử lại</Button>}
    </div>
  );
}
