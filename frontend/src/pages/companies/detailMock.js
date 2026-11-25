import { companyCatalog } from "./mock.js";

// Số liệu hoàn toàn minh họa để thử giao diện, không trích từ báo cáo thật.
// [tổng tài sản, nợ phải trả], đơn vị tỷ VNĐ.
const financialValues = {
  VCB: { FY2025: [1800000, 1650000], "Q2/2026": [1880000, 1720000] },
  BID: { FY2025: [2000000, 1850000], "Q2/2026": [2090000, 1930000] },
  CTG: { FY2025: [1900000, 1760000], "Q2/2026": [1980000, 1830000] },
  MBB: { FY2025: [1000000, 900000], "Q2/2026": [1060000, 950000] },
  TCB: { FY2025: [980000, 870000], "Q2/2026": [1030000, 910000] },
  FPT: { FY2025: [80000, 42000], "Q2/2026": [85000, 44000] },
  CMG: { FY2025: [12000, 6000], "Q2/2026": [13000, 6500] },
  ELC: { FY2025: [2500, 1000], "Q2/2026": [2700, 1100] },
  ITD: { FY2025: [3500, 1700], "Q2/2026": [3700, 1800] },
  ICT: { FY2025: [4200, 2200], "Q2/2026": [4500, 2400] },
};

export const detailPeriods = [
  { value: "FY2025", label: "FY2025", dataDate: "31/12/2025" },
  { value: "Q2/2026", label: "Quý 2/2026", dataDate: "30/06/2026" },
];

export function makeCompanyDetail(ticker) {
  const company = companyCatalog.find((item) => item.id === ticker);
  if (!company) return null;

  return {
    ...company,
    name: ticker === "FPT" ? "Công ty Cổ phần FPT" : company.name,
    exchange: ticker === "FPT" ? "HOSE" : null,
    financials: detailPeriods.map((period) => {
      const [assets, liabilities] = financialValues[ticker][period.value];
      return {
        period: period.value,
        dataDate: period.dataDate,
        facts: [
          { id: "assets", label: "Tổng tài sản", value: assets },
          { id: "liabilities", label: "Nợ phải trả", value: liabilities },
          { id: "equity", label: "Vốn chủ sở hữu", value: assets - liabilities },
        ],
      };
    }),
    reports: detailPeriods.map((period) => ({
      id: `${ticker}-${period.value}`,
      title: `Báo cáo ${period.value} · bản ghi minh họa`,
      period: period.value,
      date: period.dataDate,
      source: "Fixture FinMind",
      url: null,
    })),
    news: [],
  };
}
