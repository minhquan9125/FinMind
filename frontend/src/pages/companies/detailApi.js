import { companyPlaceholder } from "./companySearch.js";
import { getCompanyFinancials } from "./financials.js";

// `fixture` giữ lại để thử trạng thái rỗng/lỗi qua ?fixture=...; mặc định gọi backend.
export async function getCompanyDetail(ticker, fixture = "success") {
  if (fixture === "error") throw new Error("Không thể tải chi tiết doanh nghiệp.");
  if (fixture === "empty") return null;
  const company = await getCompanyFinancials(ticker);
  if (company) return company;
  const placeholder = companyPlaceholder(ticker);
  return placeholder && { ...placeholder, isPlaceholder: true };
}
