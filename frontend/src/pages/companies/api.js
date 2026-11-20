import { getCompanyCatalog } from "./financials.js";

// `fixture` giữ lại để thử trạng thái rỗng/lỗi qua ?fixture=...; mặc định gọi backend.
export async function getCompanies(fixture = "success") {
  if (fixture === "error") throw new Error("Không thể tải danh sách doanh nghiệp.");
  if (fixture === "empty") return [];
  return getCompanyCatalog();
}
