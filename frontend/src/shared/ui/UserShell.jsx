import { useNavigate } from "../../app/router.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { userMenu } from "../../mocks/componentMock.js";
import Sidebar from "./Sidebar.jsx";
const paths = { dashboard: '/dashboard', companies: '/companies', copilot: '/research', watchlist: '/watchlist', graph: '/graph' };
export default function UserShell({ children, activeId = '', className = '' }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const name = user?.name || 'Người dùng';
  return <div className={`fm-workspace fm-user-shell flex min-h-screen ${className}`}>
    <Sidebar groups={userMenu} activeId={activeId} onSelect={id => navigate(paths[id])}
      profile={{ name, initials: name.slice(0, 2).toUpperCase(), role: user?.role === 'admin' ? 'Quản trị viên' : 'Nhà nghiên cứu' }}
      onProfile={() => navigate('/profile')} onLogout={async () => { await logout(); navigate('/login'); }} />
    <div className="min-w-0 flex-1">{children}</div>
  </div>;
}
