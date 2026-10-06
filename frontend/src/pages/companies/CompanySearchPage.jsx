import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "../../app/router.jsx";
import { Card, EmptyState, ErrorState, Input, Sidebar, Skeleton, StatusBadge } from "../../shared/ui/index.js";
import { userMenu } from "../../mocks/componentMock.js";
import { getCompanies } from "./api.js";

const menuPaths = {
  dashboard: "/dashboard",
  companies: "/companies",
  copilot: "/research",
  watchlist: "/watchlist",
  graph: "/graph",
};

function normalize(value) {
  return value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").trim();
}

export default function CompanySearchPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const fixture = ["empty", "error", "loading"].includes(params.get("fixture")) ? params.get("fixture") : "success";
  const [companies, setCompanies] = useState([]);
  const [search, setSearch] = useState("");
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
    getCompanies(fixture === "error" && retryCount > 0 ? "success" : fixture)
      .then((data) => { if (!cancelled) setCompanies(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fixture, retryCount]);

  const visible = companies.filter((company) => normalize(`${company.id} ${company.name}`).includes(normalize(search)));
  function renderGroup(sector) {
    const group = visible.filter((company) => company.sector === sector);
    if (group.length === 0) return null;
    return (
      <Card key={sector} className="mb-4">
        <div className="mb-3 flex items-center justify-between border-b border-slate-100 pb-2">
          <h3 className="flex items-center gap-2 text-xs font-bold tracking-wider text-slate-800">
            <span className="h-2 w-2 rounded-full bg-blue-600" />{sector.toUpperCase()}
          </h3>
          <span className="text-[11px] font-medium text-slate-500">{search ? `${group.length} kết quả` : `${group.length} doanh nghiệp niêm yết`}</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
          {group.map((company) => (
            <article key={company.id} className="flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-3.5 transition-colors hover:border-blue-300">
              <div>
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <strong className="text-sm text-slate-900">{company.id}</strong>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">{company.sector}</span>
                </div>
                <p className="mb-3 truncate text-xs text-slate-600" title={company.name}>{company.name}</p>
              </div>
              <Link to={`/companies/${company.id}`} className="inline-flex min-h-8 w-full items-center justify-center rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100">
                Xem doanh nghiệp
              </Link>
            </article>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={userMenu} activeId="companies" onSelect={(id) => navigate(menuPaths[id])}
        profile={{ initials: "NA", name: "Nguyễn Văn A", role: "Nhà nghiên cứu" }}
        onProfile={() => navigate("/profile")} onLogout={() => navigate("/login")} />
      <main className="min-w-0 flex-1">
        <header className="flex h-16 items-center justify-end border-b border-slate-200 bg-white px-4 sm:px-6 lg:px-8">
          <StatusBadge tone="neutral">Dữ liệu minh họa · Mock</StatusBadge>
        </header>
        <div className="mx-auto w-full max-w-[1240px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold tracking-tight">Doanh nghiệp</h1>
          <Card>
            <Input type="search" label="Tìm doanh nghiệp" placeholder="Nhập tên hoặc mã doanh nghiệp..." autoComplete="off"
              value={search} onChange={(event) => setSearch(event.target.value)} />
            <p aria-live="polite" className="mt-2 text-xs text-slate-500">
              {loading ? "Đang tải danh sách..." : search ? `${visible.length} kết quả phù hợp` : `${companies.length} doanh nghiệp trong phạm vi nghiên cứu`}
            </p>
          </Card>

          {loading ? <Skeleton rows={5} /> : error ? (
            <ErrorState message={error} onRetry={() => setRetryCount((count) => count + 1)} />
          ) : companies.length === 0 ? (
            <EmptyState title="Chưa có doanh nghiệp" description="Danh sách doanh nghiệp minh họa hiện đang rỗng." />
          ) : (
            <>
              <section aria-labelledby="supported-title">
                <h2 id="supported-title" className="text-sm font-bold">Doanh nghiệp được hỗ trợ</h2>
                <p className="mb-4 mt-0.5 text-xs text-slate-500">Khám phá các doanh nghiệp hiện nằm trong phạm vi nghiên cứu của FinMind.</p>
                {visible.length === 0 ? <EmptyState title="Không tìm thấy doanh nghiệp phù hợp" description="Thử nhập mã hoặc tên khác trong phạm vi nghiên cứu của FinMind." /> : ["Ngân hàng", "Công nghệ"].map(renderGroup)}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
