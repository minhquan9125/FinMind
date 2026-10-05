export default function EmptyState({ title = "Chưa có dữ liệu", description, action }) {
  return (
    <div className="rounded-xl border border-dashed border-[#CBD5E1] bg-white px-6 py-10 text-center">
      <div aria-hidden="true" className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#F1F5F9] text-[#64748B]">–</div>
      <p className="text-sm font-semibold text-[#0F172A]">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-md text-xs text-[#64748B]">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
