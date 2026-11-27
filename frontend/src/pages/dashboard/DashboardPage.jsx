import { useEffect, useLayoutEffect, useState } from "react";
import { Link, useAuth } from "../../app/router.jsx";
import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { EmptyState, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getDashboard } from "./api.js";
import MarketOverview from "./MarketOverview.jsx";
import MarketNews from "./MarketNews.jsx";

export default function DashboardPage() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retry, setRetry] = useState(0);
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDashboard()
      .then((data) => {
        if (!cancelled) setDashboard(data);
      })
      .catch((caught) => {
        if (!cancelled) setError(caught.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [retry, user?.id]);
  return (
    <UserShell activeId="dashboard" className="fm-dashboard desk-dashboard">
      <DeskHeader
        title="Tổng quan thị trường"
        section="Tổng quan"
        description="Chỉ số, doanh nghiệp theo dõi và tin tức trong phiên."
      >
        <span className="date-tag">
          <AppIcon name="calendar" />
          {new Date().toLocaleDateString("vi-VN")}
        </span>
      </DeskHeader>
      <main className="desk-dashboard-content">
        <div className="approved-dashboard-grid">
          <div className="approved-dashboard-main">
            <MarketOverview
              watchlistCount={loading || error ? null : dashboard?.watchlist?.length ?? null}
            />
            <MarketNews />
          </div>
          <aside className="approved-dashboard-rail">
            <section className="desk-side-section">
              <div className="desk-panel-heading">
                <h2>Danh sách theo dõi</h2>
                <Link to="/watchlist" aria-label="Mở danh sách theo dõi">
                  <AppIcon name="arrow" />
                </Link>
              </div>
              {loading ? (
                <Skeleton rows={3} />
              ) : error ? (
                <ErrorState
                  message={error}
                  onRetry={() => setRetry((value) => value + 1)}
                />
              ) : dashboard?.watchlistError ? (
                <p role="alert" className="desk-muted">
                  {dashboard.watchlistError}
                </p>
              ) : dashboard?.watchlist?.length ? (
                dashboard.watchlist.map((company) => (
                  <Link
                    className="desk-compact-company"
                    key={company.ticker}
                    to={`/companies/${company.ticker}`}
                  >
                    <strong>{company.ticker}</strong>
                    <span>{company.name}</span>
                    <AppIcon name="chevron" />
                  </Link>
                ))
              ) : (
                <EmptyState
                  title="Chưa có doanh nghiệp theo dõi"
                  description="Thêm mã bạn quan tâm từ trang doanh nghiệp."
                />
              )}
            </section>
            <section className="approved-copilot-card">
              <p>FINMIND RESEARCH COPILOT</p>
              <h2>
                Đi sâu hơn
                <br />
                với một câu hỏi.
              </h2>
              <span>Đọc doanh nghiệp cùng báo cáo và bằng chứng có nguồn.</span>
              <Link to="/research">
                Bắt đầu nghiên cứu <AppIcon name="arrow" />
              </Link>
            </section>
          </aside>
        </div>
        <footer className="approved-footer">
          <span>
            <strong>FinMind</strong> · Không gian nghiên cứu doanh nghiệp
          </span>
          <span>Chỉ hỗ trợ nghiên cứu · Không phải khuyến nghị đầu tư</span>
        </footer>
      </main>
    </UserShell>
  );
}
