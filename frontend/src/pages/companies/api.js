import { authorizedFetch } from "../../shared/api/authorization.js";

const apiBase = (import.meta.env?.VITE_MARKET_DATA_API_URL || "").replace(/\/$/, "");

export async function readCompanyData(path) {
  let response;
  try {
    response = await authorizedFetch(`${apiBase}/api/companies${path}`);
  } catch (error) {
    if (error.status === 401 || error.name === "AbortError") throw error;
    throw new Error("Không kết nối được API dữ liệu. Hãy kiểm tra backend đang chạy.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw Object.assign(new Error(typeof body?.detail === "string" ? body.detail : `API trả lỗi ${response.status}.`), { status: response.status });
  }
  return response.json();
}

export async function getCompanies(fixture = "success") {
  if (fixture === "error") throw new Error("Không thể tải danh sách doanh nghiệp minh họa.");
  if (fixture === "empty") return [];
  if (fixture === "loading") return new Promise(() => {});
  const companies = await readCompanyData("");
  return companies.map(({ id, name, sector, exchange, has_financials }) => ({
    id, name, sector: sector || "Chưa phân ngành", exchange,
    status: has_financials ? "Có dữ liệu" : "Chưa có BCTC",
    tone: has_financials ? "success" : "neutral",
  }));
}
