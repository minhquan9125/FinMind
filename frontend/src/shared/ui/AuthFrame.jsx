import { Link } from '../../app/router.jsx';
import AppIcon from './AppIcon.jsx';

export default function AuthFrame({ children }) {
  return <div className="desk-auth-frame">
    <aside className="desk-auth-story">
      <Link to="/" className="desk-auth-brand"><span>FM</span>FinMind</Link>
      <div><p className="desk-section-number">Không gian nghiên cứu doanh nghiệp</p><h2>Một câu hỏi.<br />Một góc nhìn<br />có nguồn.</h2><p>Đi từ doanh nghiệp bạn quan tâm đến báo cáo, tin tức và các quan hệ có thể đối chiếu.</p>
        <ol>{['Chọn doanh nghiệp', 'Đặt câu hỏi nghiên cứu', 'Đối chiếu bằng chứng gốc'].map((step, index) => <li key={step}><span>0{index + 1}</span>{step}<AppIcon name={index === 2 ? 'document' : 'arrow'} /></li>)}</ol>
      </div>
      <footer>Chỉ hỗ trợ nghiên cứu · Không phải khuyến nghị đầu tư</footer>
    </aside>
    {children}
  </div>;
}
