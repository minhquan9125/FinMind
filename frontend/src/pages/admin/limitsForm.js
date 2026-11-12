// Biểu mẫu giới hạn trả lời (token, số lượt, thời gian chờ) và trạng thái xoay khóa Gemini.
// Mọi kiểm tra ở đây chỉ để báo lỗi sớm; backend mới là nơi kiểm tra cuối cùng.

export const LIMIT_FIELDS = [
  { key: "max_input_tokens", label: "Token đầu vào tối đa", hint: "Độ dài tối đa của câu hỏi cộng nguồn gửi cho model" },
  { key: "max_output_tokens", label: "Token đầu ra tối đa", hint: "Độ dài tối đa của câu trả lời do model sinh" },
  { key: "max_total_tokens", label: "Tổng token tối đa mỗi câu hỏi", hint: "Trần cộng dồn trong một lượt hỏi" },
  { key: "max_generation_calls", label: "Số lần gọi model tối đa mỗi câu hỏi", hint: "Áp dụng riêng cho từng câu hỏi" },
  { key: "read_timeout_seconds", label: "Thời gian chờ model (giây)", hint: "Quá thời gian này thì báo lỗi, không tự gọi lại" },
];

export const draftFrom = values => Object.fromEntries(LIMIT_FIELDS.map(({ key }) => [key, String(values?.[key] ?? "")]));

/** Chuỗi nhập → lỗi theo từng ô (rỗng nếu hợp lệ). */
export function validateDraft(draft, bounds) {
  const errors = {};
  for (const { key } of LIMIT_FIELDS) {
    const raw = String(draft?.[key] ?? "").trim();
    const range = bounds?.[key];
    if (!/^\d+$/.test(raw)) { errors[key] = "Nhập số nguyên"; continue; }
    const value = Number(raw);
    if (range && (value < range.min || value > range.max)) errors[key] = `Trong khoảng ${range.min.toLocaleString("vi-VN")}–${range.max.toLocaleString("vi-VN")}`;
  }
  if (!errors.max_total_tokens && !errors.max_output_tokens && Number(draft.max_total_tokens) < Number(draft.max_output_tokens)) {
    errors.max_total_tokens = "Không được nhỏ hơn token đầu ra tối đa";
  }
  return errors;
}

/** Các giá trị khác mặc định, đúng dạng backend lưu; rỗng nghĩa là quay về mặc định. */
export function overridesFrom(draft, defaults) {
  const result = {};
  for (const { key } of LIMIT_FIELDS) {
    const value = Number(String(draft[key]).trim());
    if (value !== defaults?.[key]) result[key] = value;
  }
  return result;
}

export const isUnchanged = (overrides, current) => JSON.stringify(sorted(overrides)) === JSON.stringify(sorted(current || {}));
const sorted = object => Object.fromEntries(Object.entries(object).sort(([a], [b]) => a.localeCompare(b)));

const ERROR_TEXT = {
  LIMITS_CONFIG_CHANGED: "Người khác vừa lưu một phiên bản mới. Tải lại rồi sửa tiếp.",
  LIMITS_OUT_OF_RANGE: "Có giá trị nằm ngoài khoảng cho phép.",
  LIMITS_FIELD_NOT_EDITABLE: "Có trường không được phép sửa.",
  LIMITS_INCONSISTENT: "Các giá trị không khớp nhau (tổng token phải lớn hơn hoặc bằng token đầu ra).",
  LIMITS_REASON_REQUIRED: "Cần nhập lý do thay đổi (ít nhất 3 ký tự).",
};
export const limitsErrorMessage = (code, status) =>
  ERROR_TEXT[code] || (status === 401 ? "Phiên đăng nhập hết hạn." : status === 403 ? "Tài khoản không có quyền quản trị." : "Không lưu được cấu hình.");

