import { createElement } from "react";
import GraphIcon from "../shared/ui/GraphIcon.jsx";
import { userFixtures } from "./userMock.js";
import { adminFixtures } from "./adminMock.js";

// Dữ liệu minh họa cho trang xem component. Không phải dữ liệu thật.
export const userMenu = [
  { label: "Nghiên cứu chính", items: [
    { id: "dashboard", label: "Tổng quan", icon: "▦" },
    { id: "companies", label: "Doanh nghiệp", icon: "▤" },
    { id: "copilot", label: "Trợ lý nghiên cứu", icon: "◫" },
    { id: "watchlist", label: "Danh sách theo dõi", icon: "☆" },
  ] },
  { label: "Tính năng mở rộng", items: [
    { id: "graph", label: "Đồ thị tri thức", icon: createElement(GraphIcon) },
  ] },
];

export const adminMenu = [
  { label: "Vận hành", items: [
    { id: "overview", label: "Tổng quan vận hành", icon: "▦" },
    { id: "traces", label: "Theo dõi truy vấn", icon: "◫" },
  ] },
  { label: "Quản trị dữ liệu", items: [
    { id: "sources", label: "Cấu hình nguồn", icon: "▤" },
    { id: "corpus", label: "Phiên bản kho dữ liệu", icon: "▣" },
  ] },
  { label: "Cấu hình hệ thống", items: [
    { id: "configuration", label: "Ngưỡng & ngân sách API", icon: "⚙" },
    { id: "audit", label: "Nhật ký kiểm toán", icon: "☷" },
  ] },
];

export const mockDatasets = { ...userFixtures, ...adminFixtures };

// Page gọi hàm này hôm nay; khi có FastAPI, thay phần thân hàm này bằng fetch.
export async function getMockRows(dataset = "sources", state = "success") {
  await new Promise((resolve) => setTimeout(resolve, 350));
  const fixture = mockDatasets[dataset];
  if (!fixture) throw new Error(`Không có bộ dữ liệu mẫu: ${dataset}`);
  if (state === "error") throw new Error(fixture.error);
  return fixture[state] || fixture.success;
}
