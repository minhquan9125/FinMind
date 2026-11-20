import { companies } from "../../mocks/userMock.js";

// Danh mục 10 mã theo interface/finmind_doanh_nghiep_duoc_ho_tro.
// Metadata phía dưới là fixture nội bộ, không phải số liệu thị trường thật.
export const companyCatalog = companies.map((company) => ({
  ...company,
  profile: { ticker: company.id, name: company.name, sector: company.sector },
  source: "Fixture FinMind · Dữ liệu minh họa",
  period: "FY2025",
  unit: "tỷ VNĐ",
  updatedAt: "05/10/2026",
}));

export const catalogFixtures = {
  success: companyCatalog,
  empty: [],
  error: "Không thể tải danh sách doanh nghiệp minh họa.",
};
