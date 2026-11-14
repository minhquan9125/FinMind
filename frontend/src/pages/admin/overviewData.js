import { getOperations, localTime, STATE_LABELS } from "./operationsApi.js";
import { pipelineServices } from "./traceMetrics.js";

export function overviewData(operations, journal = null) {
  const storage = operations.storage;
  const ready = storage.status === "available" && storage.corpus_status === "FROZEN" && storage.index_status === "ACTIVE";
  const alerts = [];
  if (!ready) alerts.push({ id: "storage", tone: "error", text: "Chưa đọc được phiên kho dữ liệu đang phục vụ hoặc phiên chưa sẵn sàng.", to: "/admin/ingestion", linkLabel: "Kiểm tra dữ liệu" });
  if (operations.counts.QUARANTINED) alerts.push({ id: "review", tone: "warning", text: `${operations.counts.QUARANTINED} bài cần kiểm tra nguồn hoặc OCR.`, to: "/admin/ingestion", linkLabel: "Xem bài" });
  if (operations.job_counts.FAILED) alerts.push({ id: "jobs", tone: "warning", text: `${operations.job_counts.FAILED} lần xử lý thất bại trong lịch sử.`, to: "/admin/ingestion", linkLabel: "Xem lần chạy" });
  const init = operations.initialization || {};
  const telemetry = operations.telemetry?.status === "available" ? operations.telemetry : null;
  const budget = operations.api_budget?.usage?.configured ? operations.api_budget : null;
  const amount = value => Number(value).toLocaleString("vi-VN", { style: "currency", currency: "USD", maximumFractionDigits: 6 });
  if (budget?.usage.warning) alerts.push({ id: "api-budget", tone: budget.usage.exceeded ? "error" : "warning", text: `Ngân sách API ước tính đã dùng ${budget.usage.percent.toFixed(2)}%${budget.usage.complete ? "" : " (số liệu chưa đầy đủ)"}.`, to: "/admin/configuration", linkLabel: "Xem ngân sách" });
  const labels = { SUCCESS: "Có câu trả lời", ERROR: "Lỗi vận hành", INSUFFICIENT_EVIDENCE: "Không đủ bằng chứng", CLARIFICATION: "Cần làm rõ", OTHER: "Phản hồi khác" };
  const recentTraces = (telemetry?.recent || []).map(row => ({
    id: row.id, time: localTime(row.created_at), company: row.companies.join(", ") || "—",
    status: labels[row.outcome] || row.outcome, tone: row.outcome === "ERROR" ? "error" : row.outcome === "SUCCESS" ? "success" : "warning",
    duration: `${(row.duration_ms / 1000).toFixed(2)}s`,
    tokens: row.unknown_calls ? `${row.known_total.toLocaleString("vi-VN")} đã biết · ${row.unknown_calls} lần chưa xác định` : row.known_total.toLocaleString("vi-VN"),
    model: [...new Set(row.calls.map(c => c.model))].join(", ") || "Không gọi model",
  }));
  const initialization = key => init[key] === "ready" ? "Đã khởi tạo" : init[key] ? "Chưa sẵn sàng" : "Chưa triển khai giám sát";
  const measured = [
    { id: "research-api", name: "Research API", desc: "Khởi tạo mô hình truy hồi và cache; chưa kiểm tra nhà cung cấp LLM.", label: initialization("research"), tone: init.research === "ready" ? "success" : "warning" },
    { id: "retrieval", name: "Retrieval Service", desc: "Khởi tạo Hybrid Router trên backend đang chạy.", label: initialization("router"), tone: init.router === "ready" ? "success" : "warning" },
    { id: "vector", name: "Vector Store", desc: "Kết nối DB và trạng thái phiên dữ liệu đang phục vụ.", label: ready ? "Đã kết nối" : "Cần kiểm tra", tone: ready ? "success" : "warning" },
  ];
  return {
    operations, telemetry, journalAvailable: journal !== null, alerts, budget, recentTraces,
    kpis: ["Truy vấn hôm nay", "Truy vấn thành công", "Truy vấn không đủ bằng chứng", "Lỗi vận hành AI", "Token đã sử dụng", "Ngân sách API đã sử dụng"].map((label, id) => ({ id, label,
      value: id === 5 && budget ? `${amount(budget.usage.used_usd)} / ${amount(budget.usage.limit_usd)}` : telemetry && id < 5 ? [telemetry.total, telemetry.outcomes.SUCCESS || 0, telemetry.outcomes.INSUFFICIENT_EVIDENCE || 0, telemetry.outcomes.ERROR || 0, telemetry.total_tokens][id].toLocaleString("vi-VN") : "—",
      note: id === 5 ? budget ? `Ước tính theo ${budget.usage.period === "month" ? "tháng" : "ngày"}${budget.usage.complete ? "" : " · Chưa đầy đủ"}` : "Chưa cấu hình giá API" : !telemetry ? "Chưa đọc được thống kê" : id === 4 && telemetry.unknown_calls ? `Tổng đã biết · ${telemetry.unknown_calls} lần gọi chưa xác định` : "Hôm nay · giờ Việt Nam" })),
    activities: (journal?.items || []).map(e => ({ id: e.id, time: localTime(e.created_at),
      text: `${e.actor} · ${STATE_LABELS[e.action] || ({ SOURCE_CONFIG: "Cập nhật cấu hình nguồn", RETRY_INDEX: "Thử nạp lại", INTERRUPT: "Ngắt lần chạy" })[e.action] || e.action}`,
      resource: e.resource })),
    activityDate: "Giờ Việt Nam",
    services: [...measured, { id: "telemetry", name: "Telemetry", tone: telemetry ? "success" : "warning", label: telemetry ? "Đã kết nối thống kê" : "Chưa đọc được thống kê", desc: "Ghi nhận truy vấn Chat và token Gemini trên máy này." }, ...pipelineServices(telemetry?.pipeline)],
  };
}

export async function getOverview(signal) {
  const [operations, journal] = await Promise.all([
    getOperations("/overview", signal),
    getOperations("/audit?limit=5", signal).catch(error => {
      if (signal?.aborted) throw error;
      return null;
    }),
  ]);
  return overviewData(operations, journal);
}
