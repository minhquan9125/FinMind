// Dữ liệu danh mục doanh nghiệp phục vụ trang Watchlist (R05)
// Trích xuất chuẩn xác từ interface finmind_r05_danh_s_ch_theo_d_i_b_n_chu_n_h_a_kh_ng_seed_m_u/code.html

export const COMPANY_DIRECTORY = {
  FPT: {
    ticker: "FPT",
    name: "Công ty Cổ phần FPT",
    sector: "Công nghệ",
    exchange: "HOSE",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  VCB: {
    ticker: "VCB",
    name: "Ngân hàng TMCP Ngoại thương Việt Nam",
    sector: "Ngân hàng",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  BID: {
    ticker: "BID",
    name: "BIDV",
    sector: "Ngân hàng",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  CTG: {
    ticker: "CTG",
    name: "VietinBank",
    sector: "Ngân hàng",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  MBB: {
    ticker: "MBB",
    name: "Ngân hàng TMCP Quân đội",
    sector: "Ngân hàng",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  TCB: {
    ticker: "TCB",
    name: "Techcombank",
    sector: "Ngân hàng",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  CMG: {
    ticker: "CMG",
    name: "Công ty Cổ phần Tập đoàn Công nghệ CMC",
    sector: "Công nghệ",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  ELC: {
    ticker: "ELC",
    name: "ELCOM",
    sector: "Công nghệ",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  ITD: {
    ticker: "ITD",
    name: "ITD",
    sector: "Công nghệ",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
  ICT: {
    ticker: "ICT",
    name: "ICT",
    sector: "Công nghệ",
    exchange: "Chưa có dữ liệu",
    latestPeriod: "FY2025",
    sourceStatus: "Đã có nguồn công bố",
  },
};

export const STORAGE_KEY = "finmind_watchlist";

export function getStoredWatchlist() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveStoredWatchlist(tickers) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
}
