import React, { useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";
import { apiResetPassword } from "../../shared/api/authApi.js";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token") || searchParams.get("token") || "";
  const email = searchParams.get("email") || "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!token) {
      setErrorMessage("Liên kết đặt mật khẩu không hợp lệ. Vui lòng yêu cầu liên kết mới.");
      return;
    }

    if (!newPassword) {
      setErrorMessage("Vui lòng nhập mật khẩu mới.");
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage("Mật khẩu mới phải có ít nhất 8 ký tự.");
      return;
    }

    if (!confirmPassword) {
      setErrorMessage("Vui lòng xác nhận mật khẩu mới.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("Xác nhận mật khẩu mới không khớp.");
      return;
    }

    setLoading(true);

    try {
      const res = await apiResetPassword(token, newPassword, confirmPassword);
      setSuccessMessage(
        res.message || "Đặt lại mật khẩu thành công. Đang chuyển hướng về trang đăng nhập..."
      );

      // Tự động chuyển hướng về trang đăng nhập sau 2 giây
      setTimeout(() => {
        navigate(PATHS.login, {
          replace: true,
          state: {
            message: "Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.",
            email: res.email || email,
          },
        });
      }, 2000);
    } catch (err) {
      setErrorMessage(err.message || "Không thể đặt lại mật khẩu. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col antialiased font-sans text-slate-900">
      {/* Thanh Header trên cùng */}
      <header className="w-full bg-white border-b border-slate-100 px-6 sm:px-8 py-3.5 flex items-center">
        <Link to={PATHS.home} className="flex items-center gap-2.5 no-underline">
          <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center font-bold text-xs tracking-tight">
            FM
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-slate-900 leading-tight">
              FinMind
            </span>
            <span className="text-[11px] text-slate-500 font-normal">
              Research Copilot
            </span>
          </div>
        </Link>
      </header>

      {/* Vùng nội dung chính giữa màn hình */}
      <main className="flex-1 flex flex-col justify-center items-center px-4 py-12">
        <div className="w-full max-w-[440px]">
          {/* Card Đặt lại mật khẩu */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] p-8 sm:p-9">
            {/* Tiêu đề & phụ đề */}
            <h1 className="text-[24px] font-bold tracking-tight text-slate-900 leading-snug">
              Đặt lại mật khẩu
            </h1>
            <p className="text-sm text-slate-500 mt-2 mb-6 leading-relaxed">
              Nhập mật khẩu mới và xác nhận để tiếp tục.
            </p>

            {/* Thông báo lỗi */}
            {errorMessage && (
              <div className="mb-5 p-3 rounded-lg bg-red-50 border border-red-200/80 text-red-700 text-sm">
                {errorMessage}
              </div>
            )}

            {/* Thông báo thành công */}
            {successMessage && (
              <div className="mb-5 p-3.5 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-800 text-sm">
                <div className="font-medium">{successMessage}</div>
                <div className="mt-2 text-xs text-emerald-700">
                  <Link
                    to={PATHS.login}
                    className="underline font-semibold hover:text-emerald-900"
                  >
                    Bấm vào đây nếu không tự động chuyển hướng &rarr;
                  </Link>
                </div>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Mật khẩu mới <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    if (errorMessage) setErrorMessage("");
                  }}
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  Ít nhất 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Xác nhận mật khẩu mới <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errorMessage) setErrorMessage("");
                  }}
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full !mt-6 py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-medium text-sm rounded-lg shadow-sm hover:shadow transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer text-center"
              >
                {loading ? "Đang xử lý..." : "Đặt lại mật khẩu"}
              </button>
            </form>

            {/* Phân cách & Điều hướng phụ */}
            <div className="my-6 border-t border-slate-100" />
            <div className="text-center text-sm text-slate-600">
              Nhớ mật khẩu?{" "}
              <Link
                to={PATHS.login}
                className="font-medium text-blue-600 hover:text-blue-700 transition-colors no-underline ml-1"
              >
                Đăng nhập
              </Link>
            </div>

          </div>

          {/* Dòng chữ chân trang */}
          <p className="text-center text-xs text-slate-400 mt-8 tracking-tight">
            Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư
          </p>
        </div>
      </main>
    </div>
  );
}
