import { lazy, Suspense } from 'react';
import { ArrowDownRight, ArrowUpRight, ChevronRight, FileText, Link2, AlertCircle } from 'lucide-react';
import FinMindMark from '../../shared/ui/FinMindMark.jsx';
import Skeleton from '../../shared/ui/Skeleton.jsx';
import { formatFact, verification } from '../companies/financials.js';
import { LANDING_SYMBOL, summarizeMarket, selectFinancialEvidence } from './landingMarketData.js';
import { useLandingCompany, useLandingVisibility } from './useLandingMarket.js';
import LandingMarketStrip from './LandingMarketStrip.jsx';
import './companyPreviewHero.css';

const PriceHistory = lazy(() => import('../companies/PriceHistory.jsx'));
const companyPath = `/companies/${LANDING_SYMBOL}`;
const number = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const date = (value) => value ? new Date(value).toLocaleDateString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '';
const tabs = [['overview', 'Tổng quan'], ['finance', 'Tài chính'], ['news', 'Tin tức'], ['reports', 'Báo cáo & nguồn']];

export default function CompanyPreviewHero() {
  const { host, active } = useLandingVisibility();
  const { signedIn, checkingAuth, company, price, retry } = useLandingCompany(active);
  const quote = summarizeMarket(price.data);
  const evidence = selectFinancialEvidence(company.data);
  const Direction = quote?.change < 0 ? ArrowDownRight : ArrowUpRight;
  return <div ref={host} className="company-preview hero-enter delay-3" aria-label="Phân tích doanh nghiệp FinMind">
    <div className="company-preview-frame">
      <div className="preview-app-bar">
        <span className="preview-app-brand"><FinMindMark />FinMind <span>/ Doanh nghiệp</span></span>
        <a className="preview-open-company" href={companyPath}>Phân tích {LANDING_SYMBOL}<ArrowUpRight size={15} aria-hidden="true" /></a>
      </div>
      <div className="preview-company-heading">
        <div className="preview-company-identity">
          <span className="preview-ticker">{LANDING_SYMBOL}</span>
          <div><h2>{company.data?.name || LANDING_SYMBOL}</h2>
            {company.data && <p>{company.data.exchange}{company.data.exchange && <span>/</span>}{company.data.sector}</p>}
          </div>
        </div>
        {company.error && <button className="preview-retry" onClick={retry} title={company.error}>Tải lại doanh nghiệp</button>}
      </div>
      <nav className="preview-company-tabs" aria-label="Khám phá thông tin FPT">
        {tabs.map(([tab, label]) => <a key={tab} className={tab === 'overview' ? 'is-highlighted' : ''} href={`${companyPath}?tab=${tab}`}>{label}</a>)}
      </nav>
      <div className="preview-chart-panel">
        <div className="preview-chart-heading">
          <div>
            <p className="preview-chart-label">Giá & khối lượng <span>· {LANDING_SYMBOL}</span></p>
            <div className="preview-price-line">
              <strong>{quote ? number.format(quote.close) : '—'}</strong>
              {quote?.change != null && <span className={quote.change < 0 ? 'preview-price-down' : quote.change > 0 ? 'preview-price-up' : 'preview-price-flat'}><Direction size={16} aria-hidden="true" />{quote.change > 0 ? '+' : ''}{number.format(quote.change)} ({quote.percent > 0 ? '+' : ''}{number.format(quote.percent)}%)</span>}
            </div>
            {quote?.date && <p className="preview-price-date">{quote.status === 'closed' ? 'Đóng cửa' : 'Phiên'} {date(quote.date)} · {price.data.price_unit === 'thousand_vnd' ? 'Nghìn đồng' : price.data.price_unit === 'VND' ? 'Đồng' : 'Đơn vị nguồn'}
              {(price.data.live?.stale || price.error) && <span className="preview-feed-notice" title={price.error || price.data.live.reason}><AlertCircle size={11} aria-hidden="true" />Nguồn có thể trễ</span>}
            </p>}
          </div>
          <span className="preview-chart-period">Nến ngày · 1D</span>
        </div>
        <div className="preview-interactive-chart">
          {checkingAuth || (signedIn && !quote && price.loading !== false) ? <Skeleton rows={5} /> : !signedIn ?
            <div className="preview-signin"><p>Khám phá dữ liệu thị trường cùng FinMind</p><a href="/login">Đăng nhập để xem biểu đồ<ArrowUpRight size={15} aria-hidden="true" /></a></div> : quote ?
              <Suspense fallback={<Skeleton rows={5} />}><PriceHistory data={price.data} compact embedded /></Suspense> :
              <div className="preview-signin" role="status"><p>{price.error || 'Chưa có dữ liệu giá cho FPT'}</p><button className="preview-retry" onClick={retry}>Thử lại</button></div>}
        </div>
      </div>
      {signedIn && <div className="preview-proof-row">
        <div className="preview-proof-copy"><span><Link2 size={16} aria-hidden="true" />Dữ liệu đi cùng nguồn</span><a href={`${companyPath}?tab=finance${evidence ? `&period=${evidence.period.period}` : ''}`}>Tài chính doanh nghiệp<ChevronRight size={14} aria-hidden="true" /></a></div>
        <aside className="preview-citation" aria-label="Nguồn báo cáo tài chính FPT">
          <div className="preview-citation-top"><span><FileText size={16} aria-hidden="true" />Báo cáo tài chính</span>{evidence && <span>[1]</span>}</div>
          {company.loading && !company.data ? <Skeleton rows={2} /> : evidence ? <>
            <p>{evidence.period.label} · {LANDING_SYMBOL}<span className="preview-report-status">{verification(evidence.period.status).label}</span></p>
            <div className="preview-cited-metric"><span>Lợi nhuận sau thuế</span><strong>{evidence.fact ? formatFact(evidence.fact, 'money') : '—'}</strong></div>
            <a href={evidence.report.url} target="_blank" rel="noopener noreferrer">{evidence.report.title}<ArrowUpRight size={15} aria-hidden="true" /></a>
          </> : <p>{company.error || 'Chưa có báo cáo kèm nguồn'}</p>}
        </aside>
      </div>}
    </div>
    <LandingMarketStrip active={active} />
  </div>;
}
