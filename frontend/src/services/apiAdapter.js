/**
 * FinMind API Adapter Layer
 * ─────────────────────────────────────────────────────────────────────────────
 * Lớp trung gian giữa Mock API và các React Component:
 *   1. Gọi các hàm mockApi tương ứng.
 *   2. Chuẩn hóa & mapping tên trường khớp với state của từng component.
 *   3. Bổ sung fallback values khi dữ liệu null / undefined.
 *   4. Bọc lỗi mạng thành cấu trúc thống nhất để UI xử lý.
 *
 * Tất cả hàm export đều trả về:
 *   { success: true,  data: <adapted>,  error: null       }  – khi thành công
 *   { success: false, data: null,        error: <adapted> }  – khi có lỗi
 */

import {
  fetchCompaniesMock,
  fetchWatchlistDirectoryMock,
  fetchDashboardMock,
  fetchResearchDataMock,
  fetchAdminOverviewMock,
  fetchAdminTracesMock,
  fetchAdminSourcesMock,
  fetchAdminCorpusMock,
  fetchAdminAuditMock,
  fetchAdminConfigMock,
  fetchGraphMock,
  fetchProfileMock,
  fetchResearchEvaluationMock,
  fetchWatchlistTickersMock,
  updateWatchlistTickersMock,
  fetchAuthLoginMock,
  fetchAuthRegisterMock,
  fetchAuthLogoutMock,
  fetchDocumentsMock,
} from "./mockApi";

// ─── Tiện ích chung ────────────────────────────────────────────────────────────

/** Chuẩn hóa lỗi thô từ mockEndpoint về dạng thống nhất cho UI */
const adaptError = (err) => ({
  status:    err?.status  ?? 500,
  traceId:   err?.trace_id ?? "TRC-ERR-" + Date.now().toString(36).toUpperCase(),
  message:   err?.message ?? "Đã xảy ra lỗi không xác định. Vui lòng thử lại.",
  timestamp: err?.timestamp ?? new Date().toISOString(),
});

/** Bọc toàn bộ vòng đời gọi API: fetch → adapt thành công → adapt lỗi */
async function callApi(fetchFn, adaptFn) {
  try {
    const raw = await fetchFn();
    return {
      success: true,
      data: adaptFn(raw),
      error: null,
      traceId: raw.trace_id,
      citationId: raw.citation_id,
    };
  } catch (err) {
    return {
      success: false,
      data: null,
      error: adaptError(err),
    };
  }
}

const fallback = (value, def) => (value !== null && value !== undefined ? value : def);

// ─── 1. COMPANIES ──────────────────────────────────────────────────────────────
// Dùng bởi: CompanySearchPage, DashboardPage (companyCatalog)

const adaptCompanyItem = (raw = {}) => ({
  id:        fallback(raw.id,      "UNKNOWN"),
  name:      fallback(raw.name,    "Doanh nghiệp chưa đặt tên"),
  sector:    fallback(raw.sector,  "Chưa phân loại"),
  status:    fallback(raw.status,  "Chưa có dữ liệu"),
  tone:      fallback(raw.tone,    "neutral"),
  period:    fallback(raw.period,  "FY2025"),
  source:    fallback(raw.source,  "Fixture FinMind"),
  unit:      fallback(raw.unit,    "tỷ VNĐ"),
  updatedAt: fallback(raw.updatedAt, "—"),
  // Trường dùng cho companyCatalog (CompanySearchPage, DashboardPage)
  profile:   { ticker: raw.id, name: raw.name, sector: raw.sector },
});

export const getCompanies = (options = {}) =>
  callApi(
    () => fetchCompaniesMock(options),
    (raw) => ({
      items: (raw.payload ?? []).map(adaptCompanyItem),
      total: (raw.payload ?? []).length,
    })
  );

// ─── 2. WATCHLIST ──────────────────────────────────────────────────────────────
// Dùng bởi: WatchlistPage
// State cần: ticker, name, sector, exchange, latestPeriod, sourceStatus

