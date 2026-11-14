// Dữ liệu minh họa cho trang Ngưỡng & ngân sách API (từ A04-configuration.html).
// Khi backend xong, thay getConfigurationData() bằng hàm gọi API.
//
// versions[].params: giá trị từng tham số (khóa khớp với FIELDS trong AdminConfigurationPage.jsx).
// budget: ngân sách kỳ hiện tại (đơn vị) và token trung bình mỗi request.

const BASE_PARAMS = {
  relevance: 75, evidence: 75, verifier: 80, minEvidence: 3, freshness: 365,
  vectorLimit: 20, graphLimit: 10, fusionTopK: 8, rerankLimit: 5,
  contextCeiling: 5000, inputCeiling: 6500, outputCeiling: 2500, totalCeiling: 8000,
  warningThreshold: 80,
};

const by = "System Admin";

export const versionsMock = [
  {
    v: "CFG v2.5", kind: "PRODUCTION", status: "Đang chờ kích hoạt", created: "04/10/2026", by, activated: "—",
    changes: ["Ngưỡng bằng chứng 75% → 80%", "Tổng token tối đa 8,000 → 7,000", "Warning threshold 80% → 75%"],
    params: { ...BASE_PARAMS, evidence: 80, totalCeiling: 7000, warningThreshold: 75 },
  },
  {
    v: "CFG v2.4", kind: "PRODUCTION", status: "Đang hoạt động", created: "01/10/2026", by, activated: "02/10/2026", activatedBy: by,
    corpus: "v1.4", changes: ["Giới hạn kết quả sau fusion 6 → 8"],
    traceExample: { id: "TRC-DEMO-004", text: "TRC-DEMO-004 — Verifier 60% < ngưỡng 80% → Không đạt" },
    params: { ...BASE_PARAMS },
  },
  {
    v: "CFG v2.3", kind: "PRODUCTION", status: "Đã thay thế", created: "24/09/2026", by, activated: "25/09/2026",
    changes: ["Ngưỡng xác minh 75% → 80%"],
    params: { ...BASE_PARAMS, fusionTopK: 6 },
  },
  {
    v: "CFG v2.2", kind: "PRODUCTION", status: "Đã thay thế", created: "17/09/2026", by, activated: "18/09/2026",
    changes: ["Rerank limit 8 → 5"],
    params: { ...BASE_PARAMS, fusionTopK: 6, verifier: 75 },
  },
];

export const budgetMock = { limit: 100, used: 61, avgTokens: 4666 };

// Giả lập gọi API. Đặt window.__FM_FAIL = true trong console để thử trạng thái lỗi.
export function getConfigurationData() {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (typeof window !== "undefined" && window.__FM_FAIL) reject(new Error("Không thể tải dữ liệu cấu hình."));
      else resolve({ versions: versionsMock.map((v) => ({ ...v, params: { ...v.params }, changes: [...v.changes] })), budget: { ...budgetMock } });
    }, 400);
  });
}
