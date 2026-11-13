// Cờ tự động hóa chuỗi: thu thập → duyệt → tạo chunk/vector và lưu DB → chuyển corpus.
// Chỉ là logic hiển thị; backend là nơi quyết định và kiểm tra.

/** Cập nhật cờ, giữ ràng buộc: chuyển corpus tự động chỉ có nghĩa khi đã bật lưu DB tự động. */
export function withPipelineFlag(source, flag, value) {
  const next = { ...source, [flag]: value };
  if (flag === "auto_index" && !value) next.auto_activate = false;
  if (flag === "auto_activate" && value) next.auto_index = true;
  return next;
}

/** Mô tả những bước sẽ tự chạy với cấu hình hiện tại. */
export function pipelineSummary(source) {
  const steps = ["Thu thập"];
  if (source?.auto_approve) steps.push("duyệt tự động");
  if (source?.auto_index) steps.push("tạo chunk/vector và lưu vào database");
  if (source?.auto_activate) steps.push("chuyển corpus cho Chat");
  return steps.join(" → ");
}

/** Lần nạp đã lưu vào DB nhưng chưa chuyển corpus thì mới có nút "Chuyển corpus". */
export function canActivate(job) {
  return job?.kind === "INDEX" && job.status === "INDEXED" && Boolean(job.details?.manifest_sha256)
    && !job.details?.recovery_job_id;
}

const SKIPPED = {
  AUTO_INDEX_OFF: "Chưa bật tự động lưu database",
  NO_APPROVED_ARTICLES: "Không có bài đã duyệt để lưu",
  CRAWL_NOT_COMPLETED: "Lần thu thập chưa hoàn tất",
  ANOTHER_JOB_IS_RUNNING: "Đang có job khác chạy",
  ADMIN_INGEST_DATABASE_URL_REQUIRED: "Chưa cấu hình kết nối ghi database",
};

/** Kết quả chạy nối tiếp ghi trên lần thu thập; null nếu lần đó không chạy nối tiếp. */
export function pipelineResult(job) {
  const result = job?.details?.pipeline;
  if (!result) return null;
  if (result.error) return { tone: "error", text: `Tự động dừng ở bước lưu database: ${result.error}` };
  if (result.skipped) return { tone: "neutral", text: `Chạy nối tiếp bỏ qua: ${SKIPPED[result.skipped] || result.skipped}` };
  const count = result.articles ? ` ${result.articles} bài` : "";
  if (result.index_status === "ACTIVE") return { tone: "success", text: `Đã lưu${count} vào database và chuyển corpus` };
  if (result.index_status === "INDEXED") return { tone: "warning", text: `Đã lưu${count} vào database, chờ bấm Chuyển corpus` };
  return { tone: "neutral", text: `Lần lưu database: ${result.index_status || "đang chạy"}` };
}

const SKIP_REASON = {
  NOT_APPROVED: "không còn ở trạng thái Đã duyệt",
  IN_INDEX_JOB: "đang nằm trong lần lưu database chưa chuyển corpus",
  NOT_FOUND: "không còn tồn tại",
};

/** Thông báo sau khi xóa bài: số bài đã xóa và lý do từng nhóm bị bỏ qua. */
export function deleteResultMessage(result) {
  const deleted = result?.deleted?.length || 0;
  const groups = {};
  for (const item of result?.skipped || []) groups[item.reason] = (groups[item.reason] || 0) + 1;
  const skipped = Object.entries(groups).map(([reason, n]) => `${n} bài ${SKIP_REASON[reason] || reason}`);
  const head = deleted ? `Đã xóa ${deleted} bài.` : "Không xóa được bài nào.";
  return skipped.length ? `${head} Bỏ qua: ${skipped.join("; ")}.` : head;
}
