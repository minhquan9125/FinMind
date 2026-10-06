import { companyCatalog } from "../companies/mock.js";
import { watchlist } from "../../mocks/userMock.js";

// Số dưới đây là giả lập để thử UI, không lấy từ báo cáo hay API thị trường.
// [tổng tài sản, nợ phải trả] · đơn vị: tỷ VNĐ.
const values = {
  VCB: { FY2025: [1800000, 1650000], "Q2/2026": [1880000, 1720000] },
  BID: { FY2025: [2000000, 1850000], "Q2/2026": [2090000, 1930000] },
  CTG: { FY2025: [1900000, 1760000], "Q2/2026": [1980000, 1830000] },
  MBB: { FY2025: [1000000, 900000], "Q2/2026": [1060000, 950000] },
  TCB: { FY2025: [980000, 870000], "Q2/2026": [1030000, 910000] },
  FPT: { FY2025: [80000, 42000], "Q2/2026": [85000, 44000] },
  CMG: { FY2025: [12000, 6000], "Q2/2026": [13000, 6500] },
  ELC: { FY2025: [2500, 1000], "Q2/2026": [2700, 1100] },
  ITD: { FY2025: [3500, 1700], "Q2/2026": [3700, 1800] },
  ICT: { FY2025: [4200, 2200], "Q2/2026": [4500, 2400] },
};

export const periods = [
  { value: "FY2025", label: "FY2025", dataDate: "31/12/2025" },
  { value: "Q2/2026", label: "Quý 2/2026", dataDate: "30/06/2026" },
];

export const researcherMock = { initials: "NA", name: "Nguyễn Văn A", role: "Nhà nghiên cứu" };
export const popularTickers = ["FPT", "VCB", "MBB", "TCB", "CMG"];

export const marketMock = ["VN-INDEX", "HNX-INDEX", "UPCOM-INDEX"].map((name) => ({
  id: name, name, value: null, change: null, liquidity: null,
  source: "Chưa kết nối nguồn thị trường", label: "EOD · Dữ liệu minh họa",
}));

export const recentResearchMock = [
  { id: "research-fpt", ticker: "FPT", title: "Phân tích xu hướng doanh thu FY2025", time: "Ví dụ minh họa" },
  { id: "research-vcb", ticker: "VCB", title: "So sánh một số chỉ tiêu tài chính FY2025", time: "Ví dụ minh họa" },
];

export function makeCompanySnapshot(ticker, period) {
  const company = companyCatalog.find((item) => item.id === ticker);
  const periodInfo = periods.find((item) => item.value === period);
  const pair = values[ticker]?.[period];
  if (!company || !periodInfo || !pair) return null;

  const [assets, liabilities] = pair;
  return {
    profile: company.profile,
    period,
    dataDate: periodInfo.dataDate,
    updatedAt: company.updatedAt,
    source: company.source,
    unit: company.unit,
    facts: [
      { id: "assets", label: "Tổng tài sản", value: assets },
      { id: "liabilities", label: "Nợ phải trả", value: liabilities },
      { id: "equity", label: "Vốn chủ sở hữu", value: assets - liabilities },
    ],
    news: [
      { id: `${ticker}-${period}-report`, ticker, title: `Ví dụ công bố báo cáo ${period}`, type: "Báo cáo minh họa", date: periodInfo.dataDate, source: "Fixture FinMind" },
    ],
  };
}

export function makeDashboardFixture(ticker, period) {
  const company = ticker ? makeCompanySnapshot(ticker, period) : null;
  return {
    company,
    market: marketMock,
    watchlist,
    announcements: company?.news ?? ["FPT", "VCB", "MBB"].map((id) => makeCompanySnapshot(id, "FY2025").news[0]),
    recentResearch: recentResearchMock,
  };
}

export const emptyDashboardFixture = {
  company: null, market: [], watchlist: [], announcements: [], recentResearch: [],
};
