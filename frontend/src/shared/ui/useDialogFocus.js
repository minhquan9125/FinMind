import { useEffect, useRef } from "react";

const focusable = 'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]';

export default function useDialogFocus(open, dialog, initialFocus, onClose) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const panel = dialog.current;
    if (!open || !panel) return;
    const previous = document.activeElement;
    const targets = () => [...panel.querySelectorAll(focusable)]
      .filter(element => element.tabIndex >= 0 && element.getClientRects().length && !element.closest('[inert]'));
    const isTopmost = () => [...document.querySelectorAll('[role="dialog"][aria-modal="true"]')]
      .filter(element => element.getClientRects().length).at(-1) === panel;
    const focusFirst = () => (initialFocus.current || targets()[0] || panel).focus({ preventScroll: true });
    focusFirst();
    function keydown(event) {
      if (!isTopmost()) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close.current?.();
      } else if (event.key === "Tab") {
        const items = targets(), first = items[0], last = items.at(-1);
        if (!first) { event.preventDefault(); panel.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) {
          event.preventDefault(); first.focus();
        }
      }
    }
    function focusin(event) {
      if (isTopmost() && !panel.contains(event.target)) focusFirst();
    }
    document.addEventListener("keydown", keydown, true);
    document.addEventListener("focusin", focusin);
    return () => {
      document.removeEventListener("keydown", keydown, true);
      document.removeEventListener("focusin", focusin);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [open, dialog, initialFocus]);
}
