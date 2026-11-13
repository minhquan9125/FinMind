// Khởi chạy lần chạy fixture WBS16 từ trang Job dữ liệu: kiểm tra tệp tải lên và trạng thái hiển thị.
// Backend kiểm tra lại toàn bộ; ở đây chỉ để báo lỗi sớm và không gửi những tệp chắc chắn sai.

export const MAX_BYTES = 8 * 1024 * 1024;
export const MAX_ARTICLES = 5000;

/** kind: "manifest" | "articles". Trả { ok: true, value } hoặc { ok: false, error }. */
export function parseUpload(kind, text, size = text?.length || 0) {
  if (size > MAX_BYTES) return { ok: false, error: "Tệp lớn hơn 8 MB." };
  let value;
  try { value = JSON.parse(text); } catch { return { ok: false, error: "Tệp không phải JSON hợp lệ." }; }
  if (kind === "manifest") {
    const valid = value && typeof value === "object" && !Array.isArray(value)
      && typeof value.corpus_version_id === "string" && value.corpus_version_id
      && /^[a-f0-9]{64}$/.test(value.manifest_sha256 || "") && value.manifest && typeof value.manifest === "object";
    return valid ? { ok: true, value } : { ok: false, error: "Manifest cần có corpus_version_id, manifest_sha256 (64 ký tự hex) và manifest." };
  }
  if (!Array.isArray(value)) return { ok: false, error: "Tệp bài viết phải là một mảng JSON." };
  if (value.length > MAX_ARTICLES) return { ok: false, error: `Tối đa ${MAX_ARTICLES} bài mỗi lần.` };
  if (!value.length) return { ok: false, error: "Tệp bài viết đang rỗng." };
  if (value.some(item => !item || typeof item !== "object" || !item.article_id)) return { ok: false, error: "Mỗi bài cần có article_id." };
  return { ok: true, value };
}

const ERRORS = {
  JOB_ALREADY_RUNNING: "Đang có một lần chạy khác. Đợi nó xong rồi chạy tiếp.",
  JOB_INPUT_TOO_LARGE: "Dữ liệu gửi lên lớn hơn 8 MB.",
};
export const launchErrorMessage = (code, status) =>
  ERRORS[code] || (status === 401 ? "Phiên đăng nhập hết hạn." : status === 403 ? "Tài khoản không có quyền quản trị."
    : status === 422 ? "Dữ liệu gửi lên chưa đúng định dạng." : "Không khởi chạy được.");

const FAILURE = {
  INPUT_VALIDATION_OR_IO_FAILED: "đầu vào không hợp lệ", WORKER_STOPPED: "tiến trình đã dừng giữa chừng",
  UNEXPECTED_ERROR: "lỗi không xác định",
};

/** Nhãn, tông màu và có mở được chi tiết hay không, theo trạng thái trả về của danh sách. */
export function jobStatusView(item) {
  switch (item?.status) {
    case "STAGED": return { label: "Đã xử lý đầu vào", tone: "neutral", linkable: true };
    case "RUNNING": return { label: "Đang chạy", tone: "warning", linkable: false };
    case "LAUNCH_FAILED": return { label: `Lỗi${item.reason ? `: ${FAILURE[item.reason] || item.reason}` : ""}`, tone: "error", linkable: false };
    case "INVALID_REPORT": return { label: "Báo cáo lỗi", tone: "warning", linkable: false };
    default: return { label: "Cần xử lý tiếp", tone: "warning", linkable: true };
  }
}

export const hasRunning = items => (items || []).some(item => item.status === "RUNNING");
