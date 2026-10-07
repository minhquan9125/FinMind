/**
 * FinMind Mock API Service (Client-side)
 * ─────────────────────────────────────────────────────────────────────────────
 * Xây dựng dựa trên dữ liệu thực tế của các trang UI:
 *   - WatchlistPage    ← watchlist/mock.js  (COMPANY_DIRECTORY)
 *   - DashboardPage    ← dashboard/mock.js  (makeCompanySnapshot, marketMock, …)
 *   - ResearchPage     ← research/mock.js   (companyDirectory, companyFinancialFacts, …)
 *   - AdminOverview    ← admin/mock.js      (overviewMock)
 *   - AdminTraces      ← admin/tracesMock.js
 *   - AdminSources     ← admin/sourcesMock.js
 *   - AdminCorpus      ← admin/corpusMock.js
 *   - AdminAudit       ← admin/auditMock.js
 *   - AdminConfig      ← admin/configurationMock.js
 *   - CompanySearch    ← companies/mock.js  (companyCatalog)
 *   - GraphPage        ← graph/mock.js      (graphFixture)
 *   - ProfilePage      ← profile/mock.js    (profileMock)
 *
 * Cấu trúc response chuẩn:
 *   { trace_id, payload, citation_id }
 *
 * Giả lập độ trễ mạng: 500ms – 1000ms (ngẫu nhiên).
 * Kích hoạt lỗi: truyền { shouldFail: true, errorCode: 400 | 500 }.
 */

// ─── Tiện ích ─────────────────────────────────────────────────────────────────

const generateTraceId = () =>
  "TRC-" +
  Math.random().toString(36).substring(2, 7).toUpperCase() +
  "-" +
  Date.now().toString(36).toUpperCase();

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const randomDelay = () => Math.floor(Math.random() * 501) + 500; // 500–1000 ms

/**
 * Helper bọc Promise với delay + cấu trúc response chuẩn.
 * @param {any}     payload     - Dữ liệu thô trả về
 * @param {string}  citationId  - Mã trích dẫn nguồn (có thể null)
 * @param {boolean} shouldFail  - Giả lập lỗi
 * @param {number}  errorCode   - Mã lỗi HTTP (400 | 500)
 * @param {number}  [customDelay] - Delay tuỳ chỉnh (ms), mặc định ngẫu nhiên
 */
function mockEndpoint(payload, citationId, shouldFail, errorCode, customDelay) {
  return new Promise(async (resolve, reject) => {
    const traceId = generateTraceId();
    await delay(customDelay ?? randomDelay());

    if (shouldFail) {
      return reject({
        trace_id: traceId,
        status: errorCode || 500,
        message:
          errorCode === 400
            ? "Bad Request: Tham số không hợp lệ hoặc thiếu quyền truy cập."
            : "Internal Server Error: Dịch vụ FinMind tạm thời không khả dụng.",
        timestamp: new Date().toISOString(),
      });
    }

    return resolve({
      trace_id: traceId,
      citation_id: citationId || null,
      payload,
    });
  });
}

// ─── 1. COMPANIES ─────────────────────────────────────────────────────────────
// Nguồn: companies/mock.js → companyCatalog; mocks/userMock.js → companies[]

