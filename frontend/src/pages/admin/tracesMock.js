// Dữ liệu minh họa cho trang Theo dõi truy vấn (từ A01-traces.html).
// Khi backend xong, thay getTraces() bằng hàm gọi API.
//
// Mỗi trace:
//   steps: [[ms, trạng_thái], ...] theo thứ tự 7 bước pipeline; trạng thái: done | fail | run | skip
//   cat:   nhóm nguyên nhân: none | B (bằng chứng) | C (xác minh) | D (ngân sách) | E (hạ tầng)
//   vec / gr / gate / ver / tok: chi tiết từng khối (null = chưa có số liệu)

export const ACTIVE_CONFIG = "CFG v2.4";
export const ACTIVE_CORPUS = "Corpus v1.4";

export const STEP_NAMES = [
  "Nhận truy vấn",
  "Phân tích ý định",
  "Vector Retrieval",
  "Graph Retrieval",
  "Evidence Gate",
  "Tạo câu trả lời",
  "Verifier",
];

export const tracesMock = [
  {
    id: "TRC-DEMO-001", co: "FPT", q: "Doanh thu và lợi nhuận sau thuế FY2025",
    s: "10:32:07.00", e: "10:32:08.64", st: "Thành công", cat: "none",
    steps: [[42, "done"], [78, "done"], [290, "done"], [170, "done"], [66, "done"], [780, "done"], [210, "done"]],
    vec: { ms: 290, found: 11, kept: 5, sel: 4 },
    gr: { ms: 170, found: 6, valid: 4, state: "Hoàn thành" },
    gate: { run: true, found: 9, passed: 6, elig: 5, minEv: 3, req: 3, have: 3, unit: "năm tài chính", st: "Đạt" },
    ver: {
      run: true, total: 5, sup: 5, thr: 80,
      cites: ["EV-DEMO-101", "EV-DEMO-102", "EV-DEMO-103", "EV-DEMO-104", "EV-DEMO-105"],
      claims: ["Doanh thu FY2025", "Lợi nhuận sau thuế FY2025", "Doanh thu FY2024", "Lợi nhuận sau thuế FY2024", "Doanh thu FY2023"],
    },
    tok: { in: 3980, out: 610, limit: 8000 },
  },
  {
    id: "TRC-DEMO-002", co: "VCB", q: "Tỷ lệ nợ xấu qua 4 quý gần nhất",
    s: "10:28:15.00", e: "10:28:15.61", st: "Không đủ bằng chứng", cat: "B",
    steps: [[40, "done"], [75, "done"], [280, "done"], [160, "done"], [58, "fail"], [0, "skip"], [0, "skip"]],
    vec: { ms: 280, found: 9, kept: 3, sel: 2 },
    gr: { ms: 160, found: 5, valid: 2, state: "Hoàn thành" },
    gate: { run: true, found: 5, passed: 3, elig: 2, minEv: 3, req: 4, have: 2, unit: "quý", st: "Không đạt" },
    ver: { run: false },
    tok: { in: 1850, out: 0, limit: 8000 },
  },
  {
    id: "TRC-DEMO-003", co: "MBB", q: "Biên lãi thuần FY2025",
    s: "10:25:11.00", e: null, st: "Đang xử lý", cat: "none",
    steps: [[40, "done"], [80, "done"], [300, "done"], [0, "run"], [0, "skip"], [0, "skip"], [0, "skip"]],
    vec: { ms: 300, found: 8, kept: 4, sel: null },
    gr: { ms: null, found: null, valid: null, state: "Đang chạy" },
    gate: { run: false },
    ver: { run: false },
    tok: { in: null, out: null, limit: 8000 },
  },
  {
    id: "TRC-DEMO-004", co: "TCB", q: "Tính toán tỷ lệ an toàn vốn CAR và CASA qua các quý",
    s: "10:19:22.00", e: "10:19:23.75", st: "Xác minh không đạt", cat: "C",
    steps: [[42, "done"], [82, "done"], [310, "done"], [190, "done"], [74, "done"], [820, "done"], [230, "fail"]],
    vec: { ms: 310, found: 12, kept: 5, sel: 3 },
    gr: { ms: 190, found: 7, valid: 4, state: "Hoàn thành" },
    gate: { run: true, found: 8, passed: 5, elig: 4, minEv: 3, req: 4, have: 3, unit: "quý", st: "Đạt một phần" },
    ver: {
      run: true, total: 5, sup: 3, thr: 80,
      cites: ["EV-DEMO-001", "EV-DEMO-002", null, "EV-DEMO-003", null],
      claims: ["CAR Q1/2025", "CAR Q2/2025", "CASA Q2/2025", "CASA Q1/2025", "Xu hướng CAR giữa các quý"],
      why: [null, null, "Thiếu bằng chứng: không tìm thấy nguồn đủ điều kiện cho đúng kỳ.", null, "Không đủ hỗ trợ."],
    },
    tok: { in: 4220, out: 685, limit: 8000 },
  },
  {
    id: "TRC-DEMO-005", co: "CMG", q: "Doanh thu theo mảng FY2025",
    s: "10:14:40.00", e: "10:14:40.92", st: "Lỗi vận hành", cat: "E",
    steps: [[41, "done"], [79, "done"], [300, "done"], [500, "fail"], [0, "skip"], [0, "skip"], [0, "skip"]],
    vec: { ms: 300, found: 10, kept: 4, sel: 3 },
    gr: { ms: 500, found: null, valid: null, state: "Không khả dụng", err: "Không thể truy cập graph service trong lần chạy này. Thông tin nhạy cảm đã được ẩn." },
    gate: { run: false },
    ver: { run: false },
    tok: { in: 1200, out: 0, limit: 8000 },
  },
  {
    id: "TRC-DEMO-006", co: "BID", q: "Tổng tài sản FY2025",
    s: "10:10:05.00", e: "10:10:06.72", st: "Lỗi vận hành", cat: "D",
    steps: [[40, "done"], [80, "done"], [300, "done"], [170, "done"], [70, "done"], [1060, "fail"], [0, "skip"]],
    vec: { ms: 300, found: 10, kept: 5, sel: 3 },
    gr: { ms: 170, found: 6, valid: 4, state: "Hoàn thành" },
    gate: { run: true, found: 8, passed: 5, elig: 4, minEv: 3, req: 3, have: 3, unit: "năm tài chính", st: "Đạt" },
    ver: { run: false },
    tok: { in: 5900, out: 2100, limit: 8000 },
  },
  {
    id: "TRC-DEMO-007", co: "CTG", q: "Vốn chủ sở hữu FY2024 và FY2025",
    s: "10:06:30.00", e: "10:06:31.90", st: "Thành công", cat: "none",
    steps: [[44, "done"], [90, "done"], [330, "done"], [200, "done"], [80, "done"], [900, "done"], [260, "done"]],
    vec: { ms: 330, found: 14, kept: 6, sel: 4 },
    gr: { ms: 200, found: 8, valid: 5, state: "Hoàn thành" },
    gate: { run: true, found: 9, passed: 6, elig: 5, minEv: 3, req: 2, have: 2, unit: "năm tài chính", st: "Đạt" },
    ver: {
      run: true, total: 5, sup: 5, thr: 80,
      cites: ["EV-DEMO-201", "EV-DEMO-202", "EV-DEMO-203", "EV-DEMO-204", "EV-DEMO-205"],
      claims: ["Vốn chủ sở hữu FY2025", "Vốn chủ sở hữu FY2024", "Biến động so với FY2024", "Cơ cấu vốn FY2025", "Cơ cấu vốn FY2024"],
    },
    tok: { in: 6350, out: 1100, limit: 8000 },
  },
];

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getTraces() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải danh sách truy vấn."));
      else resolve(tracesMock);
    }, 400);
  });
}
