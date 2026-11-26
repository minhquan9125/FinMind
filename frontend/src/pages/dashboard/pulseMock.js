// Dữ liệu minh họa cho băng giá, bản đồ nhiệt và nhịp phiên HOSE.
// Chưa nối nguồn giá thật: khi backend có API giá, chỉ cần thay mảng này.

export const PULSE_SECTORS = { bank: "Ngân hàng", tech: "Công nghệ" };

// tile: "w2" = rộng 2 cột, "h2" = cao 2 hàng (ô to = vốn hóa lớn)
export const pulseCompanies = [
  { code: "VCB", name: "Vietcombank", sector: "bank", price: 92.1, change: 0.87, tile: "w2 h2", note: "Ngân hàng lớn nhất sàn, nợ xấu thấp" },
  { code: "FPT", name: "FPT Corporation", sector: "tech", price: 128.4, change: 2.31, tile: "w2 h2", note: "Tăng mạnh nhất nhóm sau tin hợp đồng Nhật Bản" },
  { code: "BID", name: "BIDV", sector: "bank", price: 47.85, change: 0.42, tile: "w2", note: "Tăng nhẹ theo nhóm ngân hàng" },
  { code: "CTG", name: "VietinBank", sector: "bank", price: 36.7, change: 0.27, tile: "", note: "Đi ngang quanh tham chiếu" },
  { code: "TCB", name: "Techcombank", sector: "bank", price: 24.35, change: -1.02, tile: "", note: "Giảm sau tin điều chỉnh lãi suất huy động" },
  { code: "MBB", name: "MB", sector: "bank", price: 23.8, change: 1.49, tile: "w2", note: "Thanh khoản cao nhất nhóm, hơn 12 triệu cp" },
  { code: "CMG", name: "CMC Corporation", sector: "tech", price: 41.25, change: -0.48, tile: "", note: "Chờ thông tin trung tâm dữ liệu mới" },
  { code: "ELC", name: "ELCOM", sector: "tech", price: 21.6, change: 0.93, tile: "", note: "Hồi phục phiên thứ hai liên tiếp" },
  { code: "ITD", name: "ITD", sector: "tech", price: 13.45, change: -0.74, tile: "w2", note: "Thanh khoản thấp" },
  { code: "ICT", name: "ICT", sector: "tech", price: 15.2, change: 0, tile: "w2", note: "Đứng giá tham chiếu" },
];

export const pulseIndices = [
  { code: "VN-INDEX", price: 1268.42, change: 0.64 },
  { code: "VN30", price: 1302.15, change: 0.81 },
  { code: "HNX-INDEX", price: 236.9, change: -0.22 },
];

export const pulseBreadth = { up: 214, flat: 58, down: 121 };
