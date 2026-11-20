import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { useEffect, useLayoutEffect, useState } from "react";
import { Link, useAuth, useNavigate, useSearchParams } from "../../app/router.jsx";
import { EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { getDashboard } from "./api.js";
import { popularTickers } from "./mock.js";
import { searchCompanies } from "../companies/companySearch.js";
import { getRevealed, visibleCompanies } from "../companies/visibleCompanies.js";
import MarketOverview from "./MarketOverview.jsx";
import MarketNews from "./MarketNews.jsx";

export default function DashboardPage() {
  const { user } = useAuth();
  const userId = user?.id;
  const navigate = useNavigate();
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const [params] = useSearchParams();
  const [search, setSearch] = useState("");
  const [question, setQuestion] = useState("");
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";

  useEffect(() => {
    if (fixture === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDashboard(fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setDashboard(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fixture, retryCount, userId]);

  const allCompanies = dashboard?.companies || [];
  const catalog = visibleCompanies(allCompanies, getRevealed(userId), (dashboard?.watchlist || []).map(({ ticker }) => ticker));
  const shown = new Set(catalog.map(company => company.id));
  const matches = search.trim()
    ? searchCompanies(catalog, search).filter(company => shown.has(company.id))
    : [];

  return <UserShell activeId="dashboard" className="fm-dashboard desk-dashboard">
    <DeskHeader title="Bàn nghiên cứu" section="Tổng quan" description="Doanh nghiệp, thị trường và những nguồn bạn cần theo dõi.">
      <Link to="/research" className="desk-primary"><AppIcon name="copilot" />Mở Hỏi FinMind</Link>
    </DeskHeader>
    <main className="desk-dashboard-content">
      <div className="desk-dashboard-intro">
        <section className="desk-start-research">
          <div className="desk-section-number">01 / Nghiên cứu</div>
          <h2>Bạn đang tìm hiểu<br />doanh nghiệp nào?</h2>
          <p>Đặt câu hỏi về báo cáo, nhân sự hoặc tin tức. Kiểm chứng thông tin bằng nguồn đi kèm câu trả lời.</p>
          <form className="desk-ask-form" onSubmit={event => { event.preventDefault(); if (question.trim()) navigate(`/research?question=${encodeURIComponent(question.trim())}`); }}>
            <label htmlFor="desk-start-question">Câu hỏi nghiên cứu</label>
            <div><input id="desk-start-question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ví dụ: Giới thiệu tổng quan về VCB" maxLength={4000} /><button type="submit" disabled={!question.trim()} aria-label="Mở câu hỏi trong Hỏi FinMind"><AppIcon name="arrow" /></button></div>
          </form>
          <div className="desk-quick-links"><span>Bắt đầu từ</span>{popularTickers.map(id => <Link key={id} to={`/companies/${id}`}>{id}</Link>)}</div>
        </section>
        <aside className="desk-company-directory">
          <div className="desk-panel-heading"><h2>Danh mục doanh nghiệp</h2><span>{catalog.length} mã</span></div>
          <label className="desk-directory-search"><AppIcon name="search" /><input aria-label="Tìm doanh nghiệp" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tên hoặc mã chứng khoán" type="search" /></label>
          <div className="desk-directory-list">{(search.trim() ? matches : catalog).map(company => <Link to={`/companies/${company.id}`} key={company.id}><strong>{company.id}</strong><span>{company.name}</span><AppIcon name="chevron" /></Link>)}{search.trim() && !matches.length && <p className="desk-muted">Không có mã phù hợp trong danh mục.</p>}</div>
          <Link className="desk-text-link" to="/companies">Khám phá danh mục <AppIcon name="arrow" /></Link>
        </aside>
      </div>
      <div className="desk-dashboard-body">
        <div className="desk-market-column"><div className="desk-section-heading"><span className="desk-section-number">02 / Thị trường</span><p>Giá và tin từ nguồn dữ liệu · Không phải khuyến nghị đầu tư</p></div><MarketOverview /><MarketNews /></div>
        <aside className="desk-personal-column">
          {loading ? <Skeleton rows={5} /> : error ? <ErrorState message={error} onRetry={() => setRetryCount(count => count + 1)} /> : <>
            <section className="desk-side-section"><div className="desk-panel-heading"><h2>Theo dõi doanh nghiệp</h2><AppIcon name="watchlist" /></div><p className="desk-sample-label">Lưu theo tài khoản của bạn</p>
              {dashboard.watchlistError ? <p role="alert" className="desk-muted">{dashboard.watchlistError}</p> : dashboard.watchlist.length ? dashboard.watchlist.map(company => <Link className="desk-compact-company" key={company.ticker} to={`/companies/${company.ticker}`}><strong>{company.ticker}</strong><span>{company.name}</span><AppIcon name="chevron" /></Link>) : <EmptyState title="Chưa có doanh nghiệp" />}
              <Link to="/watchlist" className="desk-text-link">Mở danh sách theo dõi <AppIcon name="arrow" /></Link>
            </section>
            <section className="desk-side-section"><div className="desk-panel-heading"><h2>Nghiên cứu gần đây</h2><AppIcon name="history" /></div><p className="desk-sample-label">Các phiên minh họa</p>
              {dashboard.recentResearch.length ? dashboard.recentResearch.map(item => <Link className="desk-recent-item" key={item.id} to={`/research?company=${item.ticker}&history=1`}><span>{item.ticker} · {item.time}</span><p>{item.title}</p><AppIcon name="arrow" /></Link>) : <EmptyState title="Chưa có nghiên cứu" />}
            </section>
          </>}
          <section className="desk-research-note"><AppIcon name="shield" /><h3>Luôn đối chiếu nguồn</h3><p>Thông tin trong báo cáo phản ánh thời điểm của nguồn. Kiểm tra kỳ báo cáo và ngày công bố trước khi sử dụng.</p><Link to="/graph">Khám phá quan hệ có nguồn →</Link></section>
        </aside>
      </div>
    </main>
  </UserShell>;
}
