// Context quản lý trạng thái xác thực toàn cục kết nối Backend thật (/api/v1/auth).
// Bọc ứng dụng bằng <AuthProvider> để mọi component con
// đều có thể gọi useAuth() lấy thông tin người dùng và phiên làm việc.

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiLogin, apiRegister } from "../api/authApi.js";

// ─── Key lưu phiên trong localStorage ────────────────────────────────────────
// Chỉ lưu profile người dùng và access token; TUYỆT ĐỐI KHÔNG LƯU MẬT KHẨU
const STORAGE_KEY = "finmind_auth_session";

function getStoredSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    if (!session || !session.expiresAtTimestamp) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    if (Date.now() > session.expiresAtTimestamp) {
      localStorage.removeItem(STORAGE_KEY);
      return { isExpired: true };
    }
    return { ...session, isExpired: false };
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

// ─── Context mặc định ────────────────────────────────────────────────────────
const AuthContext = createContext({
  /** @type {object|null} Thông tin người dùng hiện tại */
  user: null,
  /** @type {string|null} "researcher" | "admin" | null */
  role: null,
  /** @type {boolean} Đã đăng nhập hay chưa */
  isAuthenticated: false,
  /** @type {boolean} Đang kiểm tra phiên (hydrate từ localStorage) */
  isLoading: true,
  /** @type {boolean} Phiên làm việc đã hết hạn hay chưa */
  isSessionExpired: false,
  /** @type {(email:string, password:string, rememberMe?:boolean) => Promise<void>} */
  login: async () => {},
  /** @type {(name:string, email:string, password:string, confirmPassword?:string) => Promise<void>} */
  register: async () => {},
  /** @type {() => Promise<void>} */
  logout: async () => {},
  /** @type {() => void} Làm hết hạn phiên ngay lập tức để test */
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
      setUser(null);
      setIsSessionExpired(true);
    } else if (session?.user) {
      setUser(session.user);
      setIsSessionExpired(false);
    }
    setIsLoading(false);
  }, []);

  // 2. Cơ chế ngầm kiểm tra định kỳ (Heartbeat):
  // Định kỳ mỗi 5 giây kiểm tra thời hạn phiên.
  // Nếu phiên hết hạn trong lúc đang mở web, tự động ngắt phiên và bật cờ isSessionExpired.
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
    const res = await apiLogin(email, password);

    const now = Date.now();
    // RememberMe: 7 ngày; Mặc định: theo expires_in từ backend hoặc 15 phút
    const ttlMs = rememberMe
      ? 7 * 24 * 60 * 60 * 1000
      : (res.expires_in || 900) * 1000;
    const expiresAtTimestamp = now + ttlMs;

    const primaryRole = (res.user.roles?.[0] || "RESEARCHER").toLowerCase();
    const authUser = {
      id: res.user.user_id,
      email: res.user.email,
      name: res.user.full_name,
      role: primaryRole,
      roles: res.user.roles || ["RESEARCHER"],
    };

    const session = {
      user: authUser,
      token: res.access_token,
      rememberMe,
      loginAt: new Date(now).toISOString(),
      expiresAt: new Date(expiresAtTimestamp).toISOString(),
      expiresAtTimestamp,
    };

    // Lưu phiên vào localStorage (không lưu password, confirmPassword hay secret)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));

    setUser(authUser);
    setIsSessionExpired(false);
  }, []);

  const register = useCallback(async (name, email, password, confirmPassword) => {
    // 1. Gọi đăng ký tài khoản mới lên Backend
    await apiRegister(name, email, password, confirmPassword || password);

    // 2. Tự động đăng nhập để cấp access token và khởi tạo phiên cho người dùng
    await login(email, password, false);
  }, [login]);

  const logout = useCallback(async () => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
    setIsSessionExpired(false);
  }, []);

  // Hàm hỗ trợ test: làm hết hạn phiên ngay lập tức
  const expireSessionNow = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
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
  export function useAuth() {
  return useContext(AuthContext);
}
