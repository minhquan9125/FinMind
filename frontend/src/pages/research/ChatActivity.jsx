import { useEffect, useState } from 'react';
import ResearchIcon from './ResearchIcon.jsx';
export default function ChatActivity({ kind = 'chat' }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  return <div className="research-activity" role="status">
    <ResearchIcon name="document" /><div><p>{kind === 'history' ? 'Đang mở hội thoại' : 'Đang xử lý câu hỏi'}<span className="research-elapsed">{seconds}s</span></p>
    {seconds >= 20 && <p className="research-activity-note">Yêu cầu đang mất nhiều thời gian hơn. Bạn có thể dừng để gửi câu khác.</p>}</div>
  </div>;
}
