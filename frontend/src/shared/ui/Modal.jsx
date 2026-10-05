import { useEffect, useId, useRef } from "react";

export default function Modal({ open, title, children, footer, onClose }) {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby={titleId} className="w-full max-w-md rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-base font-semibold text-[#0F172A]">{title}</h2>
          <button ref={closeButton} type="button" aria-label="Đóng" onClick={onClose} className="rounded p-1 text-[#64748B] hover:bg-[#F1F5F9]">✕</button>
        </div>
        <div className="mt-3 text-sm text-[#475569]">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}
