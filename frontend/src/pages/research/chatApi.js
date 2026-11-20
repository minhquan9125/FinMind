import { authorizedFetch } from "../../shared/api/authorization.js";

const base = "/api/research/chat/sessions";
function failure(message, status) { const error = new Error(message); error.status = status; return error; }
async function requestUrl(url, method = "GET", body, signal) {
  let response;
  try { response = await authorizedFetch(url, { method, signal, headers: { "Content-Type": "application/json" }, cache: "no-store",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }) }); }
  catch (error) {
    if (signal?.aborted || error?.name === 'AbortError') throw error;
    if (error?.status) throw error;
    throw failure("Không kết nối được máy chủ. Hãy kiểm tra backend đang chạy.", 0);
  }
  let data;
  try { data = await response.json(); }
  catch (error) {
    if (signal?.aborted || error?.name === 'AbortError') throw error;
    throw failure(response.ok ? "Máy chủ trả dữ liệu không hợp lệ." : `Máy chủ trả lỗi ${response.status}.`, response.ok ? 502 : response.status);
  }
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail
      : typeof data?.detail?.message === "string" ? data.detail.message
      : typeof data?.message === "string" ? data.message : `Yêu cầu thất bại (${response.status}).`;
    throw failure(detail, response.status);
  }
  return data;
}
const request = (path = "", method = "GET", body, signal) => requestUrl(base + path, method, body, signal);
export const createSession = signal => request("", "POST", undefined, signal);
export const listSessions = () => request();
export const getSession = (id, signal) => request(`/${encodeURIComponent(id)}`, "GET", undefined, signal);
export const sendMessage = (id, text, revision, signal) => request(`/${encodeURIComponent(id)}/messages`, "POST", { text, revision }, signal);
// Opening history continues the same session; POST /resume creates a separate fork.
export const resumeSession = getSession;

// Download the chat as a summary file; the server builds it, the browser saves it under the server's name.
export async function exportSession(id, format) {
  let response;
  try { response = await authorizedFetch(`${base}/${encodeURIComponent(id)}/export?format=${format}`, { cache: "no-store" }); }
  catch (error) {
    if (error?.status) throw error;
    throw failure("Không kết nối được máy chủ. Hãy kiểm tra backend đang chạy.", 0);
  }
  if (!response.ok) throw failure(`Không xuất được đoạn chat (lỗi ${response.status}).`, response.status);
  const name = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "")?.[1] || `finmind-chat.${format}`;
  return { blob: await response.blob(), name };
}

export function saveFile({ blob, name }) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Explicit diagnostic inspection. The chat answer now stores its own routed
// evidence, so ResearchChat does not call this on every submitted question.
export async function inspectBoth(question) {
  const payload = { question, require_live: true };
  const plan = await requestUrl("/api/hybrid-router/test", "POST", payload);
  if (plan.route !== "BOTH") return null;
  const result = await requestUrl("/api/hybrid-router/run", "POST", payload);
  if (result.route !== "BOTH") throw failure("Tuyến tìm kiếm đã thay đổi; vui lòng thử lại.", 409);
  if (result.execution_mode !== "LIVE") throw failure("Backend chưa dùng database thật cho tuyến BOTH.", 503);
  return result;
}
