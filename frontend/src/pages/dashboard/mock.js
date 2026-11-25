import { watchlist } from "../../mocks/userMock.js";

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

export function makeDashboardFixture() {
  return {
    market: marketMock,
    watchlist,
    announcements: ["FPT", "VCB", "MBB"].map((ticker) => ({
      id: `${ticker}-sample-report`, ticker, title: `Ví dụ công bố báo cáo FY2025 của ${ticker}`,
      type: "Báo cáo minh họa", date: "31/12/2025", source: "Fixture FinMind",
    })),
    recentResearch: recentResearchMock,
  };
}

export const emptyDashboardFixture = {
  market: [], watchlist: [], announcements: [], recentResearch: [],
};
