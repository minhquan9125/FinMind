export function readNewsGraphPackage(text) {
  let data;
  try { data = JSON.parse(text); } catch { throw new Error("File không phải JSON hợp lệ."); }
  if (!data || !Array.isArray(data.items) || !data.items.length || data.items.length > 20)
    throw new Error("File cần chứa từ 1 đến 20 quan hệ cùng bằng chứng nguồn.");
  if (data.graph_version_id != null && (typeof data.graph_version_id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.graph_version_id)))
    throw new Error("Mã phiên graph trong file không hợp lệ.");
  const ids = new Set();
  for (const row of data.items) {
    const value = row?.candidate;
    if (!value || typeof value.candidate_id !== "string" || !value.candidate_id.trim()
        || ids.has(value.candidate_id) || typeof value.relation_type !== "string"
        || ![value.subject?.canonical_name, value.object?.canonical_name].every(name => typeof name === "string" && name.trim())
        || !Array.isArray(value.evidence) || !value.evidence.length
        || value.evidence.some(e => !e || typeof e.quote !== "string" || !e.quote.trim()
          || typeof e.chunk_id !== "string" || !e.locator || typeof e.locator !== "object"))
      throw new Error("Quan hệ thiếu tên, mã duy nhất hoặc đoạn bằng chứng hợp lệ.");
    if ([value.attributes?.cooperation_scope, value.attributes?.position].some(v => v != null && typeof v !== "string")
        || (value.temporal?.as_of != null && (typeof value.temporal.as_of !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value.temporal.as_of))))
      throw new Error("Phạm vi hoặc ngày trong nguồn chưa đúng định dạng.");
    ids.add(value.candidate_id);
  }
  // A file's claimed evaluation/approval is never restored as server state.
  return { graph_version_id: data.graph_version_id,
    items: data.items.map(row => ({ candidate: row.candidate, title: row.title })) };
}

export function newsGraphError(status, detail) {
  if (status === 401 || status === 403) return "Cần đăng nhập bằng tài khoản có quyền quản trị.";
  const code = typeof detail === "string" ? detail : detail?.code;
  const messages = {
    QUARANTINE_HISTORY_MISSING: "Không lưu được lịch sử duyệt do thiếu bản ghi đối chiếu. Cần kiểm tra luồng lưu duyệt, không phải bổ sung bài nguồn.",
    CANDIDATE_CONTENT_CHANGED: "Nội dung quan hệ đã khác bản lưu trước đó. Cần tạo bản trích xuất mới, không ghi đè bản cũ.",
    REVIEW_REVISION_CHANGED: "Quyết định đã được cập nhật ở lượt khác. Hãy tải lại trạng thái trước khi duyệt.",
    GRAPH_VERSION_NOT_REVIEWABLE: "Phiên graph đã công bố hoặc không còn cho phép sửa quyết định.",
    NO_APPROVED_NEWS_RELATIONS: "Chưa có quan hệ NEWS đã lưu quyết định duyệt để nạp.",
    NEWS_REVIEW_NOT_READY: "Lần kiểm tra lại chưa đạt. Bấm Kiểm tra nguồn để xem điều kiện còn thiếu.",
    NEWS_WRITER_NOT_CONFIGURED: "Backend chưa có cấu hình ghi quyết định duyệt. Cần cấu hình tài khoản vận hành.",
    REJECTED_CANDIDATE_IS_TERMINAL: "Bản này đã bị từ chối. Cần gửi bản trích xuất sửa đổi với mã mới.",
  };
  return messages[code] || (status >= 500 ? "Dịch vụ lưu hoặc nạp quan hệ đang gặp lỗi. Vui lòng thử lại sau."
    : "Chưa thể hoàn tất. Hãy kiểm tra nguồn và trạng thái duyệt mới nhất.");
}
