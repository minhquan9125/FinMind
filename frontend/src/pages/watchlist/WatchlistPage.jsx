import { useEffect, useState } from "react";
import { Link, useNavigate } from "../../app/router.jsx";
import { Sidebar } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { researcherMock } from "../dashboard/mock.js";
import { PATHS } from "../../shared/paths.js";
import {
  COMPANY_DIRECTORY,
  STORAGE_KEY,
  getStoredWatchlist,
  saveStoredWatchlist,
} from "./mock.js";

const menuPaths = {
  dashboard: "/dashboard",
  companies: "/companies",
  copilot: "/research",
  watchlist: "/watchlist",
  graph: "/graph",
};

export default function WatchlistPage() {
  const navigate = useNavigate();

  // Danh sách các mã cổ phiếu đang theo dõi (lấy từ localStorage)
  const [watchlistTickers, setWatchlistTickers] = useState(getStoredWatchlist);

  // State tìm kiếm & bộ lọc
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("name");

  // State toast hoàn tác khi bỏ theo dõi
  const [lastRemovedTicker, setLastRemovedTicker] = useState(null);
  const [toastMessage, setToastMessage] = useState("");
  const [showToast, setShowToast] = useState(false);

  // Modal thêm nhanh doanh nghiệp vào watchlist
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedTickerToAdd, setSelectedTickerToAdd] = useState("");

  // Lưu vào localStorage khi watchlist thay đổi
  const saveWatchlist = (newTickers) => {
    setWatchlistTickers(newTickers);
    saveStoredWatchlist(newTickers);
  };

  // Lắng nghe sự kiện storage để đồng bộ realtime giữa các tab
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === STORAGE_KEY) {
        setWatchlistTickers(getStoredWatchlist());
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  // Lấy dữ liệu công ty đầy đủ cho các mã trong watchlist
  const watchlistItems = watchlistTickers.map((ticker) => {
    const found = COMPANY_DIRECTORY[ticker];
    return (
      found || {
        ticker,
        name: `Doanh nghiệp ${ticker}`,
        sector: "Khác",
        exchange: "Chưa có dữ liệu",
        latestPeriod: "FY2025",
        sourceStatus: "Đã có nguồn công bố",
      }
    );
  });

  // Danh sách các ngành duy nhất có trong watchlist
  const distinctSectors = Array.from(
    new Set(watchlistItems.map((item) => item.sector))
  ).filter(Boolean);

  // Lọc theo từ khóa tìm kiếm và ngành
  let filteredItems = watchlistItems.filter((item) => {
    const query = search.trim().toLowerCase();
    const matchSearch =
      !query ||
      item.ticker.toLowerCase().includes(query) ||
      item.name.toLowerCase().includes(query);
    const matchSector = sectorFilter === "ALL" || item.sector === sectorFilter;
    return matchSearch && matchSector;
  });

  // Sắp xếp
  filteredItems.sort((a, b) => {
    if (sortBy === "name") {
      return a.name.localeCompare(b.name, "vi");
    }
    if (sortBy === "sector") {
      return (
        a.sector.localeCompare(b.sector, "vi") ||
        a.ticker.localeCompare(b.ticker)
      );
    }
    return 0;
  });

  // Xóa doanh nghiệp khỏi watchlist
  const handleRemove = (ticker) => {
    const updated = watchlistTickers.filter((t) => t !== ticker);
    saveWatchlist(updated);
    setLastRemovedTicker(ticker);
    setToastMessage(`Đã bỏ ${ticker} khỏi danh sách theo dõi`);
    setShowToast(true);
  };

  // Hoàn tác xóa (Undo)
  const handleUndo = () => {
    if (!lastRemovedTicker) return;
    if (!watchlistTickers.includes(lastRemovedTicker)) {
      const updated = [...watchlistTickers, lastRemovedTicker];
      saveWatchlist(updated);
    }
    setShowToast(false);
    setLastRemovedTicker(null);
  };

  // Tự động đóng toast sau 5 giây
  useEffect(() => {
    if (!showToast) return;
    const timer = setTimeout(() => {
      setShowToast(false);
    }, 5000);
    return () => clearTimeout(timer);
  }, [showToast]);

  // Thêm mã vào watchlist
  const handleAddTicker = (ticker) => {
    if (!ticker) return;
    if (!watchlistTickers.includes(ticker)) {
      saveWatchlist([...watchlistTickers, ticker]);
    }
    setIsAddModalOpen(false);
    setSelectedTickerToAdd("");
  };

  // Danh sách mã có thể thêm
  const allAvailableTickers = Object.keys(COMPANY_DIRECTORY);
  const availableToAdd = allAvailableTickers.filter(
    (t) => !watchlistTickers.includes(t)
  );

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A] selection:bg-[#EEF4FF] selection:text-[#2563EB]">
      {/* 1. Shared Researcher Sidebar có sẵn */}
      <Sidebar
        groups={userMenu}
        activeId="watchlist"
        onSelect={(id) => navigate(menuPaths[id] || "/dashboard")}
        profile={researcherMock}
        onProfile={() => navigate("/profile")}
        onLogout={() => navigate("/login")}
      />

      {/* 2. Main Viewport */}
      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
        {/* MAIN CONTENT CANVAS */}
        <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 space-y-8">
          {/* View Header Block */}
          <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-transparent">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
                  Danh sách theo dõi
                </h1>
              </div>
              <p className="text-sm text-slate-500 mt-1">
                Theo dõi nhanh các doanh nghiệp bạn quan tâm.
              </p>
            </div>

            <div className="flex items-center gap-2.5">
              {watchlistTickers.length > 0 && (
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-medium shadow-xs transition-colors"
                >
                  <span className="material-symbols-outlined text-sm">add</span>
                  <span>Thêm mã</span>
                </button>
              )}

              <Link
                to={PATHS.companies}
                className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] hover:border-[#CBD5E1] rounded-lg text-xs font-medium text-slate-800 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-all no-underline"
              >
                <span className="material-symbols-outlined text-slate-500 text-base">
                  search
                </span>
                <span>Tìm doanh nghiệp</span>
              </Link>
            </div>
          </header>

          {/* ───────────────────────────────────────────────────────────── */}
          {/* POPULATED STATE CONTAINER                                     */}
          {/* ───────────────────────────────────────────────────────────── */}
          {watchlistTickers.length > 0 ? (
            <div className="space-y-6" id="populatedView">
              {/* Summary Analytical Metrics Cards (3-column Bento Grid) */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Card 1 */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] hover:border-[#CBD5E1] transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-medium">
                      Doanh nghiệp đang theo dõi
                    </span>
                    <span className="material-symbols-outlined text-slate-400 text-lg">
                      bookmark
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-semibold text-slate-900 tabular-numbers">
                      {watchlistItems.length}
                    </span>
                    <span className="text-xs text-slate-400">mã cổ phiếu</span>
                  </div>
                </div>

                {/* Card 2 */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] hover:border-[#CBD5E1] transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-medium">Ngành</span>
                    <span className="material-symbols-outlined text-slate-400 text-lg">
                      pie_chart
                    </span>
                  </div>
                  <div className="truncate">
                    <span className="text-base font-semibold text-slate-800 truncate block">
                      {distinctSectors.length > 0
                        ? distinctSectors.join(", ")
                        : "--"}
                    </span>
                  </div>
                </div>

                {/* Card 3 */}
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] hover:border-[#CBD5E1] transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-medium">
                      Kỳ dữ liệu gần nhất
                    </span>
                    <span className="material-symbols-outlined text-slate-400 text-lg">
                      calendar_today
                    </span>
                  </div>
                  <div>
                    <span className="text-3xl font-semibold text-slate-900 tabular-numbers">
                      FY2025
                    </span>
                  </div>
                </div>
              </div>

              {/* Analytical Toolbar: Filter, Search & Sort */}
              <div className="bg-white border border-[#E2E8F0] rounded-xl p-3.5 shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
                {/* Live Search Input */}
                <div className="relative flex-1 max-w-md">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-base">
                    search
                  </span>
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Tìm trong danh sách theo dõi..."
                    className="w-full h-9 pl-9 pr-4 bg-white border border-[#E2E8F0] rounded-lg text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/15 transition-all"
                  />
                </div>

                {/* Sector Filter Pills & Sorting Select */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                    <button
                      type="button"
                      onClick={() => setSectorFilter("ALL")}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                        sectorFilter === "ALL"
                          ? "bg-white text-[#2563EB] shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Tất cả
                    </button>
                    <button
                      type="button"
                      onClick={() => setSectorFilter("Ngân hàng")}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                        sectorFilter === "Ngân hàng"
                          ? "bg-white text-[#2563EB] shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Ngân hàng
                    </button>
                    <button
                      type="button"
                      onClick={() => setSectorFilter("Công nghệ")}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                        sectorFilter === "Công nghệ"
                          ? "bg-white text-[#2563EB] shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Công nghệ
                    </button>
                  </div>

                  {/* Sort Select */}
                  <div className="relative">
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                      className="h-9 pl-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-xs text-slate-700 font-medium appearance-none focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/15 cursor-pointer"
                    >
                      <option value="name">Sắp xếp: Tên doanh nghiệp (A-Z)</option>
                      <option value="sector">Sắp xếp: Ngành</option>
                    </select>
                    <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none text-base">
                      expand_more
                    </span>
                  </div>
                </div>
              </div>

              {/* Watchlist Data Table Container */}
              <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="h-9 bg-[#F1F5F9] text-slate-500 border-b border-[#E2E8F0] text-xs font-semibold uppercase tracking-wider select-none">
                        <th className="px-5 py-2.5 text-left whitespace-nowrap" scope="col">
                          Doanh nghiệp
                        </th>
                        <th className="px-4 py-2.5 text-left whitespace-nowrap w-32" scope="col">
                          Ngành
                        </th>
                        <th className="px-4 py-2.5 text-left whitespace-nowrap w-24" scope="col">
                          Sàn
                        </th>
                        <th className="px-4 py-2.5 text-left whitespace-nowrap w-40" scope="col">
                          Kỳ dữ liệu gần nhất
                        </th>
                        <th className="px-4 py-2.5 text-left whitespace-nowrap w-48" scope="col">
                          Trạng thái nguồn
                        </th>
                        <th className="px-5 py-2.5 text-right whitespace-nowrap w-64" scope="col">
                          Thao tác
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#F1F5F9] text-xs text-slate-700">
                      {filteredItems.map((company) => {
                        const exchangeClass =
                          company.exchange === "Chưa có dữ liệu"
                            ? "text-slate-400 font-normal"
                            : "text-slate-700 font-medium";

                        return (
                          <tr
                            key={company.ticker}
                            className="h-16 hover:bg-[#F8FAFC] transition-colors border-b border-[#F1F5F9] last:border-b-0"
                          >
                            <td className="px-5 py-3">
                              <div className="flex flex-col">
                                <Link
                                  to={PATHS.companyDetail(company.ticker)}
                                  className="font-semibold text-slate-900 hover:text-[#2563EB] tracking-tight transition-colors no-underline text-sm"
                                >
                                  {company.ticker}
                                </Link>
                                <span className="text-xs text-slate-500 truncate max-w-xs mt-0.5">
                                  {company.name}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-700 font-medium">
                                {company.sector}
                              </span>
                            </td>
                            <td className={`px-4 py-3 ${exchangeClass}`}>
                              {company.exchange}
                            </td>
                            <td className="px-4 py-3 tabular-numbers text-slate-800 font-medium">
                              FY2025
                            </td>
                            <td className="px-4 py-3">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-[#DCFCE7] text-[#15803D] font-medium border border-emerald-200">
                                <span className="material-symbols-outlined text-xs text-[#15803D]">
                                  check_circle
                                </span>
                                <span>Đã có nguồn công bố</span>
                              </span>
                            </td>
                            <td className="px-5 py-3 text-right">
                              <div className="inline-flex items-center justify-end gap-3 text-xs font-medium">
                                <Link
                                  to={PATHS.companyDetail(company.ticker)}
                                  className="text-[#2563EB] hover:underline no-underline"
                                >
                                  Xem chi tiết
                                </Link>
                                <span className="text-slate-300">·</span>
                                <Link
                                  to={`/research?company=${encodeURIComponent(
                                    company.ticker
                                  )}&period=FY2025`}
                                  className="text-[#2563EB] hover:underline no-underline"
                                >
                                  Hỏi FinMind
                                </Link>
                                <span className="text-slate-300">·</span>
                                <button
                                  type="button"
                                  onClick={() => handleRemove(company.ticker)}
                                  className="text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                                >
                                  Bỏ theo dõi
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Filter zero-match empty state */}
                {filteredItems.length === 0 && (
                  <div className="py-12 px-6 text-center" id="filterEmptyState">
                    <span className="material-symbols-outlined text-3xl text-slate-300 mx-auto mb-2 block">
                      filter_alt_off
                    </span>
                    <p className="text-sm font-medium text-slate-700">
                      Không có doanh nghiệp phù hợp với bộ lọc.
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Vui lòng điều chỉnh từ khóa tìm kiếm hoặc danh mục ngành.
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ───────────────────────────────────────────────────────────── */
            /* ZERO WATCHLIST EMPTY STATE (Khớp 100% bản chuẩn hóa không seed mẫu) */
            /* ───────────────────────────────────────────────────────────── */
            <div
              className="bg-white border border-[#E2E8F0] rounded-xl p-12 text-center shadow-[0_1px_3px_0_rgba(15,23,42,0.04)] max-w-2xl mx-auto my-12"
              id="zeroStateView"
            >
              <div className="w-16 h-16 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mx-auto mb-5">
                <span className="material-symbols-outlined text-slate-400 text-3xl">
                  bookmark_border
                </span>
              </div>
              <h2 className="text-lg sm:text-xl font-semibold text-slate-900">
                Chưa có doanh nghiệp nào trong danh sách theo dõi
              </h2>
              <p className="text-sm text-slate-500 mt-2 mb-6 max-w-md mx-auto leading-relaxed">
                Theo dõi doanh nghiệp để truy cập nhanh thông tin, báo cáo và
                nghiên cứu liên quan.
              </p>
              <div>
                <Link
                  to={PATHS.companies}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] active:bg-[#1E40AF] text-white rounded-lg font-medium text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 no-underline"
                >
                  <span className="material-symbols-outlined text-white text-base">
                    explore
                  </span>
                  <span>Khám phá doanh nghiệp</span>
                </Link>
              </div>
            </div>
          )}
        </main>

        {/* RESEARCH INTEGRITY INSTITUTIONAL FOOTER */}
        <footer className="mt-auto py-6 border-t border-[#E2E8F0] bg-white select-none">
          <div className="max-w-6xl mx-auto px-8 text-center">
            <p className="text-xs text-slate-400 tracking-tight">
              Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư
            </p>
          </div>
        </footer>
      </div>

      {/* FLOATING ACTION TOAST NOTIFICATION FOR UNDO */}
      {showToast && (
        <div
          className="fixed bottom-6 right-6 bg-slate-900 text-white border border-slate-800 rounded-xl px-4 py-3 shadow-[0_10px_25px_-5px_rgba(15,23,42,0.3)] flex items-center gap-3.5 z-50 transition-all duration-200"
          id="toastNotification"
        >
          <span className="material-symbols-outlined text-emerald-400 text-lg">
            check_circle
          </span>
          <span className="text-xs text-slate-200">{toastMessage}</span>
          <button
            type="button"
            onClick={handleUndo}
            className="text-xs font-medium text-blue-400 hover:text-blue-300 underline underline-offset-4 ml-1 cursor-pointer"
          >
            Hoàn tác
          </button>
        </div>
      )}

      {/* MODAL THÊM DOANH NGHIỆP VÀO WATCHLIST */}
      {isAddModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-2xs p-4"
          onClick={() => setIsAddModalOpen(false)}
        >
          <div
            className="w-full max-w-md bg-white rounded-2xl border border-slate-200 p-6 shadow-xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">
                Thêm doanh nghiệp vào danh sách theo dõi
              </h3>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded p-1 text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Chọn doanh nghiệp trong danh mục được hỗ trợ:
            </p>

            <div className="space-y-3">
              <select
                value={selectedTickerToAdd}
                onChange={(e) => setSelectedTickerToAdd(e.target.value)}
                className="w-full h-10 px-3 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:border-blue-600"
              >
                <option value="">-- Chọn mã cổ phiếu --</option>
                {availableToAdd.map((ticker) => {
                  const comp = COMPANY_DIRECTORY[ticker];
                  return (
                    <option key={ticker} value={ticker}>
                      {ticker} · {comp?.name || ticker} ({comp?.sector || "Khác"})
                    </option>
                  );
                })}
              </select>

              {availableToAdd.length === 0 && (
                <p className="text-xs text-emerald-600">
                  Tất cả các doanh nghiệp hiện có đều đã nằm trong danh sách theo dõi.
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Hủy
              </button>
              <button
                type="button"
                disabled={!selectedTickerToAdd}
                onClick={() => handleAddTicker(selectedTickerToAdd)}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer"
              >
                Thêm vào theo dõi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
