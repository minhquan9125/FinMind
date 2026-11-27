// Company catalog and BCTC facts from the backend (/api/companies), shared by the company and compare pages.
import { authorizedFetch } from "../../shared/api/authorization.js";

async function readJson(path, signal) {
  const response = await authorizedFetch(`/api/companies${path}`, { cache: "no-store", signal });
  if (response.status === 404) return null;
  if (!response.ok) {
    let body = null;
    try { body = await response.json(); } catch { /* API may return an empty error body. */ }
    throw Object.assign(new Error(response.status === 403 ? "Tài khoản không có quyền xem dữ liệu doanh nghiệp."
      : typeof body?.detail === "string" ? body.detail : `Không tải được dữ liệu doanh nghiệp (lỗi ${response.status}).`),
    { status: response.status });
  }
  return response.json();
}

const NO_SECTOR = "Chưa phân ngành";

export async function getCompanyCatalog() {
  const data = await readJson("");
  return (data?.items || []).map((item) => ({
    id: item.ticker, name: item.name || item.ticker, sector: item.sector || NO_SECTOR,
    exchange: item.exchange, latestPeriod: item.latestPeriod,
  }));
}

// null when the backend does not know the ticker.
export async function getCompanyFinancials(ticker, signal) {
  const data = await readJson(`/${encodeURIComponent(ticker)}`, signal);
  return data && {
    id: data.ticker, name: data.name || data.ticker, sector: data.sector || NO_SECTOR, exchange: data.exchange,
    periods: data.periods || [], reports: data.reports || [], sources: data.sources || [],
  };
}

export const FACTS = [
  { key: "revenue", label: "Doanh thu thuần / Tổng thu nhập hoạt động", kind: "money" },
  { key: "revenueYoy", label: "Tăng trưởng doanh thu so với cùng kỳ", kind: "growth" },
  { key: "netProfit", label: "Lợi nhuận sau thuế", kind: "money" },
  { key: "totalAssets", label: "Tổng tài sản", kind: "money" },
  { key: "liabilities", label: "Nợ phải trả", kind: "money" },
  { key: "equity", label: "Vốn chủ sở hữu", kind: "money" },
  { key: "roe", label: "ROE", kind: "percent" },
  { key: "roa", label: "ROA", kind: "percent" },
];

const vi = (value, digits) => value.toLocaleString("vi-VN", { maximumFractionDigits: digits });

// Ratios are stored as fractions (0.28 = 28%). Money is shown in tỷ đồng only when the unit is confirmed VND.
export function formatFact(fact, kind) {
  if (!fact || fact.value == null) return "—";
  const value = Number(fact.value);
  if (kind === "percent") return `${vi(value * 100, 1)}%`;
  if (kind === "growth") return `${value > 0 ? "+" : ""}${vi(value * 100, 1)}%`;
  // Vietcap money tagged SOURCE_NATIVE is dong (continuous with the VND-verified periods), so both read in tỷ.
  if (fact.unit === "VND" || fact.unit === "SOURCE_NATIVE") return `${vi(value / 1e9, 0)} tỷ đồng`;
  return vi(value, 0);
}

export const VERIFICATION = {
  VERIFIED: { label: "Khớp BCTC gốc", tone: "success" },
  PARTIAL: { label: "Đối chiếu một phần", tone: "warning" },
  MISMATCH: { label: "Lệch so với BCTC gốc", tone: "error" },
};
export const verification = (status) => VERIFICATION[status] || { label: "Chưa đối chiếu BCTC", tone: "neutral" };

// Old links use FY2025 / Q2/2026; the API uses 2025-YEAR / 2026-Q2.
export function toPeriodCode(value) {
  const text = (value || "").trim().toUpperCase();
  let match = text.match(/^FY(\d{4})$/);
  if (match) return `${match[1]}-YEAR`;
  match = text.match(/^Q([1-4])\/(\d{4})$/);
  if (match) return `${match[2]}-Q${match[1]}`;
  return /^\d{4}-(YEAR|Q[1-4])$/.test(text) ? text : "";
}