const adaptWatchlistDirectoryItem = (raw = {}) => ({
  ticker:       fallback(raw.ticker,       "—"),
  name:         fallback(raw.name,         "Doanh nghiệp chưa xác định"),
  sector:       fallback(raw.sector,       "Chưa phân loại"),
  exchange:     fallback(raw.exchange,     "Chưa có dữ liệu"),
  latestPeriod: fallback(raw.latestPeriod, "FY2025"),
  sourceStatus: fallback(raw.sourceStatus, "Chưa có nguồn công bố"),
});

export const getWatchlistDirectory = (options = {}) =>
  callApi(
    () => fetchWatchlistDirectoryMock(options),
    (raw) => {
      const dir = raw.payload ?? {};
      // Trả về object { [TICKER]: adaptedItem } để WatchlistPage tra cứu nhanh
      const adapted = {};
      Object.entries(dir).forEach(([ticker, item]) => {
        adapted[ticker] = adaptWatchlistDirectoryItem(item);
      });
      return { directory: adapted, tickers: Object.keys(adapted) };
    }
  );

// ─── 3. DASHBOARD ─────────────────────────────────────────────────────────────
// Dùng bởi: DashboardPage
// State cần: company (profile, facts, period, dataDate, updatedAt, source, unit, news)
//            market, watchlist, announcements, recentResearch, periods, popularTickers, researcher

const adaptFact = (raw = {}) => ({
  id:    fallback(raw.id,    "unknown"),
  label: fallback(raw.label, "—"),
  value: fallback(raw.value, 0),
});

const adaptCompanySnapshot = (raw) => {
  if (!raw) return null;
  return {
    profile:   raw.profile ?? { ticker: "—", name: "—", sector: "—" },
    period:    fallback(raw.period,    "FY2025"),
    dataDate:  fallback(raw.dataDate,  "—"),
    updatedAt: fallback(raw.updatedAt, "—"),
    source:    fallback(raw.source,    "Fixture FinMind"),
    unit:      fallback(raw.unit,      "tỷ VNĐ"),
    facts:     (raw.facts ?? []).map(adaptFact),
    news:      raw.news ?? [],
  };
};

const adaptMarketIndex = (raw = {}) => ({
  id:        fallback(raw.id,        raw.name ?? "—"),
  name:      fallback(raw.name,      "—"),
  value:     raw.value  ?? null,
  change:    raw.change ?? null,
  liquidity: raw.liquidity ?? null,
  source:    fallback(raw.source,    "Chưa kết nối nguồn thị trường"),
  label:     fallback(raw.label,     "EOD · Dữ liệu minh họa"),
});

const adaptAnnouncement = (raw = {}) => ({
  id:     fallback(raw.id,     "ann-" + Math.random().toString(36).substring(2, 6)),
  ticker: fallback(raw.ticker, "—"),
  title:  fallback(raw.title,  "Công bố chưa có tiêu đề"),
  type:   fallback(raw.type,   "Báo cáo minh họa"),
  date:   fallback(raw.date,   "—"),
  source: fallback(raw.source, "Fixture FinMind"),
});

const adaptRecentResearch = (raw = {}) => ({
  id:     fallback(raw.id,     "res-" + Math.random().toString(36).substring(2, 6)),
  ticker: fallback(raw.ticker, "—"),
  title:  fallback(raw.title,  "Phiên nghiên cứu chưa có tiêu đề"),
  time:   fallback(raw.time,   "—"),
});

export const getDashboard = (ticker, period = "FY2025", options = {}) =>
  callApi(
    () => fetchDashboardMock(ticker, period, options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        company:        adaptCompanySnapshot(p.company),
        market:         (p.market         ?? []).map(adaptMarketIndex),
        watchlist:      (p.watchlist      ?? []).map(adaptCompanyItem),
        announcements:  (p.announcements  ?? []).map(adaptAnnouncement),
        recentResearch: (p.recentResearch ?? []).map(adaptRecentResearch),
        periods:        p.periods        ?? [],
        popularTickers: p.popularTickers ?? ["FPT","VCB","MBB","TCB","CMG"],
        researcher:     p.researcher     ?? { initials:"NA", name:"Nguyễn Văn A", role:"Nhà nghiên cứu" },
      };
    }
  );

