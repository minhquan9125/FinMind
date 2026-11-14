import { companies } from "../../mocks/userMock.js";
import { companyCatalog } from "../companies/mock.js";

export const researchCompanyCatalog = companyCatalog;

export const researchPeriods = [
  { value: "FY2025", label: "Cả năm FY2025 (12 tháng)" },
  { value: "FY2024", label: "Cả năm FY2024 (Đã kiểm toán)" },
  { value: "FY2023", label: "Cả năm FY2023 (Đã kiểm toán)" },
  { value: "Q2/2026", label: "Quý 2/2026 (Chưa kiểm toán)" },
  { value: "Q3/2024", label: "Quý 3/2024 (Soát xét)" },
];

export const companyDirectory = {
  FPT: {
    fullName: "Công ty Cổ phần FPT",
    corporateName: "FPT Corporation",
    industry: "Công nghệ",
    exchange: "HOSE",
    revenueFY2025: "52.618 tỷ VNĐ",
    growthFY2025: "+19,6% YoY",
    grossMarginFY2025: "38,2%",
    netProfitFY2025: "7.788 tỷ VNĐ",
    sources: [
      {
        id: "1",
        title: "Báo cáo thường niên FPT 2025",
        publisher: "FPT Corporation",
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: "Trang 48, Mục 3.2 – Báo cáo kết quả hoạt động kinh doanh hợp nhất",
        fact: "Doanh thu thuần hợp nhất năm 2025 đạt 52.618 tỷ đồng (+19,6% YoY); trong đó khối Công nghệ đạt 31.449 tỷ đồng, chiếm 59,5% cơ cấu.",
        provenance: "Hồ sơ công bố thông tin HOSE #2026-FPT-0329 · Thẩm định công bố UBCKNN · Hash lưu trữ FinMind SHA-256 #8fa9b2c1",
        location: "Trang 48 – Báo cáo kết quả hoạt động kinh doanh",
        url: "https://fpt.com/vi/nha-dau-tu/bao-cao-tai-chinh",
      },
      {
        id: "2",
        title: "Báo cáo tài chính hợp nhất kiểm toán FY2025",
        publisher: "PwC Việt Nam / FPT",
        type: "Báo cáo tài chính kiểm toán",
        status: "Đã đối soát",
        locator: "Trang 12 – Báo cáo lưu chuyển tiền tệ & Thuyết minh số 24 (Doanh thu bộ phận)",
        fact: "Lợi nhuận sau thuế đạt 7.788 tỷ đồng (+20,1% YoY); biên lợi nhuận gộp hợp nhất đạt 38,2%. Lưu chuyển tiền thuần từ HĐKD đạt 8.420 tỷ đồng.",
        provenance: "Kiểm toán độc lập PwC Việt Nam (Ý kiến chấp nhận toàn phần ngày 28/03/2026) · Lưu chiểu kho Corpus FinMind v2.4",
        location: "Trang 12 – Báo cáo lưu chuyển tiền tệ & Thuyết minh số 24",
        url: "https://fpt.com/vi/nha-dau-tu/bao-cao-tai-chinh",
      },
    ],
  },
  VCB: {
    fullName: "Ngân hàng TMCP Ngoại thương Việt Nam",
    corporateName: "Vietcombank",
    industry: "Ngân hàng",
    exchange: "HOSE",
    revenueFY2025: "68.240 tỷ VNĐ (TOI)",
    growthFY2025: "+11,2% YoY",
    grossMarginFY2025: "NIM 3,12%",
    netProfitFY2025: "33.560 tỷ VNĐ",
    sources: [
      {
        id: "1",
        title: "Báo cáo thường niên Vietcombank 2025",
        publisher: "Vietcombank",
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: "Trang 36 – Báo cáo kết quả hoạt động ngân hàng mẹ & hợp nhất",
        fact: "Tổng thu nhập hoạt động (TOI) đạt 68.240 tỷ VNĐ (+11,2% YoY); tỷ lệ tiền gửi không kỳ hạn (CASA) duy trì ở mức 34,2%.",
        provenance: "Công bố thông tin chính thức VCB-IR-202603 · Lưu trữ hệ thống CBTT HNX & HOSE · Hash SHA-256 #3d7e81a9",
        location: "Phần tổng kết tài chính ngân hàng mẹ & hợp nhất",
        url: "https://vietcombank.com.vn/vi-VN/Nha-dau-tu",
      },
      {
        id: "2",
        title: "Báo cáo tài chính kiểm toán VCB FY2025",
        publisher: "KPMG Việt Nam / VCB",
        type: "Báo cáo tài chính kiểm toán",
        status: "Đã đối soát",
        locator: "Trang 18 – Bảng cân đối kế toán & Thuyết minh thu nhập lãi thuần (Mục 19)",
        fact: "Lợi nhuận trước thuế hợp nhất đạt 41.200 tỷ VNĐ; lợi nhuận sau thuế đạt 33.560 tỷ VNĐ; tỷ lệ an toàn vốn CAR đạt 11,8%.",
        provenance: "Kiểm toán độc lập KPMG Việt Nam (Báo cáo số 25/2026/KPMG-HN) · Chứng thư số kiểm toán đã xác thực",
        location: "Bảng cân đối kế toán & Báo cáo kết quả hoạt động",
        url: "https://vietcombank.com.vn/vi-VN/Nha-dau-tu",
      },
    ],
  },
  MBB: {
    fullName: "Ngân hàng TMCP Quân đội",
    corporateName: "Military Bank",
    industry: "Ngân hàng",
    exchange: "HOSE",
    revenueFY2025: "48.150 tỷ VNĐ (TOI)",
    growthFY2025: "+14,5% YoY",
    grossMarginFY2025: "NIM 4,68%",
    netProfitFY2025: "21.300 tỷ VNĐ",
    sources: [
      {
        id: "1",
        title: "Báo cáo thường niên MB 2025",
        publisher: "MB Bank",
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: "Trang 52 – Báo cáo thường niên ngân hàng số & tăng trưởng tín dụng",
        fact: "Tổng thu nhập hoạt động TOI đạt 48.150 tỷ đồng; doanh thu ngân hàng số đóng góp 32% tổng thu nhập phí dịch vụ.",
        provenance: "Bản công bố thông tin MBB-IR-FY25 · Sở Giao dịch Chứng khoán TP.HCM tiếp nhận · Hash SHA-256 #7c1a93ff",
        location: "Báo cáo thường niên ngân hàng số & tài chính",
        url: "https://mbbank.com.vn",
      },
      {
        id: "2",
        title: "Báo cáo tài chính hợp nhất MBB FY2025",
        publisher: "Ernst & Young / MB",
        type: "Báo cáo tài chính",
        status: "Đã đối soát",
        locator: "Trang 15 – Thuyết minh chi phí hoạt động và trích lập dự phòng rủi ro tín dụng",
        fact: "Lợi nhuận sau thuế đạt 21.300 tỷ VNĐ (+15,2% YoY); tỷ lệ bao phủ nợ xấu đạt 122%.",
        provenance: "Kiểm toán độc lập EY Việt Nam · Ý kiến kiểm toán chấp nhận toàn phần số 412/2026",
        location: "Thuyết minh chi phí hoạt động và trích lập dự phòng",
        url: "https://mbbank.com.vn",
      },
    ],
  },
  TCB: {
    fullName: "Ngân hàng TMCP Kỹ Thương Việt Nam",
    corporateName: "Techcombank",
    industry: "Ngân hàng",
    exchange: "HOSE",
    revenueFY2025: "42.800 tỷ VNĐ (TOI)",
    growthFY2025: "+18,1% YoY",
    grossMarginFY2025: "NIM 4,20%",
    netProfitFY2025: "22.100 tỷ VNĐ",
    sources: [
      {
        id: "1",
        title: "Báo cáo thường niên Techcombank 2025",
        publisher: "Techcombank",
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: "Trang 44 – Báo cáo ban điều hành & tỷ lệ tiền gửi CASA",
        fact: "Tỷ lệ CASA dẫn đầu thị trường đạt 40,5%; tổng tài sản cán mốc 920.000 tỷ VNĐ.",
        provenance: "Công bố thông tin UBCKNN / HOSE #TCB-2026 · Hồ sơ IR xác thực",
        location: "Báo cáo quản trị & chỉ tiêu CASA",
        url: "https://techcombank.com",
      },
      {
        id: "2",
        title: "BCTC hợp nhất kiểm toán TCB FY2025",
        publisher: "PwC Việt Nam / Techcombank",
        type: "Báo cáo tài chính",
        status: "Đã đối soát",
        locator: "Trang 14 – Báo cáo kết quả hoạt động kinh doanh hợp nhất năm 2025",
        fact: "Lợi nhuận sau thuế đạt 22.100 tỷ VNĐ (+18,1% YoY); thu nhập ngoài lãi tăng 26,4%.",
        provenance: "Kiểm toán PwC Việt Nam · Hồ sơ kiểm toán hợp nhất số 88/TCB-PWC",
        location: "Báo cáo kết quả kinh doanh",
        url: "https://techcombank.com",
      },
    ],
  },
  CMG: {
    fullName: "Công ty Cổ phần Tập đoàn Công nghệ CMC",
    corporateName: "CMC Corporation",
    industry: "Công nghệ",
    exchange: "HOSE",
    revenueFY2025: "7.820 tỷ VNĐ",
    growthFY2025: "+12,8% YoY",
    grossMarginFY2025: "21,4%",
    netProfitFY2025: "415 tỷ VNĐ",
    sources: [
      {
        id: "1",
        title: "Báo cáo thường niên CMC Corp 2025",
        publisher: "CMC Corporation",
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: "Trang 28 – Kết quả hoạt động khối Khách hàng Doanh nghiệp & Quốc tế",
        fact: "Doanh thu khối Công nghệ & Giải pháp đạt 4.600 tỷ đồng; khối Kinh doanh quốc tế tăng trưởng 24%.",
        provenance: "Bản công bố thông tin thường niên CMG-2026-CBTT · Hash SHA-256 #6b5c4a22",
        location: "Báo cáo kết quả các khối kinh doanh",
        url: "https://cmc.com.vn",
      },
      {
        id: "2",
        title: "Báo cáo tài chính kiểm toán CMG FY2025",
        publisher: "Deloitte / CMC",
        type: "Báo cáo tài chính",
        status: "Đã đối soát",
        locator: "Trang 10 – Bảng cân đối kế toán hợp nhất & Báo cáo lưu chuyển tiền tệ",
        fact: "Lợi nhuận sau thuế đạt 415 tỷ VNĐ (+14,1% YoY); biên lợi nhuận gộp đạt 21,4%.",
        provenance: "Kiểm toán Deloitte Việt Nam · Báo cáo kiểm toán số 104/DELOITTE-CMG",
        location: "Bảng cân đối kế toán hợp nhất",
        url: "https://cmc.com.vn",
      },
    ],
  },
};

