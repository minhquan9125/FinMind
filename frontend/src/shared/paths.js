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

  // Companies
  companies: "/companies",
  companyDetail: (ticker) => `/companies/${ticker}`,

  // Research (R01)
  research: "/research",
  researchQuery: ({ company, period, question, autosubmit, history } = {}) => {
    const params = new URLSearchParams();
    if (company) params.set("company", company);
    if (period) params.set("period", period);
    if (question) params.set("question", question);
    if (autosubmit) params.set("autosubmit", "1");
    if (history) params.set("history", "1");
    const qs = params.toString();
    return qs ? `/research?${qs}` : "/research";
  },

  // Watchlist (R05)
  watchlist: "/watchlist",

  // Knowledge Graph (R06)
  graph: "/graph",
  graphQuery: (company) =>
    company ? `/graph?company=${encodeURIComponent(company)}` : "/graph",

  // Profile
  profile: "/profile",

  // Admin Workspace
  admin: "/admin",
  adminOverview: "/admin/overview",
  adminTraces: "/admin/traces",
  adminTraceDetail: (traceId) => `/admin/traces/${traceId}`,
  adminSources: "/admin/sources",
  adminSourceDetail: (sourceId) => `/admin/sources/${sourceId}`,
  adminCorpus: "/admin/corpus",
  adminCorpusVersion: (version) => `/admin/corpus/${version}`,
  adminConfiguration: "/admin/configuration",
  adminConfigDetail: (configId) => `/admin/configuration/${configId}`,
  adminAudit: "/admin/audit",
  adminAuditQuery: ({ trace, config, corpus, source, event } = {}) => {
    const params = new URLSearchParams();
    if (trace) params.set("trace", trace);
    if (config) params.set("config", config);
    if (corpus) params.set("corpus", corpus);
    if (source) params.set("source", source);
    if (event) params.set("event", event);
    const qs = params.toString();
    return qs ? `/admin/audit?${qs}` : "/admin/audit";
  },
};