// ─── 4. RESEARCH ──────────────────────────────────────────────────────────────
// Dùng bởi: ResearchPage
// State cần: companyMeta (fullName, revenueFY2025, sources…),
//            financialFacts (revenue, growth, …, evidenceStatus),
//            history, periods, comparisonMetrics

const adaptSource = (raw = {}) => ({
  id:         fallback(raw.id,         "src-auto"),
  title:      fallback(raw.title,      "Nguồn không có tiêu đề"),
  publisher:  fallback(raw.publisher,  "Chưa xác định"),
  type:       fallback(raw.type,       "Tài liệu"),
  status:     fallback(raw.status,     "Chưa đối soát"),
  locator:    fallback(raw.locator,    "—"),
  fact:       fallback(raw.fact,       "Chưa có trích dẫn."),
  provenance: fallback(raw.provenance, "Chưa có thông tin nguồn gốc."),
  location:   fallback(raw.location,   "—"),
  url:        fallback(raw.url,        "#"),
});

const adaptCompanyMeta = (raw) => {
  if (!raw) return null;
  return {
    fullName:         fallback(raw.fullName,         "Doanh nghiệp chưa xác định"),
    corporateName:    fallback(raw.corporateName,    "—"),
    industry:         fallback(raw.industry,         "—"),
    exchange:         fallback(raw.exchange,         "—"),
    revenueFY2025:    fallback(raw.revenueFY2025,    "—"),
    growthFY2025:     fallback(raw.growthFY2025,     "—"),
    grossMarginFY2025:fallback(raw.grossMarginFY2025,"—"),
    netProfitFY2025:  fallback(raw.netProfitFY2025,  "—"),
    sources:          (raw.sources ?? []).map(adaptSource),
  };
};

const adaptFinancialFacts = (raw) => {
  if (!raw) return null;
  return {
    revenue:        fallback(raw.revenue,        "—"),
    growth:         fallback(raw.growth,         "—"),
    grossMargin:    fallback(raw.grossMargin,     "—"),
    netProfit:      fallback(raw.netProfit,       "—"),
    totalAssets:    fallback(raw.totalAssets,     "—"),
    equity:         fallback(raw.equity,          "—"),
    liability:      fallback(raw.liability,       "—"),
    evidenceStatus: fallback(raw.evidenceStatus,  "insufficient"),
    evidenceLabel:  fallback(raw.evidenceLabel,   "Chưa có bằng chứng"),
  };
};

const adaptHistoryItem = (raw = {}) => ({
  id:          fallback(raw.id,          "h-auto"),
  company:     fallback(raw.company,     "—"),
  companyName: fallback(raw.companyName, "—"),
  period:      fallback(raw.period,      "FY2025"),
  question:    fallback(raw.question,    "Câu hỏi chưa có nội dung"),
  time:        fallback(raw.time,        "—"),
  status:      fallback(raw.status,      "insufficient"),
  statusLabel: fallback(raw.statusLabel, "—"),
  isPinned:    raw.isPinned ?? false,
});

export const getResearchData = (ticker = "FPT", period = "FY2025", options = {}) =>
  callApi(
    () => fetchResearchDataMock(ticker, period, options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        companyMeta:       adaptCompanyMeta(p.companyMeta),
        financialFacts:    adaptFinancialFacts(p.financialFacts),
        history:           (p.history           ?? []).map(adaptHistoryItem),
        periods:           p.periods            ?? [],
        comparisonMetrics: p.comparisonMetrics  ?? [],
        availableTickers:  p.availableTickers   ?? [],
      };
    }
  );

// ─── 5. ADMIN OVERVIEW ────────────────────────────────────────────────────────
// Dùng bởi: AdminOverviewPage
// State cần: kpis, budget, recentTraces, alerts, activities, activityDate, services

