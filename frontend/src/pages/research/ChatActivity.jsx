import { useEffect, useState } from 'react';
import { Search, MessagesSquare } from 'lucide-react';
import './chatActivity.css';
export default function ChatActivity({ kind = 'chat' }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  const Icon = kind === 'history' ? MessagesSquare : Search;
  return <div className="research-activity finmind-chat-activity">
    <span className="finmind-activity-icon" aria-hidden="true"><Icon size={18} strokeWidth={1.7} /></span>
    <div className="finmind-activity-content">
      <div className="finmind-activity-heading">
        <p role="status" aria-live="polite">
          {kind === 'history' ? 'Đang mở hội thoại' : 'FinMind đang tìm câu trả lời'}
          <span className="finmind-thinking-dots" aria-hidden="true"><i /><i /><i /></span>
        </p>
        <span className="research-elapsed" aria-hidden="true">{seconds} giây</span>
      </div>
      <p className="research-activity-note">
        {seconds >= 20
          ? 'Yêu cầu đang mất nhiều thời gian hơn. Bạn có thể dừng để gửi câu khác.'
          : kind === 'history' ? 'Đang tải nội dung cuộc trò chuyện của bạn.' : 'Bạn có thể dừng xử lý bất cứ lúc nào.'}
      </p>
    </div>
  </div>;
}
