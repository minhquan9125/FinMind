import SidebarItem from "./SidebarItem.jsx";

// groups: [{ label: "Nghiên cứu chính", items: [{ id, label, icon }] }]
// The parent page owns activeId and decides what onSelect does.
export default function Sidebar({ groups = [], activeId, onSelect, brand = "FinMind", badge, profile }) {
  return (
    <aside className="flex h-screen w-16 shrink-0 flex-col border-r border-[#E2E8F0] bg-white md:w-64">
      <div className="flex h-16 shrink-0 items-center justify-center gap-2 border-b border-[#F1F5F9] md:justify-start md:px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB] text-xs font-bold text-white">FM</span>
        <strong className="hidden text-base text-[#0F172A] md:block">{brand}</strong>
        {badge && <span className="hidden rounded bg-[#EFF6FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#1D4ED8] md:block">{badge}</span>}
      </div>
      <nav aria-label={`${brand} menu`} className="flex-1 space-y-5 overflow-y-auto px-2 py-3 md:px-3">
        {groups.map((group, index) => (
          <div key={group.label || index}>
            {group.label && <p className="mb-1 hidden px-3 text-[10px] font-bold uppercase tracking-wide text-[#94A3B8] md:block">{group.label}</p>}
            <div className="space-y-0.5">
              {group.items.map((item) => <SidebarItem key={item.id} item={item} active={activeId === item.id} onSelect={onSelect} />)}
            </div>
          </div>
        ))}
      </nav>
      {profile && (
        <div className="border-t border-[#F1F5F9] p-2 md:p-3">
          <div className="flex items-center justify-center gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2 md:justify-start">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[#1D4ED8]">{profile.initials}</span>
            <div className="hidden min-w-0 md:block">
              <p className="truncate text-xs font-semibold text-[#0F172A]">{profile.name}</p>
              <p className="truncate text-[11px] text-[#64748B]">{profile.role}</p>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