const adaptKpi = (raw = {}) => ({
  id:    fallback(raw.id,    "kpi-auto"),
  label: fallback(raw.label, "—"),
  value: fallback(raw.value, "—"),
});

const adaptService = (raw = {}) => ({
  id:   fallback(raw.id,   "svc-auto"),
  name: fallback(raw.name, "—"),
  desc: fallback(raw.desc, "—"),
  ok:   raw.ok ?? false,
});

export const getAdminOverview = (options = {}) =>
  callApi(
    () => fetchAdminOverviewMock(options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        kpis:         (p.kpis         ?? []).map(adaptKpi),
        budget:       p.budget        ?? { used: 0, limit: 100, warnAt: 80 },
        recentTraces: p.recentTraces  ?? [],
        alerts:       p.alerts        ?? [],
        activities:   p.activities    ?? [],
        activityDate: fallback(p.activityDate, "—"),
        services:     (p.services ?? []).map(adaptService),
      };
    }
  );

// ─── 6. ADMIN TRACES ──────────────────────────────────────────────────────────
// Dùng bởi: AdminTracesPage
// State cần: traces[], stepNames[], activeConfig, activeCorpus

const adaptTrace = (raw = {}) => ({
  id:    fallback(raw.id,  "TRC-AUTO"),
  co:    fallback(raw.co,  "—"),
  q:     fallback(raw.q,   "Câu hỏi chưa có nội dung"),
  s:     fallback(raw.s,   "—"),
  e:     raw.e ?? null,
  st:    fallback(raw.st,  "—"),
  cat:   fallback(raw.cat, "none"),
  steps: raw.steps ?? [],
  vec:   raw.vec   ?? null,
  gr:    raw.gr    ?? null,
  gate:  raw.gate  ?? { run: false },
  ver:   raw.ver   ?? { run: false },
  tok:   raw.tok   ?? { in: null, out: null, limit: 8000 },
});

export const getAdminTraces = (options = {}) =>
  callApi(
    () => fetchAdminTracesMock(options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        traces:       (p.traces ?? []).map(adaptTrace),
        stepNames:    p.stepNames    ?? [],
        activeConfig: fallback(p.activeConfig, "—"),
        activeCorpus: fallback(p.activeCorpus, "—"),
      };
    }
  );

// ─── 7. ADMIN SOURCES ─────────────────────────────────────────────────────────
// Dùng bởi: AdminSourcesPage
// State cần: id, name, type, access, status, version, lastTest, testOk,
//            willPassTest, failReason, schedule, usage, scope, fallback,
//            owner, url, terms, cred, history[]

const adaptSource_admin = (raw = {}) => ({
  id:           fallback(raw.id,           "src-auto"),
  name:         fallback(raw.name,         "Nguồn chưa đặt tên"),
  type:         fallback(raw.type,         "Chưa phân loại"),
  access:       fallback(raw.access,       "—"),
  status:       fallback(raw.status,       "Chưa kiểm tra"),
  version:      fallback(raw.version,      "v1.0"),
  lastTest:     fallback(raw.lastTest,     "none"),
  testOk:       raw.testOk       ?? false,
  willPassTest: raw.willPassTest ?? false,
  failReason:   raw.failReason   ?? null,
  schedule:     fallback(raw.schedule,     "Thủ công"),
  usage:        fallback(raw.usage,        "—"),
  scope:        fallback(raw.scope,        "—"),
  fallback:     fallback(raw.fallback,     "—"),
  owner:        fallback(raw.owner,        "—"),
  url:          fallback(raw.url,          ""),
  terms:        fallback(raw.terms,        ""),
  cred:         fallback(raw.cred,         "Chưa cấu hình"),
  history:      raw.history ?? [],
});

export const getAdminSources = (options = {}) =>
  callApi(
    () => fetchAdminSourcesMock(options),
    (raw) => ({
      items: (raw.payload ?? []).map(adaptSource_admin),
      total: (raw.payload ?? []).length,
    })
  );

