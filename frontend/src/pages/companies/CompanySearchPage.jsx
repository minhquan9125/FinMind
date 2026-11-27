import UserShell from "../../shared/ui/UserShell.jsx";
import DeskHeader from "../../shared/ui/DeskHeader.jsx";
import AppIcon from "../../shared/ui/AppIcon.jsx";
import { useEffect, useState } from "react";
import { Link, useAuth, useSearchParams } from "../../app/router.jsx";
import {
  Drawer,
  EmptyState,
  ErrorState,
  Skeleton,
} from "../../shared/ui/index.js";
import { getCompanies } from "./api.js";
import { searchCompanies } from "./companySearch.js";
import { getWatchlist } from "../watchlist/api.js";
import { getRevealed, visibleCompanies } from "./visibleCompanies.js";

function CompanyPreview({ company }) {
  return (
    <>
      <div className="desk-preview-kicker">Hồ sơ doanh nghiệp</div>
      <span className="desk-large-ticker">{company.id}</span>
      <h2>{company.name}</h2>
      <dl>
        <div>
          <dt>Ngành</dt>
          <dd>{company.sector}</dd>
        </div>
        <div>
          <dt>Sàn giao dịch</dt>
          <dd>{company.exchange || "Chưa có dữ liệu"}</dd>
        </div>
      </dl>
      <Link className="desk-primary" to={`/companies/${company.id}`}>
        Mở hồ sơ <AppIcon name="arrow" />
      </Link>
      <Link
        className="desk-secondary"
        to={`/research?company=${company.id}&question=${encodeURIComponent("Giới thiệu tổng quan về " + company.id)}`}
      >
        <AppIcon name="copilot" />
        Hỏi về {company.id}
      </Link>
      <p className="desk-preview-note">
        Xem báo cáo, tin tức và các quan hệ có nguồn tại trang doanh nghiệp.
      </p>
    </>
  );
}

export default function CompanySearchPage() {
  const { user } = useAuth();
  const userId = user?.id;
  const [params] = useSearchParams();
  const [companies, setCompanies] = useState([]);
  const [followed, setFollowed] = useState([]);
  const [search, setSearch] = useState(() => params.get("search") || "");
  useEffect(() => {
    setSearch(params.get("search") || "");
  }, [params]);
  const [sector, setSector] = useState("");
  const [view, setView] = useState("table");
  const [selectedId, setSelectedId] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const watchlist =
      userId
        ? getWatchlist()
            .then(({ items }) => items.map(({ ticker }) => ticker))
            .catch(() => [])
        : [];
    Promise.all([getCompanies(), watchlist])
      .then(([catalog, tickers]) => {
        if (cancelled) return;
        setCompanies(catalog);
        setFollowed(tickers);
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
  }, [retryCount, userId]);

  // Search stays inside the codes with full data (plus opened/followed ones); no placeholder for other codes.
  const catalog = visibleCompanies(companies, getRevealed(userId), followed);
  const shown = new Set(catalog.map((company) => company.id));
  const sectors = [...new Set(catalog.map((company) => company.sector))];
  const visible = searchCompanies(catalog, search).filter(
    (company) =>
      shown.has(company.id) && (!sector || company.sector === sector),
  );
  const selected =
    visible.find((company) => company.id === selectedId) || visible[0];
  return (
    <UserShell activeId="companies" className="fm-company-catalog desk-catalog">
      <DeskHeader
        title="Bắt đầu từ một doanh nghiệp."
        section="Danh mục"
        description="Tìm mã, khám phá dữ liệu và giữ lại những câu hỏi bạn muốn tìm hiểu."
      ></DeskHeader>
      <main className="approved-catalog">
        <section className="fm-card approved-catalog-surface">
          <div className="approved-catalog-toolbar">
            <label className="approved-catalog-search">
              <AppIcon name="search" />
              <input
                type="search"
                placeholder="Mã cổ phiếu hoặc tên doanh nghiệp…"
                aria-label="Tìm doanh nghiệp"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <select
              aria-label="Lọc theo ngành"
              value={sector}
              onChange={(event) => setSector(event.target.value)}
            >
              <option value="">Tất cả ngành</option>
              {sectors.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
            <div className="approved-view-toggle">
              <button
                type="button"
                aria-pressed={view === "table"}
                aria-label="Hiển thị bảng"
                onClick={() => setView("table")}
              >
                <AppIcon name="compare" />
              </button>
              <button
                type="button"
                aria-pressed={view === "cards"}
                aria-label="Hiển thị thẻ"
                onClick={() => setView("cards")}
              >
                <AppIcon name="dashboard" />
              </button>
            </div>
          </div>
          <p className="approved-catalog-count" aria-live="polite">
            {loading ? "Đang tải danh mục…" : `${visible.length} doanh nghiệp`}{" "}
            · Giá, báo cáo tài chính và nguồn hiển thị ở hồ sơ từng mã.
          </p>
          {loading ? (
            <Skeleton rows={6} />
          ) : error ? (
            <ErrorState
              message={error}
              onRetry={() => setRetryCount((count) => count + 1)}
            />
          ) : !visible.length ? (
            <EmptyState
              title="Không tìm thấy doanh nghiệp"
              description="Thử đổi từ khóa hoặc chọn lại ngành."
            />
          ) : view === "table" ? (
            <div className="approved-catalog-table-scroll">
              <table className="approved-catalog-table">
                <thead>
                  <tr>
                    <th>Doanh nghiệp</th>
                    <th>Ngành</th>
                    <th>Sàn</th>
                    <th>Kỳ báo cáo gần nhất</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((company) => (
                    <tr key={company.id}>
                      <td>
                        <Link
                          className="approved-catalog-company"
                          to={`/companies/${company.id}`}
                        >
                          <span>{company.id}</span>
                          <div>
                            <strong>{company.id}</strong>
                            <small>{company.name}</small>
                          </div>
                        </Link>
                      </td>
                      <td>{company.sector}</td>
                      <td>{company.exchange || "—"}</td>
                      <td>{company.latestPeriod || "Chưa có dữ liệu"}</td>
                      <td>
                        <button
                          type="button"
                          className="approved-catalog-preview"
                          onClick={() => {
                            setSelectedId(company.id);
                            setPreviewOpen(true);
                          }}
                        >
                          Xem nhanh <AppIcon name="arrow" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="approved-catalog-cards">
              {visible.map((company) => (
                <article key={company.id}>
                  <Link to={`/companies/${company.id}`}>
                    <span className="approved-company-monogram">
                      {company.id}
                    </span>
                    <h2>{company.name}</h2>
                  </Link>
                  <p>
                    {company.sector} · {company.exchange || "Chưa có sàn"}
                  </p>
                  <div>
                    <Link to={`/companies/${company.id}`}>
                      Mở hồ sơ <AppIcon name="arrow" />
                    </Link>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedId(company.id);
                        setPreviewOpen(true);
                      }}
                    >
                      Xem nhanh
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
        <footer className="approved-footer">
          <span>FinMind · Nghiên cứu doanh nghiệp có nguồn</span>
          <span>Chỉ hỗ trợ nghiên cứu · Không phải khuyến nghị đầu tư</span>
        </footer>
      </main>
      <Drawer
        open={previewOpen}
        title="Hồ sơ doanh nghiệp"
        onClose={() => setPreviewOpen(false)}
      >
        {selected && (
          <div className="desk-company-preview desk-company-preview-drawer">
            <CompanyPreview company={selected} />
          </div>
        )}
      </Drawer>
    </UserShell>
  );
}
