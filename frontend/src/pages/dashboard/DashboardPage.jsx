import { useEffect, useLayoutEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "../../app/router.jsx";
import { Card, EmptyState, ErrorState, Input, Sidebar, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { companyCatalog } from "../companies/mock.js";
import { getDashboard } from "./api.js";
import { popularTickers, researcherMock } from "./mock.js";
import { searchCompanies } from "../companies/companySearch.js";
import MarketOverview from "./MarketOverview.jsx";
import MarketNews from "./MarketNews.jsx";

const menuPaths = {
  dashboard: "/dashboard", companies: "/companies", copilot: "/research",
  watchlist: "/watchlist", graph: "/graph",
};

export default function DashboardPage() {
  const navigate = useNavigate();
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const [params] = useSearchParams();
  const [search, setSearch] = useState("");
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
  }, [fixture, retryCount]);

  const matches = search.trim()
    ? searchCompanies(companyCatalog, search)
    : [];

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={userMenu} activeId="dashboard" onSelect={(id) => navigate(menuPaths[id])}
        profile={researcherMock} onProfile={() => navigate("/profile")} onLogout={() => navigate("/login")} />
      <main className="min-w-0 flex-1">
        <header className="flex h-16 items-center justify-end border-b border-slate-200 bg-white px-4 sm:px-6 lg:px-8">
          <StatusBadge tone="neutral">Giá và tin từ dữ liệu nguồn · Hồ sơ minh họa</StatusBadge>
        </header>
        <div className="mx-auto w-full max-w-[1240px] space-y-7 px-4 py-6 sm:px-6 lg:px-8">
          <section aria-labelledby="hero-title" className="rounded-2xl border border-[#BCCEFB] bg-[#E8F0FF] p-5 shadow-sm md:p-6">
            <StatusBadge tone="info">Khám phá doanh nghiệp</StatusBadge>
            <h1 id="hero-title" className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Chào buổi sáng, {researcherMock.name}!</h1>
            <p className="mt-1.5 text-sm text-slate-600">Bạn muốn tìm hiểu doanh nghiệp nào hôm nay?</p>
            <div className="relative mt-5">
              <Input label="TÌM DOANH NGHIỆP" type="search" autoComplete="off"
                placeholder="Tìm theo tên hoặc mã doanh nghiệp..." value={search}
                onChange={(event) => setSearch(event.target.value)} />
              {search.trim() && (
                <div className="absolute z-10 mt-1.5 max-h-72 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
                  {matches.length ? matches.map((company) => (
                    <Link key={company.id} to={`/companies/${company.id}`}
                      className="flex w-full items-center justify-between gap-2 border-b border-slate-100 p-3 text-left text-xs hover:bg-blue-50">
                      <span><strong className="text-sm">{company.id}</strong> · {company.name}</span>
                      <span className="text-slate-500">{company.sector}</span>
                    </Link>
                  )) : <p className="p-3 text-center text-xs text-slate-500">Không tìm thấy doanh nghiệp trong phạm vi hỗ trợ</p>}
                </div>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-500">Ví dụ: FPT, Vietcombank, MBB...</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-700">Doanh nghiệp phổ biến:</span>
              {popularTickers.map((id) => (
                <Link key={id} to={`/companies/${id}`} className="inline-flex min-h-8 items-center rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:border-blue-600 hover:text-blue-700">{id}</Link>
              ))}
              <Link className="ml-auto text-xs font-medium text-blue-700 hover:underline" to="/companies">Tìm mã cổ phiếu →</Link>
            </div>
          </section>

          {loading ? <Skeleton rows={7} /> : error ? (
            <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
          ) : (
            <>
              <MarketOverview />
              <MarketNews />

              <section aria-labelledby="watchlist-title" className="space-y-3">
                <div><h2 id="watchlist-title" className="text-sm font-bold">Doanh nghiệp bạn đang theo dõi</h2><p className="mt-0.5 text-xs text-slate-500">Danh sách mẫu, chưa lưu theo tài khoản.</p></div>
                {dashboard.watchlist.length ? (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {dashboard.watchlist.map((company) => <Card key={company.id}>
                      <strong className="text-sm">{company.id}</strong><p className="mt-1 text-xs text-slate-600">{company.name}</p>
                      <Link className="mt-3 inline-block text-xs font-medium text-blue-600 hover:underline" to={`/companies/${company.id}`}>Xem doanh nghiệp →</Link>
                    </Card>)}
                  </div>
                ) : <EmptyState title="Bạn chưa theo dõi doanh nghiệp nào" description="Khám phá doanh nghiệp để bắt đầu." action={<Link className="text-xs font-semibold text-blue-600" to="/companies">Khám phá doanh nghiệp →</Link>} />}
              </section>

              <Card title="Nghiên cứu gần đây" description="Các phiên trò chuyện minh họa" action={<StatusBadge tone="neutral">Ví dụ minh họa</StatusBadge>}>
                {dashboard.recentResearch.length ? <div className="space-y-2.5">
                  {dashboard.recentResearch.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3">
                    <div><strong className="text-xs text-blue-700">{item.ticker}</strong><span className="ml-3 text-xs font-semibold">{item.title}</span><p className="mt-1 text-[11px] text-slate-500">{item.time}</p></div>
                    <Link className="text-xs font-medium text-blue-600 hover:underline" to={`/research?company=${item.ticker}&history=1`}>Xem lại →</Link>
                  </div>)}
                </div> : <EmptyState title="Chưa có nghiên cứu gần đây" />}
              </Card>
            </>
          )}
          <footer className="border-t border-slate-200 pb-8 pt-3 text-center text-xs text-slate-500">Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư</footer>
        </div>
      </main>
    </div>
  );
}
