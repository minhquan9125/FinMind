import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import { Modal, Button, EmptyState } from "../../shared/ui/index.js";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { useEffect, useState } from "react";
import { Link } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";
import {
  COMPANY_DIRECTORY,
  STORAGE_KEY,
  getStoredWatchlist,
  saveStoredWatchlist,
} from "./mock.js";

export default function WatchlistPage() {
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

  return <UserShell activeId="watchlist" className="fm-watchlist desk-watchlist">
    <DeskHeader title="Danh sách theo dõi" section="Cá nhân" description="Tổ chức những doanh nghiệp bạn muốn tìm hiểu."><button type="button" className="desk-primary" onClick={() => setIsAddModalOpen(true)}><AppIcon name="plus" />Thêm doanh nghiệp</button></DeskHeader>
    <main className="desk-watchlist-workbench">
      <aside className="desk-watchlist-sidebar"><div className="desk-watchlist-total"><span>Đang theo dõi</span><strong>{watchlistTickers.length}</strong><p>doanh nghiệp</p></div><h2>Lọc theo ngành</h2><button type="button" aria-pressed={sectorFilter === 'ALL'} onClick={() => setSectorFilter('ALL')}>Tất cả<span>{watchlistTickers.length}</span></button>{distinctSectors.map(item => <button type="button" key={item} aria-pressed={sectorFilter === item} onClick={() => setSectorFilter(item)}>{item}<span>{watchlistItems.filter(c => c.sector === item).length}</span></button>)}<p className="desk-filter-note">Danh sách theo dõi được lưu trên trình duyệt này. Hồ sơ và kỳ dữ liệu trong danh mục là minh họa.</p></aside>
      <section className="desk-watchlist-table"><div className="desk-explorer-toolbar"><label><AppIcon name="search" /><input type="search" aria-label="Tìm trong danh sách theo dõi" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tên hoặc mã doanh nghiệp" /></label><label className="desk-sort-label">Sắp xếp<select value={sortBy} onChange={event => setSortBy(event.target.value)}><option value="name">Tên doanh nghiệp</option><option value="sector">Ngành</option></select></label></div>
      {filteredItems.length ? <div className="desk-table-scroll"><table><thead><tr><th>Doanh nghiệp</th><th>Sàn / Ngành</th><th>Kỳ dữ liệu mẫu</th><th>Thao tác</th></tr></thead><tbody>{filteredItems.map(company => <tr key={company.ticker}><td><Link className="desk-row-ticker" to={PATHS.companyDetail(company.ticker)}>{company.ticker}</Link><p>{company.name}</p></td><td><span>{company.exchange}</span><small>{company.sector}</small></td><td>{company.latestPeriod}<small>{company.sourceStatus}</small></td><td><div className="desk-row-actions"><Link to={`/research?company=${company.ticker}&question=${encodeURIComponent('Phân tích '+company.ticker)}`}>Nghiên cứu <AppIcon name="arrow" /></Link><button type="button" onClick={() => handleRemove(company.ticker)} aria-label={`Bỏ theo dõi ${company.ticker}`}><AppIcon name="close" /></button></div></td></tr>)}</tbody></table></div> : <EmptyState title={watchlistTickers.length ? 'Không có doanh nghiệp khớp bộ lọc' : 'Danh sách của bạn đang trống'} description="Thêm doanh nghiệp hoặc đổi bộ lọc để bắt đầu theo dõi." action={<button className="desk-text-link" type="button" onClick={() => setIsAddModalOpen(true)}>Thêm doanh nghiệp →</button>} />}
      <div className="desk-table-footer">{filteredItems.length} / {watchlistTickers.length} doanh nghiệp<span>Dữ liệu danh mục minh họa</span></div></section>
    </main>
    {showToast && <div className="desk-toast" role="status"><AppIcon name="check" /><span>{toastMessage}</span><button type="button" onClick={handleUndo}>Hoàn tác</button></div>}
    <Modal open={isAddModalOpen} title="Thêm doanh nghiệp theo dõi" onClose={() => setIsAddModalOpen(false)} footer={<Button disabled={!selectedTickerToAdd} onClick={() => handleAddTicker(selectedTickerToAdd)}>Thêm vào danh sách</Button>}>
      {availableToAdd.length ? <label className="desk-add-company">Doanh nghiệp trong danh mục<select value={selectedTickerToAdd} onChange={event => setSelectedTickerToAdd(event.target.value)}><option value="">Chọn doanh nghiệp</option>{availableToAdd.map(ticker => <option key={ticker} value={ticker}>{ticker} · {COMPANY_DIRECTORY[ticker]?.name || ticker}</option>)}</select></label> : <p>Bạn đã theo dõi tất cả doanh nghiệp trong danh mục.</p>}
    </Modal>
  </UserShell>;
}
