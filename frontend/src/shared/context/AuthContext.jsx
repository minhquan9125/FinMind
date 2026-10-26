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

import { apiLogin, apiRegister, apiGoogleLogin, apiForgotPassword, apiRefreshSession, apiLogout } from "../api/authApi.js";
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
    return { ...session, isExpired: Date.now() >= session.expiresAtTimestamp };
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
  /** @type {(credential:string, rememberMe?:boolean) => Promise<void>} */
  loginWithGoogle: async () => {},
  /** @type {(name:string, email:string, password:string, confirmPassword?:string) => Promise<void>} */
  register: async () => {},
  /** @type {(email:string) => Promise<any>} */
  forgotPassword: async () => {},
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

  const refreshSession = useCallback(async (session) => {
    if (!session?.refreshToken) throw new Error("Missing refresh token");
    const response = await apiRefreshSession(session.refreshToken);
    const now = Date.now();
    const next = {
      ...session,
      token: response.access_token,
      refreshToken: response.refresh_token,
      expiresAt: new Date(now + response.expires_in * 1000).toISOString(),
      expiresAtTimestamp: now + response.expires_in * 1000,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setUser(next.user);
    setIsSessionExpired(false);
  }, []);

  // Khôi phục phiên khi mở lại ứng dụng; refresh an toàn nếu access token đã hết hạn.
  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      const session = getStoredSession();
      if (session?.user) {
        if (session.isExpired) {
          try { await refreshSession(session); }
          catch {
            localStorage.removeItem(STORAGE_KEY);
            if (!cancelled) setIsSessionExpired(true);
          }
        } else if (!cancelled) {
          setUser(session.user);
          setIsSessionExpired(false);
        }
      }
      if (!cancelled) setIsLoading(false);
    };
    restore();
    return () => { cancelled = true; };
  }, [refreshSession]);

  // Xoay refresh token trước khi access token hết hạn.
  useEffect(() => {
    if (!user) return;
    const session = getStoredSession();
    if (!session) return;
    const timeout = setTimeout(async () => {
      try { await refreshSession(session); }
      catch {
        localStorage.removeItem(STORAGE_KEY);
        setUser(null);
        setIsSessionExpired(true);
      }
    }, Math.max(0, session.expiresAtTimestamp - Date.now() - 30_000));
    return () => clearTimeout(timeout);
  }, [user, refreshSession]);

  const login = useCallback(async (email, password, rememberMe = false) => {
    const res = await apiLogin(email, password);

    const now = Date.now();
    const ttlMs = (res.expires_in || 900) * 1000;
    const expiresAtTimestamp = now + ttlMs;

    const rawRole = (res.user.roles?.[0] || "RESEARCHER").toLowerCase();
    const primaryRole = rawRole === "admin" ? "admin" : "user";
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
      refreshToken: res.refresh_token,
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

  const loginWithGoogle = useCallback(async (credential, rememberMe = true) => {
    // 1. Gửi Google credential lên Backend FinMind để xác thực thật
    const res = await apiGoogleLogin(credential);

    const now = Date.now();
    const ttlMs = (res.expires_in || 900) * 1000;
    const expiresAtTimestamp = now + ttlMs;

    const rawRole = (res.user.roles?.[0] || "RESEARCHER").toLowerCase();
    const primaryRole = rawRole === "admin" ? "admin" : "user";
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
      refreshToken: res.refresh_token,
      rememberMe,
      loginAt: new Date(now).toISOString(),
      expiresAt: new Date(expiresAtTimestamp).toISOString(),
      expiresAtTimestamp,
    };

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

  const forgotPassword = useCallback(async (email) => {
    return await apiForgotPassword(email);
  }, []);

  const logout = useCallback(async () => {
    const session = getStoredSession();
    try {
      if (session?.refreshToken) await apiLogout(session.refreshToken);
    } catch {
      // Luôn xóa trạng thái cục bộ để người dùng thoát được khi backend không phản hồi.
    } finally {
      localStorage.removeItem(STORAGE_KEY);
      setUser(null);
      setIsSessionExpired(false);
    }
  }, []);

  // Hàm hỗ trợ test: làm hết hạn phiên ngay lập tức
  const expireSessionNow = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
    setIsSessionExpired(true);
  }, []);

  const userProfile = useMemo(() => {
    const displayName = user?.name || "Nhà nghiên cứu";
    const parts = displayName.trim().split(/\s+/).filter(Boolean);
    const initials = parts.length === 0
      ? "NN"
      : parts.length === 1
      ? parts[0].slice(0, 2).toUpperCase()
      : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return {
      initials,
      name: displayName,
      role: user?.role === "admin" ? "Quản trị viên" : "Nhà nghiên cứu",
    };
  }, [user]);

  const value = useMemo(
    () => ({
      user,
      userProfile,
      role: user?.role === "admin" ? "admin" : (user ? "user" : null),
      isAuthenticated: !!user,
      isLoading,
      isSessionExpired,
      login,
      loginWithGoogle,
      register,
      forgotPassword,
      logout,
      expireSessionNow,
    }),
    [user, userProfile, isLoading, isSessionExpired, login, loginWithGoogle, register, forgotPassword, logout, expireSessionNow],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

// ─── Hook tiện ích ───────────────────────────────────────────────────────────
  export function useAuth() {
  return useContext(AuthContext);
}
