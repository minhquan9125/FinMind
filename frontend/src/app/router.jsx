// [TL] Điều hướng giữa các trang: Link, useNavigate, useParams, Routes.
// Thành viên chỉ dùng, không sửa.
//
// Cách dùng trong trang của bạn:
//   import { Link, useNavigate, useParams } from "../../app/router.jsx";

import React, { Suspense, lazy } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Link,
  useNavigate,
  useParams,
  useLocation,
  useSearchParams,
} from "react-router-dom";

import routes from "./routes.js";

// Re-export để thành viên import từ đây, không cần biết react-router-dom
export { Link, useNavigate, useParams, useLocation, useSearchParams };


const pageModules = import.meta.glob("../pages/*/*.jsx");

function lazyPage(componentPath) {
  const loader = pageModules[`../pages/${componentPath}.jsx`];
  return lazy(() => (loader ? loader() : Promise.resolve({ default: Placeholder })));
}
/**
 * Khung giữ chỗ tạm thời — hiển thị khi file .jsx của trang chưa được tạo.
 * Thành viên không cần quan tâm đến component này.
 */
function Placeholder() {
  const location = useLocation();
  // Tìm thông tin route hiện tại từ danh sách
  const current = routes.find((r) => {
    // So sánh đơn giản phần path không có params
    const routeParts = r.path.split("/").filter(Boolean);
    const urlParts = location.pathname.split("/").filter(Boolean);
    if (routeParts.length !== urlParts.length) return false;
    return routeParts.every(
      (seg, i) => seg.startsWith(":") || seg === urlParts[i]
    );
  });

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        fontFamily: "system-ui, sans-serif",
        background: "#f8fafc",
        color: "#1e293b",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "560px",
          background: "#fff",
          border: "1px solid #e2e8f0",
          borderRadius: "16px",
          padding: "32px",
          boxShadow: "0 1px 4px rgba(0,0,0,.06)",
        }}
      >
        {/* Nhãn nhóm */}
        {current && (
          <span
            style={{
              display: "inline-block",
              fontSize: "11px",
              fontWeight: 600,
              padding: "2px 10px",
              borderRadius: "20px",
              background: "#f1f5f9",
              color: "#64748b",
              border: "1px solid #e2e8f0",
              marginBottom: "16px",
            }}
          >
            {current.category}
          </span>
        )}

        {/* Tên màn hình */}
        <h1
          style={{
            fontSize: "20px",
            fontWeight: 700,
            margin: "0 0 8px",
            color: "#0f172a",
          }}
        >
          {current?.label ?? "Màn hình chưa có tên"}
        </h1>

        {/* URL thực tế */}
        <div
          style={{
            fontFamily: "monospace",
            fontSize: "12px",
            padding: "10px 14px",
            background: "#f8fafc",
            borderRadius: "8px",
            border: "1px dashed #cbd5e1",
            color: "#475569",
            margin: "16px 0",
          }}
        >
          <div>
            <strong>Route:</strong>{" "}
            <span style={{ color: "#2563eb" }}>{current?.path ?? location.pathname}</span>
          </div>
          <div style={{ marginTop: "4px" }}>
            <strong>Component:</strong>{" "}
            <span style={{ color: "#7c3aed" }}>
              src/pages/{current?.component ?? "?"}.jsx
            </span>
          </div>
          <div style={{ marginTop: "4px" }}>
            <strong>URL hiện tại:</strong>{" "}
            <span style={{ color: "#059669" }}>
              {location.pathname}
              {location.search}
            </span>
          </div>
        </div>

        {/* Thông báo */}
        <div
          style={{
            fontSize: "12px",
            padding: "10px 14px",
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: "8px",
            color: "#92400e",
            marginBottom: "20px",
          }}
        >
         / <strong>Khung giữ chỗ tạm thời.</strong> Thành viên nhận việc tạo
          file <code>.jsx</code> theo đường dẫn component ở trên để thay thế.
        </div>

        {/* Nút điều hướng */}
        <div style={{ display: "flex", gap: "8px" }}>
          <Link
            to="/"
            style={{
              padding: "8px 16px",
              background: "#0f172a",
              color: "#fff",
              borderRadius: "8px",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: 500,
            }}
          >
            Trang chủ
          </Link>
          <Link
            to="/dashboard"
            style={{
              padding: "8px 16px",
              border: "1px solid #e2e8f0",
              color: "#334155",
              borderRadius: "8px",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: 500,
            }}
          >
            Dashboard
          </Link>
          {/* Nút quay lại Admin nếu đang ở /admin/* */}
          {location.pathname.startsWith("/admin") && (
            <Link
              to="/admin"
              style={{
                padding: "8px 16px",
                border: "1px solid #e2e8f0",
                color: "#334155",
                borderRadius: "8px",
                textDecoration: "none",
                fontSize: "13px",
                fontWeight: 500,
              }}
            >
              Admin
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * AppRoutes — đọc routes.js và lắp ráp thành hệ thống điều hướng.
 * Dùng khi BrowserRouter đã có bên ngoài (ví dụ: gắn vào AppShell).
 *
 * Luồng điều hướng:
 *   - User: / → /login → /dashboard → /companies/:ticker → /research → /graph → /watchlist → /profile
 *   - Admin: /admin → /admin/traces/:traceId → /admin/configuration/:configId → /admin/audit → ...
 *   - URL /admin/* không khớp → về /admin
 *   - URL khác không khớp → về /
 */
export function AppRoutes() {
  return (
    <Suspense fallback={null}>
      <Routes>
        {routes.map(({ path, component }) => {
          const Page = lazyPage(component);
          return <Route key={path} path={path} element={<Page />} />;
        })}

        {/* Fallback cho admin: URL /admin/* không khớp → về Tổng quan vận hành */}
        <Route path="/admin/*" element={<Navigate to="/admin" replace />} />

        {/* Fallback chung: URL không khớp → về trang Landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

/**
 * AppRouter — bọc AppRoutes trong BrowserRouter.
 * Dùng trong App.jsx hoặc main.jsx.
 *
 *   import AppRouter from "./app/router.jsx";
 *   export default function App() { return <AppRouter />; }
 */
export default function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
