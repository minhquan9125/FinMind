export const QUALITY_REASONS = {
  SHORT_OR_EMPTY_BODY: "Nội dung quá ngắn hoặc chưa lấy được phần chữ",
  ATTACHMENT_TEXT_REQUIRED: "Thông báo ngắn — cần đọc tệp đính kèm",
  OCR_REQUIRED: "Nội dung dạng ảnh — cần OCR",
  OCR_REVIEW_REQUIRED: "Đã đọc PDF/OCR — cần kiểm tra nội dung trước khi duyệt",
  SHORT_TITLE: "Thiếu tiêu đề rõ ràng",
  UNCONFIRMED_PROVIDER_SOURCE: "Cần xác minh URL hoặc ID nguồn",
  UNCONFIRMED_PUBLICATION_DATE: "Cần xác minh ngày đăng",
  PROVIDER_BODY_DATE_CHECKS_PASSED: "Đạt kiểm tra nguồn, nội dung và ngày đăng",
};
export function qualityLabel(code) { return QUALITY_REASONS[code] || code; }
export function replacementArticleId(detail) {
  if (detail?.replacement_article_id) return detail.replacement_article_id;
  const pattern = /^Đã thay bằng bản trích xuất cần duyệt: ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;
  return [...(detail?.reviews || [])].reverse().map(r => r.note?.match(pattern)?.[1]).find(Boolean) || null;
}
export function reviewNote(note = "") {
  if (!/^source-quality-v\d+: /.test(note)) return note;
  return note.replace(/^source-quality-v\d+: /, "Tự động: ").split(",").map(part =>
    part.startsWith("Tự động: ") ? "Tự động: " + qualityLabel(part.slice(9)) : qualityLabel(part)).join("; ");
}
