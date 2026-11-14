import React, { useState } from "react";
import { Link, useNavigate } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";

export default function HomePage() {
  const navigate = useNavigate();
  const [selectedTicker, setSelectedTicker] = useState("FPT");
  const [selectedPeriod, setSelectedPeriod] = useState("FY2025");
  const [queryInput, setQueryInput] = useState("");
  const [copied, setCopied] = useState(false);

  // Submit câu hỏi nghiên cứu
  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    const q = queryInput.trim();
    navigate(
      PATHS.researchQuery({
        company: selectedTicker || undefined,
        period: selectedPeriod || undefined,
        question: q || undefined,
        autosubmit: Boolean(q),
      })
    );
  };

  // Chọn mã cổ phiếu từ danh sách ngành
  const handleSelectTicker = (ticker) => {
    setSelectedTicker(ticker);
    navigate(PATHS.companyDetail(ticker));
  };

  // Sao chép liên kết nguồn
  const handleCopyCitation = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-[#F8FAFC] text-[#0F172A] min-h-screen font-sans antialiased selection:bg-blue-100 selection:text-blue-900">
      {/* ──────────────── 1. HEADER ──────────────── */}
      <header className="bg-white border-b border-slate-200 shadow-xs sticky top-0 z-50">
        <div className="flex justify-between items-center max-w-7xl mx-auto px-4 sm:px-8 h-16 w-full">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <Link to={PATHS.home} className="flex items-center gap-2 group no-underline">
              <div className="w-8 h-8 rounded-lg bg-[#2563EB] text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-xs">
                FM
              </div>
              <span className="text-xl font-bold text-slate-900 tracking-tight">FinMind</span>
            </Link>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-8 h-full">
            <a
              href="#research"
              className="text-[#2563EB] font-medium border-b-2 border-[#2563EB] py-5 text-sm no-underline"
            >
              Nghiên cứu
            </a>
            <a
              href="#companies"
              className="text-slate-600 hover:text-slate-900 font-medium py-5 text-sm transition-colors no-underline"
            >
              Doanh nghiệp
            </a>
            <a
              href="#methodology"
              className="text-slate-600 hover:text-slate-900 font-medium py-5 text-sm transition-colors no-underline"
            >
              Phương pháp
            </a>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-4">
            <Link
              to={PATHS.login}
              className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors no-underline"
            >
              Đăng nhập
            </Link>
            <Link
              to={PATHS.register}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg text-sm font-medium text-white bg-[#2563EB] hover:bg-blue-700 shadow-xs transition-all no-underline"
            >
              Bắt đầu nghiên cứu
            </Link>
          </div>
        </div>
      </header>

      {/* ──────────────── MAIN CANVAS ──────────────── */}
      <main className="w-full">
        {/* ──────────────── 2. HERO SECTION ──────────────── */}
        <section
          className="relative pt-16 pb-20 overflow-hidden bg-gradient-to-b from-[#EFF6FF]/70 via-white to-[#F8FAFC] border-b border-slate-200"
          id="research"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-8 text-center">
            {/* Eyebrow Pill */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#2563EB] text-xs font-semibold tracking-wider uppercase mb-6 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-[#2563EB] animate-pulse"></span>
              TRỢ LÝ NGHIÊN CỨU FINMIND
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-[52px] leading-tight font-bold text-slate-900 tracking-tight max-w-5xl mx-auto mb-6">
              Nghiên cứu doanh nghiệp Việt Nam<br />
              <span className="text-[#2563EB]">với bằng chứng có thể kiểm chứng.</span>
            </h1>

            {/* Subheading */}
            <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed">
              Đặt câu hỏi về tình hình tài chính, công bố thông tin và mối quan hệ doanh nghiệp dựa trên các nguồn dữ liệu có thể truy xuất và kiểm chứng.
            </p>

            {/* AI Research Query Box */}
            <form
              onSubmit={handleSearchSubmit}
              className="max-w-2xl mx-auto bg-white rounded-2xl border border-slate-300 shadow-md p-3.5 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-100/60 transition-all text-left mb-6"
              id="query"
            >
              <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-100">
                {selectedTicker && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-50 text-[#2563EB] text-xs font-medium border border-blue-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB]"></span>
                    {selectedTicker}
                    <button
                      type="button"
                      onClick={() => setSelectedTicker("")}
                      className="hover:opacity-75 focus:outline-none"
                    >
                      <span className="material-symbols-outlined text-[14px]">close</span>
                    </button>
                  </span>
                )}
                {selectedPeriod && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-100 text-slate-700 text-xs font-medium border border-slate-200">
                    {selectedPeriod}
                    <button
                      type="button"
                      onClick={() => setSelectedPeriod("")}
                      className="hover:opacity-75 focus:outline-none"
                    >
                      <span className="material-symbols-outlined text-[14px]">close</span>
                    </button>
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 flex-1 pl-1">
                  <span className="material-symbols-outlined text-slate-400 text-[20px]">search</span>
                  <input
                    type="text"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="Hỏi về FPT, VCB, MBB..."
                    className="w-full text-sm sm:text-base text-slate-800 border-0 p-0 focus:ring-0 focus:outline-none placeholder:text-slate-400 bg-transparent font-medium"
                  />
                </div>
                <button
                  type="submit"
                  aria-label="Bắt đầu nghiên cứu"
                  className="w-9 h-9 rounded-xl bg-[#2563EB] hover:bg-blue-700 text-white flex items-center justify-center transition-all shadow-xs flex-shrink-0 group cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px] group-hover:translate-x-0.5 transition-transform">
                    arrow_forward
                  </span>
                </button>
              </div>
            </form>

            {/* Trust Indicators */}
            <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-8 text-xs text-slate-600 mb-8">
              <div className="inline-flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-600 flex items-center justify-center">
                  <span className="material-symbols-outlined text-[12px] font-bold">check</span>
                </span>
                <span>Dựa trên bằng chứng</span>
              </div>
              <div className="inline-flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-600 flex items-center justify-center">
                  <span className="material-symbols-outlined text-[12px] font-bold">check</span>
                </span>
                <span>Câu trả lời đã kiểm chứng</span>
              </div>
              <div className="inline-flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-600 flex items-center justify-center">
                  <span className="material-symbols-outlined text-[12px] font-bold">check</span>
                </span>
                <span>Nguồn trích dẫn có thể truy xuất</span>
              </div>
            </div>

            {/* CTAs */}
            <div className="flex items-center justify-center gap-3">
              <Link
                to={PATHS.research}
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-white bg-[#2563EB] hover:bg-blue-700 shadow-xs transition-all no-underline"
              >
                Bắt đầu nghiên cứu
              </Link>
              <a
                href="#methodology"
                className="px-5 py-2.5 rounded-lg text-sm font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition-all shadow-xs no-underline"
              >
                Xem phương pháp
              </a>
            </div>
          </div>
        </section>

        {/* ──────────────── 3. PRODUCT PREVIEW ──────────────── */}
        <section className="py-20 bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Câu trả lời nghiên cứu được hỗ trợ bởi bằng chứng
              </h2>
              <p className="text-slate-600 text-base mb-2">
                Từ câu hỏi đến thông tin tài chính có thể kiểm chứng mà không cần tự tìm kiếm qua nhiều báo cáo phân tán.
              </p>
              <span className="inline-block text-xs text-slate-400 bg-slate-50 px-2.5 py-0.5 rounded border border-slate-200">
                Bản xem trước minh họa
              </span>
            </div>

            {/* Mockup Window Container */}
            <div className="max-w-5xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden">
              {/* Window Title Bar */}
              <div className="bg-slate-50 border-b border-slate-200 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                  <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
                  <span className="ml-2 text-xs text-slate-500 font-medium">
                    FPT · Phân tích kết quả kinh doanh FY2025
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span className="text-xs text-slate-600 font-medium">Đã kiểm chứng</span>
                </div>
              </div>

              {/* Split Panel Layout */}
              <div className="grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-slate-200">
                {/* LEFT PANEL: Research Answer */}
                <div className="md:col-span-7 p-6 sm:p-8 flex flex-col justify-between h-full">
                  <div className="space-y-6">
                    {/* Query Bubble */}
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 flex items-start gap-3">
                      <span className="material-symbols-outlined text-[#2563EB] text-[20px] mt-0.5">
                        help
                      </span>
                      <div>
                        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-0.5">
                          CÂU HỎI NGHIÊN CỨU
                        </div>
                        <div className="text-sm sm:text-base font-medium text-slate-800">
                          Doanh thu của FPT thay đổi như thế nào trong FY2025?
                        </div>
                      </div>
                    </div>

                    {/* Answer Block */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                          CÂU TRẢ LỜI CỦA FINMIND
                        </span>
                      </div>
                      <p className="text-slate-800 leading-relaxed text-sm sm:text-base">
                        FPT ghi nhận doanh thu tăng trưởng trong FY2025, với sự đóng góp của dịch vụ công nghệ và thị trường nước ngoài.
                        <a
                          href="#citation-1"
                          className="inline-flex items-center justify-center px-2 py-0.5 ml-1 text-xs font-semibold bg-blue-100 text-[#2563EB] rounded border border-blue-200 hover:bg-blue-200 transition-colors no-underline"
                        >
                          [1]
                        </a>
                      </p>

                      {/* Tabular Financial Metric Row */}
                      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                          <div>
                            <span className="block text-xs text-slate-500 mb-1">Doanh thu</span>
                            <span className="block text-sm sm:text-base font-bold text-slate-900 font-mono">
                              62.849 tỷ VND
                            </span>
                          </div>
                          <div>
                            <span className="block text-xs text-slate-500 mb-1">Tăng trưởng cùng kỳ</span>
                            <span className="block text-sm sm:text-base font-bold text-slate-900 font-mono">
                              +19,4%
                            </span>
                          </div>
                          <div>
                            <span className="block text-xs text-slate-500 mb-1">Kỳ báo cáo</span>
                            <span className="block text-sm font-medium text-slate-700 mt-0.5">
                              FY2025
                            </span>
                          </div>
                          <div>
                            <span className="block text-xs text-slate-500 mb-1">Phạm vi báo cáo</span>
                            <span className="block text-sm font-medium text-slate-700 mt-0.5">
                              Hợp nhất
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Bottom Status Badge */}
                  <div className="pt-4 mt-6 flex items-center justify-between border-t border-slate-100">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                      <span className="material-symbols-outlined text-[15px]">verified</span>
                      Câu trả lời đã kiểm chứng
                    </span>
                  </div>
                </div>

                {/* RIGHT PANEL: Verified Evidence Drawer */}
                <div className="md:col-span-5 bg-slate-50/70 p-6 sm:p-8 flex flex-col justify-between h-full" id="citation-1">
                  <div className="space-y-4">
                    {/* Panel Header */}
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        XÁC MINH NGUỒN
                      </span>
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Nguồn đã xác minh
                      </span>
                    </div>

                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-100 border border-blue-200 text-blue-800 text-xs font-semibold">
                      <span>[1]</span>
                      <span>Trích dẫn nguồn</span>
                    </div>

                    {/* Citation Details Card */}
                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3 text-left">
                      <div>
                        <span className="text-[11px] font-semibold text-slate-400 block mb-0.5 uppercase tracking-wider">
                          Tên nguồn
                        </span>
                        <span className="text-sm font-medium text-slate-900">
                          Báo cáo thường niên FPT 2025
                        </span>
                      </div>
                      <div>
                        <span className="text-[11px] font-semibold text-slate-400 block mb-0.5 uppercase tracking-wider">
                          Đơn vị công bố
                        </span>
                        <span className="text-xs font-medium text-slate-700">
                          Công ty Cổ phần FPT / Quan hệ nhà đầu tư
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-slate-400 block text-[11px] uppercase tracking-wider">Loại nguồn</span>
                          <span className="font-medium text-slate-700">Báo cáo thường niên</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[11px] uppercase tracking-wider">Kỳ báo cáo</span>
                          <span className="font-mono text-slate-700">FY2025</span>
                        </div>
                      </div>
                      <div>
                        <span className="text-[11px] font-semibold text-slate-400 block mb-0.5 uppercase tracking-wider">
                          Vị trí bằng chứng
                        </span>
                        <span className="text-xs font-medium text-slate-700">
                          Trang 82 · Bảng 14
                        </span>
                      </div>
                      <div>
                        <span className="text-[11px] font-semibold text-slate-400 block mb-0.5 uppercase tracking-wider">
                          Nguồn chính thức
                        </span>
                        <span className="text-xs font-medium text-slate-700">
                          Trang Quan hệ nhà đầu tư của FPT
                        </span>
                      </div>
                      <div className="pt-2 border-t border-slate-100">
                        <span className="text-xs text-slate-400 italic">
                          Đường dẫn nguồn: trang web chính thức của đơn vị công bố
                        </span>
                      </div>
                    </div>

                    {/* Quote Block */}
                    <div className="bg-white border-l-2 border-emerald-500 rounded-r-xl border-y border-r border-slate-200 p-4 space-y-1.5 text-left">
                      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Tham chiếu bằng chứng
                      </span>
                      <p className="text-xs text-slate-700 italic leading-relaxed">
                        “Doanh thu hợp nhất FY2025 tăng so với FY2024.”
                      </p>
                    </div>
                  </div>

                  {/* Action Links & Verification Note */}
                  <div className="pt-4 border-t border-slate-200 space-y-4">
                    <div className="flex flex-col sm:flex-row items-center gap-2">
                      <a
                        href="https://fpt.com/vi/nhadautu"
                        target="_blank"
                        rel="noreferrer"
                        className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-white bg-[#2563EB] hover:bg-blue-700 transition-colors shadow-xs no-underline"
                      >
                        <span>Mở nguồn chính thức</span>
                        <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                      </a>
                      <button
                        type="button"
                        onClick={handleCopyCitation}
                        className="w-full sm:w-auto inline-flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition-colors shadow-xs cursor-pointer"
                      >
                        {copied ? "Đã sao chép!" : "Sao chép liên kết nguồn"}
                      </button>
                    </div>

                    <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-100 flex items-start gap-2 text-left">
                      <span className="material-symbols-outlined text-[#2563EB] text-[18px] mt-0.5 flex-shrink-0">
                        open_in_new
                      </span>
                      <div>
                        <div className="text-xs font-semibold text-slate-800">Kiểm chứng tại nguồn gốc</div>
                        <p className="text-[11px] text-slate-600 leading-snug">
                          FinMind cung cấp thông tin nguồn có thể truy xuất để người dùng tự kiểm tra trực tiếp tại website của đơn vị công bố.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 4. DATA VISUALIZATION ──────────────── */}
        <section className="py-20 bg-[#F8FAFC] border-b border-slate-200" id="visualization">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-[#2563EB] text-xs font-semibold tracking-wider uppercase mb-3 shadow-xs">
                TRỰC QUAN HÓA DỮ LIỆU
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Theo dõi xu hướng tài chính với nguồn dữ liệu có thể kiểm chứng
              </h2>
              <p className="text-slate-600 text-base">
                Trực quan hóa các chỉ tiêu tài chính theo kỳ và truy xuất trực tiếp đến nguồn công bố chính thức.
              </p>
            </div>

            <div className="max-w-5xl mx-auto bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
              <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
                <div>
                  <h3 className="text-slate-900 font-bold text-lg tracking-tight">FPT Corporation</h3>
                  <p className="text-xs text-slate-500 font-medium">Doanh thu</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-lg border border-slate-200 px-3 py-1 text-xs text-slate-700 bg-white font-medium shadow-xs cursor-pointer hover:border-slate-300">
                    Hằng năm ▾
                  </span>
                  <span className="rounded-full bg-slate-100 text-slate-600 px-2.5 py-0.5 text-xs font-medium">
                    Dữ liệu minh họa
                  </span>
                </div>
              </div>

              {/* Line Chart SVG */}
              <div className="relative w-full h-56">
                <svg
                  className="w-full h-full overflow-visible"
                  fill="none"
                  viewBox="0 0 900 220"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <line stroke="#F1F5F9" strokeWidth="1.5" x1="80" x2="820" y1="30" y2="30"></line>
                  <line stroke="#F1F5F9" strokeWidth="1.5" x1="80" x2="820" y1="85" y2="85"></line>
                  <line stroke="#F1F5F9" strokeWidth="1.5" x1="80" x2="820" y1="140" y2="140"></line>
                  <line stroke="#E2E8F0" strokeWidth="1.5" x1="80" x2="820" y1="190" y2="190"></line>

                  {/* Trend line */}
                  <path
                    d="M150 140 L450 100 L750 55"
                    stroke="#2563EB"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2.5"
                  ></path>

                  {/* Points */}
                  <circle cx="150" cy="140" fill="white" r="5" stroke="#2563EB" strokeWidth="2.5"></circle>
                  <circle cx="450" cy="100" fill="white" r="5" stroke="#2563EB" strokeWidth="2.5"></circle>
                  <circle cx="750" cy="55" fill="white" r="5" stroke="#2563EB" strokeWidth="2.5"></circle>

                  {/* Years */}
                  <text fill="#64748B" fontFamily="Inter" fontSize="12" fontWeight="500" textAnchor="middle" x="150" y="210">
                    2023
                  </text>
                  <text fill="#64748B" fontFamily="Inter" fontSize="12" fontWeight="500" textAnchor="middle" x="450" y="210">
                    2024
                  </text>
                  <text fill="#64748B" fontFamily="Inter" fontSize="12" fontWeight="500" textAnchor="middle" x="750" y="210">
                    2025
                  </text>
                </svg>

                {/* Floating Tooltip */}
                <div className="absolute -top-3 right-[12%] sm:right-[14%] bg-white border border-slate-200 rounded-lg px-3 py-1.5 shadow-sm text-center pointer-events-none">
                  <span className="block text-xs font-bold text-blue-600 font-mono">62.849 tỷ VND</span>
                </div>
              </div>

              <div className="border-t border-slate-100 my-5"></div>

              {/* Metric Meta */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 font-medium">
                <span>Chỉ tiêu: <strong className="text-slate-700 font-semibold">Doanh thu</strong></span>
                <span className="text-slate-300">•</span>
                <span>Kỳ báo cáo: <strong className="text-slate-700 font-semibold">FY2025</strong></span>
                <span className="text-slate-300">•</span>
                <span>Phạm vi: <strong className="text-slate-700 font-semibold">Hợp nhất</strong></span>
                <span className="text-slate-300">•</span>
                <span>Đơn vị: <strong className="text-slate-700 font-semibold">Tỷ VND</strong></span>
              </div>

              {/* Source Details Card */}
              <div className="bg-[#F8FAFC] rounded-xl p-4 mt-4 border border-slate-200/60 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-left">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-slate-400 tracking-wider uppercase">NGUỒN DỮ LIỆU</span>
                    <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 rounded px-2 py-0.5 text-[11px] font-medium inline-flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px] font-bold">check</span>
                      Đã xác minh
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs text-slate-600">
                    <div>
                      <span className="text-slate-400">Tên nguồn:</span>{" "}
                      <span className="font-medium text-slate-800">Báo cáo thường niên FPT 2025</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Đơn vị công bố:</span>{" "}
                      <span className="font-medium text-slate-800">FPT Corporation</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Nguồn chính thức:</span>{" "}
                      <span className="font-medium text-slate-800">FPT Investor Relations</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Vị trí bằng chứng:</span>{" "}
                      <span className="font-medium text-slate-800">Trang 82 · Bảng 14</span>
                    </div>
                  </div>
                </div>

                <a
                  href="https://fpt.com/vi/nhadautu"
                  target="_blank"
                  rel="noreferrer"
                  className="bg-[#2563EB] hover:bg-blue-700 text-white font-medium text-xs px-4 py-2.5 rounded-lg inline-flex items-center gap-1.5 transition-colors shadow-xs flex-shrink-0 no-underline"
                >
                  <span>Mở nguồn chính thức</span>
                  <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 5. RESEARCH PRINCIPLES ──────────────── */}
        <section className="py-20 bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <div className="text-xs font-semibold text-[#2563EB] uppercase tracking-wider mb-2">
                NGUYÊN TẮC NGHIÊN CỨU
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                Tính minh bạch và khả năng kiểm chứng trong từng câu trả lời
              </h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
              {/* Card 01 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between h-full">
                <div className="flex-1 flex flex-col">
                  <div className="font-mono text-[#2563EB] font-bold text-lg mb-3">01</div>
                  <h3 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Nghiên cứu dựa trên bằng chứng
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[72px]">
                    Câu trả lời được tạo từ dữ liệu tài chính đã được xác thực thay vì chỉ dựa vào kiến thức sẵn có của mô hình.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 mt-6 flex items-start text-xs text-slate-500 gap-2 min-h-[52px]">
                  <span className="material-symbols-outlined text-slate-400 text-[16px] shrink-0 mt-0.5">database</span>
                  <span className="leading-snug">Chỉ sử dụng tập dữ liệu đã được xác thực</span>
                </div>
              </div>

              {/* Card 02 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between h-full">
                <div className="flex-1 flex flex-col">
                  <div className="font-mono text-[#2563EB] font-bold text-lg mb-3">02</div>
                  <h3 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Trích dẫn theo từng luận điểm
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[72px]">
                    Các nhận định quan trọng được liên kết với nguồn và vị trí bằng chứng cụ thể.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 mt-6 flex items-start text-xs text-slate-500 gap-2 min-h-[52px]">
                  <span className="material-symbols-outlined text-slate-400 text-[16px] shrink-0 mt-0.5">link</span>
                  <span className="leading-snug">Tham chiếu nguồn và vị trí</span>
                </div>
              </div>

              {/* Card 03 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between h-full">
                <div className="flex-1 flex flex-col">
                  <div className="font-mono text-[#2563EB] font-bold text-lg mb-3">03</div>
                  <h3 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Kiểm chứng câu trả lời
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[72px]">
                    Câu trả lời được đối chiếu với bằng chứng hỗ trợ trước khi hiển thị cho người dùng.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 mt-6 flex items-start text-xs text-slate-500 gap-2 min-h-[52px]">
                  <span className="material-symbols-outlined text-slate-400 text-[16px] shrink-0 mt-0.5">verified_user</span>
                  <span className="leading-snug">Kiểm chứng trước khi công bố</span>
                </div>
              </div>

              {/* Card 04 */}
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between h-full">
                <div className="flex-1 flex flex-col">
                  <div className="font-mono text-[#2563EB] font-bold text-lg mb-3">04</div>
                  <h3 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Phản hồi an toàn khi thiếu dữ liệu
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[72px]">
                    Khi bằng chứng chưa đủ, FinMind nêu rõ giới hạn thay vì đưa ra thông tin không được hỗ trợ.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 mt-6 flex items-start text-xs text-slate-500 gap-2 min-h-[52px]">
                  <span className="material-symbols-outlined text-slate-400 text-[16px] shrink-0 mt-0.5">shield</span>
                  <span className="leading-snug">Không đưa ra câu trả lời thiếu bằng chứng</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 6. VERIFICATION PIPELINE ──────────────── */}
        <section className="py-20 bg-[#F8FAFC] border-b border-slate-200" id="methodology">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <div className="text-xs font-semibold text-[#2563EB] uppercase tracking-wider mb-2">
                QUY TRÌNH
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Từ câu hỏi đến câu trả lời đã kiểm chứng
              </h2>
              <p className="text-slate-600 text-base">
                Quy trình nghiên cứu có kiểm soát giúp truy xuất bằng chứng, đánh giá mức độ hỗ trợ, liên kết nguồn trích dẫn và kiểm chứng câu trả lời trước khi hiển thị.
              </p>
            </div>

            {/* 4-step Pipeline */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative text-left">
              {/* Step 1 */}
              <div className="relative bg-white border border-slate-200 rounded-xl p-6 flex flex-col justify-between h-full shadow-xs">
                <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-lg bg-blue-100 text-[#2563EB] flex items-center justify-center font-mono font-bold text-xs">
                      01
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#2563EB] tracking-wider uppercase mb-2 min-h-[16px]">
                    ĐẶT CÂU HỎI
                  </div>
                  <h4 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Đặt câu hỏi nghiên cứu
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[110px]">
                    Đặt câu hỏi bằng ngôn ngữ tự nhiên về doanh nghiệp, kỳ tài chính hoặc chỉ tiêu được FinMind hỗ trợ.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-500 min-h-[50px] flex items-start leading-snug">
                  Doanh nghiệp · Kỳ báo cáo · Chỉ tiêu
                </div>
                {/* Chevron */}
                <div className="hidden md:flex absolute -right-3.5 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white border border-slate-200 items-center justify-center text-slate-400 shadow-xs">
                  <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                </div>
              </div>

              {/* Step 2 */}
              <div className="relative bg-white border border-slate-200 rounded-xl p-6 flex flex-col justify-between h-full shadow-xs">
                <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-lg bg-blue-100 text-[#2563EB] flex items-center justify-center font-mono font-bold text-xs">
                      02
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#2563EB] tracking-wider uppercase mb-2 min-h-[16px]">
                    TRUY XUẤT & KIỂM TRA
                  </div>
                  <h4 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Truy xuất bằng chứng đã được phê duyệt
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[110px]">
                    FinMind truy xuất dữ liệu có cấu trúc, dữ liệu vector và quan hệ đồ thị, sau đó kiểm tra bằng chứng có đủ để hỗ trợ câu trả lời hay không.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-500 min-h-[50px] flex items-start leading-snug">
                  Dữ liệu cấu trúc + Vector + Đồ thị · Cổng kiểm tra
                </div>
                <div className="hidden md:flex absolute -right-3.5 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white border border-slate-200 items-center justify-center text-slate-400 shadow-xs">
                  <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                </div>
              </div>

              {/* Step 3 */}
              <div className="relative bg-white border border-slate-200 rounded-xl p-6 flex flex-col justify-between h-full shadow-xs">
                <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-lg bg-blue-100 text-[#2563EB] flex items-center justify-center font-mono font-bold text-xs">
                      03
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#2563EB] tracking-wider uppercase mb-2 min-h-[16px]">
                    TẠO CÂU TRẢ LỜI & GẮN NGUỒN
                  </div>
                  <h4 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Tạo bản trả lời dựa trên bằng chứng
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[110px]">
                    Câu trả lời chỉ được xây dựng từ bằng chứng đã được phê duyệt và các luận điểm quan trọng được liên kết với nguồn có thể truy xuất.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-500 min-h-[50px] flex items-start leading-snug">
                  Tổng hợp dựa trên bằng chứng · Liên kết trích dẫn
                </div>
                <div className="hidden md:flex absolute -right-3.5 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white border border-slate-200 items-center justify-center text-slate-400 shadow-xs">
                  <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                </div>
              </div>

              {/* Step 4 */}
              <div className="relative bg-white border border-slate-200 rounded-xl p-6 flex flex-col justify-between h-full shadow-xs">
                <div className="flex-1 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-lg bg-blue-100 text-[#2563EB] flex items-center justify-center font-mono font-bold text-xs">
                      04
                    </span>
                  </div>
                  <div className="text-xs font-bold text-[#2563EB] tracking-wider uppercase mb-2 min-h-[16px]">
                    KIỂM CHỨNG & HIỂN THỊ
                  </div>
                  <h4 className="text-base font-bold text-slate-900 mb-2 min-h-[48px] flex items-start">
                    Kiểm chứng trước khi hiển thị
                  </h4>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed min-h-[110px]">
                    FinMind đối chiếu câu trả lời đã gắn nguồn với bằng chứng hỗ trợ. Nếu chưa đạt yêu cầu, hệ thống chỉ thực hiện một lần sửa có kiểm soát hoặc trả về phản hồi an toàn.
                  </p>
                </div>
                <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-500 min-h-[50px] flex items-start leading-snug">
                  Kiểm chứng câu trả lời · Phản hồi an toàn
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 7. RESEARCH COVERAGE ──────────────── */}
        <section className="py-20 bg-white border-b border-slate-200" id="companies">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <div className="text-xs font-semibold text-[#2563EB] uppercase tracking-wider mb-2">
                PHẠM VI DỮ LIỆU
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Phạm vi nghiên cứu được kiểm soát
              </h2>
              <p className="text-slate-600 text-base">
                MVP tập trung vào tập dữ liệu được kiểm soát gồm các doanh nghiệp niêm yết Việt Nam được hỗ trợ và các nguồn công khai đã được phê duyệt.
              </p>
            </div>

            {/* Two Sector Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8 text-left">
              {/* BANKING SECTOR */}
              <div className="bg-[#F8FAFC] rounded-xl border border-slate-200 p-6 shadow-xs">
                <div className="flex items-center justify-between mb-4">
                  <span className="px-2.5 py-1 rounded bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                    NGÀNH NGÂN HÀNG
                  </span>
                  <span className="text-xs text-slate-400">5 doanh nghiệp</span>
                </div>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-6">
                  Báo cáo tài chính, báo cáo thường niên và các công bố doanh nghiệp đã được phê duyệt.
                </p>
                <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200/60">
                  {["VCB", "BID", "CTG", "MBB", "TCB"].map((ticker) => (
                    <button
                      key={ticker}
                      type="button"
                      onClick={() => handleSelectTicker(ticker)}
                      className="px-3.5 py-1.5 rounded-lg bg-white border border-slate-200 text-xs sm:text-sm font-semibold text-slate-800 hover:border-blue-400 hover:text-[#2563EB] transition-colors cursor-pointer font-mono shadow-2xs"
                    >
                      {ticker}
                    </button>
                  ))}
                </div>
              </div>

              {/* TECHNOLOGY SECTOR */}
              <div className="bg-[#F8FAFC] rounded-xl border border-slate-200 p-6 shadow-xs">
                <div className="flex items-center justify-between mb-4">
                  <span className="px-2.5 py-1 rounded bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                    NGÀNH CÔNG NGHỆ
                  </span>
                  <span className="text-xs text-slate-400">5 doanh nghiệp</span>
                </div>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-6">
                  Báo cáo tài chính, báo cáo thường niên và các công bố doanh nghiệp đã được phê duyệt.
                </p>
                <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200/60">
                  {["FPT", "CMG", "ELC", "ITD", "ICT"].map((ticker) => (
                    <button
                      key={ticker}
                      type="button"
                      onClick={() => handleSelectTicker(ticker)}
                      className="px-3.5 py-1.5 rounded-lg bg-white border border-slate-200 text-xs sm:text-sm font-semibold text-slate-800 hover:border-blue-400 hover:text-[#2563EB] transition-colors cursor-pointer font-mono shadow-2xs"
                    >
                      {ticker}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Metric Bottom Bar */}
            <div className="bg-[#F8FAFC] rounded-xl border border-slate-200 p-4 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-slate-400 text-[18px]">inventory_2</span>
                <span className="text-xs sm:text-sm text-slate-700 font-medium">
                  Phạm vi tập dữ liệu được kiểm soát:
                </span>
              </div>
              <div className="text-xs font-medium text-slate-700 flex flex-wrap items-center justify-center sm:justify-end gap-2">
                <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-800">
                  10 doanh nghiệp niêm yết
                </span>
                <span className="text-slate-300">•</span>
                <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-800">
                  3 năm tài chính
                </span>
                <span className="text-slate-300">•</span>
                <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-800">
                  4 quý gần nhất
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 8. ETHICAL STANCE ──────────────── */}
        <section className="py-20 bg-[#F1F5F9]/60 border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-8">
            <div className="text-center max-w-3xl mx-auto mb-12">
              <div className="text-xs font-semibold text-[#2563EB] uppercase tracking-wider mb-2">
                PHẠM VI SẢN PHẨM
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Được thiết kế cho nghiên cứu, không phải tín hiệu giao dịch.
              </h2>
              <p className="text-slate-600 text-base leading-relaxed">
                FinMind hỗ trợ nghiên cứu doanh nghiệp dựa trên bằng chứng. Hệ thống không cung cấp khuyến nghị mua, bán, nắm giữ hoặc giá mục tiêu.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-blue-50 text-[#2563EB] flex items-center justify-center mb-4">
                    <span className="material-symbols-outlined text-[20px]">description</span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">NGUỒN CÓ THỂ TRUY XUẤT</h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                    Các thông tin tài chính được liên kết với nguồn công khai để người dùng có thể tự kiểm chứng.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 flex items-center gap-1.5 text-xs text-[#2563EB] font-medium">
                  <span>Liên kết đến nguồn chính thức</span>
                  <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-blue-50 text-[#2563EB] flex items-center justify-center mb-4">
                    <span className="material-symbols-outlined text-[20px]">lock</span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">TẬP DỮ LIỆU ĐƯỢC KIỂM SOÁT</h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                    Hoạt động nghiên cứu chỉ sử dụng dữ liệu đã được phê duyệt và xác thực trong phạm vi FinMind hỗ trợ.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 text-xs text-slate-500">
                  Tập dữ liệu nghiên cứu đã xác thực
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
                <div>
                  <div className="w-10 h-10 rounded-lg bg-blue-50 text-[#2563EB] flex items-center justify-center mb-4">
                    <span className="material-symbols-outlined text-[20px]">visibility</span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mb-2">MINH BẠCH VỀ GIỚI HẠN</h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                    Khi bằng chứng không đủ hoặc câu hỏi nằm ngoài phạm vi hỗ trợ, FinMind nêu rõ giới hạn cho người dùng.
                  </p>
                </div>
                <div className="pt-4 border-t border-slate-100 text-xs text-slate-500">
                  Trạng thái phản hồi rõ ràng
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ──────────────── 9. FINAL CTA ──────────────── */}
        <section className="py-20 bg-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-8">
            <div className="bg-gradient-to-b from-blue-50/60 via-white to-white border border-blue-100 rounded-2xl p-10 md:p-14 text-center shadow-xs">
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 tracking-tight mb-4">
                Bắt đầu nghiên cứu với bằng chứng có thể kiểm chứng.
              </h2>
              <p className="text-slate-600 text-base max-w-xl mx-auto mb-8 leading-relaxed">
                Đặt câu hỏi, kiểm tra nguồn và tự xác minh thông tin.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link
                  to={PATHS.register}
                  className="w-full sm:w-auto px-6 py-3 rounded-lg text-sm font-medium text-white bg-[#2563EB] hover:bg-blue-700 shadow-xs transition-all text-center no-underline"
                >
                  Bắt đầu nghiên cứu
                </Link>
                <a
                  href="#methodology"
                  className="w-full sm:w-auto px-6 py-3 rounded-lg text-sm font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition-all shadow-xs text-center no-underline"
                >
                  Xem phương pháp
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ──────────────── 10. FOOTER ──────────────── */}
      <footer className="w-full bg-white border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8 flex flex-col md:flex-row justify-between items-center gap-4 w-full">
          {/* Brand & Disclaimer */}
          <div className="space-y-1 text-center md:text-left">
            <div className="flex items-center justify-center md:justify-start gap-2">
              <span className="text-lg font-bold text-slate-900">FinMind</span>
            </div>
            <p className="text-xs text-slate-500">
              Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư · Đồ án tốt nghiệp đại học
            </p>
          </div>

          {/* Links */}
          <div className="flex flex-wrap justify-center md:justify-end gap-x-6 gap-y-2 text-xs sm:text-sm">
            <a href="#research" className="text-slate-600 hover:text-slate-900 transition-colors no-underline">
              Nghiên cứu
            </a>
            <a href="#companies" className="text-slate-600 hover:text-slate-900 transition-colors no-underline">
              Doanh nghiệp
            </a>
            <a href="#methodology" className="text-slate-600 hover:text-slate-900 transition-colors no-underline">
              Phương pháp
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
