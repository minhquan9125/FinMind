const base = "/api/research/chat/sessions";
function failure(message, status) { const error = new Error(message); error.status = status; return error; }
function authHeaders() {
  let token;
  try { token = JSON.parse(localStorage.getItem("finmind_auth_session") || "null")?.token; }
  catch { token = null; }
  if (typeof token !== "string" || !token.trim()) throw failure("Vui lòng đăng nhập để sử dụng hội thoại.", 401);
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}
async function request(path = "", method = "GET", body) {
  const headers = authHeaders();
  let response;
  try { response = await fetch(base + path, { method, headers, cache: "no-store",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) }); }
  catch { throw failure("Không kết nối được máy chủ. Hãy kiểm tra backend đang chạy.", 0); }
  let data;
  try { data = await response.json(); }
  catch { throw failure(response.ok ? "Máy chủ trả dữ liệu không hợp lệ." : `Máy chủ trả lỗi ${response.status}.`, response.ok ? 502 : response.status); }
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : typeof data?.message === "string" ? data.message : `Yêu cầu thất bại (${response.status}).`;
    throw failure(detail, response.status);
  }
  return data;
}
export const createSession = () => request("", "POST");
export const listSessions = () => request();
export const getSession = id => request(`/${encodeURIComponent(id)}`);
export const sendMessage = (id, text, revision) => request(`/${encodeURIComponent(id)}/messages`, "POST", { text, revision });
export const resumeSession = id => request(`/${encodeURIComponent(id)}/resume`, "POST");