// ─── 8. ADMIN CORPUS ──────────────────────────────────────────────────────────
// Dùng bởi: AdminCorpusPage
// State cần: corpora[] (v, status, created, manifest, docs, …),
//            documents[] (id, name, co, type, period, source, ver, hash, validation, issue?)

const adaptCorpusVersion = (raw = {}) => ({
  v:         fallback(raw.v,         "v?.?"),
  status:    fallback(raw.status,    "Không xác định"),
  created:   fallback(raw.created,   "—"),
  manifest:  raw.manifest ?? false,
  docs:      raw.docs     ?? [],
  companies: fallback(raw.companies, "—"),
  period:    fallback(raw.period,    "—"),
  by:        fallback(raw.by,        "—"),
  config:    fallback(raw.config,    "—"),
});

const adaptCorpusDocument = (raw = {}) => ({
  id:         fallback(raw.id,         "doc-auto"),
  name:       fallback(raw.name,       "Tài liệu chưa đặt tên"),
  co:         fallback(raw.co,         "—"),
  type:       fallback(raw.type,       "—"),
  period:     fallback(raw.period,     "—"),
  source:     fallback(raw.source,     "—"),
  srcVer:     fallback(raw.srcVer,     "—"),
  ver:        fallback(raw.ver,        "v1"),
  hash:       fallback(raw.hash,       "—"),
  pub:        fallback(raw.pub,        "—"),
  ingest:     fallback(raw.ingest,     "—"),
  validation: fallback(raw.validation, "Chưa xác thực"),
  issue:      raw.issue      ?? null,
  family:     raw.family     ?? null,
  supersedes:   raw.supersedes   ?? null,
  supersededBy: raw.supersededBy ?? null,
});

export const getAdminCorpus = (options = {}) =>
  callApi(
    () => fetchAdminCorpusMock(options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        corpora:         (p.corpora   ?? []).map(adaptCorpusVersion),
        documents:       (p.documents ?? []).map(adaptCorpusDocument),
        candidateDocIds: p.candidateDocIds ?? [],
      };
    }
  );

// ─── 9. ADMIN AUDIT ───────────────────────────────────────────────────────────
// Dùng bởi: AdminAuditPage
// State cần: id, time, actor, role, action, type, rtype, resource, result,
//            config, corpus, trace, source, reason, sanitized, retentionExpired

const adaptAuditEvent = (raw = {}) => ({
  id:               fallback(raw.id,      "AUD-AUTO"),
  time:             fallback(raw.time,    "—"),
  actor:            fallback(raw.actor,   "—"),
  role:             fallback(raw.role,    "—"),
  action:           fallback(raw.action,  "—"),
  type:             fallback(raw.type,    "—"),
  rtype:            fallback(raw.rtype,   "—"),
  resource:         fallback(raw.resource,"—"),
  result:           fallback(raw.result,  "—"),
  config:           raw.config  ?? null,
  corpus:           raw.corpus  ?? null,
  trace:            raw.trace   ?? null,
  source:           raw.source  ?? null,
  reason:           raw.reason  ?? null,
  sanitized:        raw.sanitized ?? null,
  retentionExpired: raw.retentionExpired ?? false,
});

export const getAdminAudit = (options = {}) =>
  callApi(
    () => fetchAdminAuditMock(options),
    (raw) => ({
      events: (raw.payload ?? []).map(adaptAuditEvent),
      total:  (raw.payload ?? []).length,
    })
  );

// ─── 10. ADMIN CONFIGURATION ──────────────────────────────────────────────────
// Dùng bởi: AdminConfigurationPage
// State cần: versions[] (v, kind, status, created, by, activated, changes, params),
//            budget (limit, used, avgTokens)

const adaptConfigVersion = (raw = {}) => ({
  v:            fallback(raw.v,         "CFG v?.?"),
  kind:         fallback(raw.kind,      "PRODUCTION"),
  status:       fallback(raw.status,    "—"),
  created:      fallback(raw.created,   "—"),
  by:           fallback(raw.by,        "—"),
  activated:    fallback(raw.activated, "—"),
  activatedBy:  raw.activatedBy ?? null,
  corpus:       raw.corpus      ?? null,
  changes:      raw.changes     ?? [],
  traceExample: raw.traceExample ?? null,
  params:       raw.params       ?? {},
});

