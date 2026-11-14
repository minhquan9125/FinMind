import { authorizedHeaders } from "../../shared/api/authorization.js";

export async function getOperations(path, signal, options = {}) {
  const base = (import.meta.env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) abort();
  const timer = setTimeout(abort, 15000);
  try {
    const response = await fetch(`${base}/api/v1/admin/ingestion${path}`, {
      method: options.method || "GET", body: options.body === undefined ? undefined : JSON.stringify(options.body),
      headers: authorizedHeaders(options.body === undefined ? {} : { "Content-Type": "application/json" }), signal: controller.signal, cache: "no-store",
    });
    if (!response.ok) throw new Error(response.status === 401 ? "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại."
      : response.status === 403 ? "Tài khoản không có quyền quản trị." : response.status === 409 ? "Cấu hình đã được người khác sửa. Hãy tải lại trước khi lưu."
      : response.status === 422 ? "Dữ liệu hoặc bộ lọc chưa hợp lệ. Kiểm tra lại các trường nhập."
      : response.status === 404 ? "Không tìm thấy bản ghi này." : "Không tải được dữ liệu quản trị. Hãy thử lại.");
    return await response.json();
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error("Tải dữ liệu quá thời gian. Hãy thử lại.");
    throw error;
  } finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
}

export function localTime(value) {
  return value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "—";
}

export const STATE_LABELS = { PENDING: "Chờ duyệt", APPROVED: "Đã duyệt", INDEXED: "Đã xử lý",
  QUARANTINED: "Cần kiểm tra", REJECTED: "Đã từ chối", SUPERSEDED: "Đã thay bằng bản OCR",
  QUEUED: "Đang đợi", RUNNING: "Đang xử lý", ACTIVE: "Đã nạp xong", COMPLETED: "Hoàn tất",
  PARTIAL: "Có lỗi thu thập", FAILED: "Thất bại", INTERRUPTED: "Đã ngắt" };
