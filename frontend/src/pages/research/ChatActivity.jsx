import { useEffect, useState } from 'react';
import './chatActivity.css';

export default function ChatActivity({ kind = 'chat' }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  const opening = kind === 'history';
  return <div className="flex max-w-full items-center gap-4 rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-4 sm:max-w-[85%]">
    <div className="fm-chat-activity relative h-20 w-20 shrink-0 overflow-hidden rounded-2xl bg-white shadow-sm" aria-hidden="true">
      <svg viewBox="0 0 80 80" className="h-full w-full" fill="none">
        <circle cx="40" cy="40" r="33" fill="#EFF6FF" />
        <g className="fm-chat-paper">
          <rect x="20" y="15" width="35" height="48" rx="7" fill="white" stroke="#93C5FD" strokeWidth="2" />
          <path d="M28 25h18M28 31h14M28 48h13M28 54h18" stroke="#BFDBFE" strokeWidth="3" strokeLinecap="round" />
          <circle cx="31" cy="39" r="2" fill="#2563EB" /><circle cx="43" cy="39" r="2" fill="#2563EB" />
          <path d="M33 43q4 4 8 0" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" />
        </g>
        <g className="fm-chat-lens">
          <path d="m55 54 10 10" stroke="#2563EB" strokeWidth="6" strokeLinecap="round" />
          <circle cx="48" cy="47" r="13" fill="#DBEAFE" fillOpacity=".8" stroke="#2563EB" strokeWidth="3" />
          <path d="M42 43q1-4 6-4" stroke="white" strokeWidth="3" strokeLinecap="round" />
        </g>
        <path className="fm-chat-spark" d="m63 16 1.5 4.5L69 22l-4.5 1.5L63 28l-1.5-4.5L57 22l4.5-1.5Z" fill="#60A5FA" />
      </svg>
    </div>
    <div className="min-w-0">
      <p role="status" className="flex flex-wrap items-center gap-2 text-sm font-semibold text-blue-900">
        {opening ? 'Đang mở lại cuộc trò chuyện' : 'FinMind đang tìm câu trả lời'}
        <span className="fm-chat-dots inline-flex gap-1" aria-hidden="true"><i /><i /><i /></span>
      </p>
      <p className="mt-1 text-xs leading-relaxed text-slate-600">{opening ? 'Mang những lượt hỏi đáp trước trở lại với bạn.' : seconds >= 20 ? 'FinMind vẫn đang xử lý. Lần tra cứu đầu có thể lâu hơn để nạp mô hình.' : 'Bạn đợi một chút nhé, FinMind đang xử lý câu hỏi của bạn.'}</p>
      <span aria-hidden="true" className="mt-2 inline-block rounded-full bg-blue-100 px-2 py-1 text-[11px] font-medium text-blue-700">Đã chờ {seconds} giây</span>
    </div>
  </div>;
}
