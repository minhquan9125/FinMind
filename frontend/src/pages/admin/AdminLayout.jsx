// Khung chung cho các trang Admin: sidebar bên trái + vùng nội dung cuộn.
// Dùng Sidebar từ shared/ui; mục đang chọn lấy từ URL hiện tại.

import { useLocation, useNavigate } from "../../app/router.jsx";
import { Sidebar } from "../../shared/ui";

// Địa chỉ lấy theo src/app/routes.js (paths.js chưa có đủ các địa chỉ admin này).
export const ADMIN_LINKS = {
  overview: "/admin/overview",
  traces: "/admin/traces",
  sources: "/admin/sources",
  jobs: "/admin/jobs",
  ingestion: "/admin/ingestion",
  corpus: "/admin/corpus",
  configuration: "/admin/configuration",
  evaluation: "/admin/evaluation",
  audit: "/admin/audit",
};

const groups = [
  { label: "Vận hành", items: [
    { id: "overview", label: "Tổng quan vận hành", icon: "▦" },
    { id: "traces", label: "Theo dõi truy vấn", icon: "∿" },
    { id: "evaluation", label: "Đánh giá chất lượng", icon: "✔" },
  ] },
  { label: "Quản trị dữ liệu", items: [
    { id: "ingestion", label: "Thu thập & duyệt", icon: "↓" },
    { id: "jobs", label: "Job dữ liệu", icon: "▤" },
    { id: "sources", label: "Cấu hình nguồn", icon: "◍" },
    { id: "corpus", label: "Phiên bản kho dữ liệu", icon: "☰" },
  ] },
  { label: "Cấu hình hệ thống", items: [
    { id: "configuration", label: "Ngưỡng & ngân sách API", icon: "⚙" },
  ] },
  { label: "Kiểm toán", items: [
    { id: "audit", label: "Nhật ký kiểm toán", icon: "✓" },
  ] },
];

function activeIdFor(pathname) {
  if (pathname === "/admin" || pathname.startsWith("/admin/overview")) return "overview";
  const hit = Object.entries(ADMIN_LINKS).find(([id, path]) => id !== "overview" && pathname.startsWith(path));
  return hit ? hit[0] : "overview";
}

export default function AdminLayout({ children }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  // Mọi mục trong menu hiện đã dùng dữ liệu thật; thêm id vào mảng này khi có trang mới còn là minh họa.
  const unfinished = [].includes(activeIdFor(pathname));

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#F8FAFC]">
      <Sidebar
        groups={groups}
        activeId={activeIdFor(pathname)}
        onSelect={(id) => navigate(ADMIN_LINKS[id])}
        badge="ADMIN"
        profile={{ initials: "AD", name: "Quản trị viên", role: "System Admin" }}
      />
      <main className="flex h-screen flex-1 flex-col gap-8 overflow-y-auto p-4 md:p-8">
        {unfinished && <aside className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <strong>Chưa triển khai kết nối dữ liệu thật cho mục này.</strong>
          <p className="mt-1">Giao diện và các số liệu bên dưới là minh họa. Thao tác tại đây chưa thay đổi cấu hình hoặc dữ liệu đang phục vụ.</p>
        </aside>}
        {children}
      </main>
    </div>
  );
}
