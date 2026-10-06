// Đồ thị nhỏ để thử UI. ID và quan hệ theo backend/src/graph/graph_store.py;
// mọi bản ghi và provenance dưới đây đều là fixture, không đọc Neo4j.
export const rootOptions = [
  { value: "company:FPT", label: "FPT · Doanh nghiệp" },
  { value: "company:VCB", label: "VCB · Doanh nghiệp" },
  { value: "report:FPT:2025-YEAR", label: "FPT · Báo cáo 2025" },
  { value: "observation:FPT:assets", label: "FPT · Quan sát tổng tài sản" },
];

export const nodeTypes = [
  { type: "Company", label: "Doanh nghiệp", color: "#2563EB" },
  { type: "Dataset", label: "Dataset", color: "#475569" },
  { type: "FinancialReport", label: "Báo cáo", color: "#0284C7" },
  { type: "ReportingPeriod", label: "Kỳ báo cáo", color: "#EA580C" },
  { type: "Observation", label: "Quan sát", color: "#6366F1" },
  { type: "Metric", label: "Chỉ tiêu", color: "#7C3AED" },
  { type: "PriceBar", label: "Giá EOD", color: "#059669" },
];

const provenance = (datasetId, sourceFile, jsonPointer, note) => ({
  kind: "Dữ liệu minh họa",
  datasetId,
  source: "MOCK_FINMIND",
  sourceFile,
  jsonPointer,
  note,
});

export const graphFixture = {
  nodes: [
    { id: "company:FPT", type: "Company", label: "FPT", detail: "FPT Corporation" },
    { id: "dataset:FPT:demo", type: "Dataset", label: "FPT · dataset", detail: "Bản dữ liệu mock 2025" },
    { id: "report:FPT:2025-YEAR", type: "FinancialReport", label: "Báo cáo FPT", detail: "Kỳ 2025-YEAR · balance_sheet" },
    { id: "period:2025-YEAR", type: "ReportingPeriod", label: "2025-YEAR", detail: "Kỳ năm 2025" },
    { id: "observation:FPT:assets", type: "Observation", label: "Tổng tài sản", detail: "Quan sát mẫu của FPT" },
    { id: "metric:assets", type: "Metric", label: "totalAssets", detail: "Mã chỉ tiêu mẫu" },
    { id: "price:FPT:2025-12-31", type: "PriceBar", label: "Giá FPT EOD", detail: "31/12/2025 · không có giá thật" },
    { id: "company:VCB", type: "Company", label: "VCB", detail: "Vietcombank" },
    { id: "dataset:VCB:demo", type: "Dataset", label: "VCB · dataset", detail: "Bản dữ liệu mock 2025" },
    { id: "report:VCB:2025-YEAR", type: "FinancialReport", label: "Báo cáo VCB", detail: "Kỳ 2025-YEAR · balance_sheet" },
  ],
  edges: [
    { id: "fpt-has-dataset", source: "company:FPT", target: "dataset:FPT:demo", type: "HAS_DATASET", provenance: provenance("FPT:demo", null, null, "Quan hệ liên kết dataset; chưa có nguồn tài liệu riêng trên edge.") },
    { id: "fpt-has-report", source: "dataset:FPT:demo", target: "report:FPT:2025-YEAR", type: "HAS_REPORT", provenance: provenance("FPT:demo", "mock://fpt/financials.json", "/financial_data/balance_sheet/0", "Nguồn mẫu lấy từ metadata của FinancialReport.") },
    { id: "fpt-for-period", source: "report:FPT:2025-YEAR", target: "period:2025-YEAR", type: "FOR_PERIOD", provenance: provenance("FPT:demo", "mock://fpt/financials.json", "/financial_data/balance_sheet/0", "Kỳ báo cáo gắn với FinancialReport mẫu.") },
    { id: "fpt-has-observation", source: "report:FPT:2025-YEAR", target: "observation:FPT:assets", type: "HAS_OBSERVATION", provenance: provenance("FPT:demo", "mock://fpt/financials.json", "/financial_data/balance_sheet/0/totalAssets", "JSON Pointer mẫu lấy từ Observation.") },
    { id: "fpt-of-metric", source: "observation:FPT:assets", target: "metric:assets", type: "OF_METRIC", provenance: provenance("FPT:demo", "mock://fpt/financials.json", "/financial_data/balance_sheet/0/totalAssets", "Chỉ tiêu của Observation mẫu.") },
    { id: "fpt-has-price", source: "dataset:FPT:demo", target: "price:FPT:2025-12-31", type: "HAS_PRICE", provenance: provenance("FPT:demo", "mock://fpt/prices.json", "/price_history/0", "Giá cuối ngày mẫu; không phải giá thị trường thật.") },
    { id: "vcb-has-dataset", source: "company:VCB", target: "dataset:VCB:demo", type: "HAS_DATASET", provenance: provenance("VCB:demo", null, null, "Quan hệ liên kết dataset; chưa có nguồn tài liệu riêng trên edge.") },
    { id: "vcb-has-report", source: "dataset:VCB:demo", target: "report:VCB:2025-YEAR", type: "HAS_REPORT", provenance: provenance("VCB:demo", "mock://vcb/financials.json", "/financial_data/balance_sheet/0", "Nguồn mẫu lấy từ metadata của FinancialReport.") },
    { id: "vcb-for-period", source: "report:VCB:2025-YEAR", target: "period:2025-YEAR", type: "FOR_PERIOD", provenance: provenance("VCB:demo", "mock://vcb/financials.json", "/financial_data/balance_sheet/0", "Kỳ báo cáo gắn với FinancialReport mẫu.") },
  ],
};

export const emptyGraphFixture = { nodes: [], edges: [] };