export function getCompanyMeta(ticker) {
  const code = (ticker || "FPT").toUpperCase();
  if (companyDirectory[code]) {
    return { code, ...companyDirectory[code] };
  }
  const found = companies.find((c) => c.id === code);
  return {
    code,
    fullName: found ? found.name : `Công ty Cổ phần ${code}`,
    corporateName: `${code} Corporation`,
    industry: found ? found.sector : "Doanh nghiệp niêm yết",
    exchange: "HOSE",
    revenueFY2025: "—",
    growthFY2025: "—",
    grossMarginFY2025: "—",
    netProfitFY2025: "—",
    sources: [
      {
        id: "1",
        title: `Báo cáo thường niên ${code} 2025`,
        publisher: `${code} Corporation`,
        type: "Báo cáo thường niên",
        status: "Đã đối soát",
        locator: `Trang 30 – Báo cáo tóm tắt tài chính ${code} FY2025`,
        fact: `Dữ liệu tài chính cơ bản của ${code} được lưu trữ theo hồ sơ công bố thông tin chính thức.`,
        provenance: `Hồ sơ CBTT ${code} lưu chiểu FinMind Corpus SHA-256 #std_${code.toLowerCase()}`,
        location: "Hồ sơ công bố thông tin",
        url: "#",
      },
    ],
  };
}

