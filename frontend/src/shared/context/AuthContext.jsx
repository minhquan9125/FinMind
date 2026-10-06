// Context quản lý trạng thái xác thực toàn cục.
// Bọc ứng dụng bằng <AuthProvider> để mọi component con
// đều có thể gọi useAuth() lấy thông tin người dùng và phiên làm việc.
//
// Hiện tại dùng mock (authMock.js). Khi backend sẵn sàng, chỉ cần thay
// phần thân của login/logout bằng fetch tới API, không đổi giao diện.

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getStoredSession,
  mockLogin,
  mockRegister,
  mockLogout,
  mockExpireCurrentSession,
} from "../../mocks/authMock.js";

// ─── Context mặc định (chưa có Provider) ────────────────────────────────────
const AuthContext = createContext({
  /** @type {object|null} Thông tin người dùng hiện tại */
  user: null,
  /** @type {string|null} "user" | "admin" | null */
  role: null,
  /** @type {boolean} Đã đăng nhập hay chưa */
  isAuthenticated: false,
  /** @type {boolean} Đang kiểm tra phiên (hydrate từ localStorage) */
  isLoading: true,
  /** @type {boolean} Phiên làm việc đã hết hạn hay chưa */
  isSessionExpired: false,
  /** @type {(email:string, password:string, rememberMe?:boolean) => Promise<void>} */
  login: async () => {},
  /** @type {(name:string, email:string, password:string) => Promise<void>} */
  register: async () => {},
  /** @type {() => Promise<void>} */
  logout: async () => {},
  /** @type {() => void} Giả lập làm hết hạn phiên ngay lập tức để test */
  expireSessionNow: () => {},
});

// ─── Provider ────────────────────────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSessionExpired, setIsSessionExpired] = useState(false);

  // 1. Khôi phục phiên đã lưu khi mount lần đầu (F5 / mở tab mới).
  useEffect(() => {
    const session = getStoredSession();
    if (session?.isExpired) {
      // Phiên đã quá hạn
      setUser(null);
      setIsSessionExpired(true);
    } else if (session?.user) {
      // Phiên còn hạn hợp lệ
      setUser(session.user);
      setIsSessionExpired(false);
    }
    setIsLoading(false);
  }, []);

  // 2. Cơ chế ngầm kiểm tra định kỳ (Heartbeat):
  // Khi người dùng đang ở trong ứng dụng, định kỳ mỗi 5 giây kiểm tra thời hạn phiên.
  // Nếu phiên hết hạn trong lúc đang mở web, tự động ngắt phiên và kích hoạt cờ isSessionExpired.
  useEffect(() => {
    if (!user) return;

    const interval = setInterval(() => {
      const session = getStoredSession();
      if (!session || session.isExpired) {
        setUser(null);
        setIsSessionExpired(true);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [user]);

  const login = useCallback(async (email, password, rememberMe = false) => {
    const session = await mockLogin(email, password, rememberMe);
    setUser(session.user);
    setIsSessionExpired(false);
  }, []);

  const register = useCallback(async (name, email, password) => {
    const session = await mockRegister(name, email, password);
    setUser(session.user);
    setIsSessionExpired(false);
  }, []);

  const logout = useCallback(async () => {
    await mockLogout();
    setUser(null);
    setIsSessionExpired(false);
  }, []);

  // Hàm hỗ trợ test: làm hết hạn phiên ngay lập tức
  const expireSessionNow = useCallback(() => {
    mockExpireCurrentSession();
    setUser(null);
    setIsSessionExpired(true);
  }, []);

  const value = useMemo(
    () => ({
      user,
      role: user?.role ?? null,
      isAuthenticated: !!user,
      isLoading,
      isSessionExpired,
      login,
      register,
      logout,
      expireSessionNow,
    }),
    [user, isLoading, isSessionExpired, login, register, logout, expireSessionNow],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

// ─── Hook tiện ích ───────────────────────────────────────────────────────────
/**
 * Hook lấy trạng thái xác thực.
 *
 * @example
 *   const { user, role, isAuthenticated, isSessionExpired, login, logout, expireSessionNow } = useAuth();
 */
export function useAuth() {
  return useContext(AuthContext);
}
