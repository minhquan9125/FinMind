// Dữ liệu minh họa cho trang Tổng quan vận hành (từ A00-overview.html).
// Khi backend xong, thay getOverview() bằng hàm gọi API trong pages/admin/api.js.

export const overviewMock = {
  kpis: [
    { id: "queries", label: "Truy vấn hôm nay", value: "7" },
    { id: "success", label: "Truy vấn thành công", value: "2" },
    { id: "noEvidence", label: "Truy vấn không đủ bằng chứng", value: "1" },
    { id: "errors", label: "Lỗi vận hành", value: "2" },
    { id: "tokens", label: "Token đã sử dụng", value: "27,995" },
    { id: "budget", label: "Ngân sách API đã sử dụng", value: "61 / 100" },
  ],
  budget: { used: 61, limit: 100, warnAt: 80 },
  recentTraces: [
    { id: "TRC-DEMO-001", time: "10:32", company: "FPT", status: "Thành công", tone: "success", gate: { label: "Đạt", tone: "success" }, verifier: { label: "Đạt", tone: "success" }, duration: "1.64s", tokens: "4,590" },
    { id: "TRC-DEMO-002", time: "10:28", company: "VCB", status: "Không đủ bằng chứng", tone: "warning", gate: { label: "Không đạt", tone: "warning" }, verifier: null, duration: "0.61s", tokens: "1,850" },
    { id: "TRC-DEMO-003", time: "10:25", company: "MBB", status: "Đang xử lý", tone: "info", gate: null, verifier: null, duration: null, tokens: null },
    { id: "TRC-DEMO-004", time: "10:19", company: "TCB", status: "Xác minh không đạt", tone: "error", gate: { label: "Đạt một phần", tone: "warning" }, verifier: { label: "Không đạt", tone: "error" }, duration: "1.75s", tokens: "4,905" },
    { id: "TRC-DEMO-005", time: "10:14", company: "CMG", status: "Lỗi vận hành", tone: "error", gate: null, verifier: null, duration: "0.92s", tokens: "1,200" },
  ],
  alerts: [
    { id: "al-1", tone: "error", text: "Nguồn SSC kiểm tra kết nối thất bại", linkLabel: "Xem nguồn", to: "/admin/sources?source=src-4" },
    { id: "al-2", tone: "warning", text: "2 truy vấn lỗi vận hành hôm nay (CMG, BID)", linkLabel: "Xem trace", to: "/admin/traces?trace=TRC-DEMO-005" },
  ],
  activities: [
    { id: "AUD-DEMO-031", time: "20:45", text: "Cập nhật cấu hình CFG v2.5", ok: true },
    { id: "AUD-DEMO-030", time: "20:41", text: "Tạo cấu hình CFG v2.5", ok: true },
    { id: "AUD-DEMO-029", time: "20:30", text: "Kích hoạt Corpus v1.4", ok: true },
    { id: "AUD-DEMO-027", time: "19:58", text: "Tạo corpus freeze v1.6", ok: false },
  ],
  activityDate: "04/10/2026",
  services: [
    { id: "research-api", name: "Research API", desc: "Cổng tiếp nhận yêu cầu phân tích", ok: true },
    { id: "retrieval", name: "Retrieval Service", desc: "Động cơ truy hồi dữ liệu lai", ok: true },
    { id: "vector", name: "Vector Store", desc: "Kho lưu trữ biểu diễn ngữ nghĩa", ok: true },
    { id: "graph", name: "Graph Service", desc: "Đồ thị tri thức doanh nghiệp", ok: true },
    { id: "gate", name: "Evidence Gate", desc: "Bộ lọc đối soát bằng chứng", ok: true },
    { id: "verifier", name: "Verifier", desc: "Kiểm tra tính nhất quán tài chính", ok: true },
    { id: "telemetry", name: "Telemetry", desc: "Ghi nhận Trace & số đo hiệu năng", ok: true },
  ],
};

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getOverview() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải dữ liệu tổng quan vận hành."));
      else resolve(overviewMock);
    }, 400);
  });
}
