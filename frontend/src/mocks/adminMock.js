// Các mã, phiên bản và trạng thái lấy từ interface/admin/js/mockData.js.
// Các cột bổ sung chỉ phục vụ xem thử component, không phải dữ liệu vận hành thật.
export const sources = [
  { id: "src-1", name: "FPT Investor Relations", type: "Website", status: "Hoạt động", tone: "success" },
  { id: "src-2", name: "HOSE", type: "Website", status: "Hoạt động", tone: "success" },
  { id: "src-3", name: "HNX", type: "Website", status: "Chưa kiểm tra", tone: "neutral" },
  { id: "src-4", name: "SSC", type: "Website", status: "Kiểm tra thất bại", tone: "error" },
  { id: "src-5", name: "Tệp CSV có kiểm soát", type: "Tệp", status: "Tạm dừng", tone: "warning" },
  { id: "src-6", name: "API được phê duyệt", type: "API", status: "Vô hiệu hóa", tone: "neutral" },
];

export const traces = [
  { id: "TRC-DEMO-001", company: "FPT", status: "Thành công", tone: "success" },
  { id: "TRC-DEMO-002", company: "VCB", status: "Không đủ bằng chứng", tone: "warning" },
  { id: "TRC-DEMO-003", company: "MBB", status: "Đang xử lý", tone: "info" },
  { id: "TRC-DEMO-004", company: "TCB", status: "Xác minh không đạt", tone: "error" },
  { id: "TRC-DEMO-005", company: "CMG", status: "Lỗi vận hành", tone: "error" },
  { id: "TRC-DEMO-006", company: "BID", status: "Lỗi vận hành", tone: "error" },
  { id: "TRC-DEMO-007", company: "CTG", status: "Thành công", tone: "success" },
];

export const corpora = [
  { id: "v1.4", name: "Corpus v1.4", status: "Đang hoạt động", tone: "success" },
  { id: "v1.5", name: "Corpus v1.5", status: "Chưa kích hoạt", tone: "warning" },
  { id: "v1.6", name: "Corpus v1.6", status: "Đang chuẩn bị", tone: "info" },
  { id: "v1.3", name: "Corpus v1.3", status: "Đã lưu trữ", tone: "neutral" },
  { id: "v1.2", name: "Corpus v1.2", status: "Đã lưu trữ", tone: "neutral" },
  { id: "v1.1", name: "Corpus v1.1", status: "Kiểm tra không đạt", tone: "error" },
];

export const configs = [
  { id: "CFG v2.5", status: "Đang chờ kích hoạt", tone: "warning" },
  { id: "CFG v2.4", status: "Đang hoạt động", tone: "success" },
  { id: "CFG v2.3", status: "Đã thay thế", tone: "neutral" },
  { id: "CFG v2.2", status: "Đã thay thế", tone: "neutral" },
];

export const adminFixtures = {
  sources: { success: sources, empty: [], error: "Không thể tải danh sách nguồn minh họa." },
  traces: { success: traces, empty: [], error: "Không thể tải danh sách trace minh họa." },
  corpora: { success: corpora, empty: [], error: "Không thể tải phiên bản corpus minh họa." },
  configs: { success: configs, empty: [], error: "Không thể tải cấu hình minh họa." },
};
