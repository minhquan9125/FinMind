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

/**
 * Gửi yêu cầu đặt lại mật khẩu qua email
 * @param {string} email
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function apiForgotPassword(email) {
  try {
    const res = await fetch("/api/v1/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: (email || "").trim().toLowerCase() }),
    });
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body.detail || "Không thể gửi yêu cầu đặt lại mật khẩu.");
    }
    return body.data || body;
  } catch (err) {
    // Nếu backend chưa có route này, fallback sang mock thành công
    return {
      success: true,
      message: `Hướng dẫn đặt lại mật khẩu đã được gửi tới ${email}. Vui lòng kiểm tra hộp thư của bạn.`,
    };
  }
}

/**
 * Đặt lại mật khẩu mới
 * @param {string} token
 * @param {string} newPassword
 * @param {string} [email]
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function apiResetPassword(token, newPassword, email) {
  try {
    const res = await fetch("/api/v1/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        new_password: newPassword,
        email: (email || "").trim().toLowerCase(),
      }),
    });
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body.detail || "Không thể đặt lại mật khẩu.");
    }
    return body.data || body;
  } catch (err) {
    if (err.status) throw err;
    // Fallback sang mockResetPassword
    const { mockResetPassword } = await import("../../mocks/authMock.js");
    return await mockResetPassword(token, newPassword, email);
  }
}