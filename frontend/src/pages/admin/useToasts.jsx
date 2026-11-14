// Thông báo nổi nhỏ cho các trang Admin: const { toast, toastNode } = useToasts();
// Gọi toast("Nội dung", "success" | "warning" | "error" | "info"); đặt {toastNode} ở cuối trang.

import { useCallback, useEffect, useRef, useState } from "react";

const TONE = { info: "bg-slate-900", success: "bg-green-600", warning: "bg-amber-600", error: "bg-red-600" };

export default function useToasts(durationMs = 4000) {
  const [items, setItems] = useState([]);
  const timers = useRef(new Set());

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const toast = useCallback((message, type = "info") => {
    const id = `${Date.now()}-${Math.random()}`;
    setItems((list) => [...list, { id, message, type }]);
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      setItems((list) => list.filter((t) => t.id !== id));
    }, durationMs);
    timers.current.add(timer);
  }, [durationMs]);

  const toastNode = (
    <div role="status" aria-live="polite" className="pointer-events-none fixed bottom-12 left-1/2 z-[60] flex w-[min(90vw,32rem)] -translate-x-1/2 flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} className={`rounded-lg px-4 py-2.5 text-xs font-medium text-white shadow-xl ${TONE[t.type] || TONE.info}`}>{t.message}</div>
      ))}
    </div>
  );

  return { toast, toastNode };
}
