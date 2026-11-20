/**
 * FinMind Authentication API Service
 * Nối trực tiếp tới FastAPI Backend (/api/v1/auth)
 */

/**
 * Gọi API Đăng nhập thật
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{access_token: string, refresh_token: string, token_type: string, expires_in: number, user: object}>}
 */
export async function apiLogin(email, password) {
  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password: password,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      const error = new Error(data.detail || "Đăng nhập thất bại.");
      error.status = response.status;
      error.detail = data.detail;
      throw error;
    }

    return data.data;
  } catch (err) {
    if (err.status) throw err;
    // Bắt lỗi không kết nối được máy chủ / lỗi mạng
    const netErr = new Error(
      "Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại kết nối mạng hoặc đảm bảo backend đang chạy."
    );
    netErr.status = 0;
    throw netErr;
  }
}

/**
 * Gọi API Đăng ký tài khoản thật
 * @param {string} fullName
 * @param {string} email
 * @param {string} password
 * @param {string} [confirmPassword]
 * @returns {Promise<{user_id: string, email: string, full_name: string, roles: string[], created_at: string}>}
 */
export async function apiRegister(fullName, email, password, confirmPassword) {
  try {
    const response = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password: password,
        confirm_password: confirmPassword || password,
        accept_terms: true,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      let message = data.detail;
      if (Array.isArray(data.detail)) {
        // Format mảng lỗi validation của Pydantic
        message = data.detail.map((d) => d.msg).join(". ");
      }
      const error = new Error(message || "Đăng ký không thành công.");
      error.status = response.status;
      error.detail = data.detail;
      throw error;
    }

    return data.data;
  } catch (err) {
    if (err.status) throw err;
    const netErr = new Error(
      "Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại kết nối mạng hoặc đảm bảo backend đang chạy."
    );
    netErr.status = 0;
    throw netErr;
  }
}
/**
 * Gửi Google ID Token lên backend để xác thực và lấy session JWT của FinMind
 * @param {string} credential - Token Google trả về sau khi đăng nhập thành công
 */
export async function apiGoogleLogin(credential) {
  const res = await fetch("/api/v1/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });

  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.detail || "Đăng nhập bằng tài khoản Google thất bại.");
  }
  return body.data;
}

async function postSessionAction(path, refreshToken) {
  const response = await fetch(`/api/v1/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.");
    error.status = response.status;
    throw error;
  }
  return body.data;
}

export const apiRefreshSession = (refreshToken) => postSessionAction("refresh", refreshToken);
export const apiLogout = (refreshToken) => postSessionAction("logout", refreshToken);

/**
 * Gửi yêu cầu đặt lại mật khẩu qua email
 * @param {string} email
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function apiForgotPassword(email) {
  const response = await fetch("/api/v1/auth/password/forgot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  });

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Không thể gửi yêu cầu. Vui lòng thử lại."
    );
  }
  return body;
}

/**
 * Đặt lại mật khẩu bằng mã nhận qua email.
 */
export async function apiResetPassword(token, newPassword, confirmPassword) {
  const response = await fetch("/api/v1/auth/password/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recovery_code: token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(". ")
      : detail;
    throw new Error(message || "Không thể đặt lại mật khẩu.");
  }

  return { success: true, message: "Đặt lại mật khẩu thành công." };
}