export const comparisonMetricsList = [
  { key: "revenue", label: "Doanh thu thuần / TOI" },
  { key: "growth", label: "Tăng trưởng doanh thu" },
  { key: "grossMargin", label: "Biên lợi nhuận gộp / NIM" },
  { key: "netProfit", label: "Lợi nhuận sau thuế" },
  { key: "totalAssets", label: "Tổng tài sản" },
  { key: "equity", label: "Vốn chủ sở hữu" },
  { key: "liability", label: "Nợ phải trả" },
  { key: "evidenceStatus", label: "Tình trạng kiểm chứng" },
];

export const companyFinancialFacts = {
  FPT: {
    FY2025: {
      revenue: "52.618 tỷ VNĐ",
      growth: "+19,6% YoY",
      grossMargin: "38,2%",
      netProfit: "7.788 tỷ VNĐ",
      totalAssets: "80.000 tỷ VNĐ",
      equity: "38.000 tỷ VNĐ",
      liability: "42.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    FY2024: {
      revenue: "43.985 tỷ VNĐ",
      growth: "+18,2% YoY",
      grossMargin: "37,6%",
      netProfit: "6.512 tỷ VNĐ",
      totalAssets: "68.200 tỷ VNĐ",
      equity: "31.500 tỷ VNĐ",
      liability: "36.700 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    "Q2/2026": {
      revenue: "—",
      growth: "—",
      grossMargin: "—",
      netProfit: "—",
      totalAssets: "85.000 tỷ VNĐ",
      equity: "41.000 tỷ VNĐ",
      liability: "44.000 tỷ VNĐ",
      evidenceStatus: "insufficient",
      evidenceLabel: "Chưa công bố BCTC Q2",
    },
  },
  CMG: {
    FY2025: {
      revenue: "7.820 tỷ VNĐ",
      growth: "+12,8% YoY",
      grossMargin: "21,4%",
      netProfit: "415 tỷ VNĐ",
      totalAssets: "12.000 tỷ VNĐ",
      equity: "5.200 tỷ VNĐ",
      liability: "6.800 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    FY2024: {
      revenue: "6.930 tỷ VNĐ",
      growth: "+11,5% YoY",
      grossMargin: "20,8%",
      netProfit: "364 tỷ VNĐ",
      totalAssets: "10.800 tỷ VNĐ",
      equity: "4.800 tỷ VNĐ",
      liability: "6.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    "Q2/2026": {
      revenue: "—",
      growth: "—",
      grossMargin: "—",
      netProfit: "—",
      totalAssets: "12.500 tỷ VNĐ",
      equity: "5.400 tỷ VNĐ",
      liability: "7.100 tỷ VNĐ",
      evidenceStatus: "insufficient",
      evidenceLabel: "Chưa công bố BCTC Q2",
    },
  },
  VCB: {
    FY2025: {
      revenue: "68.240 tỷ VNĐ",
      growth: "+11,2% YoY",
      grossMargin: "NIM 3,12%",
      netProfit: "33.560 tỷ VNĐ",
      totalAssets: "1.920.000 tỷ VNĐ",
      equity: "165.000 tỷ VNĐ",
      liability: "1.755.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    FY2024: {
      revenue: "61.350 tỷ VNĐ",
      growth: "+10,4% YoY",
      grossMargin: "NIM 3,18%",
      netProfit: "30.180 tỷ VNĐ",
      totalAssets: "1.810.000 tỷ VNĐ",
      equity: "148.000 tỷ VNĐ",
      liability: "1.662.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    "Q2/2026": {
      revenue: "—",
      growth: "—",
      grossMargin: "—",
      netProfit: "—",
      totalAssets: "1.980.000 tỷ VNĐ",
      equity: "172.000 tỷ VNĐ",
      liability: "1.808.000 tỷ VNĐ",
      evidenceStatus: "insufficient",
      evidenceLabel: "Chưa công bố BCTC Q2",
    },
  },
  MBB: {
    FY2025: {
      revenue: "48.150 tỷ VNĐ",
      growth: "+14,5% YoY",
      grossMargin: "NIM 4,68%",
      netProfit: "21.300 tỷ VNĐ",
      totalAssets: "1.020.000 tỷ VNĐ",
      equity: "105.000 tỷ VNĐ",
      liability: "915.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    FY2024: {
      revenue: "42.050 tỷ VNĐ",
      growth: "+13,2% YoY",
      grossMargin: "NIM 4,60%",
      netProfit: "18.500 tỷ VNĐ",
      totalAssets: "880.000 tỷ VNĐ",
      equity: "88.000 tỷ VNĐ",
      liability: "792.000 tỷ VNĐ",
      evidenceStatus: "verified",
      evidenceLabel: "Đã kiểm chứng (2 nguồn)",
    },
    "Q2/2026": {
      revenue: "—",
      growth: "—",
      grossMargin: "—",
      netProfit: "—",
      totalAssets: "1.060.000 tỷ VNĐ",
      equity: "110.000 tỷ VNĐ",
      liability: "950.000 tỷ VNĐ",
      evidenceStatus: "insufficient",
      evidenceLabel: "Chưa công bố BCTC Q2",
    },
  },
};

