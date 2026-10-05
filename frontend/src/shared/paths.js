// [TL] Bảng địa chỉ các trang trong hệ thống FinMind.
// Các trang chuyển qua lại bằng file này, không viết cứng chuỗi url.

export const PATHS = {
  // Public & Authentication
  home: "/",
  login: "/login",
  register: "/register",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",

  // Legacy RAG flow (upload → search → analysis)
  upload: "/upload",
  search: (docId) => `/documents/${docId}/search`,
  analysis: (docId) => `/documents/${docId}/analysis`,

  // Core Features
  dashboard: "/dashboard",
  dashboardTab: (tab = "liquidity") => `/dashboard?tab=${tab}`,

  // Companies
  companies: "/companies",
  companiesSearch: (query = "") => (query ? `/companies?q=${encodeURIComponent(query)}` : "/companies"),
  companyDetail: (ticker) => `/companies/${ticker}`,
  companyFinancials: (ticker, view) =>
    view ? `/companies/${ticker}/financials?view=${view}` : `/companies/${ticker}/financials`,

  // Documents
  documents: "/documents",
  documentViewer: (documentId) => `/documents/${documentId}/view`,

  // Compare & Knowledge Graph
  compare: "/compare",
  compareTickers: (tickers = "FPT,CMG", period) =>
    period
      ? `/compare?tickers=${encodeURIComponent(tickers)}&period=${period}`
      : `/compare?tickers=${encodeURIComponent(tickers)}`,
  knowledgeGraph: "/knowledge-graph",
  knowledgeGraphQuery: (partner) =>
    partner ? `/knowledge-graph?q=${encodeURIComponent(partner)}` : "/knowledge-graph",

  // AI Copilot
  copilot: "/copilot",
  copilotSession: (sessionId) => `/copilot/${sessionId}`,

  // Personal Workspaces & Watchlist
  watchlist: "/watchlist",
  workspaces: "/workspaces",
  history: "/history",
  historyDetail: (sessionId) => `/history/${sessionId}`,

  // Settings
  settings: "/settings",
  settingsAppearance: "/settings/appearance",
  settingsLanguage: "/settings/language",
  settingsSecurity: "/settings/security",
  settingsData: "/settings/data",

  // Admin Workspace
  admin: "/admin",
  adminSources: "/admin/sources",
  adminIngestion: "/admin/ingestion",
  adminIngestionRun: (runId) => `/admin/ingestion?run=${runId}`,
  adminDataQuality: "/admin/data-quality",
  adminValidationDetail: (validationId) => `/admin/data-quality/${validationId}`,
  adminIndex: "/admin/index",
  adminCorpus: "/admin/corpus",
  adminQueryTraces: "/admin/query-traces",
  adminSystemControls: "/admin/system-controls",
  adminUsers: "/admin/users",

  // Evaluation Workspace
  evaluation: "/evaluation",
  evaluationRun: "/evaluation/run",
  evaluationGoldenTestSet: "/evaluation/golden-test-set",
  evaluationTraceDetail: (traceId) => `/evaluation/traces/${traceId}`,

  // Status & Errors
  forbidden: "/403",
  error: "/error",
};
