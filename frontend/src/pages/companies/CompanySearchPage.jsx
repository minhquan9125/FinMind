import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { useEffect, useState } from "react";
import { Link, useAuth, useSearchParams } from "../../app/router.jsx";
import { Drawer, EmptyState, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getCompanies } from "./api.js";
import { searchCompanies } from "./companySearch.js";
import { getWatchlist } from "../watchlist/api.js";
import { getRevealed, visibleCompanies } from "./visibleCompanies.js";

function CompanyPreview({ company }) {
  return <>
        <div className="desk-preview-kicker">Hồ sơ doanh nghiệp</div><span className="desk-large-ticker">{company.id}</span><h2>{company.name}</h2><dl><div><dt>Ngành</dt><dd>{company.sector}</dd></div><div><dt>Sàn giao dịch</dt><dd>{company.exchange || 'Chưa có dữ liệu'}</dd></div></dl>
        <Link className="desk-primary" to={`/companies/${company.id}`}>Mở hồ sơ <AppIcon name="arrow" /></Link><Link className="desk-secondary" to={`/research?company=${company.id}&question=${encodeURIComponent('Giới thiệu tổng quan về '+company.id)}`}><AppIcon name="copilot" />Hỏi về {company.id}</Link>
        <p className="desk-preview-note">Xem báo cáo, tin tức và các quan hệ có nguồn tại trang doanh nghiệp.</p>
  </>;
}

export default function CompanySearchPage() {
  const { user } = useAuth();
  const userId = user?.id;
  const [params] = useSearchParams();
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";
  const [companies, setCompanies] = useState([]);
  const [followed, setFollowed] = useState([]);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (fixture === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const scenario = fixture === "error" && retryCount > 0 ? "success" : fixture;
    const watchlist = scenario === "success" && userId
      ? getWatchlist().then(({ items }) => items.map(({ ticker }) => ticker)).catch(() => [])
      : [];
    Promise.all([getCompanies(scenario), watchlist])
      .then(([catalog, tickers]) => {
        if (cancelled) return;
        setCompanies(catalog);
        setFollowed(tickers);
      })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fixture, retryCount, userId]);

  // Search stays inside the codes with full data (plus opened/followed ones); no placeholder for other codes.
  const catalog = visibleCompanies(companies, getRevealed(userId), followed);
  const shown = new Set(catalog.map(company => company.id));
  const sectors = [...new Set(catalog.map(company => company.sector))];
  const visible = searchCompanies(catalog, search).filter(company => shown.has(company.id) && (!sector || company.sector === sector));
  const selected = visible.find(company => company.id === selectedId) || visible[0];
  return <UserShell activeId="companies" className="fm-company-catalog desk-catalog">
    <DeskHeader title="Khám phá doanh nghiệp" section="Danh mục" description="Chọn doanh nghiệp để xem hồ sơ và bắt đầu nghiên cứu."></DeskHeader>
    <main className="desk-explorer">
      <aside className="desk-explorer-filters"><h2>Phạm vi nghiên cứu</h2><p>Ngành doanh nghiệp</p>
        <button type="button" aria-pressed={!sector} onClick={() => setSector('')}>Tất cả ngành<span>{catalog.length}</span></button>
        {sectors.map(item => <button type="button" key={item} aria-pressed={sector === item} onClick={() => setSector(item)}>{item}<span>{catalog.filter(c => c.sector === item).length}</span></button>)}
        <div className="desk-filter-note"><AppIcon name="document" /><p>Danh mục lấy từ cơ sở dữ liệu. Giá, BCTC và tài liệu nguồn được ghi rõ ở trang chi tiết.</p></div>
      </aside>
      <section className="desk-explorer-results" aria-label="Doanh nghiệp trong danh mục">
        <div className="desk-explorer-toolbar"><label><AppIcon name="search" /><input type="search" placeholder="Tìm theo tên hoặc mã" aria-label="Tìm doanh nghiệp" value={search} onChange={event => setSearch(event.target.value)} /></label><span aria-live="polite">{loading ? 'Đang tải' : `${visible.length} doanh nghiệp`}</span></div>
        {loading ? <Skeleton rows={6} /> : error ? <ErrorState message={error} onRetry={() => setRetryCount(count => count + 1)} /> : !visible.length ? <EmptyState title="Không tìm thấy doanh nghiệp" description="Thử đổi từ khóa hoặc chọn lại ngành." /> : <div className="desk-company-rows">{visible.map(company => <button type="button" className="desk-company-row" key={company.id} aria-pressed={selected?.id === company.id} onClick={() => { setSelectedId(company.id); setPreviewOpen(window.matchMedia("(max-width: 1200px)").matches); }}><span className="desk-ticker-mark">{company.id}</span><span className="desk-company-row-name"><strong>{company.name}</strong><small>{company.sector}</small></span><AppIcon name="chevron" /></button>)}</div>}
      </section>
      <aside className="desk-company-preview" aria-label="Xem trước doanh nghiệp">{selected && !loading && !error ? <>
        <CompanyPreview company={selected} />
      </> : <div className="desk-preview-empty"><AppIcon name="companies" /><p>Chọn một doanh nghiệp để xem trước hồ sơ.</p></div>}</aside>
    </main>
    <Drawer open={previewOpen} title="Hồ sơ doanh nghiệp" onClose={() => setPreviewOpen(false)}>{selected && <div className="desk-company-preview desk-company-preview-drawer"><CompanyPreview company={selected} /></div>}</Drawer>
  </UserShell>;
}
