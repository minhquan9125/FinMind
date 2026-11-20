// Nhãn hiển thị cho trang Phiên bản kho dữ liệu (dữ liệu thật, chỉ đọc).

export const DOC_TYPE_LABELS = {
  FINANCIAL_STATEMENT: "Báo cáo tài chính", ANNUAL_REPORT: "Báo cáo thường niên", NEWS: "Tin tức",
  COMPANY_PROFILE: "Hồ sơ doanh nghiệp", PRICE_HISTORY: "Lịch sử giá", MARKET_INDEX: "Chỉ số thị trường",
  MARKET_SNAPSHOT: "Ảnh chụp thị trường", CORPORATE_DISCLOSURE: "Công bố thông tin",
};
const CORPUS_STATUS = { FROZEN: "Đã đóng băng", DRAFT: "Bản nháp", ARCHIVED: "Đã lưu trữ" };
const INDEX_STATUS = { ACTIVE: "Đang hoạt động", BUILDING: "Đang xây dựng", FAILED: "Lỗi", ARCHIVED: "Đã lưu trữ" };

export const docTypeLabel = type => DOC_TYPE_LABELS[type] || type || "Không rõ";
export const corpusStatusLabel = status => CORPUS_STATUS[status] || status || "Không rõ";
export const indexStatusLabel = status => INDEX_STATUS[status] || status || "Chưa có chỉ mục";
export const shortId = id => (typeof id === "string" ? id.slice(0, 8) : "—");

/** Tông màu huy hiệu: chỉ mục hoạt động là xanh, đang xây dựng là vàng, còn lại trung tính. */
export function indexTone(status) {
  if (status === "ACTIVE") return "success";
  if (status === "BUILDING") return "warning";
  if (status === "FAILED") return "error";
  return "neutral";
}

/** Các loại tài liệu của một phiên, nhiều nhất trước, dạng [{type,label,count}]. */
export function typeBreakdown(byType) {
  return Object.entries(byType || {})
    .map(([type, count]) => ({ type, label: docTypeLabel(type), count: Number(count) }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "vi"));
}

/** Phiên đang phục vụ Chat lên đầu, còn lại giữ nguyên thứ tự backend (mới nhất trước). */
export function servingFirst(items) {
  return [...(items || [])].sort((a, b) => Number(!!b.serving) - Number(!!a.serving));
}

export function pageLabel(page) {
  if (!page?.total) return "0 tài liệu";
  return `${page.offset + 1}–${Math.min(page.offset + page.limit, page.total)} / ${page.total.toLocaleString("vi-VN")}`;
}

/** Thao tác khả dụng cho một phiên, theo trạng thái thật. Phiên đang phục vụ không được lưu trữ. */
export function availableActions(item) {
  if (!item) return [];
  const actions = [];
  if (!item.serving && item.servable) {
    actions.push({ id: "serve", label: "Chuyển Chat sang phiên này", tone: "primary",
      confirm: `Chuyển Chat sang phiên ${shortId(item.corpus_version_id)}? Mọi người dùng chung backend này sẽ hỏi trên dữ liệu của phiên đó. Có thể chuyển lại bất cứ lúc nào.` });
  }
  if (item.status === "FROZEN" && !item.serving) {
    actions.push({ id: "archive", label: "Lưu trữ", tone: "secondary",
      confirm: `Lưu trữ phiên ${shortId(item.corpus_version_id)}? Phiên đã lưu trữ không thể phục vụ Chat cho tới khi khôi phục.` });
  }
  if (item.status === "ARCHIVED") {
    actions.push({ id: "restore", label: "Khôi phục", tone: "secondary",
      confirm: `Khôi phục phiên ${shortId(item.corpus_version_id)} về trạng thái đã đóng băng?` });
  }
  return actions;
}

const ACTION_ERRORS = {
  CORPUS_NOT_FOUND: "Không tìm thấy phiên này.",
  CORPUS_NOT_SERVABLE: "Phiên này chưa phục vụ được: cần đã đóng băng, chỉ mục đang hoạt động và có manifest.",
  ALREADY_SERVING: "Chat đang dùng phiên này rồi.",
  CORPUS_IN_USE: "Phiên đang được Chat dùng hoặc là phiên nền mặc định nên không lưu trữ được.",
  CORPUS_STATE_CHANGED: "Trạng thái phiên vừa thay đổi. Làm mới rồi thử lại.",
  ADMIN_INGEST_DATABASE_URL_REQUIRED: "Chưa cấu hình kết nối ghi database cho admin.",
  CORPUS_UNAVAILABLE: "Chưa kết nối được database. Thử lại sau.",
};
export const actionErrorMessage = (code, status) =>
  ACTION_ERRORS[code] || (status === 401 ? "Phiên đăng nhập hết hạn." : status === 403 ? "Tài khoản không có quyền quản trị." : "Thao tác không thành công.");

export function actionSuccessMessage(id, result) {
  if (id === "serve") return `Chat đã chuyển sang phiên ${shortId(result?.corpus_version_id)}${result?.warmed ? "" : ". Câu hỏi đầu tiên có thể chậm hơn vì còn nạp bộ nhớ tìm kiếm"}.`;
  if (id === "archive") return `Đã lưu trữ phiên ${shortId(result?.corpus_version_id)}.`;
  return `Đã khôi phục phiên ${shortId(result?.corpus_version_id)}.`;
}
