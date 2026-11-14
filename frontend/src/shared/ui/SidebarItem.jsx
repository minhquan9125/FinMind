export default function SidebarItem({ item, active = false, onSelect }) {
  return (
    <button type="button" title={item.label} aria-current={active ? "page" : undefined}
      onClick={() => onSelect(item.id)}
      className={`flex min-h-10 w-full items-center justify-center gap-3 rounded-lg px-2 text-left text-sm font-medium md:justify-start md:px-3 ${active ? "bg-[#EFF6FF] text-[#1D4ED8]" : "text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]"}`}>
      <span aria-hidden="true" className="w-5 shrink-0 text-center text-lg leading-none">{item.icon || "•"}</span>
      <span className="hidden truncate md:block">{item.label}</span>
    </button>
  );
}
