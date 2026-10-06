// Dữ liệu tài khoản minh họa — không phải thông tin thật.
// Khi backend Auth (Supabase / FastAPI) sẵn sàng, thay toàn bộ file này
// bằng lệnh gọi API thật trong shared/api/client.js.

// ─── Tài khoản mẫu ──────────────────────────────────────────────────────────
export const MOCK_USERS = {
  user: {
    id: "usr-001",
    email: "user@finmind.vn",
    name: "Nguyễn Văn An",
    avatar: null,
    role: "user", // "user" | "admin"
  },
  admin: {
    id: "adm-001",
    email: "admin@finmind.vn",
    name: "Trần Minh Quản trị",
    avatar: null,
    role: "admin",
  },
};

// Mật khẩu mẫu — chỉ phục vụ kiểm thử giao diện, không bảo mật.
const MOCK_PASSWORDS = {
  "user@finmind.vn": "user123",
  "admin@finmind.vn": "admin123",
};

// ─── Cấu hình thời hạn phiên làm việc (Session TTL) ─────────────────────────
// Mặc định phiên sống trong 30 phút. Nếu chọn "Ghi nhớ đăng nhập" thì sống 7 ngày.
export const SESSION_DURATION_MS = 30 * 60 * 1000; // 30 phút
export const REMEMBER_ME_DURATION_MS = 7 * 24 * 60 * 60 * 1000; // 7 ngày

// ─── Key lưu phiên trong localStorage ────────────────────────────────────────
const STORAGE_KEY = "finmind_auth_session";

// ─── Hàm giả lập ────────────────────────────────────────────────────────────

/**
 * Giả lập đăng nhập: so khớp email + password với danh sách cứng.
 * Trả về Promise để giữ cùng interface với API thật sau này.
 * @param {string} email
 * @param {string} password
 * @param {boolean} [rememberMe=false]
 * @returns {Promise<{user: object, token: string, loginAt: string, expiresAt: string, expiresAtTimestamp: number}>}
 */
export async function mockLogin(email, password, rememberMe = false) {
  // Giả lập độ trễ mạng
  await new Promise((r) => setTimeout(r, 400));

  const correctPassword = MOCK_PASSWORDS[email];
  if (!correctPassword || correctPassword !== password) {
    throw new Error("Email hoặc mật khẩu không đúng.");
  }

  const user =
    Object.values(MOCK_USERS).find((u) => u.email === email) ?? null;
  if (!user) throw new Error("Không tìm thấy tài khoản.");

  // Token giả — chuỗi bất kỳ, chỉ để mô phỏng luồng.
  const token = `mock-token-${user.role}-${Date.now()}`;

  const now = Date.now();
  const ttl = rememberMe ? REMEMBER_ME_DURATION_MS : SESSION_DURATION_MS;
  const expiresAtTimestamp = now + ttl;

  // Lưu phiên vào localStorage kèm mốc thời gian hết hạn
  const session = {
    user,
    token,
    rememberMe,
    loginAt: new Date(now).toISOString(),
    expiresAt: new Date(expiresAtTimestamp).toISOString(),
    expiresAtTimestamp,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));

  return session;
}

/**
 * Giả lập đăng ký tài khoản mới.
 * @param {string} name
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{user: object, token: string, loginAt: string, expiresAt: string, expiresAtTimestamp: number}>}
 */
export async function mockRegister(name, email, password) {
  await new Promise((r) => setTimeout(r, 400));

  const existingEmail = Object.values(MOCK_USERS).some((u) => u.email === email);
  if (existingEmail) {
    throw new Error("Email này đã được sử dụng. Vui lòng chọn email khác.");
  }

  const newUser = {
    id: `usr-${Date.now().toString().slice(-4)}`,
    email,
    name: name.trim(),
    avatar: null,
    role: "user",
  };

  const token = `mock-token-user-${Date.now()}`;
  const now = Date.now();
  const expiresAtTimestamp = now + SESSION_DURATION_MS;

  const session = {
    user: newUser,
    token,
    rememberMe: false,
    loginAt: new Date(now).toISOString(),
    expiresAt: new Date(expiresAtTimestamp).toISOString(),
    expiresAtTimestamp,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));

  return session;
}

/**
 * Giả lập đăng xuất: xoá phiên khỏi localStorage.
 * @returns {Promise<void>}
 */
export async function mockLogout() {
  await new Promise((r) => setTimeout(r, 200));
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Kiểm tra đối tượng session xem đã quá thời hạn hay chưa.
 * @param {object|null} session
 * @returns {boolean}
 */
export function isSessionExpired(session) {
  if (!session || !session.expiresAtTimestamp) return true;
  return Date.now() > session.expiresAtTimestamp;
}

/**
 * Lấy phiên hiện tại từ localStorage và tự động kiểm tra thời hạn sống.
 * Dùng để khôi phục trạng thái đăng nhập khi tải lại trang (F5).
 * - Nếu phiên đã hết hạn: Tự động xóa khỏi localStorage và trả về cờ isExpired: true.
 * - Nếu phiên còn hạn: Trả về dữ liệu phiên bình thường với isExpired: false.
 * @returns {{ user: object, token: string, loginAt: string, expiresAt: string, expiresAtTimestamp: number, isExpired: boolean } | null}
 */
export function getStoredSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);

    // Kiểm tra thời hạn sống của phiên làm việc
    if (session.expiresAtTimestamp && Date.now() > session.expiresAtTimestamp) {
      // Phiên đã hết hạn! Tự động dọn dẹp storage
      localStorage.removeItem(STORAGE_KEY);
      return { ...session, isExpired: true };
    }

    return { ...session, isExpired: false };
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

/**
 * HÀM TEST HỖ TRỢ KIỂM THỬ:
 * Giả lập làm hết hạn phiên làm việc hiện tại ngay lập tức.
 * Dùng để test thông báo hết hạn và cơ chế tự động chuyển hướng về /login.
 */
export function mockExpireCurrentSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const session = JSON.parse(raw);
    const expiredTimestamp = Date.now() - 1000; // Đặt mốc thời gian về quá khứ 1 giây trước
    const expiredSession = {
      ...session,
      expiresAt: new Date(expiredTimestamp).toISOString(),
      expiresAtTimestamp: expiredTimestamp,
    };
    // Ghi đè lại để khi getStoredSession() đọc sẽ xác nhận đã hết hạn
    localStorage.setItem(STORAGE_KEY, JSON.stringify(expiredSession));
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}