const KEY_STATES = { ready: { label: "Sẵn sàng", tone: "success" }, quota: { label: "Hết hạn mức tạm thời", tone: "warning" }, invalid: { label: "Bị từ chối / không hợp lệ", tone: "error" } };
export function keyStatusView(item) {
  const state = KEY_STATES[item?.state] || { label: item?.state || "Không rõ", tone: "neutral" };
  const wait = item?.retry_in_seconds || 0;
  const retry = wait <= 0 ? "" : wait >= 3600 ? ` · thử lại sau ${Math.round(wait / 3600)} giờ` : wait >= 60 ? ` · thử lại sau ${Math.round(wait / 60)} phút` : ` · thử lại sau ${wait} giây`;
  return { name: item?.key || "key", label: state.label + retry, tone: state.tone };
}

// ---- khóa Gemini thêm từ trang web ----------------------------------------------------------

// Google cấp hai dạng khóa: "AIza..." (cũ) và "AQ.xxxx" (mới, có dấu chấm).
export const KEY_PATTERN = /^(?:AIza[0-9A-Za-z_-]{30,60}|AQ\.[0-9A-Za-z_.-]{30,100})$/;

/** Lỗi nhập sớm cho biểu mẫu thêm khóa; backend kiểm tra lại. Không bao giờ chứa nội dung khóa. */
export function validateKeyForm({ label = "", key = "" } = {}) {
  const errors = {};
  const name = label.trim();
  if (!name || name.length > 60) errors.label = "Đặt tên gợi nhớ, tối đa 60 ký tự";
  if (!KEY_PATTERN.test(key.trim())) errors.key = "Khóa Gemini bắt đầu bằng AIza hoặc AQ. và không có khoảng trắng bên trong";
  return errors;
}

const KEY_ERRORS = {
  KEY_FORMAT_INVALID: "Khóa không đúng định dạng.",
  KEY_LABEL_INVALID: "Tên gợi nhớ không hợp lệ.",
  KEY_DUPLICATE: "Khóa này đã có (trên trang này hoặc trong .env).",
  KEY_REJECTED: "Google từ chối khóa này. Kiểm tra lại khóa, chưa lưu.",
  KEY_LIMIT_REACHED: "Đã đạt số khóa tối đa. Xóa bớt khóa không dùng.",
  KEY_NOT_FOUND: "Không tìm thấy khóa này.",
  KEY_STORE_DISABLED: "Chưa bật kho khóa: cần đặt GEMINI_KEYS_SECRET (ít nhất 16 ký tự) trong backend/.env rồi khởi động lại backend.",
  KEY_BODY_INVALID: "Dữ liệu gửi lên không hợp lệ.",
};
export const keyErrorMessage = (code, status) =>
  KEY_ERRORS[code] || (status === 401 ? "Phiên đăng nhập hết hạn." : status === 403 ? "Tài khoản không có quyền quản trị." : "Không thực hiện được.");

/** Câu nhận định sau khi thêm khóa, dựa trên kết quả kiểm tra với Google. */
export function addResultNote(result) {
  const checks = { OK: "Google chấp nhận khóa.", QUOTA: "Khóa hợp lệ nhưng đang hết hạn mức, sẽ tự dùng lại khi hồi.",
    UNAVAILABLE: "Chưa kiểm tra được với Google (mạng hoặc dịch vụ), khóa vẫn được lưu." };
  const base = checks[result?.verification] || "Đã lưu khóa.";
  return result?.restart_needed ? `${base} Chat chưa chạy Gemini lúc khởi động nên cần khởi động lại backend một lần để bắt đầu dùng.` : `${base} Có hiệu lực ngay, không cần khởi động lại.`;
}

/** Hiển thị một khóa đã thêm: chỉ tên, 4 ký tự cuối và trạng thái. */
export function managedKeyView(item) {
  const state = !item.readable ? { label: "Không đọc được (khóa mã hóa đã đổi)", tone: "error" }
    : !item.enabled ? { label: "Đang tắt", tone: "neutral" }
    : item.verified ? { label: "Đã kiểm tra", tone: "success" } : { label: "Chưa kiểm tra", tone: "neutral" };
  return { id: item.id, name: item.label, tail: `…${item.last4}`, ...state };
}

export const testResultLabel = result => ({ OK: "Khóa dùng được.", QUOTA: "Khóa hợp lệ nhưng đang hết hạn mức.", INVALID: "Google từ chối khóa này.", UNAVAILABLE: "Chưa kiểm tra được với Google." })[result] || "Không rõ.";
