import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Input, Select, Sidebar, Skeleton, Stat, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { companyCatalog } from "../companies/mock.js";
import { getDashboard } from "./api.js";
import { periods, popularTickers, researcherMock } from "./mock.js";

const menuPaths = {
  dashboard: "/dashboard", companies: "/companies", copilot: "/research",
  watchlist: "/watchlist", graph: "/graph",
};

function normalize(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
}

const formatNumber = (value) => new Intl.NumberFormat("vi-VN").format(value);

export default function DashboardPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialTicker = (params.get("company") || "").toUpperCase();
  const [ticker, setTicker] = useState(companyCatalog.some((item) => item.id === initialTicker) ? initialTicker : null);
  const [period, setPeriod] = useState(periods.some((item) => item.value === params.get("period")) ? params.get("period") : "FY2025");
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
    getDashboard(ticker, period, fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setDashboard(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, period, fixture, retryCount]);

  const matches = search.trim()
    ? companyCatalog.filter((item) => normalize(`${item.id} ${item.name} ${item.sector}`).includes(normalize(search)))
    : [];

  function selectCompany(id) {
    setTicker(id);
    setSearch("");
  }

  const selected = dashboard?.company;

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={userMenu} activeId="dashboard" onSelect={(id) => navigate(menuPaths[id])}
        profile={researcherMock} />
      <main className="min-w-0 flex-1">
        <header className="flex h-16 items-center justify-end border-b border-slate-200 bg-white px-4 sm:px-6 lg:px-8">
          <StatusBadge tone="neutral">Mock · EOD · Dữ liệu cuối ngày</StatusBadge>
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
                    <button type="button" key={company.id} onClick={() => selectCompany(company.id)}
                      className="flex w-full items-center justify-between gap-2 border-b border-slate-100 p-3 text-left text-xs hover:bg-blue-50">
                      <span><strong className="text-sm">{company.id}</strong> · {company.name}</span>
                      <span className="text-slate-500">{company.sector}</span>
                    </button>
                  )) : <p className="p-3 text-center text-xs text-slate-500">Không tìm thấy doanh nghiệp trong phạm vi hỗ trợ</p>}
                </div>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-500">Ví dụ: FPT, Vietcombank, MBB...</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-700">Doanh nghiệp phổ biến:</span>
              {popularTickers.map((id) => (
                <Button key={id} variant={ticker === id ? "primary" : "secondary"} className="!min-h-8 !px-3 !py-1 !text-xs" onClick={() => selectCompany(id)}>{id}</Button>
              ))}
              <Link className="ml-auto text-xs font-medium text-blue-700 hover:underline" to="/companies">Xem cả 10 doanh nghiệp →</Link>
            </div>
          </section>

          {loading ? <Skeleton rows={7} /> : error ? (
            <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
          ) : (
            <>
              {ticker && (
                <section aria-label="Thông tin doanh nghiệp đã chọn" className="space-y-3">
                  <Card title={selected ? `${selected.profile.ticker} · ${selected.profile.name}` : "Chưa có dữ liệu doanh nghiệp"}
                    description={selected ? `${selected.profile.sector} · Nguồn: ${selected.source}` : undefined}
                    action={<Select label="Kỳ dữ liệu" options={periods} value={period} onChange={(event) => setPeriod(event.target.value)} />}>
                    {selected ? (
                      <div className="space-y-3">
                        <p className="text-xs text-slate-500">Dữ liệu minh họa · Kỳ: {selected.period} · Ngày dữ liệu: {selected.dataDate} · Ngày cập nhật mock: {selected.updatedAt} · Đơn vị: {selected.unit}</p>
                        <div className="grid gap-3 md:grid-cols-3">
                          {selected.facts.map((fact) => <Stat key={fact.id} label={fact.label} value={formatNumber(fact.value)} note={`${selected.unit} · ${selected.period} · Mock`} />)}
                        </div>
                        <p className="text-xs text-slate-500">Số liệu giả lập để thử giao diện, không phải số liệu từ báo cáo tài chính.</p>
                      </div>
                    ) : <EmptyState title="Chưa có dữ liệu cho mã hoặc kỳ này" />}
                  </Card>
                </section>
              )}

              <section aria-labelledby="market-title" className="space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div><h2 id="market-title" className="text-sm font-bold">Tổng quan thị trường</h2><p className="mt-0.5 text-xs text-slate-500">Dữ liệu tham khảo cuối ngày (EOD)</p></div>
                  <StatusBadge tone="neutral">Dữ liệu minh họa</StatusBadge>
                </div>
                {dashboard.market.length ? (
                  <div className="grid gap-3.5 md:grid-cols-3">
                    {dashboard.market.map((index) => <Card key={index.id}>
                      <div className="flex items-center justify-between gap-2"><strong className="text-sm">{index.name}</strong><StatusBadge tone="neutral">Mock</StatusBadge></div>
                      <p className="my-2 text-2xl font-bold">{index.value ?? "—"}</p>
                      <p className="text-xs text-slate-500">% thay đổi: {index.change ?? "—"} · Thanh khoản: {index.liquidity ?? "—"}</p>
                      <p className="mt-2 border-t border-slate-100 pt-2 text-[11px] text-slate-400">{index.label} · {index.source}</p>
                    </Card>)}
                  </div>
                ) : <EmptyState title="Chưa có dữ liệu thị trường" description="Panel EOD hiện không có bản ghi mock." />}
                <Card title="Diễn biến VN-INDEX" description="EOD · Dữ liệu minh họa">
                  <EmptyState title="Chưa có chuỗi EOD để vẽ biểu đồ" description="Không hiển thị đường giá giả như dữ liệu thị trường thực." />
                </Card>
              </section>

              <section aria-labelledby="watchlist-title" className="space-y-3">
                <div><h2 id="watchlist-title" className="text-sm font-bold">Doanh nghiệp bạn đang theo dõi</h2><p className="mt-0.5 text-xs text-slate-500">Danh sách mẫu, chưa lưu theo tài khoản.</p></div>
                {dashboard.watchlist.length ? (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {dashboard.watchlist.map((company) => <Card key={company.id}>
                      <strong className="text-sm">{company.id}</strong><p className="mt-1 text-xs text-slate-600">{company.name}</p>
                      <Button variant="ghost" className="mt-3 !px-0 !text-xs" onClick={() => selectCompany(company.id)}>Xem trên Dashboard →</Button>
                    </Card>)}
                  </div>
                ) : <EmptyState title="Bạn chưa theo dõi doanh nghiệp nào" description="Khám phá doanh nghiệp để bắt đầu." action={<Link className="text-xs font-semibold text-blue-600" to="/companies">Khám phá doanh nghiệp →</Link>} />}
              </section>

              <Card title={ticker ? `Công bố minh họa · ${ticker}` : "Công bố gần đây"} description="Tin mẫu từ fixture, chưa kết nối nguồn công bố chính thức" action={<StatusBadge tone="neutral">Ví dụ minh họa</StatusBadge>}>
                {dashboard.announcements.length ? <div className="grid gap-3 md:grid-cols-3">
                  {dashboard.announcements.map((item) => <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50/50 p-3.5">
                    <div className="flex items-center justify-between gap-2"><strong className="text-xs text-blue-700">{item.ticker}</strong><span className="text-[10px] text-slate-500">{item.type}</span></div>
                    <h3 className="mt-2 text-xs font-semibold">{item.title}</h3>
                    <p className="mt-2 text-[11px] text-slate-500">Ngày/kỳ: {item.date} · Nguồn: {item.source}</p>
                  </article>)}
                </div> : <EmptyState title="Chưa có công bố minh họa" />}
              </Card>

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
