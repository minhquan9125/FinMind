import test from "node:test";
import assert from "node:assert/strict";
import {
  apiForgotPassword,
  apiGoogleLogin,
  apiLogin,
  apiLogout,
  apiRefreshSession,
  apiRegister,
  apiResetPassword,
} from "./authApi.js";

const session = { access_token: "access-fixture", refresh_token: "refresh-fixture" };
const email = "researcher@example.test";

const successCases = [
  ["login", () => apiLogin(" Researcher@Example.Test ", "pass-fixture"),
    { email, password: "pass-fixture" }, Response.json({ data: session }), session],
  ["register", () => apiRegister(" Researcher ", " Researcher@Example.Test ", "pass-fixture"),
    { full_name: "Researcher", email, password: "pass-fixture", confirm_password: "pass-fixture", accept_terms: true },
    Response.json({ data: { email } }, { status: 201 }), { email }],
  ["google", () => apiGoogleLogin("google-fixture"), { credential: "google-fixture" },
    Response.json({ data: session }), session],
  ["refresh", () => apiRefreshSession("old-fixture"), { refresh_token: "old-fixture" },
    Response.json({ data: session }), session],
  ["logout", () => apiLogout("old-fixture"), { refresh_token: "old-fixture" },
    new Response(null, { status: 204 }), null],
  ["password/forgot", () => apiForgotPassword(" Researcher@Example.Test "), { email },
    Response.json({ success: true }, { status: 202 }), { success: true }],
  ["password/reset", () => apiResetPassword("code-fixture", "new-fixture", "new-fixture"),
    { recovery_code: "code-fixture", new_password: "new-fixture", confirm_password: "new-fixture" },
    new Response(null, { status: 204 }), { success: true, message: "Đặt lại mật khẩu thành công." }],
];

for (const [endpoint, call, expectedPayload, response, expectedResult] of successCases) {
  test("auth client sends the expected payload to " + endpoint, async (t) => {
    const fetch = t.mock.method(globalThis, "fetch", async (url, options) => {
      assert.equal(url, "/api/v1/auth/" + endpoint);
      assert.equal(options.method, "POST");
      assert.equal(options.headers["Content-Type"], "application/json");
      assert.deepEqual(JSON.parse(options.body), expectedPayload);
      return response;
    });
    assert.deepEqual(await call(), expectedResult);
    assert.equal(fetch.mock.callCount(), 1);
  });
}

test("auth client preserves an HTTP error status for login", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ detail: "Sai thông tin đăng nhập" }, { status: 401 }));
  await assert.rejects(apiLogin(email, "wrong-fixture"), {
    status: 401,
    message: "Sai thông tin đăng nhập",
  });
});

test("auth client gives network failures a separate status", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(apiLogin(email, "pass-fixture"), { status: 0, message: /kết nối/ });
});

test("registration and reset render field validation details", async (t) => {
  const detail = [{ msg: "Mật khẩu quá ngắn" }, { msg: "Xác nhận chưa khớp" }];
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail }, { status: 422 }));
  const message = "Mật khẩu quá ngắn. Xác nhận chưa khớp";

  await assert.rejects(apiRegister("Researcher", email, "x", "y"), { status: 422, message });
  await assert.rejects(apiResetPassword("code-fixture", "x", "y"), { message });
});
