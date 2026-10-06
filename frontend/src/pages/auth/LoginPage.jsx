import React, { useState } from "react";
import { Link, useNavigate, useLocation, useAuth } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, login, logout, isSessionExpired, expireSessionNow } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Kiểm tra nếu được redirect từ route bảo vệ kèm thông báo hoặc phiên hết hạn
  const redirectNotice =
    location.state?.message ||
    (location.state?.expired || isSessionExpired
      ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
      : "");

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!email.trim() || !password) {
      setErrorMessage("Vui lòng điền đầy đủ email và mật khẩu.");
      return;
    }

    setErrorMessage("");
    setLoading(true);

    try {
      await login(email.trim(), password, rememberMe);
      // Điều hướng về trang trước đó nếu có, hoặc vào trang tương ứng
      const destination = location.state?.from?.pathname || (email.includes("admin") ? PATHS.admin : PATHS.dashboard);
      navigate(destination, { replace: true });
    } catch (err) {
      setErrorMessage(err.message || "Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.");
    } finally {
      setLoading(false);
    }
  };

  // Nút điền nhanh tài khoản thử nghiệm
  const fillSample = (sampleEmail, samplePass) => {
    setEmail(sampleEmail);
    setPassword(samplePass);
    setErrorMessage("");
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center items-center px-4 py-12 antialiased font-sans text-slate-900">
      {/* Khung chứa nội dung trung tâm */}
      <div className="w-full max-w-[460px]">
        {/* Nút quay về trang chủ */}
        <div className="mb-6">
          <Link
            to={PATHS.home}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors no-underline"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
            <span>Về trang chủ</span>
          </Link>
        </div>

        {/* Card Đăng nhập */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] p-8 sm:p-10">
          {/* Header */}
          <div className="mb-7">
            <h1 className="text-[26px] font-bold tracking-tight text-slate-900 leading-snug">
              Đăng nhập vào FinMind
            </h1>
            <p className="text-sm text-slate-500 mt-1.5">
              Tiếp tục vào không gian nghiên cứu của bạn.
            </p>
          </div>

          {/* Thanh hiển thị nếu đang có tài khoản đăng nhập */}
          {isAuthenticated && (
            <div className="mb-5 p-3 rounded-lg bg-blue-50 border border-blue-200/80 text-blue-900 text-xs sm:text-sm flex items-center justify-between gap-2">
              <div className="truncate">
                <span className="text-slate-600">Đang đăng nhập:</span>{" "}
                <strong className="text-blue-800">{user?.name || user?.email}</strong>{" "}
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-mono">
                  {user?.role}
                </span>
              </div>
              <button
                type="button"
                onClick={async () => {
                  await logout();
                }}
                className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-semibold cursor-pointer transition-colors shrink-0"
              >
                Đăng xuất
              </button>
            </div>
          )}

          {/* Thông báo điều hướng hoặc phiên hết hạn */}
          {redirectNotice && !errorMessage && (
            <div className="mb-5 p-3.5 rounded-lg bg-amber-50 border border-amber-200/80 text-amber-800 text-sm flex items-start gap-2.5">
              <svg className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{redirectNotice}</span>
            </div>
          )}

          {/* Thông báo lỗi khi đăng nhập sai */}
          {errorMessage && (
            <div className="mb-5 p-3.5 rounded-lg bg-red-50 border border-red-200/80 text-red-700 text-sm flex items-start gap-2.5">
              <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Trường Email */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Email <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ten@congty.vn"
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
              />
            </div>

            {/* Trường Mật khẩu */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-slate-700">
                  Mật khẩu <span className="text-red-500">*</span>
                </label>
                <Link
                  to={PATHS.forgotPassword}
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors no-underline"
                >
                  Quên mật khẩu?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2.5 pr-10 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 focus:outline-none transition-colors"
                  aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                >
                  {showPassword ? (
                    /* Biểu tượng Mắt gạch (Ẩn) */
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                    </svg>
                  ) : (
                    /* Biểu tượng Con mắt (Hiện) */
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Checkbox Ghi nhớ đăng nhập */}
            <div className="flex items-center gap-2 pt-0.5">
              <input
                id="rememberMe"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer"
              />
              <label htmlFor="rememberMe" className="text-sm text-slate-600 cursor-pointer select-none">
                Ghi nhớ đăng nhập
              </label>
            </div>

            {/* Nút Đăng nhập */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-medium text-sm rounded-lg shadow-sm hover:shadow transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Đang xử lý...</span>
                </>
              ) : (
                <span>Đăng nhập</span>
              )}
            </button>
          </form>

          {/* Đường kẻ phân cách */}
          <div className="my-6 border-t border-slate-100" />

          {/* Chuyển hướng Đăng ký */}
          <div className="text-center text-sm text-slate-600">
            Chưa có tài khoản?{" "}
            <Link
              to={PATHS.register}
              className="font-medium text-blue-600 hover:text-blue-700 transition-colors no-underline ml-1"
            >
              Đăng ký tài khoản
            </Link>
          </div>

          {/* Hộp vai trò mẫu để kiểm tra luồng & nút Đăng xuất */}
          <div className="mt-6 pt-4 border-t border-dashed border-slate-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-semibold tracking-wider uppercase text-slate-400">
                Tài khoản thử nghiệm nhanh (Mock)
              </span>
              {isAuthenticated && (
                <button
                  type="button"
                  onClick={async () => {
                    await logout();
                    setErrorMessage("");
                  }}
                  className="text-xs px-2 py-0.5 rounded bg-red-50 hover:bg-red-100 text-red-600 font-medium transition-colors border border-red-200 cursor-pointer"
                >
                  🚪 Đăng xuất ngay
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => fillSample("user@finmind.vn", "user123")}
                className="text-xs px-2.5 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors cursor-pointer border border-slate-200/60"
              >
                👤 Điền User (user@finmind.vn)
              </button>
              <button
                type="button"
                onClick={() => fillSample("admin@finmind.vn", "admin123")}
                className="text-xs px-2.5 py-1.5 rounded-md bg-blue-50 hover:bg-blue-100 text-blue-700 font-medium transition-colors cursor-pointer border border-blue-200/60"
              >
                🛡️ Điền Admin (admin@finmind.vn)
              </button>
              {isAuthenticated ? (
                <button
                  type="button"
                  onClick={async () => {
                    await logout();
                    setErrorMessage("");
                    navigate(PATHS.register);
                  }}
                  className="text-xs px-2.5 py-1.5 rounded-md bg-red-100 hover:bg-red-200 text-red-700 font-medium transition-colors cursor-pointer border border-red-200"
                >
                  🚪 Đăng xuất & Sang Đăng ký
                </button>
              ) : (
                <Link
                  to={PATHS.register}
                  className="text-xs px-2.5 py-1.5 rounded-md bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium transition-colors border border-emerald-200/60 no-underline"
                >
                  📝 Sang trang Đăng ký
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Dòng chữ chân trang */}
        <p className="text-center text-xs text-slate-400 mt-6 tracking-tight">
          Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư
        </p>
      </div>
    </div>
  );
}
