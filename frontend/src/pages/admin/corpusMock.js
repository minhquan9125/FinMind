// Dữ liệu minh họa cho trang Phiên bản kho dữ liệu (từ A03-corpus.html).
// Khi backend xong, thay getCorpusData() bằng hàm gọi API.
//
// corpora[].docs: danh sách id tài liệu thuộc corpus.  documents[].issue: pubDate | scope | hash (lỗi chặn freeze).

// Tài liệu ứng viên đưa vào wizard "Tạo phiên bản corpus".
export const CANDIDATE_DOC_IDS = ["d7", "d8", "d9", "d10"];

const common = { companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất", by: "FinMind Admin", config: "CFG-DEMO" };

export const corporaMock = [
  { ...common, v: "v1.4", status: "Đang hoạt động", created: "04/10/2026", manifest: true, docs: ["d1", "d2", "d3", "d4", "d5", "d6"] },
  { ...common, v: "v1.5", status: "Chưa kích hoạt", created: "04/10/2026", manifest: true, docs: ["d1", "d2", "d3", "d4", "d5", "d6", "d7"] },
  { ...common, v: "v1.6", status: "Đang chuẩn bị", created: "04/10/2026", manifest: false, docs: [] },
  { ...common, v: "v1.3", status: "Đã lưu trữ", created: "27/09/2026", manifest: true, docs: ["d1a", "d2", "d3", "d4", "d5"] },
  { ...common, v: "v1.2", status: "Đã lưu trữ", created: "20/09/2026", manifest: true, docs: ["d2", "d4"] },
  { ...common, v: "v1.1", status: "Kiểm tra không đạt", created: "14/09/2026", manifest: false, docs: [] },
];

const doc = (id, name, co, type, period, source, srcVer, ver, hash, extra = {}) => ({
  id, name, co, type, period, source, srcVer, ver, hash, pub: "—", ingest: "—", validation: "Đã xác thực", ...extra,
});

export const documentsMock = [
  doc("d1", "Báo cáo thường niên FPT 2025", "FPT", "Báo cáo thường niên", "FY2025", "FPT Investor Relations", "v1.2", "v2", "a83f…91c2", { family: "fpt-ar-2025", supersedes: "d1a" }),
  doc("d1a", "Báo cáo thường niên FPT 2025", "FPT", "Báo cáo thường niên", "FY2025", "FPT Investor Relations", "v1.2", "v1", "5c0e…7d41", { family: "fpt-ar-2025", supersededBy: "d1" }),
  doc("d2", "Báo cáo tài chính hợp nhất VCB FY2025", "VCB", "Báo cáo tài chính", "FY2025", "HOSE", "v1.0", "v1", "19be…c3a8"),
  doc("d3", "Báo cáo tài chính quý MBB Q1/2026", "MBB", "Báo cáo tài chính", "Q1/2026", "HNX", "v1.0", "v1", "e72d…0b95"),
  doc("d4", "Báo cáo tài chính hợp nhất TCB FY2024", "TCB", "Báo cáo tài chính", "FY2024", "HOSE", "v1.0", "v1", "4aa1…f6e0"),
  doc("d5", "Báo cáo tài chính quý CMG Q4/2025", "CMG", "Báo cáo tài chính", "Q4/2025", "Tệp CSV có kiểm soát", "v1.3", "v1", "b30c…28d7"),
  doc("d6", "Báo cáo thường niên BID FY2025", "BID", "Báo cáo thường niên", "FY2025", "HOSE", "v1.0", "v1", "7f58…a1c4"),
  doc("d7", "Báo cáo tài chính hợp nhất CTG FY2025", "CTG", "Báo cáo tài chính", "FY2025", "HOSE", "v1.0", "v1", "c9d2…44fb"),
  doc("d8", "Báo cáo tài chính quý ELC Q1/2026", "ELC", "Báo cáo tài chính", "Q1/2026", "HNX", "v1.0", "v1", "06a7…e913", { pub: "Thiếu", validation: "Thiếu ngày công bố", issue: "pubDate" }),
  doc("d9", "Báo cáo tài chính ITD FY2025", "ITD", "Báo cáo tài chính", "FY2025", "HOSE", "v1.0", "v1", "d41b…7a30", { validation: "Thiếu phạm vi báo cáo", issue: "scope" }),
  doc("d10", "Báo cáo tài chính quý ICT Q4/2025", "ICT", "Báo cáo tài chính", "Q4/2025", "Tệp CSV có kiểm soát", "v1.3", "v1", "88ef…12b6", { validation: "Không đạt kiểm tra integrity", issue: "hash" }),
];

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getCorpusData() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải dữ liệu phiên bản kho dữ liệu."));
      else resolve({ corpora: corporaMock.map((c) => ({ ...c, docs: [...c.docs] })), documents: documentsMock.map((d) => ({ ...d })) });
    }, 400);
  });
}
