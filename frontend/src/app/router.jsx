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
import { AuthProvider, useAuth } from "../shared/context/AuthContext.jsx";

// Re-export để thành viên import từ đây, không cần biết react-router-dom
export { Link, useNavigate, useParams, useLocation, useSearchParams };
// Re-export auth hook — thành viên dùng: import { useAuth } from "../../app/router.jsx";
export { useAuth };

// ─── ProtectedRoute ──────────────────────────────────────────────────────────
/**
 * Component bảo vệ tuyến đường dựa trên trạng thái đăng nhập và vai trò.
 *
 * Luồng kiểm tra:
 *   1. Nếu AuthProvider đang hydrate (isLoading) → hiển thị blank (tránh flash).
 *   2. Route yêu cầu đăng nhập (auth=true) mà chưa đăng nhập
 *      → chuyển hướng về /login, ghi nhớ URL hiện tại trong state.from
 *        để sau khi đăng nhập có thể quay lại đúng trang cũ.
 *   3. Đã đăng nhập nhưng vai trò không nằm trong danh sách roles
 *      → chuyển hướng về /dashboard (user) hoặc /admin (admin).
 *   4. Trang Auth (login/register) mà đã đăng nhập rồi
 *      → chuyển hướng thẳng vào workspace, không hiển thị lại form.
 *   5. Mọi điều kiện thỏa → render component bình thường.
 *
 * @param {{ routeConfig: object, children: React.ReactNode }} props
 */
function ProtectedRoute({ routeConfig, children }) {
  const { isAuthenticated, role, isLoading, isSessionExpired } = useAuth();
  const location = useLocation();

  // 1. Đang khôi phục phiên — chờ, không render gì
  if (isLoading) return null;

  const requiresAuth = routeConfig.auth === true;
  const allowedRoles = routeConfig.roles; // undefined = mọi vai trò
  const isAuthPage = routeConfig.category === "Auth"; // login, register, forgot...

  // 2. Cần đăng nhập nhưng chưa đăng nhập hoặc phiên đã hết hạn → về login kèm thông báo
  if (requiresAuth && (!isAuthenticated || isSessionExpired)) {
    return (
      <Navigate
        to="/login"
        state={{
          from: location,
          expired: isSessionExpired,
          message: isSessionExpired
            ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
            : undefined,
        }}
        replace
      />
    );
  }

  // 3. Đã đăng nhập nhưng không có quyền → chuyển hướng phù hợp
  if (requiresAuth && isAuthenticated && allowedRoles && !allowedRoles.includes(role)) {
    const fallback = role === "admin" ? "/admin" : "/dashboard";
    return <Navigate to={fallback} replace />;
  }

  // 4. Cho phép xem và kiểm thử trang Auth (login / register) mọi lúc mà không bị ép chuyển hướng
  // (Đã bỏ tự động redirect để phục vụ việc kiểm thử giao diện)

  // 5. OK — render trang
  return children;
}

/**
 * Khung giữ chỗ tạm thời — hiển thị khi file .jsx của trang chưa được tạo.
 * Thành viên không cần quan tâm đến component này.
 */
function Placeholder() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();
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

        {/* Trạng thái xác thực & Nút Đăng xuất */}
        {isAuthenticated ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              borderRadius: "8px",
              marginBottom: "16px",
              fontSize: "13px",
            }}
          >
            <div style={{ color: "#1e40af" }}>
              <strong>Đang đăng nhập:</strong> {user?.name || user?.email} (<code>{user?.role}</code>)
            </div>
            <button
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              style={{
                padding: "6px 14px",
                background: "#dc2626",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Đăng xuất
            </button>
          </div>
        ) : (
          <div
            style={{
              padding: "8px 12px",
              background: "#f1f5f9",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              marginBottom: "16px",
              fontSize: "12px",
              color: "#64748b",
            }}
          >
            Chưa đăng nhập (Khách)
          </div>
        )}

        {/* Nút điều hướng */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
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
            to="/register"
            style={{
              padding: "8px 16px",
              background: "#2563eb",
              color: "#fff",
              borderRadius: "8px",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: 500,
            }}
          >
            Trang Đăng ký (/register)
          </Link>
          <Link
            to="/login"
            style={{
              padding: "8px 16px",
              border: "1px solid #cbd5e1",
              color: "#334155",
              background: "#fff",
              borderRadius: "8px",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: 500,
            }}
          >
            Trang Đăng nhập (/login)
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
 *
 * Mỗi route được bọc bởi ProtectedRoute để kiểm tra đăng nhập và phân quyền
 * dựa trên metadata auth/roles trong routes.js.
 */
export function AppRoutes() {
  return (
    <Suspense fallback={null}>
      <Routes>
        {routes.map((routeConfig) => {
          const { path, component } = routeConfig;
          const Page = lazyPage(component);
          return (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedRoute routeConfig={routeConfig}>
                  <Page />
                </ProtectedRoute>
              }
            />
          );
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
 * AppRouter — bọc AppRoutes trong BrowserRouter và AuthProvider.
 * Dùng trong App.jsx hoặc main.jsx.
 *
 *   import AppRouter from "./app/router.jsx";
 *   export default function App() { return <AppRouter />; }
 */
export default function AppRouter() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}


const pageModules = import.meta.glob("../pages/*/*.jsx");

function lazyPage(componentPath) {
  const loader = pageModules[`../pages/${componentPath}.jsx`];
  return lazy(() => (loader ? loader() : Promise.resolve({ default: Placeholder })));
}