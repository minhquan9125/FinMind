// Dữ liệu minh họa cho trang Cấu hình nguồn dữ liệu (từ A02-sources.html).
// Khi backend xong, thay getSources() bằng hàm gọi API.
//
// Giá trị rỗng ("") nghĩa là chưa có dữ liệu; trang tự hiển thị "Chưa có dữ liệu".
// lastTest: "passed" | "failed" | "none".  willPassTest / failReason: chỉ để giả lập nút "Kiểm tra".

export const SOURCE_TYPES = [
  "Website chính thức", "Investor Relations", "HOSE", "HNX", "SSC", "Tệp CSV có kiểm soát", "API được phê duyệt",
];
export const ACCESS_METHODS = ["HTTP / Web", "API", "Tệp tải lên có kiểm soát"];
export const SCHEDULES = ["Hằng ngày", "Hằng tuần", "Thủ công"];
export const SOURCE_STATUSES = ["Hoạt động", "Tạm dừng", "Chưa kiểm tra", "Kiểm tra thất bại", "Vô hiệu hóa"];

const base = { owner: "FinMind Admin", url: "", fallback: "", terms: "", cred: "Chưa cấu hình", willPassTest: true };
const by = "Quản trị viên";

export const sourcesMock = [
  {
    ...base, id: "src-1", name: "FPT Investor Relations", type: "Investor Relations", access: "HTTP / Web",
    status: "Hoạt động", version: "v1.2", lastTest: "passed", testOk: true, schedule: "Hằng ngày",
    usage: "Tham chiếu báo cáo công bố của doanh nghiệp", scope: "Báo cáo công bố của FPT", fallback: "Nguồn HOSE",
    history: [
      { v: "v1.2", by, at: "10:15:00 Hôm nay", changed: ["Lịch cập nhật"] },
      { v: "v1.1", by, at: "09:30:00 Hôm qua", changed: ["Chủ sở hữu"] },
      { v: "v1.0", by, at: "08:00:00 12/03/2025", changed: ["Tạo cấu hình"] },
    ],
  },
  {
    ...base, id: "src-2", name: "HOSE", type: "HOSE", access: "HTTP / Web",
    status: "Hoạt động", version: "v1.0", lastTest: "passed", testOk: true, schedule: "Hằng ngày",
    usage: "Đối chiếu thông tin công bố niêm yết", scope: "Công bố thông tin của doanh nghiệp niêm yết",
    history: [{ v: "v1.0", by, at: "08:00:00 10/03/2025", changed: ["Tạo cấu hình"] }],
  },
  {
    ...base, id: "src-3", name: "HNX", type: "HNX", access: "HTTP / Web",
    status: "Chưa kiểm tra", version: "v1.0", lastTest: "none", testOk: false, schedule: "Hằng ngày",
    usage: "Đối chiếu thông tin công bố niêm yết", scope: "Công bố thông tin của doanh nghiệp niêm yết",
    history: [{ v: "v1.0", by, at: "08:00:00 09/03/2025", changed: ["Tạo cấu hình"] }],
  },
  {
    ...base, id: "src-4", name: "SSC", type: "SSC", access: "HTTP / Web",
    status: "Kiểm tra thất bại", version: "v1.1", lastTest: "failed", testOk: false, willPassTest: false,
    failReason: "Không thể truy cập endpoint", schedule: "Hằng tuần",
    usage: "Tham chiếu văn bản của cơ quan quản lý", scope: "",
    history: [
      { v: "v1.1", by, at: "14:20:00 11/03/2025", changed: ["Lịch cập nhật"] },
      { v: "v1.0", by, at: "08:00:00 08/03/2025", changed: ["Tạo cấu hình"] },
    ],
  },
  {
    ...base, id: "src-5", name: "Tệp CSV có kiểm soát", type: "Tệp CSV có kiểm soát", access: "Tệp tải lên có kiểm soát",
    status: "Tạm dừng", version: "v1.3", lastTest: "passed", testOk: true, schedule: "Thủ công",
    usage: "Bổ sung dữ liệu đã được phê duyệt", scope: "",
    history: [
      { v: "v1.3", by, at: "16:00:00 10/03/2025", changed: ["Trạng thái tạm dừng"] },
      { v: "v1.2", by, at: "11:15:00 09/03/2025", changed: ["Lịch cập nhật"] },
      { v: "v1.0", by, at: "08:00:00 05/03/2025", changed: ["Tạo cấu hình"] },
    ],
  },
  {
    ...base, id: "src-6", name: "API được phê duyệt", type: "API được phê duyệt", access: "API",
    status: "Vô hiệu hóa", version: "v1.0", lastTest: "none", testOk: false, owner: "", schedule: "",
    usage: "", scope: "",
    history: [{ v: "v1.0", by, at: "08:00:00 01/03/2025", changed: ["Tạo cấu hình"] }],
  },
];

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getSources() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải danh sách nguồn dữ liệu."));
      else resolve(sourcesMock.map((s) => ({ ...s, history: [...s.history] })));
    }, 400);
  });
}
