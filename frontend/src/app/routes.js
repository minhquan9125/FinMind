// [TL] Tự gom mọi trang trong src/pages/*/index.js thành một danh sách.
// Thêm trang mới = tạo thư mục mới trong pages/, không sửa file này.

/**
 * Danh sách đường dẫn (routes) của toàn bộ ứng dụng FinMind.
 * Được tổng hợp từ thiết kế Figma (file JSON luồng router).
 *
 * Mỗi route gồm:
 *   path        — URL đăng ký với react-router
 *   component   — Tên component (chuỗi). Router.jsx sẽ lazy-load từ pages/<component>
 *   category    — Nhóm tính năng (để dễ đọc, không ảnh hưởng runtime)
 *   label       — Tên hiển thị trên giao diện / breadcrumb
 */
const routes = [
  // ─── 1. Public & Xác thực ─────────────────────────────────────────────────
  {
    path: "/",
    component: "home/HomePage",
    category: "Public",
    label: "Landing",
  },
  {
    path: "/login",
    component: "auth/LoginPage",
    category: "Auth",
    label: "Đăng nhập",
  },
  {
    path: "/register",
    component: "auth/RegisterPage",
    category: "Auth",
    label: "Đăng ký",
  },
  {
    path: "/forgot-password",
    component: "auth/ForgotPasswordPage",
    category: "Auth",
    label: "Quên mật khẩu",
  },
  {
    path: "/reset-password",
    component: "auth/ResetPasswordPage",
    category: "Auth",
    label: "Đặt lại mật khẩu",
  },

  // ─── 2. Workspace chính (R00) ─────────────────────────────────────────────
  {
    path: "/dashboard",
    component: "dashboard/DashboardPage",
    category: "Workspace",
    label: "Dashboard",
  },

  // ─── 3. Doanh nghiệp ──────────────────────────────────────────────────────
  {
    path: "/companies",
    component: "companies/CompanySearchPage",
    category: "Doanh nghiệp",
    label: "Danh mục doanh nghiệp",
  },
  {
    path: "/companies/:ticker",
    component: "companies/CompanyDetailPage",
    category: "Doanh nghiệp",
    label: "Chi tiết doanh nghiệp",
  },

  // ─── 4. Trợ lý nghiên cứu (R01) ──────────────────────────────────────────
  //   Query params: ?company=FPT&period=FY2025&question=...&autosubmit=1&history=1
  {
    path: "/research",
    component: "research/ResearchPage",
    category: "Nghiên cứu",
    label: "Trợ lý nghiên cứu",
  },

  // ─── 5. Danh sách theo dõi (R05) ──────────────────────────────────────────
  {
    path: "/watchlist",
    component: "watchlist/WatchlistPage",
    category: "Cá nhân",
    label: "Danh sách theo dõi",
  },

  // ─── 6. Đồ thị tri thức (R06) ─────────────────────────────────────────────
  //   Query params: ?company=FPT
  {
    path: "/graph",
    component: "graph/GraphPage",
    category: "Nghiên cứu",
    label: "Đồ thị tri thức",
  },

  // ─── 7. Hồ sơ cá nhân ─────────────────────────────────────────────────────
  {
    path: "/profile",
    component: "profile/ProfilePage",
    category: "Cá nhân",
    label: "Hồ sơ cá nhân",
  },

  // ─── 8. Admin — Tổng quan vận hành ────────────────────────────────────────
  {
    path: "/admin",
    component: "admin/AdminOverviewPage",
    category: "Admin",
    label: "Tổng quan vận hành",
  },
  {
    path: "/admin/overview",
    component: "admin/AdminOverviewPage",
    category: "Admin",
    label: "Tổng quan vận hành",
  },

  // ─── 9. Admin — Theo dõi truy vấn ────────────────────────────────────────
  {
    path: "/admin/traces",
    component: "admin/AdminTracesPage",
    category: "Admin",
    label: "Theo dõi truy vấn",
  },
  {
    path: "/admin/traces/:traceId",
    component: "admin/AdminTracesPage",
    category: "Admin",
    label: "Chi tiết Trace",
  },

  // ─── 10. Admin — Cấu hình nguồn ──────────────────────────────────────────
  {
    path: "/admin/sources",
    component: "admin/AdminSourcesPage",
    category: "Admin",
    label: "Cấu hình nguồn",
  },
  {
    path: "/admin/sources/:sourceId",
    component: "admin/AdminSourcesPage",
    category: "Admin",
    label: "Chi tiết nguồn",
  },

  // ─── 11. Admin — Phiên bản kho dữ liệu (Corpus) ─────────────────────────
  //   Query params: ?tab=registry
  {
    path: "/admin/corpus",
    component: "admin/AdminCorpusPage",
    category: "Admin",
    label: "Phiên bản kho dữ liệu",
  },
  {
    path: "/admin/corpus/:version",
    component: "admin/AdminCorpusPage",
    category: "Admin",
    label: "Chi tiết Corpus",
  },

  // ─── 12. Admin — Ngưỡng & ngân sách API (Configuration) ──────────────────
  //   Query params: ?focus=budget&usage=82
  {
    path: "/admin/configuration",
    component: "admin/AdminConfigurationPage",
    category: "Admin",
    label: "Ngưỡng & ngân sách API",
  },
  {
    path: "/admin/configuration/:configId",
    component: "admin/AdminConfigurationPage",
    category: "Admin",
    label: "Chi tiết cấu hình",
  },

  // ─── 13. Admin — Nhật ký kiểm toán ───────────────────────────────────────
  //   Query params: ?trace=...&config=...&corpus=...&source=...&event=...
  {
    path: "/admin/audit",
    component: "admin/AdminAuditPage",
    category: "Admin",
    label: "Nhật ký kiểm toán",
  },

  // ─── 14. Luồng RAG thử nghiệm ban đầu (Legacy) ──────────────────────────
  {
    path: "/upload",
    component: "upload/UploadPage",
    category: "RAG Flow",
    label: "Upload tài liệu",
  },
  {
    path: "/documents/:documentId/search",
    component: "search/SearchPage",
    category: "RAG Flow",
    label: "Tìm kiếm vector",
  },
  {
    path: "/documents/:documentId/analysis",
    component: "analysis/AnalysisPage",
    category: "RAG Flow",
    label: "Phân tích chunk",
  },
];

export default routes;
