import { authorizedHeaders } from "../../shared/api/authorization.js";

export function createJobsApi({ fetchImpl = (...args) => fetch(...args), baseUrl = import.meta.env?.VITE_API_BASE_URL || "" } = {}) {
  async function request(path, { signal } = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(abort, 15000);
    try {
      const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/api/v1/admin/jobs${path}`,
        { headers: authorizedHeaders(), signal: controller.signal, cache: "no-store" });
      if (!response.ok) {
        const messages = { 401: "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.",
          403: "Tài khoản không có quyền quản trị.", 404: "Không tìm thấy báo cáo job.",
          409: "Báo cáo chưa hợp lệ hoặc chưa đọc được.", 503: "Chưa đọc được kho báo cáo." };
        throw new Error(messages[response.status] || "Không tải được báo cáo job.");
      }
      const data = await response.json();
      if (!Array.isArray(data?.items)) throw new Error("API trả báo cáo không hợp lệ.");
      return data;
    } catch (error) {
      if (controller.signal.aborted && !signal?.aborted) throw new Error("Tải báo cáo quá thời gian. Hãy thử lại.");
      throw error;
    } finally { clearTimeout(timer); signal?.removeEventListener("abort", abort); }
  }
  async function launch(body) {
    const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/api/v1/admin/jobs/runs`, {
      method: "POST", headers: authorizedHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body), cache: "no-store" });
    let data = null;
    try { data = await response.json(); } catch { /* errors may have no body */ }
    if (!response.ok) { const error = new Error(data?.detail || "LAUNCH_FAILED"); error.code = data?.detail; error.status = response.status; throw error; }
    return data;
  }
  return {
    launch,
    list: (offset = 0, options) => request(`?offset=${offset}&limit=20`, options),
    detail: (id, offset = 0, options) => request(`/${encodeURIComponent(id)}?offset=${offset}&limit=50`, options),
  };
}

export const jobsApi = createJobsApi();