// ─── STORAGE KEYS VÀ HÀM LƯU THEO USER BẰNG MOCK ────────────────────────────
export const STORAGE_KEY_HISTORY = "finmind_research_history";
export const STORAGE_KEY_FEEDBACK = "finmind_copilot_feedback";

export const defaultHistoryList = [
  {
    id: "h1",
    company: "FPT",
    companyName: "FPT Corporation",
    period: "FY2025",
    question: "Doanh thu FPT FY2025 thay đổi như thế nào?",
    time: "Hôm nay · 10:42 SA",
    status: "verified",
    statusLabel: "Đã kiểm chứng",
    isPinned: true,
  },
  {
    id: "h2",
    company: "FPT",
    companyName: "FPT Corporation",
    period: "FY2025",
    question: "Cơ cấu doanh thu khối Xuất khẩu phần mềm FPT?",
    time: "Hôm qua · 15:20 CH",
    status: "verified",
    statusLabel: "2 trích dẫn",
    isPinned: false,
  },
  {
    id: "h3",
    company: "VCB",
    companyName: "Vietcombank (VCB)",
    period: "FY2025",
    question: "Biến động tỷ lệ CASA và NIM của VCB kỳ gần nhất?",
    time: "14/02/2025",
    status: "verified",
    statusLabel: "Đã kiểm chứng",
    isPinned: false,
  },
  {
    id: "h4",
    company: "CMG",
    companyName: "CMC Corporation (CMG)",
    period: "FY2025",
    question: "So sánh doanh thu FPT và CMG trong cùng kỳ",
    time: "10/02/2025",
    status: "partial",
    statusLabel: "Bằng chứng một phần",
    isPinned: false,
  },
];

