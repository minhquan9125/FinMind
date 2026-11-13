import { readCompanyData } from "./api.js";

function sourceUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? value : null;
  } catch { return null; }
}

export async function getCompanyDetail(ticker, fixture = "success") {
  if (fixture === "error") throw new Error("Không thể tải chi tiết doanh nghiệp minh họa.");
  if (fixture === "empty") return null;
  if (fixture === "loading") return new Promise(() => {});
  const symbol = encodeURIComponent(ticker.trim().toUpperCase());
  try {
    const { id, name, sector, exchange } = await readCompanyData(`/${symbol}`);
    const { periods } = await readCompanyData(`/${symbol}/financials`);
    return {
      id, name, sector, exchange,
      financials: periods.map(({ period, facts }) => ({
        period, label: period,
        facts: facts.map(({ code, label, value_vnd, status }) => ({
          id: code, label, value: value_vnd == null ? null : Number(value_vnd) / 1e9,
          status: status === "VERIFIED" ? "VERIFIED" : "UNVERIFIED",
        })),
      })),
      reports: periods.filter(({ source }) => source).map(({ period, source }) => ({
        id: `${id}-${period}`, title: source.title, period, url: sourceUrl(source.url), page: source.page,
      })),
    };
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}
