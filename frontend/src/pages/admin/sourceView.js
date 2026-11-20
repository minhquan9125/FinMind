// Hiển thị cấu hình nguồn tin FireAnt thật và các lần thu thập gần nhất (chỉ đọc).

const yes = value => (value ? "Bật" : "Tắt");

/** Các dòng thông tin của cấu hình nguồn, theo thứ tự hiển thị. */
export function sourceRows(config) {
  if (!config) return [];
  return [
    { label: "Nhà cung cấp", value: config.provider === "fireant" ? "FireAnt" : (config.provider || "—") },
    { label: "Lịch chạy hằng ngày", value: config.enabled ? `Bật, từ ${String(config.hour).padStart(2, "0")}:00 (giờ Việt Nam)` : "Tắt" },
    { label: "Số bài tối đa mỗi lượt", value: config.limit },
    { label: "Số trang tối đa mỗi mã", value: config.max_pages },
    { label: "Mã theo dõi", value: (config.symbols || []).join(", ") || "Không có" },
    { label: "Tin thị trường chung", value: yes(config.include_market) },
    { label: "Tự động duyệt bài đạt kiểm tra nguồn", value: yes(config.auto_approve) },
    { label: "Tự động tạo chunk và lưu database", value: yes(config.auto_index) },
    { label: "Tự động chuyển corpus cho Chat", value: yes(config.auto_activate) },
  ];
}

/** Nhận định nhanh về trạng thái tự động hóa để người xem không phải tự ghép các ô Bật/Tắt. */
export function automationNote(config) {
  if (!config) return "";
  if (!config.enabled) return "Lịch hằng ngày đang tắt: chỉ thu thập khi bấm tay.";
  if (config.auto_activate) return "Chạy hằng ngày và tự chuyển corpus: dữ liệu mới vào Chat không cần bấm tay.";
  if (config.auto_index) return "Chạy hằng ngày và tự lưu database; lần lưu xong chờ bấm Chuyển corpus.";
  if (config.auto_approve) return "Chạy hằng ngày và tự duyệt; việc lưu database vẫn làm tay.";
  return "Chạy hằng ngày nhưng duyệt và lưu database vẫn làm tay.";
}

/** Các lần thu thập (CRAWL) mới nhất trước. */
export function crawlRuns(jobs, limit = 10) {
  return (jobs || []).filter(job => job.kind === "CRAWL")
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, limit);
}

/** Tóm tắt số liệu của một lần thu thập. */
export function runCounts(job) {
  const d = job?.details || {};
  const errors = Array.isArray(d.errors) ? d.errors.length : 0;
  return { fetched: d.fetched ?? null, created: d.new_articles ?? null, duplicates: d.duplicates ?? null, errors };
}