export const getAdminConfig = (options = {}) =>
  callApi(
    () => fetchAdminConfigMock(options),
    (raw) => {
      const p = raw.payload ?? {};
      return {
        versions: (p.versions ?? []).map(adaptConfigVersion),
        budget:   p.budget ?? { limit: 100, used: 0, avgTokens: 0 },
      };
    }
  );

// ─── 11. GRAPH ────────────────────────────────────────────────────────────────
// Dùng bởi: GraphPage (GraphCanvas)
// State cần: graph { nodes[], edges[] }, rootOptions[], nodeTypes[]

const adaptGraphNode = (raw = {}) => ({
  id:     fallback(raw.id,     "node-auto"),
  type:   fallback(raw.type,   "Unknown"),
  label:  fallback(raw.label,  "—"),
  detail: fallback(raw.detail, ""),
});

const adaptGraphEdge = (raw = {}) => ({
  id:         fallback(raw.id,     "edge-auto"),
  source:     fallback(raw.source, "—"),
  target:     fallback(raw.target, "—"),
  type:       fallback(raw.type,   "RELATED"),
  provenance: raw.provenance ?? null,
});

export const getGraph = (rootNodeId, options = {}) =>
  callApi(
    () => fetchGraphMock(rootNodeId, options),
    (raw) => {
      const p = raw.payload ?? {};
      const graph = p.graph ?? { nodes: [], edges: [] };
      return {
        graph: {
          nodes: (graph.nodes ?? []).map(adaptGraphNode),
          edges: (graph.edges ?? []).map(adaptGraphEdge),
        },
        rootOptions: p.rootOptions ?? [],
        nodeTypes:   p.nodeTypes   ?? [],
      };
    }
  );

// ─── 12. PROFILE ─────────────────────────────────────────────────────────────
// Dùng bởi: ProfilePage, Sidebar (researcher)
// State cần: initials, name, role, avatarUrl

const adaptProfile = (raw = {}) => ({
  initials:  fallback(raw.initials,  "?"),
  name:      fallback(raw.name,      "Người dùng"),
  role:      fallback(raw.role,      "Nhà nghiên cứu"),
  avatarUrl: raw.avatarUrl ?? null,
});

export const getProfile = (options = {}) =>
  callApi(
    () => fetchProfileMock(options),
    (raw) => adaptProfile(raw.payload ?? {})
  );

// ─── 13. RESEARCH EVALUATION (COPILOT AI) ────────────────────────────────────
// Dùng bởi: ResearchPage (Chat query evaluation)
// State cần: status ("verified"|"refusal"|"unverified"|"insufficient"|"partial"),
//            title, summary, facts[], analysis, sources[], warningText, errorText, desc, reason

const adaptEvaluationFact = (raw = {}) => ({
  label: fallback(raw.label, "—"),
  value: fallback(raw.value, "—"),
  sub:   fallback(raw.sub,   "—"),
});

const adaptEvaluationResult = (raw = {}) => ({
  status:       fallback(raw.status,      "unverified"),
  title:        fallback(raw.title,       "Kết quả nghiên cứu"),
  summary:      fallback(raw.summary,     ""),
  facts:        (raw.facts ?? []).map(adaptEvaluationFact),
  analysis:     raw.analysis ?? null,
  sources:      (raw.sources ?? []).map(adaptSource),
  suggestions:  raw.suggestions ?? [],
  actions:      raw.actions ?? [],
  warningText:  raw.warningText ?? null,
  errorText:    raw.errorText ?? null,
  desc:         raw.desc ?? null,
  reason:       raw.reason ?? null,
  evidence:     raw.evidence ?? null,
  check1:       raw.check1 ?? null,
  check2:       raw.check2 ?? null,
});

