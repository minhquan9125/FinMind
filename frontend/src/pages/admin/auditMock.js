// Dữ liệu minh họa cho trang Nhật ký kiểm toán (từ A05-audit.html).
// Khi backend xong, thay getAuditEvents() bằng hàm gọi API.
//
// Mỗi sự kiện: trace / config / corpus / source là các thành phần liên quan (null nếu không có);
// sanitized: các trường nhạy cảm đã được ẩn; retentionExpired: bản ghi đã ngoài thời hạn lưu giữ.

export const ACTION_TYPES = [
  "Đăng nhập", "Kiểm tra nguồn", "Bật nguồn", "Tạm dừng nguồn", "Tạo corpus freeze", "Kích hoạt corpus",
  "Thay đổi configuration", "Khôi phục configuration", "Xem operational trace",
];
export const RESOURCE_TYPES = ["Phiên đăng nhập", "Source adapter", "Corpus", "Configuration", "Trace"];
export const ACTORS = ["System Admin", "Chưa xác định"];
export const RESULTS = ["Thành công", "Thất bại"];

const ok = "Thành công";
const fail = "Thất bại";
const links = { reason: null, trace: null, config: null, corpus: null, source: null, sanitized: null, retentionExpired: false };
const admin = { actor: "System Admin", role: "System Admin" };
const ev = (id, time, action, type, rtype, resource, result, extra = {}) => ({
  ...links, ...admin, id, time: `04/10/2026 ${time}`, action, type, rtype, resource, result, ...extra,
});

export const auditMock = [
  ev("AUD-DEMO-031", "20:45", "Cập nhật cấu hình CFG v2.5", "Thay đổi configuration", "Configuration", "CFG v2.5", ok, { config: "v2.5", corpus: "v1.4" }),
  ev("AUD-DEMO-030", "20:41", "Tạo cấu hình CFG v2.5", "Thay đổi configuration", "Configuration", "CFG v2.5", ok, { config: "v2.5" }),
  ev("AUD-DEMO-029", "20:30", "Kích hoạt corpus", "Kích hoạt corpus", "Corpus", "Corpus v1.4", ok, { corpus: "v1.4" }),
  ev("AUD-DEMO-028", "20:12", "Tạo corpus freeze", "Tạo corpus freeze", "Corpus", "Corpus v1.5", ok, { corpus: "v1.5" }),
  ev("AUD-DEMO-027", "19:58", "Tạo corpus freeze", "Tạo corpus freeze", "Corpus", "Corpus v1.6", fail, {
    corpus: "v1.6", reason: "Không thể tạo phiên bản corpus: 1 tài liệu thiếu publication date, 1 tài liệu hash verification không đạt.",
  }),
  ev("AUD-DEMO-026", "19:40", "Bật nguồn", "Bật nguồn", "Source adapter", "HNX", fail, { source: "src-3", reason: "Kiểm tra kết nối chưa đạt." }),
  ev("AUD-DEMO-025", "19:35", "Kiểm tra nguồn", "Kiểm tra nguồn", "Source adapter", "SSC", fail, { source: "src-4", reason: "Không thể truy cập endpoint." }),
  ev("AUD-DEMO-024", "19:20", "Tạm dừng nguồn", "Tạm dừng nguồn", "Source adapter", "Tệp CSV có kiểm soát", ok, { source: "src-5" }),
  ev("AUD-DEMO-023", "19:05", "Khôi phục configuration", "Khôi phục configuration", "Configuration", "CFG v2.3", ok, { config: "v2.3" }),
  ev("AUD-DEMO-022", "18:50", "Xem operational trace", "Xem operational trace", "Trace", "TRC-DEMO-004", ok, { trace: "TRC-DEMO-004", config: "v2.4", corpus: "v1.4" }),
  ev("AUD-DEMO-021", "18:44", "Xem operational trace", "Xem operational trace", "Trace", "TRC-DEMO-002", ok, { trace: "TRC-DEMO-002", config: "v2.4", corpus: "v1.4" }),
  ev("AUD-DEMO-020", "18:30", "Đăng nhập", "Đăng nhập", "Phiên đăng nhập", "Phiên quản trị", ok, { sanitized: { Authorization: "[ĐÃ ẨN]" } }),
  ev("AUD-DEMO-019", "18:29", "Đăng nhập", "Đăng nhập", "Phiên đăng nhập", "Phiên quản trị", fail, {
    actor: "Chưa xác định", role: "—", reason: "Thông tin đăng nhập không hợp lệ.",
    sanitized: { Authorization: "[ĐÃ ẨN]", "Thông tin xác thực": "[ĐÃ ẨN]" },
  }),
  ev("AUD-DEMO-018", "17:55", "Bật nguồn", "Bật nguồn", "Source adapter", "FPT Investor Relations", ok, { source: "src-1" }),
  ev("AUD-DEMO-017", "17:50", "Kiểm tra nguồn", "Kiểm tra nguồn", "Source adapter", "FPT Investor Relations", ok, { source: "src-1", sanitized: { Authorization: "[ĐÃ ẨN]" } }),
  {
    ...links, id: "AUD-DEMO-003", time: "—", actor: "—", role: "—", action: "—", type: "—", rtype: "—", resource: "—", result: "—", retentionExpired: true,
  },
];

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getAuditEvents() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải nhật ký kiểm toán."));
      else resolve(auditMock.map((e) => ({ ...e, sanitized: e.sanitized ? { ...e.sanitized } : null })));
    }, 400);
  });
}
