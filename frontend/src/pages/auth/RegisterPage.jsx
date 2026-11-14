import React, { useState } from "react";
import { Link, useNavigate, useAuth } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated, register, logout } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setErrorMessage("");

    if (!fullName.trim() || !email.trim() || !password || !confirmPassword) {
      setErrorMessage("Vui lòng điền đầy đủ tất cả các trường thông tin.");
      return;
    }

    if (password.length < 6) {
      setErrorMessage("Mật khẩu phải có ít nhất 6 ký tự.");
      return;
    }

    const hasUppercase = /[A-Z]/.test(password);
    const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>_\-\\\/\[\]~`+=]/.test(password);

    if (!hasUppercase) {
      setErrorMessage("Mật khẩu phải chứa ít nhất 1 chữ cái viết hoa (A-Z).");
      return;
    }

    if (!hasSpecialChar) {
      setErrorMessage("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (ví dụ: !@#$%...).");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Mật khẩu xác nhận không khớp với mật khẩu đã nhập.");
      return;
    }

    if (!agreeTerms) {
      setErrorMessage("Vui lòng đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư.");
      return;
    }

    setLoading(true);

    try {
      await register(fullName.trim(), email.trim(), password);
      // Đăng ký thành công -> chuyển thẳng vào Dashboard không gian nghiên cứu
      navigate(PATHS.dashboard, { replace: true });
    } catch (err) {
      setErrorMessage(err.message || "Đăng ký không thành công. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col justify-center items-center px-4 py-10 antialiased font-sans text-slate-900">
      <div className="w-full max-w-[460px]">
        {/* Header trên cùng: Brand Logo và nút Về trang chủ */}
        <div className="flex items-center justify-between mb-6">
          <Link to={PATHS.home} className="flex items-center gap-2.5 no-underline group">
            <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center font-bold text-xs tracking-tight shadow-xs">
              FM
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold text-slate-900 leading-tight group-hover:text-blue-600 transition-colors">
                FinMind
              </span>
              <span className="text-[10px] font-semibold text-slate-400 tracking-wider uppercase">
                NỀN TẢNG PHÂN TÍCH
              </span>
            </div>
          </Link>

          <Link
            to={PATHS.home}
            className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors no-underline"
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

        {/* Card Tạo tài khoản */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.06)] p-7 sm:p-9">
          {/* Header Card */}
          <div className="mb-6">
            <h1 className="text-2xl sm:text-[26px] font-bold tracking-tight text-slate-900 leading-snug">
              Tạo tài khoản FinMind
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-1.5 leading-relaxed">
              Tạo tài khoản để bắt đầu nghiên cứu doanh nghiệp với nguồn dữ liệu có thể kiểm chứng.
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

          {/* Thông báo lỗi nếu có */}
          {errorMessage && (
            <div className="mb-5 p-3.5 rounded-lg bg-red-50 border border-red-200/80 text-red-700 text-xs sm:text-sm flex items-start gap-2.5">
              <svg className="w-4 h-4 sm:w-5 sm:h-5 text-red-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Form đăng ký */}
          <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-4.5">
            {/* 1. HỌ VÀ TÊN */}
            <div>
              <label className="block text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                HỌ VÀ TÊN <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Nguyễn Văn A"
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
              />
            </div>

            {/* 2. EMAIL */}
            <div>
              <label className="block text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                EMAIL <span className="text-red-500">*</span>
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

            {/* 3. MẬT KHẨU */}
            <div>
              <label className="block text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                MẬT KHẨU <span className="text-red-500">*</span>
              </label>
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
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
              <p className="text-[11px] sm:text-xs text-slate-400 mt-1.5">
                Mật khẩu tối thiểu 6 ký tự, gồm ít nhất 1 chữ hoa (A-Z) và 1 ký tự đặc biệt (!@#$...).
              </p>
            </div>

            {/* 4. XÁC NHẬN MẬT KHẨU */}
            <div>
              <label className="block text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
                XÁC NHẬN MẬT KHẨU <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2.5 pr-10 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 focus:outline-none transition-colors"
                  aria-label={showConfirmPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                >
                  {showConfirmPassword ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* 5. Checkbox Điều khoản sử dụng */}
            <div className="flex items-start gap-2.5 pt-1">
              <input
                id="agreeTerms"
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer mt-0.5 shrink-0"
              />
              <label htmlFor="agreeTerms" className="text-xs text-slate-600 cursor-pointer select-none leading-relaxed">
                Tôi đồng ý với{" "}
                <a href="#terms" className="text-blue-600 hover:text-blue-700 font-medium no-underline">
                  Điều khoản sử dụng
                </a>{" "}
                và{" "}
                <a href="#privacy" className="text-blue-600 hover:text-blue-700 font-medium no-underline">
                  Chính sách quyền riêng tư
                </a>
                .
              </label>
            </div>

            {/* 6. Nút Tạo tài khoản */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-3 py-2.5 sm:py-3 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-medium text-sm rounded-lg shadow-sm hover:shadow transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Đang xử lý...</span>
                </>
              ) : (
                <span>Tạo tài khoản</span>
              )}
            </button>
          </form>

          {/* Đường kẻ phân cách & Liên kết Đăng nhập */}
          <div className="my-6 border-t border-slate-100" />

          <div className="text-center text-xs sm:text-sm text-slate-600">
            Đã có tài khoản?{" "}
            <Link
              to={PATHS.login}
              className="font-medium text-blue-600 hover:text-blue-700 transition-colors no-underline ml-1"
            >
              Đăng nhập
            </Link>
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
