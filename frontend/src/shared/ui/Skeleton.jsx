export default function Skeleton({ rows = 3 }) {
  return (
    <div role="status" aria-label="Đang tải dữ liệu" className="space-y-3">
      {Array.from({ length: rows }, (_, index) => <div key={index} className="h-10 animate-pulse rounded-lg bg-[#E2E8F0]" />)}
      <span className="sr-only">Đang tải dữ liệu</span>
    </div>
  );
}
