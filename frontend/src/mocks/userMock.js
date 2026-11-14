// Dữ liệu minh họa theo danh sách doanh nghiệp trong interface/.
export const companies = [
  { id: "VCB", name: "Vietcombank", sector: "Ngân hàng", status: "Có dữ liệu", tone: "success" },
  { id: "BID", name: "BIDV", sector: "Ngân hàng", status: "Có dữ liệu", tone: "success" },
  { id: "CTG", name: "VietinBank", sector: "Ngân hàng", status: "Có dữ liệu", tone: "success" },
  { id: "MBB", name: "MB", sector: "Ngân hàng", status: "Có dữ liệu", tone: "success" },
  { id: "TCB", name: "Techcombank", sector: "Ngân hàng", status: "Có dữ liệu", tone: "success" },
  { id: "FPT", name: "FPT Corporation", sector: "Công nghệ", status: "Có dữ liệu", tone: "success" },
  { id: "CMG", name: "CMC Corporation", sector: "Công nghệ", status: "Có dữ liệu", tone: "success" },
  { id: "ELC", name: "ELCOM", sector: "Công nghệ", status: "Có dữ liệu", tone: "success" },
  { id: "ITD", name: "ITD", sector: "Công nghệ", status: "Có dữ liệu", tone: "success" },
  { id: "ICT", name: "ICT", sector: "Công nghệ", status: "Có dữ liệu", tone: "success" },
];

// Watchlist này chỉ để thử bảng; không đại diện lựa chọn của người dùng thật.
export const watchlist = ["FPT", "VCB", "MBB", "CMG"].map((id) => {
  const company = companies.find((item) => item.id === id);
  return { ...company, status: "Đang theo dõi", tone: "info" };
});

export const userFixtures = {
  companies: { success: companies, empty: [], error: "Không thể tải danh sách doanh nghiệp minh họa." },
  watchlist: { success: watchlist, empty: [], error: "Không thể tải danh sách theo dõi minh họa." },
};
