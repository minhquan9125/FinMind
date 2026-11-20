import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import { Modal, Button, EmptyState } from "../../shared/ui/index.js";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { useEffect, useState } from "react";
import { Link, useAuth } from "../../app/router.jsx";
import { PATHS } from "../../shared/paths.js";
import { followCompany, getWatchlist, toView, unfollowCompany } from "./api.js";
import { getCompanyCatalog } from "../companies/financials.js";
import { getRevealed, visibleCompanies } from "../companies/visibleCompanies.js";

export default function WatchlistPage() {
  const { user } = useAuth();
  const userId = user?.id;
  // Danh sách theo dõi và danh mục doanh nghiệp, lấy từ backend
  const [watchlistItems, setWatchlistItems] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [catalogError, setCatalogError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const watchlistTickers = watchlistItems.map((item) => item.ticker);

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

  const load = () =>
    getWatchlist().then((data) => {
      setWatchlistItems(data.items.map(toView));
      setCompanies(data.companies.map(toView));
      setError("");
    });

  // Ghi lên backend rồi tải lại, để danh sách luôn khớp với DB
  const change = (action, ticker) =>
    action(ticker).then(load).catch((e) => {
      setError(e.message);
      throw e;
    });

  useEffect(() => {
    load()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    setCatalog(null);
    setCatalogError("");
    getCompanyCatalog()
      .then((data) => { if (!cancelled) setCatalog(data); })
      .catch((caught) => { if (!cancelled) setCatalogError(caught.message); });
    return () => { cancelled = true; };
  }, [userId]);

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
    change(unfollowCompany, ticker).then(() => {
      setLastRemovedTicker(ticker);
      setToastMessage(`Đã bỏ ${ticker} khỏi danh sách theo dõi`);
      setShowToast(true);
    }, () => {});
  };

  // Hoàn tác xóa (Undo)
  const handleUndo = () => {
    if (!lastRemovedTicker) return;
    if (!watchlistTickers.includes(lastRemovedTicker)) {
      change(followCompany, lastRemovedTicker).catch(() => {});
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
      change(followCompany, ticker).catch(() => {});
    }
    setIsAddModalOpen(false);
    setSelectedTickerToAdd("");
  };

  // Danh sách doanh nghiệp có thể thêm
  const visibleTickers = new Set(visibleCompanies(catalog || [], getRevealed(userId), watchlistTickers).map(({ id }) => id));
  const availableToAdd = companies.filter(
    (c) => visibleTickers.has(c.ticker) && !watchlistTickers.includes(c.ticker)
  );

  return <UserShell activeId="watchlist" className="fm-watchlist desk-watchlist">
    <DeskHeader title="Danh sách theo dõi" section="Cá nhân" description="Tổ chức những doanh nghiệp bạn muốn tìm hiểu."><button type="button" className="desk-primary" onClick={() => setIsAddModalOpen(true)}><AppIcon name="plus" />Thêm doanh nghiệp</button></DeskHeader>
    <main className="desk-watchlist-workbench">
      <aside className="desk-watchlist-sidebar"><div className="desk-watchlist-total"><span>Đang theo dõi</span><strong>{watchlistTickers.length}</strong><p>doanh nghiệp</p></div><h2>Lọc theo ngành</h2><button type="button" aria-pressed={sectorFilter === 'ALL'} onClick={() => setSectorFilter('ALL')}>Tất cả<span>{watchlistTickers.length}</span></button>{distinctSectors.map(item => <button type="button" key={item} aria-pressed={sectorFilter === item} onClick={() => setSectorFilter(item)}>{item}<span>{watchlistItems.filter(c => c.sector === item).length}</span></button>)}<p className="desk-filter-note">Danh sách theo dõi được lưu theo tài khoản của bạn.</p></aside>
      <section className="desk-watchlist-table"><div className="desk-explorer-toolbar"><label><AppIcon name="search" /><input type="search" aria-label="Tìm trong danh sách theo dõi" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tên hoặc mã doanh nghiệp" /></label><label className="desk-sort-label">Sắp xếp<select value={sortBy} onChange={event => setSortBy(event.target.value)}><option value="name">Tên doanh nghiệp</option><option value="sector">Ngành</option></select></label></div>
      {error && <p role="alert" className="desk-muted">{error}</p>}
      {loading ? <p aria-live="polite" className="desk-muted">Đang tải danh sách theo dõi…</p> : filteredItems.length ? <div className="desk-table-scroll"><table><thead><tr><th>Doanh nghiệp</th><th>Sàn / Ngành</th><th>Thao tác</th></tr></thead><tbody>{filteredItems.map(company => <tr key={company.ticker}><td><Link className="desk-row-ticker" to={PATHS.companyDetail(company.ticker)}>{company.ticker}</Link><p>{company.name}</p></td><td><span>{company.exchange}</span><small>{company.sector}</small></td><td><div className="desk-row-actions"><Link to={`/research?company=${company.ticker}&question=${encodeURIComponent('Phân tích '+company.ticker)}`}>Nghiên cứu <AppIcon name="arrow" /></Link><button type="button" onClick={() => handleRemove(company.ticker)} aria-label={`Bỏ theo dõi ${company.ticker}`}><AppIcon name="close" /></button></div></td></tr>)}</tbody></table></div> : <EmptyState title={watchlistTickers.length ? 'Không có doanh nghiệp khớp bộ lọc' : 'Danh sách của bạn đang trống'} description="Thêm doanh nghiệp hoặc đổi bộ lọc để bắt đầu theo dõi." action={<button className="desk-text-link" type="button" onClick={() => setIsAddModalOpen(true)}>Thêm doanh nghiệp →</button>} />}
      <div className="desk-table-footer">{filteredItems.length} / {watchlistTickers.length} doanh nghiệp</div></section>
    </main>
    {showToast && <div className="desk-toast" role="status"><AppIcon name="check" /><span>{toastMessage}</span><button type="button" onClick={handleUndo}>Hoàn tác</button></div>}
    <Modal open={isAddModalOpen} title="Thêm doanh nghiệp theo dõi" onClose={() => setIsAddModalOpen(false)} footer={<Button disabled={!selectedTickerToAdd} onClick={() => handleAddTicker(selectedTickerToAdd)}>Thêm vào danh sách</Button>}>
      {catalogError ? <p role="alert">{catalogError}</p> : loading || !catalog ? <p role="status">Đang tải danh mục…</p> : availableToAdd.length ? <label className="desk-add-company">Doanh nghiệp trong danh mục<select value={selectedTickerToAdd} onChange={event => setSelectedTickerToAdd(event.target.value)}><option value="">Chọn doanh nghiệp</option>{availableToAdd.map(c => <option key={c.ticker} value={c.ticker}>{c.ticker} · {c.name}</option>)}</select></label> : <p>Không còn doanh nghiệp có thể thêm.</p>}
    </Modal>
  </UserShell>;
}
