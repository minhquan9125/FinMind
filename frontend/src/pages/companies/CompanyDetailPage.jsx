import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Select, Sidebar, Skeleton, Stat, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { researcherMock } from "../dashboard/mock.js";
import { getCompanyDetail } from "./detailApi.js";
import { detailPeriods } from "./detailMock.js";

const menuPaths = {
  dashboard: "/dashboard", companies: "/companies", copilot: "/research",
  watchlist: "/watchlist", graph: "/graph",
};

const tabs = [
  { id: "overview", label: "Tổng quan" },
  { id: "finance", label: "Tài chính" },
  { id: "reports", label: "Báo cáo & nguồn" },
];

const formatNumber = (value) => new Intl.NumberFormat("vi-VN").format(value);

export default function CompanyDetailPage() {
  const navigate = useNavigate();
  const { ticker: routeTicker } = useParams();
  const [params] = useSearchParams();
  const ticker = (routeTicker || "").toUpperCase();
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [activeTab, setActiveTab] = useState("overview");
  const [period, setPeriod] = useState(detailPeriods.some((item) => item.value === params.get("period")) ? params.get("period") : "FY2025");
  const [followed, setFollowed] = useState(false);

  useEffect(() => {
    if (fixture === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCompany(null);
    getCompanyDetail(ticker, fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setCompany(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [ticker, fixture, retryCount]);

  const selectedFinancial = company?.financials.find((item) => item.period === period);
  const graphAvailable = ticker === "FPT" || ticker === "VCB";

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={userMenu} activeId="companies" onSelect={(id) => navigate(menuPaths[id])}
        profile={researcherMock} onProfile={() => navigate("/profile")} onLogout={() => navigate("/login")} />
      <main className="min-w-0 flex-1">
        <header className="flex min-h-16 flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3 sm:px-6 lg:px-8">
          <nav aria-label="Đường dẫn" className="flex items-center gap-2 text-xs text-slate-500">
            <Link to="/dashboard" className="hover:text-blue-600">Tổng quan</Link><span>/</span>
            <Link to="/companies" className="hover:text-blue-600">Doanh nghiệp</Link><span>/</span>
            <span className="font-semibold text-slate-900">{ticker}</span>
          </nav>
          <StatusBadge tone="neutral">Mock · EOD · Dữ liệu cuối ngày</StatusBadge>
        </header>

        <div className="mx-auto w-full max-w-[1240px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          {loading ? <Skeleton rows={8} /> : error ? (
            <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
          ) : !company ? (
            <EmptyState title="Không có dữ liệu doanh nghiệp" description={`Không tìm thấy mã ${ticker} trong 10 doanh nghiệp được hỗ trợ.`}
              action={<Link className="text-sm font-semibold text-blue-600" to="/companies">Xem danh mục doanh nghiệp →</Link>} />
          ) : (
            <>
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="text-3xl font-bold tracking-tight">{company.id}</h1>
                      <StatusBadge tone="info">Mã: {company.id}</StatusBadge>
                      <StatusBadge tone="neutral">Ngành: {company.sector}</StatusBadge>
                      {company.exchange && <StatusBadge tone="neutral">Sàn: {company.exchange}</StatusBadge>}
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{company.name}</p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <Button variant="secondary" onClick={() => setFollowed((value) => !value)}>
                      <span aria-hidden="true">{followed ? "★" : "☆"}</span>{followed ? "Đang theo dõi" : "Theo dõi"}
                    </Button>
                    <span className="text-[11px] text-slate-500">Trạng thái theo dõi chỉ lưu trên màn hình mock này</span>
                    {graphAvailable && <Link className="text-sm font-medium text-blue-600 hover:underline" to={`/graph?company=${ticker}`}>Khám phá quan hệ dữ liệu →</Link>}
                  </div>
                </div>
              </Card>

              <div role="tablist" aria-label="Thông tin doanh nghiệp" className="flex gap-1 overflow-x-auto border-b border-slate-200">
                {tabs.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === tab.id ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
                  {tab.label}
                </button>)}
              </div>

              <div className="grid gap-6 lg:grid-cols-12 lg:items-start">
                <div className="space-y-5 lg:col-span-8">
                  {activeTab === "overview" && <>
                    <Card title="Tổng quan doanh nghiệp" action={<StatusBadge tone="neutral">Hồ sơ minh họa</StatusBadge>}>
                      <dl className="grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2">
                        {[
                          ["Tên doanh nghiệp", company.name], ["Mã chứng khoán", company.id],
                          ["Ngành", company.sector], ["Sàn giao dịch", company.exchange || "Chưa có dữ liệu"],
                          ["Website", "Chưa có dữ liệu"], ["Người đứng đầu / lãnh đạo", "Chưa có dữ liệu"],
                        ].map(([label, value]) => <div key={label} className="border-b border-slate-100 pb-3">
                          <dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 font-medium">{value}</dd>
                        </div>)}
                      </dl>
                      <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">Mô tả doanh nghiệp sẽ hiển thị khi có nguồn công bố được phê duyệt.</p>
                    </Card>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Stat label="Ngành" value={company.sector} />
                      <Stat label="Sàn" value={company.exchange || "—"} />
                      <Stat label="Kỳ dữ liệu mẫu" value="FY2025" />
                    </div>
                    <Card title={`Giá & khối lượng cuối ngày · ${ticker}`} description="EOD · Chưa kết nối dữ liệu thị trường đã kiểm định">
                      <EmptyState title="Chưa có chuỗi giá EOD" description="Biểu đồ sẽ hiển thị khi có nguồn dữ liệu được nạp." />
                    </Card>
                    <Card title={`Tin tức gần đây · ${ticker}`} description="Tin từ các nguồn được phê duyệt">
                      <EmptyState title="Chưa có tin tức được kiểm định" description={`Hiện chưa có tin tức được kiểm định cho ${ticker}.`} />
                    </Card>
                  </>}

                  {activeTab === "finance" && <Card title="Tổng quan tài chính" description="Số liệu giả lập để thử giao diện, không phải số liệu báo cáo tài chính"
                    action={<Select label="Kỳ dữ liệu" options={detailPeriods} value={period} onChange={(event) => setPeriod(event.target.value)} />}>
                    {selectedFinancial ? <>
                      <p className="mb-4 text-xs text-slate-500">Kỳ: {selectedFinancial.period} · Ngày dữ liệu: {selectedFinancial.dataDate} · Đơn vị: {company.unit} · Nguồn: {company.source}</p>
                      <div className="grid gap-3 sm:grid-cols-3">
                        {selectedFinancial.facts.map((fact) => <Stat key={fact.id} label={fact.label} value={formatNumber(fact.value)} note={`${company.unit} · Mock`} />)}
                      </div>
                      <p className="mt-4 text-xs text-slate-500">Chưa có chuỗi dữ liệu được kiểm định để vẽ biểu đồ xu hướng.</p>
                    </> : <EmptyState title="Chưa có dữ liệu cho kỳ này" />}
                  </Card>}

                  {activeTab === "reports" && <Card title="Báo cáo & nguồn công bố" description="Bản ghi minh họa; chưa có tài liệu gốc được kiểm định">
                    <div className="space-y-3">
                      {company.reports.map((report) => <article key={report.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold">{report.title}</h3>
                        <p className="mt-2 text-xs text-slate-500">Kỳ: {report.period} · Ngày/kỳ dữ liệu: {report.date} · Đơn vị: {company.name}</p>
                        <p className="mt-1 text-xs text-slate-500">Nguồn: {report.source} · Liên kết tài liệu gốc: chưa có</p>
                      </article>)}
                    </div>
                  </Card>}
                </div>

                <aside className="lg:col-span-4">
                  <Card title={`Hỏi FinMind về ${ticker}`} description="Tiếp tục nghiên cứu doanh nghiệp trong Trợ lý nghiên cứu">
                    <div className="space-y-3 text-sm">
                      <Link className="block rounded-lg border border-slate-200 p-3 text-blue-600 hover:bg-blue-50" to={`/research?company=${ticker}&period=FY2025&question=${encodeURIComponent(`Doanh thu ${ticker} FY2025 thay đổi như thế nào?`)}`}>
                        Doanh thu {ticker} FY2025 thay đổi như thế nào? →
                      </Link>
                      <Link className="block rounded-lg border border-slate-200 p-3 text-blue-600 hover:bg-blue-50" to={`/research?company=${ticker}`}>Đặt câu hỏi khác →</Link>
                    </div>
                  </Card>
                </aside>
              </div>
            </>
          )}
          <footer className="border-t border-slate-200 pb-8 pt-3 text-center text-xs text-slate-500">Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư</footer>
        </div>
      </main>
    </div>
  );
}
