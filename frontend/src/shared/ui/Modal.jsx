import AppIcon from "./AppIcon.jsx";
import { useId, useRef } from "react";
import useDialogFocus from "./useDialogFocus.js";

export default function Modal({ open, title, children, footer, onClose, wide = false }) {
  const titleId = useId();
  const closeButton = useRef(null);
  const dialog = useRef(null);
  useDialogFocus(open, dialog, closeButton, onClose);

  if (!open) return null;
  return (
    <div className="fm-overlay fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId} className={`max-h-[90vh] overflow-y-auto w-full ${wide ? "max-w-4xl" : "max-w-md"} rounded-xl border border-[#E2E8F0] bg-white p-5 shadow-xl`}>
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-base font-semibold text-[#0F172A]">{title}</h2>
          <button ref={closeButton} type="button" aria-label="Đóng" onClick={onClose} className="rounded p-1 text-[#64748B] hover:bg-[#F1F5F9]"><AppIcon name="close" /></button>
        </div>
        <div className="mt-3 text-sm text-[#475569]">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}
