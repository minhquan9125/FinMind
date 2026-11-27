import { Link, useAuth } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";
import UserShell from "../../shared/ui/UserShell.jsx";
import { Card } from "../../shared/ui/index.js";

export default function ProfilePage() {
  const { user, userProfile } = useAuth();
  return (
    <UserShell className="fm-profile">
      <main className="mx-auto max-w-[860px] px-5 pb-16 pt-9 sm:px-8 sm:pt-12">
        <Link className="text-sm font-semibold text-slate-500" to="/dashboard">← Về tổng quan</Link>
        <div className="mb-8 mt-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Tài khoản</p>
          <h1 className="mt-2 text-[28px] font-bold tracking-tight">Hồ sơ cá nhân</h1>
          <p className="mt-2 text-sm text-slate-500">Thông tin tài khoản từ phiên đăng nhập hiện tại.</p>
        </div>
        <Card title="Thông tin tài khoản">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 text-xl font-semibold text-blue-700" aria-hidden="true">{userProfile?.initials || "?"}</div>
            <div><strong>{user?.name || user?.email || "Chưa có thông tin"}</strong><p className="mt-1 text-sm text-slate-500">{userProfile?.role || "Chưa có thông tin vai trò"}</p></div>
          </div>
          <dl className="mt-6 grid gap-5 border-t border-slate-100 pt-5 sm:grid-cols-2">
            <div><dt className="text-xs text-slate-500">Họ tên</dt><dd className="mt-1 break-words font-medium">{user?.name || "Chưa có thông tin"}</dd></div>
            <div><dt className="text-xs text-slate-500">Email</dt><dd className="mt-1 break-all font-medium">{user?.email || "Chưa có thông tin"}</dd></div>
          </dl>
        </Card>
        <Card title="Bảo mật" className="mt-5">
          <p className="text-sm text-slate-600">Để đặt lại mật khẩu, hãy dùng liên kết xác nhận được gửi đến email tài khoản.</p>
          <Link to={PATHS.forgotPassword} className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white">Đặt lại mật khẩu</Link>
          <p className="mt-4 text-xs text-slate-500">Thay đổi ảnh đại diện và chỉnh sửa hồ sơ hiện chưa được hệ thống hỗ trợ.</p>
        </Card>
      </main>
    </UserShell>
  );
}