export const getResearchEvaluation = (question, company = "FPT", period = "FY2025", options = {}) =>
  callApi(
    () => fetchResearchEvaluationMock(question, company, period, options),
    (raw) => adaptEvaluationResult(raw.payload ?? {})
  );

// ─── 14. WATCHLIST USER TICKERS ──────────────────────────────────────────────
// Dùng bởi: WatchlistPage, DashboardPage

export const getWatchlistTickers = (options = {}) =>
  callApi(
    () => fetchWatchlistTickersMock(options),
    (raw) => (Array.isArray(raw.payload) ? raw.payload : ["FPT", "VCB", "MBB"])
  );

export const saveWatchlistTickers = (tickers, options = {}) =>
  callApi(
    () => updateWatchlistTickersMock(tickers, options),
    (raw) => raw.payload?.tickers ?? tickers
  );

// ─── 15. AUTHENTICATION ───────────────────────────────────────────────────────
// Dùng bởi: LoginPage, RegisterPage, AuthContext

export const loginUser = (email, password, rememberMe = false, options = {}) =>
  callApi(
    () => fetchAuthLoginMock(email, password, rememberMe, options),
    (raw) => raw.payload ?? null
  );

export const registerUser = (name, email, password, options = {}) =>
  callApi(
    () => fetchAuthRegisterMock(name, email, password, options),
    (raw) => raw.payload ?? null
  );

export const logoutUser = (options = {}) =>
  callApi(
    () => fetchAuthLogoutMock(options),
    (raw) => raw.payload ?? { loggedOut: true }
  );

// ─── 16. DOCUMENTS (DÙNG CHO COMPONENT DocumentList.jsx) ──────────────────────
const CATEGORY_MAP = {
  FINANCIAL_REPORT: "Báo cáo tài chính",
  MACRO_ECONOMY: "Kinh tế vĩ mô",
  EQUITY_RESEARCH: "Phân tích cổ phiếu",
  MARKET_NEWS: "Tin tức thị trường",
  REAL_ESTATE: "Bất động sản"
};

const STATUS_MAP = {
  APPROVED: { label: "Đã duyệt", color: "green" },
  REVIEWING: { label: "Đang duyệt", color: "yellow" },
  DRAFT: { label: "Bản nháp", color: "gray" },
  PENDING: { label: "Chờ xử lý", color: "blue" }
};

const formatFileSize = (bytes) => {
  if (!bytes || typeof bytes !== "number") return "0 KB";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
};

const formatDate = (epoch) => {
  if (!epoch) return "Chưa cập nhật";
  try {
    return new Date(epoch).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  } catch {
    return "Ngày không hợp lệ";
  }
};

export const adaptDocumentItem = (rawDoc = {}) => ({
  id: fallback(rawDoc.doc_id, "DOC-UNKNOWN"),
  title: fallback(rawDoc.doc_title, "Tài liệu chưa đặt tên (Không có tiêu đề)"),
  author: fallback(rawDoc.author_name, "Tác giả ẩn danh"),
  category: CATEGORY_MAP[rawDoc.category_code] || "Tài liệu chung",
  createdAt: formatDate(rawDoc.created_at_epoch),
  summary: fallback(rawDoc.summary_text, "Không có tóm tắt nội dung."),
  status: STATUS_MAP[rawDoc.status_code] || { label: "Chưa phân loại", color: "gray" },
  tags: Array.isArray(rawDoc.tag_list) && rawDoc.tag_list.length > 0 ? rawDoc.tag_list : ["Tổng hợp"],
  fileSize: formatFileSize(rawDoc.file_size_bytes),
  citationSource: fallback(rawDoc.citation_source, "Không có nguồn trích dẫn"),
  viewCount: fallback(rawDoc.view_count, 0)
});

export const getDocumentsAdapter = (options = {}) =>
  callApi(
    () => fetchDocumentsMock(options),
    (raw) => {
      const items = Array.isArray(raw.payload) ? raw.payload.map(adaptDocumentItem) : [];
      return {
        items,
        total: items.length,
        traceId: raw.trace_id,
        citationId: raw.citation_id
      };
    }
  );


