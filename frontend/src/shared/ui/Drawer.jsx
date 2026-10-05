import { useEffect, useId, useRef } from "react";

export default function Drawer({ open, title, children, footer, onClose }) {
  const titleId = useId();
  const closeButton = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement;
    closeButton.current?.focus();
    function handleKeyDown(event) { if (event.key === "Escape") onClose(); }
    document.addEventListener("keydown", handleKeyDown);
    return () => { document.removeEventListener("keydown", handleKeyDown); previousFocus?.focus?.(); };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-[#0F172A]/30" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside role="dialog" aria-modal="true" aria-labelledby={titleId} className="ml-auto flex h-full w-full max-w-[480px] flex-col border-l border-[#E2E8F0] bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold text-[#0F172A]">{title}</h2>
          <button ref={closeButton} type="button" aria-label="Đóng" onClick={onClose} className="rounded p-1 text-[#64748B] hover:bg-[#F1F5F9]">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 text-sm text-[#475569]">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-[#E2E8F0] p-4">{footer}</div>}
      </aside>
    </div>
  );
}
