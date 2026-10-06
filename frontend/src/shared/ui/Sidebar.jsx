import { useEffect, useId, useRef, useState } from "react";
import SidebarItem from "./SidebarItem.jsx";

// groups: [{ label: "Nghiên cứu chính", items: [{ id, label, icon }] }]
// The parent page owns activeId and decides what onSelect does.
export default function Sidebar({ groups = [], activeId, onSelect, brand = "FinMind", badge, profile, onProfile, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuId = useId();
  const accountRef = useRef(null);
  const hasActions = Boolean(onProfile || onLogout);

  useEffect(() => {
    if (!menuOpen) return;
    function closeOutside(event) {
      if (!accountRef.current?.contains(event.target)) setMenuOpen(false);
    }
    function closeEscape(event) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeEscape);
    };
  }, [menuOpen]);

  function selectAction(action) {
    setMenuOpen(false);
    action?.();
  }

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
        <div ref={accountRef} className="relative border-t border-[#F1F5F9] p-2 md:p-3">
          {hasActions && <div id={menuId} hidden={!menuOpen} className="absolute bottom-full left-14 z-50 mb-2 w-48 rounded-xl border border-[#E2E8F0] bg-white p-1.5 shadow-xl md:left-3 md:right-3 md:w-auto">
            {onProfile && <button type="button" onClick={() => selectAction(onProfile)} className="flex min-h-9 w-full items-center gap-2 rounded-lg px-3 text-left text-xs font-medium text-[#334155] hover:bg-[#F8FAFC]">
              <span aria-hidden="true">◯</span>Hồ sơ cá nhân
            </button>}
            {onProfile && onLogout && <div className="my-1 border-t border-[#F1F5F9]" />}
            {onLogout && <button type="button" title="Chế độ mock: chuyển tới trang đăng nhập" onClick={() => selectAction(onLogout)} className="flex min-h-9 w-full items-center gap-2 rounded-lg px-3 text-left text-xs font-medium text-[#DC2626] hover:bg-[#FEF2F2]">
              <span aria-hidden="true">↪</span>Đăng xuất
            </button>}
          </div>}
          {hasActions ? <button type="button" aria-label="Mở menu tài khoản" aria-expanded={menuOpen} aria-controls={menuId}
            onClick={() => setMenuOpen((open) => !open)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2 text-left hover:border-[#CBD5E1] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#2563EB] md:justify-start">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[#1D4ED8]">{profile.initials}</span>
            <span className="hidden min-w-0 flex-1 md:block">
              <span className="block truncate text-xs font-semibold text-[#0F172A]">{profile.name}</span>
              <span className="block truncate text-[11px] text-[#64748B]">{profile.role}</span>
            </span>
            <span aria-hidden="true" className={`hidden text-xs text-[#94A3B8] md:block ${menuOpen ? "rotate-180" : ""}`}>⌃</span>
          </button> : <div className="flex items-center justify-center gap-2 rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2 md:justify-start">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#DBEAFE] text-xs font-semibold text-[#1D4ED8]">{profile.initials}</span>
            <div className="hidden min-w-0 md:block">
              <p className="truncate text-xs font-semibold text-[#0F172A]">{profile.name}</p>
              <p className="truncate text-[11px] text-[#64748B]">{profile.role}</p>
            </div>
          </div>}
        </div>
      )}
    </aside>
  );
}