const COMPANIES_RAW = [
  { id: "VCB", name: "Vietcombank",       sector: "Ngân hàng",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "BID", name: "BIDV",              sector: "Ngân hàng",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "CTG", name: "VietinBank",        sector: "Ngân hàng",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "MBB", name: "MB",                sector: "Ngân hàng",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "TCB", name: "Techcombank",       sector: "Ngân hàng",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "FPT", name: "FPT Corporation",   sector: "Công nghệ",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "CMG", name: "CMC Corporation",   sector: "Công nghệ",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "ELC", name: "ELCOM",             sector: "Công nghệ",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "ITD", name: "ITD",               sector: "Công nghệ",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
  { id: "ICT", name: "ICT",               sector: "Công nghệ",  status: "Có dữ liệu", tone: "success", period: "FY2025", source: "Fixture FinMind · Dữ liệu minh họa", unit: "tỷ VNĐ", updatedAt: "05/10/2026" },
];

export const fetchCompaniesMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(COMPANIES_RAW, "CIT-COMPANIES-FIXTURE", shouldFail, errorCode);

// ─── 2. WATCHLIST ─────────────────────────────────────────────────────────────
// Nguồn: watchlist/mock.js → COMPANY_DIRECTORY

const WATCHLIST_DIRECTORY_RAW = {
  FPT: { ticker: "FPT", name: "Công ty Cổ phần FPT",                    sector: "Công nghệ", exchange: "HOSE",              latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  VCB: { ticker: "VCB", name: "Ngân hàng TMCP Ngoại thương Việt Nam",   sector: "Ngân hàng", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  BID: { ticker: "BID", name: "BIDV",                                    sector: "Ngân hàng", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  CTG: { ticker: "CTG", name: "VietinBank",                              sector: "Ngân hàng", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  MBB: { ticker: "MBB", name: "Ngân hàng TMCP Quân đội",                sector: "Ngân hàng", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  TCB: { ticker: "TCB", name: "Techcombank",                             sector: "Ngân hàng", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  CMG: { ticker: "CMG", name: "Công ty Cổ phần Tập đoàn Công nghệ CMC", sector: "Công nghệ", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  ELC: { ticker: "ELC", name: "ELCOM",                                   sector: "Công nghệ", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  ITD: { ticker: "ITD", name: "ITD",                                     sector: "Công nghệ", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
  ICT: { ticker: "ICT", name: "ICT",                                     sector: "Công nghệ", exchange: "Chưa có dữ liệu",   latestPeriod: "FY2025", sourceStatus: "Đã có nguồn công bố" },
};

export const fetchWatchlistDirectoryMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(WATCHLIST_DIRECTORY_RAW, "CIT-WATCHLIST-DIR", shouldFail, errorCode);

// ─── 3. DASHBOARD ─────────────────────────────────────────────────────────────
// Nguồn: dashboard/mock.js → makeDashboardFixture, marketMock, recentResearchMock

const BALANCE_SHEET_VALUES = {
  VCB: { FY2025: [1800000, 1650000], "Q2/2026": [1880000, 1720000] },
  BID: { FY2025: [2000000, 1850000], "Q2/2026": [2090000, 1930000] },
  CTG: { FY2025: [1900000, 1760000], "Q2/2026": [1980000, 1830000] },
  MBB: { FY2025: [1000000, 900000],  "Q2/2026": [1060000, 950000]  },
  TCB: { FY2025: [980000,  870000],  "Q2/2026": [1030000, 910000]  },
  FPT: { FY2025: [80000,   42000],   "Q2/2026": [85000,   44000]   },
  CMG: { FY2025: [12000,   6000],    "Q2/2026": [13000,   6500]    },
  ELC: { FY2025: [2500,    1000],    "Q2/2026": [2700,    1100]    },
  ITD: { FY2025: [3500,    1700],    "Q2/2026": [3700,    1800]    },
  ICT: { FY2025: [4200,    2200],    "Q2/2026": [4500,    2400]    },
};

const DASHBOARD_PERIODS_RAW = [
  { value: "FY2025",   label: "FY2025",       dataDate: "31/12/2025" },
  { value: "Q2/2026",  label: "Quý 2/2026",   dataDate: "30/06/2026" },
];

const MARKET_RAW = ["VN-INDEX", "HNX-INDEX", "UPCOM-INDEX"].map((name) => ({
  id: name, name, value: null, change: null, liquidity: null,
  source: "Chưa kết nối nguồn thị trường", label: "EOD · Dữ liệu minh họa",
}));

const RECENT_RESEARCH_RAW = [
  { id: "research-fpt", ticker: "FPT", title: "Phân tích xu hướng doanh thu FY2025", time: "Ví dụ minh họa" },
  { id: "research-vcb", ticker: "VCB", title: "So sánh một số chỉ tiêu tài chính FY2025", time: "Ví dụ minh họa" },
];

export const fetchDashboardMock = (ticker, period = "FY2025", { shouldFail = false, errorCode = 500 } = {}) => {
  const company = COMPANIES_RAW.find((c) => c.id === ticker);
  const periodInfo = DASHBOARD_PERIODS_RAW.find((p) => p.value === period);
  const pair = ticker ? BALANCE_SHEET_VALUES[ticker]?.[period] : null;

  let companySnapshot = null;
  if (company && periodInfo && pair) {
    const [assets, liabilities] = pair;
    companySnapshot = {
      profile: { ticker: company.id, name: company.name, sector: company.sector },
      period,
      dataDate: periodInfo.dataDate,
      updatedAt: company.updatedAt,
      source: company.source,
      unit: company.unit,
      facts: [
        { id: "assets",      label: "Tổng tài sản",      value: assets },
        { id: "liabilities", label: "Nợ phải trả",       value: liabilities },
        { id: "equity",      label: "Vốn chủ sở hữu",    value: assets - liabilities },
      ],
      news: [
        {
          id: `${ticker}-${period}-report`, ticker, type: "Báo cáo minh họa",
          title: `Ví dụ công bố báo cáo ${period}`,
          date: periodInfo.dataDate, source: "Fixture FinMind",
        },
      ],
    };
  }

  const watchlistTickers = ["FPT", "VCB", "MBB", "CMG"];
  const watchlistItems = watchlistTickers.map((id) => {
    const c = COMPANIES_RAW.find((item) => item.id === id);
    return c ? { ...c, status: "Đang theo dõi", tone: "info" } : null;
  }).filter(Boolean);

  const payload = {
    company: companySnapshot,
    market: MARKET_RAW,
    watchlist: watchlistItems,
    announcements: companySnapshot
      ? companySnapshot.news
      : ["FPT", "VCB", "MBB"].map((id) => {
          const p = BALANCE_SHEET_VALUES[id]?.FY2025;
          return {
            id: `${id}-FY2025-report`, ticker: id, type: "Báo cáo minh họa",
            title: `Ví dụ công bố báo cáo FY2025`, date: "31/12/2025", source: "Fixture FinMind",
          };
        }),
    recentResearch: RECENT_RESEARCH_RAW,
    periods: DASHBOARD_PERIODS_RAW,
    popularTickers: ["FPT", "VCB", "MBB", "TCB", "CMG"],
    researcher: { initials: "NA", name: "Nguyễn Văn A", role: "Nhà nghiên cứu" },
  };

  return mockEndpoint(payload, "CIT-DASHBOARD-FIXTURE", shouldFail, errorCode);
};

// ─── 4. RESEARCH ──────────────────────────────────────────────────────────────
// Nguồn: research/mock.js → companyDirectory, companyFinancialFacts, defaultHistoryList

const RESEARCH_COMPANY_DIRECTORY_RAW = {
  FPT: {
    fullName: "Công ty Cổ phần FPT", corporateName: "FPT Corporation",
    industry: "Công nghệ", exchange: "HOSE",
    revenueFY2025: "52.618 tỷ VNĐ", growthFY2025: "+19,6% YoY",
    grossMarginFY2025: "38,2%",      netProfitFY2025: "7.788 tỷ VNĐ",
    sources: [
      { id: "1", title: "Báo cáo thường niên FPT 2025", publisher: "FPT Corporation", type: "Báo cáo thường niên", status: "Đã đối soát", locator: "Trang 48, Mục 3.2", fact: "Doanh thu thuần hợp nhất năm 2025 đạt 52.618 tỷ đồng (+19,6% YoY).", provenance: "Hồ sơ công bố thông tin HOSE #2026-FPT-0329", location: "Trang 48 – Báo cáo kết quả hoạt động kinh doanh", url: "https://fpt.com/vi/nha-dau-tu/bao-cao-tai-chinh" },
      { id: "2", title: "Báo cáo tài chính hợp nhất kiểm toán FY2025", publisher: "PwC Việt Nam / FPT", type: "Báo cáo tài chính kiểm toán", status: "Đã đối soát", locator: "Trang 12 – Báo cáo lưu chuyển tiền tệ", fact: "Lợi nhuận sau thuế đạt 7.788 tỷ đồng (+20,1% YoY).", provenance: "Kiểm toán PwC Việt Nam · Ý kiến chấp nhận toàn phần ngày 28/03/2026", location: "Trang 12", url: "https://fpt.com/vi/nha-dau-tu/bao-cao-tai-chinh" },
    ],
  },
  VCB: {
    fullName: "Ngân hàng TMCP Ngoại thương Việt Nam", corporateName: "Vietcombank",
    industry: "Ngân hàng", exchange: "HOSE",
    revenueFY2025: "68.240 tỷ VNĐ (TOI)", growthFY2025: "+11,2% YoY",
    grossMarginFY2025: "NIM 3,12%",         netProfitFY2025: "33.560 tỷ VNĐ",
    sources: [
      { id: "1", title: "Báo cáo thường niên Vietcombank 2025", publisher: "Vietcombank", type: "Báo cáo thường niên", status: "Đã đối soát", locator: "Trang 36", fact: "Tổng thu nhập hoạt động (TOI) đạt 68.240 tỷ VNĐ (+11,2% YoY).", provenance: "Công bố thông tin chính thức VCB-IR-202603", location: "Phần tổng kết tài chính", url: "https://vietcombank.com.vn/vi-VN/Nha-dau-tu" },
      { id: "2", title: "Báo cáo tài chính kiểm toán VCB FY2025", publisher: "KPMG Việt Nam / VCB", type: "Báo cáo tài chính kiểm toán", status: "Đã đối soát", locator: "Trang 18", fact: "Lợi nhuận sau thuế đạt 33.560 tỷ VNĐ; CAR đạt 11,8%.", provenance: "Kiểm toán KPMG Việt Nam", location: "Bảng cân đối kế toán", url: "https://vietcombank.com.vn/vi-VN/Nha-dau-tu" },
    ],
  },
  MBB: {
    fullName: "Ngân hàng TMCP Quân đội", corporateName: "Military Bank",
    industry: "Ngân hàng", exchange: "HOSE",
    revenueFY2025: "48.150 tỷ VNĐ (TOI)", growthFY2025: "+14,5% YoY",
    grossMarginFY2025: "NIM 4,68%",         netProfitFY2025: "21.300 tỷ VNĐ",
    sources: [
      { id: "1", title: "Báo cáo thường niên MB 2025", publisher: "MB Bank", type: "Báo cáo thường niên", status: "Đã đối soát", locator: "Trang 52", fact: "Tổng thu nhập hoạt động TOI đạt 48.150 tỷ đồng.", provenance: "Bản công bố thông tin MBB-IR-FY25", location: "Báo cáo thường niên", url: "https://mbbank.com.vn" },
      { id: "2", title: "Báo cáo tài chính hợp nhất MBB FY2025", publisher: "Ernst & Young / MB", type: "Báo cáo tài chính", status: "Đã đối soát", locator: "Trang 15", fact: "Lợi nhuận sau thuế đạt 21.300 tỷ VNĐ (+15,2% YoY).", provenance: "Kiểm toán EY Việt Nam", location: "Thuyết minh chi phí hoạt động", url: "https://mbbank.com.vn" },
    ],
  },
  TCB: {
    fullName: "Ngân hàng TMCP Kỹ Thương Việt Nam", corporateName: "Techcombank",
    industry: "Ngân hàng", exchange: "HOSE",
    revenueFY2025: "42.800 tỷ VNĐ (TOI)", growthFY2025: "+18,1% YoY",
    grossMarginFY2025: "NIM 4,20%",         netProfitFY2025: "22.100 tỷ VNĐ",
    sources: [
      { id: "1", title: "Báo cáo thường niên Techcombank 2025", publisher: "Techcombank", type: "Báo cáo thường niên", status: "Đã đối soát", locator: "Trang 44", fact: "Tỷ lệ CASA dẫn đầu thị trường đạt 40,5%.", provenance: "Công bố thông tin UBCKNN / HOSE #TCB-2026", location: "Báo cáo quản trị & chỉ tiêu CASA", url: "https://techcombank.com" },
      { id: "2", title: "BCTC hợp nhất kiểm toán TCB FY2025", publisher: "PwC Việt Nam / Techcombank", type: "Báo cáo tài chính", status: "Đã đối soát", locator: "Trang 14", fact: "Lợi nhuận sau thuế đạt 22.100 tỷ VNĐ (+18,1% YoY).", provenance: "Kiểm toán PwC Việt Nam", location: "Báo cáo kết quả kinh doanh", url: "https://techcombank.com" },
    ],
  },
  CMG: {
    fullName: "Công ty Cổ phần Tập đoàn Công nghệ CMC", corporateName: "CMC Corporation",
    industry: "Công nghệ", exchange: "HOSE",
    revenueFY2025: "7.820 tỷ VNĐ", growthFY2025: "+12,8% YoY",
    grossMarginFY2025: "21,4%",     netProfitFY2025: "415 tỷ VNĐ",
    sources: [
      { id: "1", title: "Báo cáo thường niên CMC Corp 2025", publisher: "CMC Corporation", type: "Báo cáo thường niên", status: "Đã đối soát", locator: "Trang 28", fact: "Doanh thu khối Công nghệ & Giải pháp đạt 4.600 tỷ đồng.", provenance: "Bản công bố thông tin thường niên CMG-2026-CBTT", location: "Báo cáo kết quả các khối kinh doanh", url: "https://cmc.com.vn" },
      { id: "2", title: "Báo cáo tài chính kiểm toán CMG FY2025", publisher: "Deloitte / CMC", type: "Báo cáo tài chính", status: "Đã đối soát", locator: "Trang 10", fact: "Lợi nhuận sau thuế đạt 415 tỷ VNĐ (+14,1% YoY).", provenance: "Kiểm toán Deloitte Việt Nam", location: "Bảng cân đối kế toán hợp nhất", url: "https://cmc.com.vn" },
    ],
  },
};

const RESEARCH_FINANCIAL_FACTS_RAW = {
  FPT: {
    FY2025: { revenue: "52.618 tỷ VNĐ", growth: "+19,6% YoY", grossMargin: "38,2%", netProfit: "7.788 tỷ VNĐ", totalAssets: "80.000 tỷ VNĐ", equity: "38.000 tỷ VNĐ", liability: "42.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    FY2024: { revenue: "43.985 tỷ VNĐ", growth: "+18,2% YoY", grossMargin: "37,6%", netProfit: "6.512 tỷ VNĐ", totalAssets: "68.200 tỷ VNĐ", equity: "31.500 tỷ VNĐ", liability: "36.700 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    "Q2/2026": { revenue: "—", growth: "—", grossMargin: "—", netProfit: "—", totalAssets: "85.000 tỷ VNĐ", equity: "41.000 tỷ VNĐ", liability: "44.000 tỷ VNĐ", evidenceStatus: "insufficient", evidenceLabel: "Chưa công bố BCTC Q2" },
  },
  CMG: {
    FY2025: { revenue: "7.820 tỷ VNĐ", growth: "+12,8% YoY", grossMargin: "21,4%", netProfit: "415 tỷ VNĐ", totalAssets: "12.000 tỷ VNĐ", equity: "5.200 tỷ VNĐ", liability: "6.800 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    FY2024: { revenue: "6.930 tỷ VNĐ", growth: "+11,5% YoY", grossMargin: "20,8%", netProfit: "364 tỷ VNĐ", totalAssets: "10.800 tỷ VNĐ", equity: "4.800 tỷ VNĐ", liability: "6.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    "Q2/2026": { revenue: "—", growth: "—", grossMargin: "—", netProfit: "—", totalAssets: "12.500 tỷ VNĐ", equity: "5.400 tỷ VNĐ", liability: "7.100 tỷ VNĐ", evidenceStatus: "insufficient", evidenceLabel: "Chưa công bố BCTC Q2" },
  },
  VCB: {
    FY2025: { revenue: "68.240 tỷ VNĐ", growth: "+11,2% YoY", grossMargin: "NIM 3,12%", netProfit: "33.560 tỷ VNĐ", totalAssets: "1.920.000 tỷ VNĐ", equity: "165.000 tỷ VNĐ", liability: "1.755.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    FY2024: { revenue: "61.350 tỷ VNĐ", growth: "+10,4% YoY", grossMargin: "NIM 3,18%", netProfit: "30.180 tỷ VNĐ", totalAssets: "1.810.000 tỷ VNĐ", equity: "148.000 tỷ VNĐ", liability: "1.662.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    "Q2/2026": { revenue: "—", growth: "—", grossMargin: "—", netProfit: "—", totalAssets: "1.980.000 tỷ VNĐ", equity: "172.000 tỷ VNĐ", liability: "1.808.000 tỷ VNĐ", evidenceStatus: "insufficient", evidenceLabel: "Chưa công bố BCTC Q2" },
  },
  MBB: {
    FY2025: { revenue: "48.150 tỷ VNĐ", growth: "+14,5% YoY", grossMargin: "NIM 4,68%", netProfit: "21.300 tỷ VNĐ", totalAssets: "1.020.000 tỷ VNĐ", equity: "105.000 tỷ VNĐ", liability: "915.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    FY2024: { revenue: "42.050 tỷ VNĐ", growth: "+13,2% YoY", grossMargin: "NIM 4,60%", netProfit: "18.500 tỷ VNĐ", totalAssets: "880.000 tỷ VNĐ", equity: "88.000 tỷ VNĐ", liability: "792.000 tỷ VNĐ", evidenceStatus: "verified", evidenceLabel: "Đã kiểm chứng (2 nguồn)" },
    "Q2/2026": { revenue: "—", growth: "—", grossMargin: "—", netProfit: "—", totalAssets: "1.060.000 tỷ VNĐ", equity: "110.000 tỷ VNĐ", liability: "950.000 tỷ VNĐ", evidenceStatus: "insufficient", evidenceLabel: "Chưa công bố BCTC Q2" },
  },
};

const RESEARCH_HISTORY_RAW = [
  { id: "h1", company: "FPT", companyName: "FPT Corporation", period: "FY2025", question: "Doanh thu FPT FY2025 thay đổi như thế nào?", time: "Hôm nay · 10:42 SA", status: "verified",  statusLabel: "Đã kiểm chứng", isPinned: true },
  { id: "h2", company: "FPT", companyName: "FPT Corporation", period: "FY2025", question: "Cơ cấu doanh thu khối Xuất khẩu phần mềm FPT?",  time: "Hôm qua · 15:20 CH", status: "verified",  statusLabel: "2 trích dẫn",    isPinned: false },
  { id: "h3", company: "VCB", companyName: "Vietcombank (VCB)",    period: "FY2025", question: "Biến động tỷ lệ CASA và NIM của VCB kỳ gần nhất?", time: "14/02/2025",          status: "verified",  statusLabel: "Đã kiểm chứng", isPinned: false },
  { id: "h4", company: "CMG", companyName: "CMC Corporation (CMG)", period: "FY2025", question: "So sánh doanh thu FPT và CMG trong cùng kỳ",       time: "10/02/2025",          status: "partial",   statusLabel: "Bằng chứng một phần", isPinned: false },
];

const RESEARCH_PERIODS_RAW = [
  { value: "FY2025",   label: "Cả năm FY2025 (12 tháng)" },
  { value: "FY2024",   label: "Cả năm FY2024 (Đã kiểm toán)" },
  { value: "FY2023",   label: "Cả năm FY2023 (Đã kiểm toán)" },
  { value: "Q2/2026",  label: "Quý 2/2026 (Chưa kiểm toán)" },
  { value: "Q3/2024",  label: "Quý 3/2024 (Soát xét)" },
];

const COMPARISON_METRICS_RAW = [
  { key: "revenue",       label: "Doanh thu thuần / TOI" },
  { key: "growth",        label: "Tăng trưởng doanh thu" },
  { key: "grossMargin",   label: "Biên lợi nhuận gộp / NIM" },
  { key: "netProfit",     label: "Lợi nhuận sau thuế" },
  { key: "totalAssets",   label: "Tổng tài sản" },
  { key: "equity",        label: "Vốn chủ sở hữu" },
  { key: "liability",     label: "Nợ phải trả" },
  { key: "evidenceStatus", label: "Tình trạng kiểm chứng" },
];

export const fetchResearchDataMock = (ticker = "FPT", period = "FY2025", { shouldFail = false, errorCode = 500 } = {}) => {
  const companyMeta = RESEARCH_COMPANY_DIRECTORY_RAW[ticker] || null;
  const financialFacts = RESEARCH_FINANCIAL_FACTS_RAW[ticker]?.[period] || null;
  const payload = {
    companyMeta,
    financialFacts,
    history: RESEARCH_HISTORY_RAW,
    periods: RESEARCH_PERIODS_RAW,
    comparisonMetrics: COMPARISON_METRICS_RAW,
    availableTickers: Object.keys(RESEARCH_COMPANY_DIRECTORY_RAW),
  };
  return mockEndpoint(payload, companyMeta ? `CIT-RESEARCH-${ticker}-${period}` : null, shouldFail, errorCode);
};

// ─── 5. ADMIN OVERVIEW ────────────────────────────────────────────────────────
// Nguồn: admin/mock.js → overviewMock

const ADMIN_OVERVIEW_RAW = {
  kpis: [
    { id: "queries",    label: "Truy vấn hôm nay",               value: "7"      },
    { id: "success",    label: "Truy vấn thành công",             value: "2"      },
    { id: "noEvidence", label: "Truy vấn không đủ bằng chứng",   value: "1"      },
    { id: "errors",     label: "Lỗi vận hành",                    value: "2"      },
    { id: "tokens",     label: "Token đã sử dụng",                value: "27,995" },
    { id: "budget",     label: "Ngân sách API đã sử dụng",        value: "61 / 100" },
  ],
  budget: { used: 61, limit: 100, warnAt: 80 },
  recentTraces: [
    { id: "TRC-DEMO-001", time: "10:32", company: "FPT", status: "Thành công",          tone: "success", gate: { label: "Đạt",         tone: "success" }, verifier: { label: "Đạt",       tone: "success" }, duration: "1.64s", tokens: "4,590" },
    { id: "TRC-DEMO-002", time: "10:28", company: "VCB", status: "Không đủ bằng chứng", tone: "warning", gate: { label: "Không đạt",   tone: "warning" }, verifier: null,                                     duration: "0.61s", tokens: "1,850" },
    { id: "TRC-DEMO-003", time: "10:25", company: "MBB", status: "Đang xử lý",           tone: "info",    gate: null,                                       verifier: null,                                     duration: null,    tokens: null   },
    { id: "TRC-DEMO-004", time: "10:19", company: "TCB", status: "Xác minh không đạt",   tone: "error",   gate: { label: "Đạt một phần", tone: "warning" }, verifier: { label: "Không đạt", tone: "error" }, duration: "1.75s", tokens: "4,905" },
    { id: "TRC-DEMO-005", time: "10:14", company: "CMG", status: "Lỗi vận hành",          tone: "error",   gate: null,                                       verifier: null,                                     duration: "0.92s", tokens: "1,200" },
  ],
  alerts: [
    { id: "al-1", tone: "error",   text: "Nguồn SSC kiểm tra kết nối thất bại",           linkLabel: "Xem nguồn", to: "/admin/sources?source=src-4" },
    { id: "al-2", tone: "warning", text: "2 truy vấn lỗi vận hành hôm nay (CMG, BID)",    linkLabel: "Xem trace", to: "/admin/traces?trace=TRC-DEMO-005" },
  ],
  activities: [
    { id: "AUD-DEMO-031", time: "20:45", text: "Cập nhật cấu hình CFG v2.5",  ok: true  },
    { id: "AUD-DEMO-030", time: "20:41", text: "Tạo cấu hình CFG v2.5",       ok: true  },
    { id: "AUD-DEMO-029", time: "20:30", text: "Kích hoạt Corpus v1.4",        ok: true  },
    { id: "AUD-DEMO-027", time: "19:58", text: "Tạo corpus freeze v1.6",       ok: false },
  ],
  activityDate: "04/10/2026",
  services: [
    { id: "research-api", name: "Research API",       desc: "Cổng tiếp nhận yêu cầu phân tích",   ok: true },
    { id: "retrieval",    name: "Retrieval Service",  desc: "Động cơ truy hồi dữ liệu lai",        ok: true },
    { id: "vector",       name: "Vector Store",       desc: "Kho lưu trữ biểu diễn ngữ nghĩa",    ok: true },
    { id: "graph",        name: "Graph Service",      desc: "Đồ thị tri thức doanh nghiệp",        ok: true },
    { id: "gate",         name: "Evidence Gate",      desc: "Bộ lọc đối soát bằng chứng",          ok: true },
    { id: "verifier",     name: "Verifier",           desc: "Kiểm tra tính nhất quán tài chính",   ok: true },
    { id: "telemetry",    name: "Telemetry",          desc: "Ghi nhận Trace & số đo hiệu năng",    ok: true },
  ],
};

export const fetchAdminOverviewMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(ADMIN_OVERVIEW_RAW, "CIT-ADMIN-OVERVIEW", shouldFail, errorCode);

// ─── 6. ADMIN TRACES ──────────────────────────────────────────────────────────
// Nguồn: admin/tracesMock.js → tracesMock

const TRACES_RAW = [
  { id: "TRC-DEMO-001", co: "FPT", q: "Doanh thu và lợi nhuận sau thuế FY2025",           s: "10:32:07.00", e: "10:32:08.64", st: "Thành công",          cat: "none", steps: [[42,"done"],[78,"done"],[290,"done"],[170,"done"],[66,"done"],[780,"done"],[210,"done"]], vec: { ms:290, found:11, kept:5, sel:4 }, gr: { ms:170, found:6, valid:4, state:"Hoàn thành" }, gate: { run:true, found:9, passed:6, elig:5, minEv:3, req:3, have:3, unit:"năm tài chính", st:"Đạt" }, ver: { run:true, total:5, sup:5, thr:80, cites:["EV-DEMO-101","EV-DEMO-102","EV-DEMO-103","EV-DEMO-104","EV-DEMO-105"], claims:["Doanh thu FY2025","Lợi nhuận sau thuế FY2025","Doanh thu FY2024","Lợi nhuận sau thuế FY2024","Doanh thu FY2023"] }, tok: { in:3980, out:610, limit:8000 } },
  { id: "TRC-DEMO-002", co: "VCB", q: "Tỷ lệ nợ xấu qua 4 quý gần nhất",                  s: "10:28:15.00", e: "10:28:15.61", st: "Không đủ bằng chứng", cat: "B",    steps: [[40,"done"],[75,"done"],[280,"done"],[160,"done"],[58,"fail"],[0,"skip"],[0,"skip"]], vec: { ms:280, found:9, kept:3, sel:2 }, gr: { ms:160, found:5, valid:2, state:"Hoàn thành" }, gate: { run:true, found:5, passed:3, elig:2, minEv:3, req:4, have:2, unit:"quý", st:"Không đạt" }, ver: { run:false }, tok: { in:1850, out:0, limit:8000 } },
  { id: "TRC-DEMO-003", co: "MBB", q: "Biên lãi thuần FY2025",                              s: "10:25:11.00", e: null,          st: "Đang xử lý",           cat: "none", steps: [[40,"done"],[80,"done"],[300,"done"],[0,"run"],[0,"skip"],[0,"skip"],[0,"skip"]], vec: { ms:300, found:8, kept:4, sel:null }, gr: { ms:null, found:null, valid:null, state:"Đang chạy" }, gate: { run:false }, ver: { run:false }, tok: { in:null, out:null, limit:8000 } },
  { id: "TRC-DEMO-004", co: "TCB", q: "Tính toán tỷ lệ an toàn vốn CAR và CASA qua các quý", s: "10:19:22.00", e: "10:19:23.75", st: "Xác minh không đạt",   cat: "C",    steps: [[42,"done"],[82,"done"],[310,"done"],[190,"done"],[74,"done"],[820,"done"],[230,"fail"]], vec: { ms:310, found:12, kept:5, sel:3 }, gr: { ms:190, found:7, valid:4, state:"Hoàn thành" }, gate: { run:true, found:8, passed:5, elig:4, minEv:3, req:4, have:3, unit:"quý", st:"Đạt một phần" }, ver: { run:true, total:5, sup:3, thr:80, cites:["EV-DEMO-001","EV-DEMO-002",null,"EV-DEMO-003",null], claims:["CAR Q1/2025","CAR Q2/2025","CASA Q2/2025","CASA Q1/2025","Xu hướng CAR giữa các quý"], why:[null,null,"Thiếu bằng chứng: không tìm thấy nguồn đủ điều kiện cho đúng kỳ.",null,"Không đủ hỗ trợ."] }, tok: { in:4220, out:685, limit:8000 } },
  { id: "TRC-DEMO-005", co: "CMG", q: "Doanh thu theo mảng FY2025",                         s: "10:14:40.00", e: "10:14:40.92", st: "Lỗi vận hành",          cat: "E",    steps: [[41,"done"],[79,"done"],[300,"done"],[500,"fail"],[0,"skip"],[0,"skip"],[0,"skip"]], vec: { ms:300, found:10, kept:4, sel:3 }, gr: { ms:500, found:null, valid:null, state:"Không khả dụng", err:"Không thể truy cập graph service." }, gate: { run:false }, ver: { run:false }, tok: { in:1200, out:0, limit:8000 } },
  { id: "TRC-DEMO-006", co: "BID", q: "Tổng tài sản FY2025",                                s: "10:10:05.00", e: "10:10:06.72", st: "Lỗi vận hành",          cat: "D",    steps: [[40,"done"],[80,"done"],[300,"done"],[170,"done"],[70,"done"],[1060,"fail"],[0,"skip"]], vec: { ms:300, found:10, kept:5, sel:3 }, gr: { ms:170, found:6, valid:4, state:"Hoàn thành" }, gate: { run:true, found:8, passed:5, elig:4, minEv:3, req:3, have:3, unit:"năm tài chính", st:"Đạt" }, ver: { run:false }, tok: { in:5900, out:2100, limit:8000 } },
  { id: "TRC-DEMO-007", co: "CTG", q: "Vốn chủ sở hữu FY2024 và FY2025",                   s: "10:06:30.00", e: "10:06:31.90", st: "Thành công",            cat: "none", steps: [[44,"done"],[90,"done"],[330,"done"],[200,"done"],[80,"done"],[900,"done"],[260,"done"]], vec: { ms:330, found:14, kept:6, sel:4 }, gr: { ms:200, found:8, valid:5, state:"Hoàn thành" }, gate: { run:true, found:9, passed:6, elig:5, minEv:3, req:2, have:2, unit:"năm tài chính", st:"Đạt" }, ver: { run:true, total:5, sup:5, thr:80, cites:["EV-DEMO-201","EV-DEMO-202","EV-DEMO-203","EV-DEMO-204","EV-DEMO-205"], claims:["Vốn chủ sở hữu FY2025","Vốn chủ sở hữu FY2024","Biến động so với FY2024","Cơ cấu vốn FY2025","Cơ cấu vốn FY2024"] }, tok: { in:6350, out:1100, limit:8000 } },
];

export const STEP_NAMES_RAW = ["Nhận truy vấn","Phân tích ý định","Vector Retrieval","Graph Retrieval","Evidence Gate","Tạo câu trả lời","Verifier"];

export const fetchAdminTracesMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint({ traces: TRACES_RAW, stepNames: STEP_NAMES_RAW, activeConfig: "CFG v2.4", activeCorpus: "Corpus v1.4" }, "CIT-ADMIN-TRACES", shouldFail, errorCode);

// ─── 7. ADMIN SOURCES ─────────────────────────────────────────────────────────
// Nguồn: admin/sourcesMock.js → sourcesMock

const SOURCES_RAW = [
  { id: "src-1", name: "FPT Investor Relations", type: "Investor Relations",      access: "HTTP / Web",                 status: "Hoạt động",         version: "v1.2", lastTest: "passed", testOk: true,  willPassTest: true,  schedule: "Hằng ngày",  usage: "Tham chiếu báo cáo công bố của doanh nghiệp", scope: "Báo cáo công bố của FPT", fallback: "Nguồn HOSE", owner: "FinMind Admin", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.2", by:"Quản trị viên", at:"10:15:00 Hôm nay", changed:["Lịch cập nhật"] },{ v:"v1.1", by:"Quản trị viên", at:"09:30:00 Hôm qua", changed:["Chủ sở hữu"] },{ v:"v1.0", by:"Quản trị viên", at:"08:00:00 12/03/2025", changed:["Tạo cấu hình"] }] },
  { id: "src-2", name: "HOSE",                   type: "HOSE",                   access: "HTTP / Web",                 status: "Hoạt động",         version: "v1.0", lastTest: "passed", testOk: true,  willPassTest: true,  schedule: "Hằng ngày",  usage: "Đối chiếu thông tin công bố niêm yết",        scope: "Công bố thông tin của doanh nghiệp niêm yết", fallback: "", owner: "FinMind Admin", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.0", by:"Quản trị viên", at:"08:00:00 10/03/2025", changed:["Tạo cấu hình"] }] },
  { id: "src-3", name: "HNX",                    type: "HNX",                    access: "HTTP / Web",                 status: "Chưa kiểm tra",     version: "v1.0", lastTest: "none",   testOk: false, willPassTest: true,  schedule: "Hằng ngày",  usage: "Đối chiếu thông tin công bố niêm yết",        scope: "Công bố thông tin của doanh nghiệp niêm yết", fallback: "", owner: "FinMind Admin", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.0", by:"Quản trị viên", at:"08:00:00 09/03/2025", changed:["Tạo cấu hình"] }] },
  { id: "src-4", name: "SSC",                    type: "SSC",                    access: "HTTP / Web",                 status: "Kiểm tra thất bại", version: "v1.1", lastTest: "failed", testOk: false, willPassTest: false, failReason: "Không thể truy cập endpoint", schedule: "Hằng tuần", usage: "Tham chiếu văn bản của cơ quan quản lý", scope: "", owner: "FinMind Admin", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.1", by:"Quản trị viên", at:"14:20:00 11/03/2025", changed:["Lịch cập nhật"] },{ v:"v1.0", by:"Quản trị viên", at:"08:00:00 08/03/2025", changed:["Tạo cấu hình"] }] },
  { id: "src-5", name: "Tệp CSV có kiểm soát",  type: "Tệp CSV có kiểm soát", access: "Tệp tải lên có kiểm soát",  status: "Tạm dừng",          version: "v1.3", lastTest: "passed", testOk: true,  willPassTest: true,  schedule: "Thủ công",   usage: "Bổ sung dữ liệu đã được phê duyệt",          scope: "", owner: "FinMind Admin", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.3", by:"Quản trị viên", at:"16:00:00 10/03/2025", changed:["Trạng thái tạm dừng"] }] },
  { id: "src-6", name: "API được phê duyệt",    type: "API được phê duyệt",    access: "API",                        status: "Vô hiệu hóa",       version: "v1.0", lastTest: "none",   testOk: false, willPassTest: true,  schedule: "",           usage: "",                                            scope: "", owner: "", url: "", terms: "", cred: "Chưa cấu hình", history: [{ v:"v1.0", by:"Quản trị viên", at:"08:00:00 01/03/2025", changed:["Tạo cấu hình"] }] },
];

export const fetchAdminSourcesMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(SOURCES_RAW, "CIT-ADMIN-SOURCES", shouldFail, errorCode);

// ─── 8. ADMIN CORPUS ──────────────────────────────────────────────────────────
// Nguồn: admin/corpusMock.js → corporaMock, documentsMock

const CORPORA_RAW = [
  { v: "v1.4", status: "Đang hoạt động",  created: "04/10/2026", manifest: true,  docs: ["d1","d2","d3","d4","d5","d6"],            companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
  { v: "v1.5", status: "Chưa kích hoạt",  created: "04/10/2026", manifest: true,  docs: ["d1","d2","d3","d4","d5","d6","d7"],       companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
  { v: "v1.6", status: "Đang chuẩn bị",   created: "04/10/2026", manifest: false, docs: [],                                          companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
  { v: "v1.3", status: "Đã lưu trữ",      created: "27/09/2026", manifest: true,  docs: ["d1a","d2","d3","d4","d5"],               companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
  { v: "v1.2", status: "Đã lưu trữ",      created: "20/09/2026", manifest: true,  docs: ["d2","d4"],                                companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
  { v: "v1.1", status: "Kiểm tra không đạt", created: "14/09/2026", manifest: false, docs: [],                                      companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" },
];

const DOCUMENTS_RAW = [
  { id: "d1",  name: "Báo cáo thường niên FPT 2025",              co: "FPT", type: "Báo cáo thường niên",  period: "FY2025",   source: "FPT Investor Relations", srcVer: "v1.2", ver: "v2", hash: "a83f…91c2", pub: "—", ingest: "—", validation: "Đã xác thực", family: "fpt-ar-2025", supersedes: "d1a" },
  { id: "d1a", name: "Báo cáo thường niên FPT 2025",              co: "FPT", type: "Báo cáo thường niên",  period: "FY2025",   source: "FPT Investor Relations", srcVer: "v1.2", ver: "v1", hash: "5c0e…7d41", pub: "—", ingest: "—", validation: "Đã xác thực", family: "fpt-ar-2025", supersededBy: "d1" },
  { id: "d2",  name: "Báo cáo tài chính hợp nhất VCB FY2025",    co: "VCB", type: "Báo cáo tài chính",    period: "FY2025",   source: "HOSE",                   srcVer: "v1.0", ver: "v1", hash: "19be…c3a8", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d3",  name: "Báo cáo tài chính quý MBB Q1/2026",        co: "MBB", type: "Báo cáo tài chính",    period: "Q1/2026",  source: "HNX",                    srcVer: "v1.0", ver: "v1", hash: "e72d…0b95", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d4",  name: "Báo cáo tài chính hợp nhất TCB FY2024",    co: "TCB", type: "Báo cáo tài chính",    period: "FY2024",   source: "HOSE",                   srcVer: "v1.0", ver: "v1", hash: "4aa1…f6e0", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d5",  name: "Báo cáo tài chính quý CMG Q4/2025",        co: "CMG", type: "Báo cáo tài chính",    period: "Q4/2025",  source: "Tệp CSV có kiểm soát",   srcVer: "v1.3", ver: "v1", hash: "b30c…28d7", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d6",  name: "Báo cáo thường niên BID FY2025",            co: "BID", type: "Báo cáo thường niên",  period: "FY2025",   source: "HOSE",                   srcVer: "v1.0", ver: "v1", hash: "7f58…a1c4", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d7",  name: "Báo cáo tài chính hợp nhất CTG FY2025",    co: "CTG", type: "Báo cáo tài chính",    period: "FY2025",   source: "HOSE",                   srcVer: "v1.0", ver: "v1", hash: "c9d2…44fb", pub: "—", ingest: "—", validation: "Đã xác thực" },
  { id: "d8",  name: "Báo cáo tài chính quý ELC Q1/2026",        co: "ELC", type: "Báo cáo tài chính",    period: "Q1/2026",  source: "HNX",                    srcVer: "v1.0", ver: "v1", hash: "06a7…e913", pub: "Thiếu", ingest: "—", validation: "Thiếu ngày công bố", issue: "pubDate" },
  { id: "d9",  name: "Báo cáo tài chính ITD FY2025",              co: "ITD", type: "Báo cáo tài chính",    period: "FY2025",   source: "HOSE",                   srcVer: "v1.0", ver: "v1", hash: "d41b…7a30", pub: "—", ingest: "—", validation: "Thiếu phạm vi báo cáo", issue: "scope" },
  { id: "d10", name: "Báo cáo tài chính quý ICT Q4/2025",        co: "ICT", type: "Báo cáo tài chính",    period: "Q4/2025",  source: "Tệp CSV có kiểm soát",   srcVer: "v1.3", ver: "v1", hash: "88ef…12b6", pub: "—", ingest: "—", validation: "Không đạt kiểm tra integrity", issue: "hash" },
];

export const fetchAdminCorpusMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint({ corpora: CORPORA_RAW, documents: DOCUMENTS_RAW, candidateDocIds: ["d7","d8","d9","d10"] }, "CIT-ADMIN-CORPUS", shouldFail, errorCode);

// ─── 9. ADMIN AUDIT ───────────────────────────────────────────────────────────
// Nguồn: admin/auditMock.js → auditMock

const AUDIT_RAW = [
  { id:"AUD-DEMO-031", time:"04/10/2026 20:45", actor:"System Admin", role:"System Admin", action:"Cập nhật cấu hình CFG v2.5",     type:"Thay đổi configuration", rtype:"Configuration",    resource:"CFG v2.5",                result:"Thành công",  config:"v2.5", corpus:"v1.4", reason:null, trace:null, source:null, sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-030", time:"04/10/2026 20:41", actor:"System Admin", role:"System Admin", action:"Tạo cấu hình CFG v2.5",          type:"Thay đổi configuration", rtype:"Configuration",    resource:"CFG v2.5",                result:"Thành công",  config:"v2.5", corpus:null,  reason:null, trace:null, source:null, sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-029", time:"04/10/2026 20:30", actor:"System Admin", role:"System Admin", action:"Kích hoạt corpus",               type:"Kích hoạt corpus",       rtype:"Corpus",           resource:"Corpus v1.4",             result:"Thành công",  config:null,  corpus:"v1.4",reason:null, trace:null, source:null, sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-028", time:"04/10/2026 20:12", actor:"System Admin", role:"System Admin", action:"Tạo corpus freeze",              type:"Tạo corpus freeze",      rtype:"Corpus",           resource:"Corpus v1.5",             result:"Thành công",  config:null,  corpus:"v1.5",reason:null, trace:null, source:null, sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-027", time:"04/10/2026 19:58", actor:"System Admin", role:"System Admin", action:"Tạo corpus freeze",              type:"Tạo corpus freeze",      rtype:"Corpus",           resource:"Corpus v1.6",             result:"Thất bại",    config:null,  corpus:"v1.6",reason:"Không thể tạo phiên bản corpus: 1 tài liệu thiếu publication date.", trace:null, source:null, sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-026", time:"04/10/2026 19:40", actor:"System Admin", role:"System Admin", action:"Bật nguồn",                      type:"Bật nguồn",              rtype:"Source adapter",   resource:"HNX",                     result:"Thất bại",    config:null,  corpus:null,  reason:"Kiểm tra kết nối chưa đạt.", trace:null, source:"src-3", sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-025", time:"04/10/2026 19:35", actor:"System Admin", role:"System Admin", action:"Kiểm tra nguồn",                 type:"Kiểm tra nguồn",        rtype:"Source adapter",   resource:"SSC",                     result:"Thất bại",    config:null,  corpus:null,  reason:"Không thể truy cập endpoint.", trace:null, source:"src-4", sanitized:null, retentionExpired:false },
  { id:"AUD-DEMO-020", time:"04/10/2026 18:30", actor:"System Admin", role:"System Admin", action:"Đăng nhập",                      type:"Đăng nhập",              rtype:"Phiên đăng nhập",  resource:"Phiên quản trị",          result:"Thành công",  config:null,  corpus:null,  reason:null, trace:null, source:null, sanitized:{ Authorization:"[ĐÃ ẨN]" }, retentionExpired:false },
  { id:"AUD-DEMO-019", time:"04/10/2026 18:29", actor:"Chưa xác định",role:"—",            action:"Đăng nhập",                      type:"Đăng nhập",              rtype:"Phiên đăng nhập",  resource:"Phiên quản trị",          result:"Thất bại",    config:null,  corpus:null,  reason:"Thông tin đăng nhập không hợp lệ.", trace:null, source:null, sanitized:{ Authorization:"[ĐÃ ẨN]", "Thông tin xác thực":"[ĐÃ ẨN]" }, retentionExpired:false },
  { id:"AUD-DEMO-003", time:"—",                actor:"—",             role:"—",            action:"—",                              type:"—",                      rtype:"—",                resource:"—",                       result:"—",           config:null,  corpus:null,  reason:null, trace:null, source:null, sanitized:null, retentionExpired:true },
];

export const fetchAdminAuditMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(AUDIT_RAW, "CIT-ADMIN-AUDIT", shouldFail, errorCode);

// ─── 10. ADMIN CONFIGURATION ──────────────────────────────────────────────────
// Nguồn: admin/configurationMock.js → versionsMock, budgetMock

const BASE_PARAMS = {
  relevance:75, evidence:75, verifier:80, minEvidence:3, freshness:365,
  vectorLimit:20, graphLimit:10, fusionTopK:8, rerankLimit:5,
  contextCeiling:5000, inputCeiling:6500, outputCeiling:2500, totalCeiling:8000,
  warningThreshold:80,
};

const CONFIG_VERSIONS_RAW = [
  { v:"CFG v2.5", kind:"PRODUCTION", status:"Đang chờ kích hoạt", created:"04/10/2026", by:"System Admin", activated:"—",           changes:["Ngưỡng bằng chứng 75% → 80%","Tổng token tối đa 8,000 → 7,000","Warning threshold 80% → 75%"], params:{ ...BASE_PARAMS, evidence:80, totalCeiling:7000, warningThreshold:75 } },
  { v:"CFG v2.4", kind:"PRODUCTION", status:"Đang hoạt động",     created:"01/10/2026", by:"System Admin", activated:"02/10/2026",  activatedBy:"System Admin", corpus:"v1.4", changes:["Giới hạn kết quả sau fusion 6 → 8"], traceExample:{ id:"TRC-DEMO-004", text:"TRC-DEMO-004 — Verifier 60% < ngưỡng 80% → Không đạt" }, params:{ ...BASE_PARAMS } },
  { v:"CFG v2.3", kind:"PRODUCTION", status:"Đã thay thế",        created:"24/09/2026", by:"System Admin", activated:"25/09/2026",  changes:["Ngưỡng xác minh 75% → 80%"], params:{ ...BASE_PARAMS, fusionTopK:6 } },
  { v:"CFG v2.2", kind:"PRODUCTION", status:"Đã thay thế",        created:"17/09/2026", by:"System Admin", activated:"18/09/2026",  changes:["Rerank limit 8 → 5"], params:{ ...BASE_PARAMS, fusionTopK:6, verifier:75 } },
];

export const fetchAdminConfigMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint({ versions: CONFIG_VERSIONS_RAW, budget: { limit:100, used:61, avgTokens:4666 } }, "CIT-ADMIN-CONFIG", shouldFail, errorCode);

// ─── 11. GRAPH ────────────────────────────────────────────────────────────────
// Nguồn: graph/mock.js → graphFixture, rootOptions, nodeTypes

const GRAPH_FIXTURE_RAW = {
  nodes: [
    { id:"company:FPT",            type:"Company",          label:"FPT",          detail:"FPT Corporation" },
    { id:"dataset:FPT:demo",       type:"Dataset",          label:"FPT · dataset", detail:"Bản dữ liệu mock 2025" },
    { id:"report:FPT:2025-YEAR",   type:"FinancialReport",  label:"Báo cáo FPT",   detail:"Kỳ 2025-YEAR · balance_sheet" },
    { id:"period:2025-YEAR",       type:"ReportingPeriod",  label:"2025-YEAR",     detail:"Kỳ năm 2025" },
    { id:"observation:FPT:assets", type:"Observation",      label:"Tổng tài sản",  detail:"Quan sát mẫu của FPT" },
    { id:"metric:assets",          type:"Metric",           label:"totalAssets",   detail:"Mã chỉ tiêu mẫu" },
    { id:"price:FPT:2025-12-31",   type:"PriceBar",         label:"Giá FPT EOD",   detail:"31/12/2025 · không có giá thật" },
    { id:"company:VCB",            type:"Company",          label:"VCB",          detail:"Vietcombank" },
    { id:"dataset:VCB:demo",       type:"Dataset",          label:"VCB · dataset", detail:"Bản dữ liệu mock 2025" },
    { id:"report:VCB:2025-YEAR",   type:"FinancialReport",  label:"Báo cáo VCB",   detail:"Kỳ 2025-YEAR · balance_sheet" },
  ],
  edges: [
    { id:"fpt-has-dataset",   source:"company:FPT",          target:"dataset:FPT:demo",       type:"HAS_DATASET",    provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:null, jsonPointer:null, note:"Quan hệ liên kết dataset." } },
    { id:"fpt-has-report",    source:"dataset:FPT:demo",      target:"report:FPT:2025-YEAR",   type:"HAS_REPORT",     provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:"mock://fpt/financials.json", jsonPointer:"/financial_data/balance_sheet/0", note:"Nguồn mẫu từ metadata FinancialReport." } },
    { id:"fpt-for-period",    source:"report:FPT:2025-YEAR",  target:"period:2025-YEAR",       type:"FOR_PERIOD",     provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:"mock://fpt/financials.json", jsonPointer:"/financial_data/balance_sheet/0", note:"Kỳ báo cáo gắn với FinancialReport mẫu." } },
    { id:"fpt-has-obs",       source:"report:FPT:2025-YEAR",  target:"observation:FPT:assets", type:"HAS_OBSERVATION",provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:"mock://fpt/financials.json", jsonPointer:"/financial_data/balance_sheet/0/totalAssets", note:"JSON Pointer mẫu từ Observation." } },
    { id:"fpt-of-metric",     source:"observation:FPT:assets",target:"metric:assets",          type:"OF_METRIC",      provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:"mock://fpt/financials.json", jsonPointer:"/financial_data/balance_sheet/0/totalAssets", note:"Chỉ tiêu của Observation mẫu." } },
    { id:"fpt-has-price",     source:"dataset:FPT:demo",      target:"price:FPT:2025-12-31",   type:"HAS_PRICE",      provenance:{ kind:"Dữ liệu minh họa", datasetId:"FPT:demo", source:"MOCK_FINMIND", sourceFile:"mock://fpt/prices.json", jsonPointer:"/price_history/0", note:"Giá cuối ngày mẫu; không phải giá thị trường thật." } },
    { id:"vcb-has-dataset",   source:"company:VCB",           target:"dataset:VCB:demo",       type:"HAS_DATASET",    provenance:{ kind:"Dữ liệu minh họa", datasetId:"VCB:demo", source:"MOCK_FINMIND", sourceFile:null, jsonPointer:null, note:"Quan hệ liên kết dataset." } },
    { id:"vcb-has-report",    source:"dataset:VCB:demo",       target:"report:VCB:2025-YEAR",   type:"HAS_REPORT",     provenance:{ kind:"Dữ liệu minh họa", datasetId:"VCB:demo", source:"MOCK_FINMIND", sourceFile:"mock://vcb/financials.json", jsonPointer:"/financial_data/balance_sheet/0", note:"Nguồn mẫu từ metadata FinancialReport." } },
    { id:"vcb-for-period",    source:"report:VCB:2025-YEAR",   target:"period:2025-YEAR",       type:"FOR_PERIOD",     provenance:{ kind:"Dữ liệu minh họa", datasetId:"VCB:demo", source:"MOCK_FINMIND", sourceFile:"mock://vcb/financials.json", jsonPointer:"/financial_data/balance_sheet/0", note:"Kỳ báo cáo gắn với FinancialReport mẫu." } },
  ],
};

const GRAPH_ROOT_OPTIONS_RAW = [
  { value:"company:FPT",             label:"FPT · Doanh nghiệp" },
  { value:"company:VCB",             label:"VCB · Doanh nghiệp" },
  { value:"report:FPT:2025-YEAR",    label:"FPT · Báo cáo 2025" },
  { value:"observation:FPT:assets",  label:"FPT · Quan sát tổng tài sản" },
];

const GRAPH_NODE_TYPES_RAW = [
  { type:"Company",         label:"Doanh nghiệp", color:"#2563EB" },
  { type:"Dataset",         label:"Dataset",      color:"#475569" },
  { type:"FinancialReport", label:"Báo cáo",      color:"#0284C7" },
  { type:"ReportingPeriod", label:"Kỳ báo cáo",   color:"#EA580C" },
  { type:"Observation",     label:"Quan sát",     color:"#6366F1" },
  { type:"Metric",          label:"Chỉ tiêu",     color:"#7C3AED" },
  { type:"PriceBar",        label:"Giá EOD",      color:"#059669" },
];

export const fetchGraphMock = (rootNodeId, { shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint({ graph: GRAPH_FIXTURE_RAW, rootOptions: GRAPH_ROOT_OPTIONS_RAW, nodeTypes: GRAPH_NODE_TYPES_RAW }, "CIT-GRAPH-FIXTURE", shouldFail, errorCode);

// ─── 12. PROFILE ──────────────────────────────────────────────────────────────
// Nguồn: profile/mock.js → profileMock; dashboard/mock.js → researcherMock

const PROFILE_RAW = {
  initials: "NA",
  name: "Nguyễn Văn A",
  role: "Nhà nghiên cứu",
  avatarUrl: null,
};

export const fetchProfileMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(PROFILE_RAW, null, shouldFail, errorCode);

// ─── 13. RESEARCH QUERY EVALUATION (COPILOT AI) ──────────────────────────────
// Nguồn: research/mock.js → evaluateResearchQuery

export function evaluateResearchQueryLogic(rawQuery = "", companyCode = "FPT", periodCode = "FY2025") {
  const query = (rawQuery || "").trim();
  const lower = query.toLowerCase();

  const isNoAdvice =
    lower.includes("nên mua") ||
    lower.includes("nên bán") ||
    lower.includes("giá mục tiêu") ||
    lower.includes("mua không") ||
    lower.includes("khuyến nghị đầu tư") ||
    lower.includes("có nên lướt sóng") ||
    lower.includes("target price");

  const isProjection =
    lower.includes("dự báo") ||
    lower.includes("dự đoán") ||
    lower.includes("kỳ vọng") ||
    lower.includes("tương lai sẽ");

  const isComparison =
    lower.includes("so sánh") ||
    lower.includes("đối chiếu") ||
    lower.includes("và cmg") ||
    lower.includes("với cmg") ||
    lower.includes("với vcb");

  const isInsufficient =
    lower.includes("2026") ||
    lower.includes("quý") ||
    lower.includes("q1") ||
    lower.includes("q2") ||
    lower.includes("q3") ||
    lower.includes("q4") ||
    periodCode === "Q2/2026";

  if (isNoAdvice) {
    return {
      status: "refusal",
      title: "Quy định tuân thủ nghiên cứu FinMind",
      warningText:
        "FinMind không cung cấp khuyến nghị mua, bán, nắm giữ hoặc giá mục tiêu. Vui lòng chuyển hướng câu hỏi sang phân tích các chỉ tiêu tài chính cơ bản, biên lợi nhuận hoặc đối chiếu báo cáo tài chính công bố.",
      suggestions: [
        `Biên lợi nhuận gộp ${companyCode} 3 năm gần nhất thay đổi như thế nào?`,
        `Cơ cấu nợ vay và dòng tiền hoạt động kinh doanh ${companyCode}?`,
        `Tăng trưởng doanh thu và lợi nhuận ròng ${companyCode} kỳ ${periodCode}?`,
      ],
      sources: [],
    };
  }

  if (isProjection) {
    return {
      status: "unverified",
      title: "Không thể xác minh câu trả lời",
      errorText:
        "FinMind không thể xác nhận đầy đủ câu trả lời dựa trên các bằng chứng hiện có. Hệ thống chỉ căn cứ trên tài liệu công bố thông tin đã qua kiểm chứng và từ chối suy đoán, dự báo hoặc mô hình hóa chỉ tiêu chưa có căn cứ.",
      actions: ["Xem nguồn hiện có", "Đặt câu hỏi khác"],
      sources: [],
    };
  }

  if (isInsufficient) {
    return {
      status: "insufficient",
      title: `Chưa thể xác định số liệu cho ${companyCode} (${periodCode})`,
      desc: "FinMind chưa đưa ra con số vì thiếu số liệu đã kiểm định cho kỳ này trong dữ liệu công bố chính thức.",
      reason:
        "Để đối soát mức tăng trưởng, cần số liệu của cả kỳ được hỏi và kỳ liền kề từ nguồn được phê duyệt, cùng đơn vị và chuẩn mực kế toán. Dữ liệu kỳ này hiện chưa có BCTC kiểm toán đầy đủ.",
      company: companyCode,
      period: periodCode,
      evidence: "Chưa có bằng chứng đủ điều kiện đối soát cho câu hỏi trong kỳ này. FinMind không tự suy đoán số liệu còn thiếu.",
      sources: [],
    };
  }

  if (isComparison) {
    return {
      status: "partial",
      title: "Bằng chứng một phần",
      desc: `Một phần câu trả lời của ${companyCode} đã có nguồn hỗ trợ chính thức; phần so sánh cần bổ sung thêm báo cáo tài chính của doanh nghiệp đối ứng trong cùng kỳ.`,
      check1: `Đã đối chiếu: Dữ liệu công bố chính thức của ${companyCode} (${periodCode})`,
      check2: "Cần bổ sung: Nguồn công bố kiểm toán của doanh nghiệp so sánh trong cùng kỳ",
      sources: RESEARCH_COMPANY_DIRECTORY_RAW[companyCode]?.sources ?? [],
    };
  }

  // Mặc định: verified
  const compMeta = RESEARCH_COMPANY_DIRECTORY_RAW[companyCode] || RESEARCH_COMPANY_DIRECTORY_RAW.FPT;
  return {
    status: "verified",
    title: "Đã kiểm chứng",
    summary: `FinMind đối chiếu doanh thu ${companyCode} kỳ ${periodCode} với kỳ trước dựa trên các nguồn công bố đã được phê duyệt. Số liệu ghi nhận tăng trưởng ổn định theo BCTC hợp nhất kiểm toán.`,
    facts: [
      { label: "Doanh thu / TOI", value: compMeta.revenueFY2025, sub: "Dữ liệu chính thức" },
      { label: "Tăng trưởng", value: compMeta.growthFY2025, sub: "So với cùng kỳ" },
      { label: "Kỳ báo cáo", value: periodCode, sub: "12 tháng" },
      { label: "Phạm vi", value: "Hợp nhất", sub: "BCTC kiểm toán" },
    ],
    analysis: {
      period: `${periodCode} (12 tháng)`,
      scope: "Hợp nhất",
      sourcesCount: compMeta.sources?.length || 2,
      updatedAt: "05/10/2026 (EOD)",
    },
    sources: compMeta.sources || [],
  };
}

export const fetchResearchEvaluationMock = (question, company = "FPT", period = "FY2025", { shouldFail = false, errorCode = 500 } = {}) => {
  const result = evaluateResearchQueryLogic(question, company, period);
  const citationId = result.sources?.[0]?.id ? `CIT-RESEARCH-${company}-${result.sources[0].id}` : "CIT-RESEARCH-REF";
  return mockEndpoint(result, citationId, shouldFail, errorCode);
};

// ─── 14. WATCHLIST PERSISTENCE (USER ACTIONS) ────────────────────────────────
const STORAGE_KEY_WATCHLIST = "finmind_watchlist_tickers";
const DEFAULT_WATCHLIST = ["FPT", "VCB", "MBB", "TCB", "CMG"];

export const fetchWatchlistTickersMock = ({ shouldFail = false, errorCode = 500 } = {}) => {
  let tickers = DEFAULT_WATCHLIST;
  try {
    const raw = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY_WATCHLIST) : null;
    if (raw) tickers = JSON.parse(raw);
  } catch (_) {}
  return mockEndpoint(tickers, "CIT-WATCHLIST-USER", shouldFail, errorCode);
};

export const updateWatchlistTickersMock = (newTickers, { shouldFail = false, errorCode = 500 } = {}) => {
  try {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_WATCHLIST, JSON.stringify(newTickers));
    }
  } catch (_) {}
  return mockEndpoint({ success: true, tickers: newTickers }, "CIT-WATCHLIST-UPDATE", shouldFail, errorCode);
};

// ─── 15. AUTHENTICATION ───────────────────────────────────────────────────────
// Nguồn: mocks/authMock.js

const MOCK_AUTH_USERS = {
  "user@finmind.vn": { id: "usr-001", email: "user@finmind.vn", name: "Nguyễn Văn An", role: "user" },
  "admin@finmind.vn": { id: "adm-001", email: "admin@finmind.vn", name: "Trần Minh Quản trị", role: "admin" },
};
const MOCK_AUTH_PASSWORDS = {
  "user@finmind.vn": "user123",
  "admin@finmind.vn": "admin123",
};

export const fetchAuthLoginMock = (email, password, rememberMe = false, { shouldFail = false, errorCode = 400 } = {}) => {
  if (shouldFail) return mockEndpoint(null, null, true, errorCode);
  const correctPassword = MOCK_AUTH_PASSWORDS[email];
  if (!correctPassword || correctPassword !== password) {
    return mockEndpoint(null, null, true, 400);
  }
  const user = MOCK_AUTH_USERS[email];
  const token = "mock-jwt-" + Math.random().toString(36).substring(2);
  const session = {
    user,
    token,
    loginAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + (rememberMe ? 7 * 24 * 3600 * 1000 : 30 * 60 * 1000)).toISOString(),
  };
  return mockEndpoint(session, "CIT-AUTH-SESSION");
};

export const fetchAuthRegisterMock = (name, email, password, { shouldFail = false, errorCode = 400 } = {}) => {
  if (shouldFail) return mockEndpoint(null, null, true, errorCode);
  if (!name || !email || !password) return mockEndpoint(null, null, true, 400);
  const user = { id: "usr-" + Date.now().toString(36), email, name, role: "user" };
  const token = "mock-jwt-" + Math.random().toString(36).substring(2);
  return mockEndpoint({ user, token }, "CIT-AUTH-REGISTER");
};

export const fetchAuthLogoutMock = () =>
  mockEndpoint({ loggedOut: true }, "CIT-AUTH-LOGOUT");

// ─── 16. DOCUMENTS (DÙNG CHO COMPONENT DocumentList.jsx) ──────────────────────
const MOCK_DOCUMENTS_RAW = [
  {
    doc_id: "DOC-VN-001",
    doc_title: "Báo cáo phân tích tài chính Vinamilk (VNM) Q4/2023",
    author_name: "Nguyễn Văn Hùng",
    category_code: "FINANCIAL_REPORT",
    created_at_epoch: 1705312800000,
    summary_text: "Doanh thu xuất khẩu ghi nhận mức tăng trưởng tích cực, biên lợi nhuận gộp hồi phục nhờ giá nguyên liệu sữa bột giảm.",
    status_code: "APPROVED",
    tag_list: ["VNM", "Tiêu dùng", "BCTC"],
    file_size_bytes: 3450000,
    citation_source: "BCTC Kiểm toán Hợp nhất 2023 - Trang 14",
    view_count: 1420
  },
  {
    doc_id: "DOC-VN-002",
    doc_title: "Triển vọng ngành Ngân hàng & Tác động của chính sách lãi suất 2024",
    author_name: "Trần Mai Anh",
    category_code: "MACRO_ECONOMY",
    created_at_epoch: 1707904800000,
    summary_text: "Đánh giá chất lượng tài sản và NIM của các ngân hàng thương mại cổ phần trong bối cảnh mặt bằng lãi suất duy trì ở mức thấp.",
    status_code: "REVIEWING",
    tag_list: ["Ngân hàng", "Vĩ mô", "Lãi suất"],
    file_size_bytes: 5120000,
    citation_source: "Báo cáo vĩ mô Ngân hàng Nhà nước & Tổng cục Thống kê",
    view_count: 980
  },
  {
    doc_id: "DOC-VN-003",
    doc_title: null,
    author_name: null,
    category_code: "EQUITY_RESEARCH",
    created_at_epoch: null,
    summary_text: "Báo cáo thử nghiệm khả năng chịu lỗi và fallback giá trị null của Adapter.",
    status_code: "PENDING",
    tag_list: null,
    file_size_bytes: null,
    citation_source: null,
    view_count: 0
  }
];

export const fetchDocumentsMock = ({ shouldFail = false, errorCode = 500 } = {}) =>
  mockEndpoint(MOCK_DOCUMENTS_RAW, "CIT-FINMIND-DOCS-001", shouldFail, errorCode);


