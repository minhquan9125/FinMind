import { makeCompanyDetail } from "./detailMock.js";

// Chỉ trả fixture. Khi có FastAPI, thay thân hàm bằng request GET /companies/:ticker.
export async function getCompanyDetail(ticker, fixture = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  if (fixture === "error") throw new Error("Không thể tải chi tiết doanh nghiệp minh họa.");
  if (fixture === "empty") return null;
  return makeCompanyDetail(ticker);
}