export function getStoredResearchHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_HISTORY);
    return raw ? JSON.parse(raw) : defaultHistoryList;
  } catch {
    return defaultHistoryList;
  }
}

export function saveStoredResearchHistory(items) {
  try {
    localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(items));
  } catch {
    // Ignore storage quota errors
  }
}

export function getStoredFeedback() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_FEEDBACK);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveFeedbackItem(item) {
  try {
    const existing = getStoredFeedback();
    const updated = [item, ...existing];
    localStorage.setItem(STORAGE_KEY_FEEDBACK, JSON.stringify(updated));
    return updated;
  } catch {
    return [];
  }
}

/**
 * Trợ lý đánh giá tự động (Rule-based Evaluator theo đúng quy định tuân thủ):
 * Phân tích câu hỏi người dùng và trả về một trong các trạng thái chuẩn:
 * - 'refusal': Quy định ranh giới đạo đức / Không khuyến nghị đầu tư (khi hỏi nên mua, bán, giá mục tiêu)
 * - 'unverified': Không thể xác minh do câu hỏi dự báo/suy đoán
 * - 'insufficient': Chưa đủ bằng chứng đã kiểm định (kỳ chưa công bố, thiếu kỳ đối ứng)
 * - 'partial': Bằng chứng một phần (khi so sánh 2 công ty mà thiếu dữ liệu 1 bên)
 * - 'verified': Đã kiểm chứng đầy đủ từ nguồn công bố chính thức
 */
export function evaluateResearchQuery(rawQuery, companyCode = "FPT", periodCode = "FY2025") {
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
    };
  }

  if (isProjection) {
    return {
      status: "unverified",
      title: "Không thể xác minh câu trả lời",
      errorText:
        "FinMind không thể xác nhận đầy đủ câu trả lời dựa trên các bằng chứng hiện có. Hệ thống chỉ căn cứ trên tài liệu công bố thông tin đã qua kiểm chứng và từ chối suy đoán, dự báo hoặc mô hình hóa chỉ tiêu chưa có căn cứ.",
      actions: ["Xem nguồn hiện có", "Đặt câu hỏi khác"],
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
    };
  }

  if (isComparison) {
    return {
      status: "partial",
      title: "Bằng chứng một phần",
      desc: `Một phần câu trả lời của ${companyCode} đã có nguồn hỗ trợ chính thức; phần so sánh cần bổ sung thêm báo cáo tài chính của doanh nghiệp đối ứng trong cùng kỳ.`,
      check1: `Đã đối chiếu: Dữ liệu công bố chính thức của ${companyCode} (${periodCode})`,
      check2: "Cần bổ sung: Nguồn công bố kiểm toán của doanh nghiệp so sánh trong cùng kỳ",
    };
  }

  // Mặc định: verified
  const compMeta = getCompanyMeta(companyCode);
  return {
    status: "verified",
    title: "Đã kiểm chứng",
    summary: `FinMind đối chiếu doanh thu ${compMeta.code} kỳ ${periodCode} với kỳ trước dựa trên các nguồn công bố đã được phê duyệt. Số liệu ghi nhận tăng trưởng ổn định theo BCTC hợp nhất kiểm toán.`,
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
    followUps: [
      `Biên lợi nhuận ${compMeta.code} thay đổi như thế nào?`,
      `So sánh doanh thu ${compMeta.code} và CMG`,
      `Mảng kinh doanh nào của ${compMeta.code} đóng góp nhiều nhất?`,
      `Cơ cấu tài sản và nợ vay ${compMeta.code} kỳ ${periodCode}?`,
    ],
  };
}
