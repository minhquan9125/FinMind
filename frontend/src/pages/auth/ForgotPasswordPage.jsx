import React, { useState } from "react";
import { Link } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";
import { mockForgotPassword } from "../../mocks/authMock.js";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!email.trim()) {
      setErrorMessage("Vui lòng nhập địa chỉ email của bạn.");
      return;
    }

    setLoading(true);

    try {
      const res = await mockForgotPassword(email.trim());
      setSuccessMessage(res.message || `Hướng dẫn đặt lại mật khẩu đã được gửi tới ${email.trim()}.`);
    } catch (err) {
      setErrorMessage(err.message || "Không thể gửi yêu cầu đặt lại mật khẩu. Vui lòng thử lại.");
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
          {/* Card Quên mật khẩu */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] p-8 sm:p-9">
            {/* Tiêu đề & phụ đề */}
            <h1 className="text-[24px] font-bold tracking-tight text-slate-900 leading-snug">
              Quên mật khẩu
            </h1>
            <p className="text-sm text-slate-500 mt-2 mb-6 leading-relaxed">
              Nhập email tài khoản của bạn. FinMind sẽ gửi hướng dẫn đặt lại mật khẩu.
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
                {successMessage}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errorMessage) setErrorMessage("");
                  }}
                  placeholder="ten@congty.vn"
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white font-medium text-sm rounded-lg shadow-sm hover:shadow transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer text-center"
              >
                {loading ? "Đang gửi hướng dẫn..." : "Gửi hướng dẫn đặt lại mật khẩu"}
              </button>
            </form>

            {/* Phân cách */}
            <div className="my-6 border-t border-slate-100" />

            {/* Quay lại Đăng nhập */}
            <div className="text-center text-sm text-slate-600">
              Nhớ mật khẩu?{" "}
              <Link
                to={PATHS.login}
                className="font-medium text-blue-600 hover:text-blue-700 transition-colors no-underline ml-1"
              >
                Đăng nhập
              </Link>
            </div>

            {/* Khu vực hỗ trợ thử nghiệm Mock */}
            <div className="mt-6 pt-4 border-t border-dashed border-slate-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold tracking-wider uppercase text-slate-400">
                  Thử nghiệm nhanh (Mock)
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEmail("user@finmind.vn");
                    setErrorMessage("");
                    setSuccessMessage("");
                  }}
                  className="text-xs px-2.5 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors cursor-pointer border border-slate-200/60"
                >
                  Điền user@finmind.vn
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEmail("admin@finmind.vn");
                    setErrorMessage("");
                    setSuccessMessage("");
                  }}
                  className="text-xs px-2.5 py-1.5 rounded-md bg-blue-50 hover:bg-blue-100 text-blue-700 font-medium transition-colors cursor-pointer border border-blue-200/60"
                >
                  Điền admin@finmind.vn
                </button>
              </div>
            </div>
          </div>

          {/* Dòng chữ chân trang */}
          <p className="text-center text-xs text-slate-400 mt-8 tracking-tight">
            Chỉ hỗ trợ mục đích nghiên cứu - Không phải khuyến nghị đầu tư
          </p>
        </div>
      </main>
    </div>
  );
}
