// Số đo định tuyến và kiểm tra nguồn của một lượt hỏi, lấy đúng từ details do backend ghi.
// Không suy diễn: thiếu dữ liệu (lượt cũ) thì trả null để trang giữ câu "chưa ghi nhận".

const ROUTES = { GRAPH: "Đồ thị tri thức (Neo4j)", VECTOR: "Tìm vector / BM25", BOTH: "Đồ thị rồi tìm nội dung", CLARIFY: "Hỏi lại người dùng" };
const ADAPTERS = { GRAPH: "Graph", CONTENT: "Nội dung (vector)" };
const CHECKS = { citation_binding: "Gắn trích dẫn vào nguồn", extractive_claim_check: "Kiểm tra luận điểm trích nguyên văn",
  support_quote_check: "Đoạn trích dẫn có thật trong nguồn", numeric_source_check: "Số liệu khớp dòng nguồn" };
const B3 = { b3_evidence_gate: "Evidence Gate (B3)", b3_answer_verification: "Answer Verification (B3)" };

export const routeLabel = route => ROUTES[route] || route || "Không xác định";

/** Phần định tuyến: tuyến, các bộ nạp, số lần gọi graph/vector, phân loại bằng chứng. */
export function routingView(details) {
  const router = details?.router;
  const types = Object.entries(details?.evidence_types || {}).map(([type, count]) => ({ type, count }));
  if (!router && !types.length) return null;
  return {
    route: router ? routeLabel(router.route) : null,
    adapters: (router?.adapters || []).map(name => ADAPTERS[name] || name),
    graphCalls: router?.graph_calls ?? null,
    vectorCalls: router?.vector_calls ?? null,
    evidenceTypes: types.sort((a, b) => b.count - a.count),
  };
}

/** Kiểm tra nguồn của B1: mỗi bước đang bật hay tắt, và có bản nháp bị bác không. */
export function groundingView(details) {
  const g = details?.grounding;
  if (!g) return null;
  return {
    status: g.status || null,
    reason: g.reason_code || null,
    citations: g.citations ?? 0,
    mode: g.response_mode || null,
    checks: Object.entries(CHECKS).filter(([key]) => key in (g.checks || {})).map(([key, label]) => ({ key, label, enabled: g.checks[key] })),
    rejectedReason: g.draft_rejected_reason || null,
  };
}

/** Hai thành phần B3: nếu manifest ghi tắt thì nói rõ là tắt, không phải "đạt" hay "chưa đo". */
export function b3View(details) {
  const flags = details?.b3 || {};
  return Object.entries(B3).filter(([key]) => key in flags).map(([key, label]) => ({ key, label, enabled: flags[key] }));
}

/**
 * Ba thẻ dịch vụ của trang Tổng quan (Graph, Evidence Gate, Verifier) từ tổng hợp trong ngày.
 * Chỉ nói điều đã đo: chưa có lượt nào được ghi nhận thì giữ trạng thái "chưa có dữ liệu".
 */
export function pipelineServices(pipeline) {
  const none = { label: "Chưa có lượt hỏi nào được ghi nhận hôm nay", tone: "neutral" };
  const seen = pipeline?.requests_observed || 0;
  const b3 = pipeline?.b3 || {};
  const gateOn = b3.b3_evidence_gate, verifierOn = b3.b3_answer_verification;
  const b3Label = flag => flag === undefined ? none.label : flag ? "Đang bật" : "Tắt theo cấu hình";
  return [
    { id: "graph", name: "Graph Service", ...(seen ? { label: `${pipeline.graph_calls} lần gọi graph hôm nay`, tone: pipeline.graph_calls ? "success" : "neutral" } : none),
      desc: seen ? `Trong ${seen} lượt hỏi được ghi nhận. Tuyến: ${Object.entries(pipeline.routes || {}).map(([route, n]) => `${route} ${n}`).join(", ") || "chưa có"}. Gọi vector: ${pipeline.vector_calls}.`
        : "Số lần Chat đọc đồ thị tri thức, đo theo từng lượt hỏi thật." },
    { id: "gate", name: "Evidence Gate", label: b3Label(gateOn), tone: gateOn ? "success" : "neutral",
      desc: seen ? `Gate B3 ${gateOn === false ? "tắt" : "chưa rõ"}. Kiểm tra nguồn của B1: ${pipeline.grounded_answers} câu trả lời có nguồn, ${pipeline.drafts_rejected_by_source_check} bản nháp Gemini bị bác.`
        : "Kiểm tra bằng chứng trước khi trả lời." },
    { id: "verifier", name: "Verifier", label: b3Label(verifierOn), tone: verifierOn ? "success" : "neutral",
      desc: verifierOn === false ? "Answer Verification B3 tắt trong cấu hình nên chưa có tỷ lệ luận điểm được hỗ trợ." : "Xác minh luận điểm của câu trả lời so với nguồn." },
  ];
}
