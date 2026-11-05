import { authorizedHeaders } from "../../shared/api/authorization.js";
import { validateGraph, validateRelation } from "./graphModel.js";

export class GraphApiError extends Error {
  constructor(message, status = 0, code = "") { super(message); this.status = status; this.code = code; }
}
export function createGraphApi({ baseUrl = import.meta.env?.VITE_API_BASE_URL || "", fixture = "",
  fetchImpl = (...args) => fetch(...args), timeoutMs = 15000 } = {}) {
  async function request(path, params, { signal } = {}) {
    if (fixture) {
      const { fixtureResponse } = await import("./mock.js");
      return fixtureResponse(path, params, fixture, signal);
    }
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params || {})) {
        for (const item of Array.isArray(value) ? value : [value]) {
          if (item !== null && item !== undefined && item !== "") query.append(key, String(item));
        }
      }
      const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/api/graph${path}${query.size ? "?" + query : ""}`,
        { signal: controller.signal, headers: authorizedHeaders(), cache: "no-store" });
      let data;
      try { data = await response.json(); }
      catch { throw new GraphApiError("API graph trả dữ liệu không hợp lệ.", response.status, "INVALID_RESPONSE"); }
      if (!response.ok) {
        const detail = data?.detail;
        const message = typeof detail === "string" ? detail : detail?.message ||
          (Array.isArray(detail) ? "Tham số truy vấn không hợp lệ." : `Không tải được graph (HTTP ${response.status}).`);
        throw new GraphApiError(message, response.status, detail?.code || "");
      }
      return data;
    } catch (e) {
      if (signal?.aborted) throw e;
      if (timedOut) throw new GraphApiError("Truy vấn graph quá thời gian. Hãy giảm hop hoặc thu hẹp bộ lọc.", 504, "GRAPH_TIMEOUT");
      if (e instanceof GraphApiError) throw e;
      throw new GraphApiError("Không kết nối được API graph. Kiểm tra backend rồi thử lại.", 0, "NETWORK_ERROR");
    } finally {
      clearTimeout(timer); signal?.removeEventListener("abort", abort);
    }
  }
  return {
    async versions(options) {
      const data = await request("/versions", {}, options);
      if (!Array.isArray(data?.versions) || data.versions.some(v => !v.graph_version_id || v.status !== "READY")) {
        throw new GraphApiError("Danh sách phiên graph không đúng contract.", 502, "INVALID_RESPONSE");
      }
      return data;
    },
    async entities(params, options) {
      const data = await request("/entities", params, options);
      if (data?.meta?.graph_version_id !== params.graph_version_id || data?.meta?.status !== "READY" ||
          !Array.isArray(data.items) || data.items.some(n => !n.id || !["Company", "Person", "Event"].includes(n.type))) {
        throw new GraphApiError("Kết quả tìm thực thể sai phiên hoặc contract.", 502, "INVALID_RESPONSE");
      }
      return data;
    },
    async graph(params, options) {
      return validateGraph(await request("/neighborhood", params, options), params);
    },
    async relation(id, version, edge, options) {
      return validateRelation(await request("/relations/" + encodeURIComponent(id), { graph_version_id: version }, options), version, id, edge);
    },
  };
}
