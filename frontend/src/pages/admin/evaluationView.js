// Hiển thị trang Đánh giá chất lượng (bộ câu hỏi chuẩn chạy qua Chat thật).
// Điểm là chấm tự động theo số liệu, chỉ để người kiểm tra xem nhanh, không phải kết luận đúng/sai.

const LEVELS = {
  PASS: { label: "Đạt", tone: "success" }, PARTIAL: { label: "Đạt một phần", tone: "warning" },
  FAIL: { label: "Chưa đạt", tone: "error" }, MANUAL: { label: "Cần người xem", tone: "neutral" },
  ERROR: { label: "Lỗi khi chạy", tone: "error" },
};
export const levelView = level => LEVELS[level] || { label: level || "Không rõ", tone: "neutral" };

const RUN_STATUS = { RUNNING: "Đang chạy", COMPLETED: "Hoàn tất", INTERRUPTED: "Đã dừng", FAILED: "Thất bại" };
export const runStatusLabel = status => RUN_STATUS[status] || status || "Không rõ";

/** Tỷ lệ đạt trên các câu chấm được (bỏ qua câu cần người xem). null nếu chưa có câu nào. */
export function passRate(summary) {
  const levels = summary?.levels || {};
  const scored = (summary?.total || 0) - (levels.MANUAL || 0);
  return scored > 0 ? (levels.PASS || 0) / scored : null;
}

export const percent = value => (value == null ? "—" : `${Math.round(value * 100)}%`);

export function runSummaryText(run) {
  const s = run?.summary;
  if (!s || !s.total) return "Chưa có kết quả";
  const score = s.mean_score == null ? "" : ` · điểm trung bình ${s.mean_score.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}`;
  const latency = s.mean_latency_ms == null ? "" : ` · ${(s.mean_latency_ms / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} giây/câu`;
  return `Đạt ${s.levels?.PASS || 0}/${s.total}${score}${latency}`;
}

export function progress(run) {
  if (!run || !run.total) return 0;
  return Math.min(100, Math.round((run.done / run.total) * 100));
}

/** Câu chữ cảnh báo trước khi chạy: mỗi câu là một lượt Chat thật. */
export function estimateNote(count) {
  const minutes = Math.max(1, Math.round((count * 15) / 60));
  return `Chạy ${count} câu hỏi sẽ tạo ${count} lượt Chat thật (mỗi lượt có thể gọi Gemini 1–2 lần, tính vào hạn mức) và mất khoảng ${minutes} phút. Tiếp tục?`;
}

export const canStart = (selected, runs) => selected.length > 0 && !(runs || []).some(run => run.status === "RUNNING");

export const categories = items => [...new Set((items || []).map(item => item.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, "vi"));

export function filterQuestions(items, { category = "", verifiedOnly = false, text = "" } = {}) {
  const needle = text.trim().toLowerCase();
  return (items || []).filter(item => (!category || item.category === category) && (!verifiedOnly || item.verified)
    && (!needle || `${item.id} ${item.question}`.toLowerCase().includes(needle)));
}

const ERRORS = {
  EVALUATION_ALREADY_RUNNING: "Đang có một lần chạy khác. Đợi nó xong hoặc dừng nó trước.",
  EVALUATION_UNKNOWN_QUESTION: "Có câu hỏi không còn trong bộ câu hỏi chuẩn. Tải lại trang.",
  EVALUATION_SET_NOT_FOUND: "Không tìm thấy file bộ câu hỏi chuẩn trên máy chủ.",
  EVALUATION_ENGINE_UNAVAILABLE: "Chat thật chưa sẵn sàng (chưa bật chế độ LIVE hoặc backend đang khởi động).",
  EVALUATION_NOT_RUNNING: "Lần chạy này đã kết thúc.",
  EVALUATION_NOT_FOUND: "Không tìm thấy lần chạy này.",
};
export const evaluationErrorMessage = (code, status) =>
  ERRORS[code] || (status === 401 ? "Phiên đăng nhập hết hạn." : status === 403 ? "Tài khoản không có quyền quản trị." : "Thao tác không thành công.");
