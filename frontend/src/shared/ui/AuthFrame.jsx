import { Link } from '../../app/router.jsx';
import FinMindMark from './FinMindMark.jsx';

export default function AuthFrame({ children }) {
  return <div className="desk-auth-frame approved-auth-frame">
    <Link to="/" className="approved-auth-brand" aria-label="FinMind trang chủ"><FinMindMark />FinMind</Link>
    {children}
  </div>;
}
