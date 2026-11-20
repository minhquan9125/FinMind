# TÀI LIỆU THIẾT KẾ KIẾN TRÚC API (API SPECIFICATION)

## Dự án: FinMind — Research Copilot for Vietnamese Listed Companies

**Mã đề tài:** CMU-SE 450 – C1SE.35 | Capstone Project 1
**Phiên bản tài liệu:** 1.0.0 (Tương thích Proposal v2.1 & SRS v2.0)
**Tiêu chuẩn thiết kế:** RESTful API Specification (OpenAPI 3.0 compatible) & RFC 7807 Problem Details
**Cập nhật lần cuối:** 12/10/2026

---

## 1. NGUYÊN TẮC THIẾT KẾ VÀ QUY ƯỚC CHUNG

### 1.1. Mục tiêu & Phạm vi kiến trúc

Hệ thống API của **FinMind** được thiết kế nhằm phục vụ giao tiếp giữa Web Application (ReactJS) với Backend Services (FastAPI), hỗ trợ luồng truy vấn **Hybrid Graph–Vector RAG**, kiểm soát dữ liệu đa nguồn (PostgreSQL/pgvector, Neo4j, Gemini API), và cung cấp cơ chế kiểm định độc lập cho 4 cấu hình thử nghiệm (**B0**: Structured Control, **B1**: Vector RAG, **B2**: Hybrid Graph-Vector RAG, **B3**: Full FinMind).

* **Base URL:** `https://api.finmind.vn/api/v1` (Production) | `http://localhost:8000/api/v1` (Local Development)
* **Format dữ liệu:** `application/json` (Encoding: `UTF-8`)
* **Thời gian (Timestamp):** Chuẩn ISO-8601 UTC dạng `YYYY-MM-DDTHH:mm:ss.sssZ`
* **Quy ước đặt tên (Naming Convention):**
  * URI paths: Kebab-case (ví dụ: `/api/v1/golden-set`, `/api/v1/corpus-versions`)
  * JSON field names: Snake_case (ví dụ: `company_id`, `statement_scope`, `citation_coverage`)
* **Phân quyền (RBAC - Role-Based Access Control):**
  * `RESEARCHER` (Nhà đầu tư cá nhân / Người nghiên cứu)
  * `FINANCIAL_ANALYST` (Chuyên viên phân tích tài chính)
  * `DATA_ENGINEER` (Kỹ sư dữ liệu & vận hành Ingestion)
  * `ADMINISTRATOR` (Quản trị hệ thống, ngân sách, người dùng)
  * `EVALUATOR` (Người kiểm định mô hình, chạy benchmark B0-B3)

### 1.2. HTTP Headers chuẩn

| Tên Header          |                       Bắt buộc                       | Mô tả                                                                                    |
| :------------------- | :----------------------------------------------------: | :----------------------------------------------------------------------------------------- |
| `Authorization`    |            Có (trừ login/register/health)            | Bearer Token:`Bearer <jwt_access_token>`                                                 |
| `X-Trace-Id`       | Khuyến nghị (Client gửi) / Bắt buộc (Server trả) | UUID định danh vết truy vết xuyên suốt vòng đời Request (FR20, NFR09)             |
| `X-Corpus-Version` |                       Tùy chọn                       | Chỉ định phiên bản Corpus khi truy vấn/đánh giá (mặc định lấy active version) |
| `Content-Type`     |             Bắt buộc với POST/PUT/PATCH             | Mặc định:`application/json; charset=utf-8`                                            |

### 1.3. Định dạng phản hồi chuẩn (Standard Envelope Response)

Mọi phản hồi trả về từ API đều tuân thủ cấu trúc đồng nhất:

```json
{
  "success": true,
  "data": {},
  "meta": {
    "trace_id": "7f8b9c21-d24a-4e2a-9642-123456789abc",
    "timestamp": "2026-10-12T14:30:00.000Z",
    "version": "v1.0",
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_records": 100,
      "total_pages": 5
    }
  }
}
```

### 1.4. Xử lý lỗi chuẩn (RFC 7807 Problem Details)

Khi gặp lỗi (HTTP Status Code >= 400), payload trả về phải cung cấp mã lỗi nội bộ, lý do và gợi ý phục hồi:

```json
{
  "success": false,
  "error": {
    "type": "https://api.finmind.vn/errors/EVIDENCE_GATE_FAILED",
    "title": "Evidence Sufficiency Check Failed",
    "status": 422,
    "code": "INSUFFICIENT_EVIDENCE",
    "detail": "Retrieved evidence does not contain audited figures for metric 'Vốn chủ sở hữu' in Q2/2026.",
    "instance": "/api/v1/copilot/query",
    "trace_id": "7f8b9c21-d24a-4e2a-9642-123456789abc",
    "invalid_params": []
  }
}
```

---

## 2. BẢNG MÃ LỖI VÀ MÃ TỪ CHỐI AN TOÀN (REASON CODES)

Hệ thống FinMind tuân thủ nguyên tắc **Từ chối an toàn (Safe Abstention / Insufficient-Data Safety >= 0.95, FR13, NFR04)**:

| Mã lỗi (Reason Code)        | Ý nghĩa nghiệp vụ                                                                        |        Trạng thái phản hồi        |
| :---------------------------- | :------------------------------------------------------------------------------------------- | :-----------------------------------: |
| `CORPUS_OUT_OF_SCOPE`       | Doanh nghiệp không nằm trong 10 mã cổ phiếu được cấp phép của MVP                |    400 Bad Request / Safe Refusal    |
| `PERIOD_OUT_OF_SCOPE`       | Kỳ báo cáo vượt ngoài phạm vi 3 năm tài chính và 4 quý gần nhất                |    400 Bad Request / Safe Refusal    |
| `EVIDENCE_ABSENT`           | Không tìm thấy bất kỳ bằng chứng/tài liệu nào trong kho lưu trữ                  | 422 Unprocessable / Insufficient Data |
| `EVIDENCE_STALE`            | Dữ liệu tìm thấy quá cũ so với ngưỡng cập nhật yêu cầu                          | 422 Unprocessable / Insufficient Data |
| `EVIDENCE_CONTRADICTORY`    | Dữ liệu giữa các nguồn đối nghịch nhau và chưa được đối soát                 |  422 Unprocessable / Partial Answer  |
| `EVIDENCE_LOW_RELEVANCE`    | Điểm độ tương đồng/liên quan sau chuẩn hóa < ngưỡng cấu hình                  | 422 Unprocessable / Insufficient Data |
| `UNSUPPORTED_CALCULATION`   | Không đủ công thức tính toán hoặc thiếu số hạng hợp lệ                          | 422 Unprocessable / Insufficient Data |
| `BUDGET_CEILING_EXCEEDED`   | Đã chạm trần chi phí hoặc token của Gemini API trong tuần (Fail-closed)              |         429 Too Many Requests         |
| `PROMPT_INJECTION_DETECTED` | Phát hiện lệnh điều khiển bất thường trong tài liệu hoặc câu hỏi người dùng |            400 Bad Request            |

---

## 3. DANH SÁCH CHI TIẾT CÁC ENDPOINTS

```
+-------------------------------------------------------------------------------------------------------------+
|                                    BẢN ĐỒ CÁC PHÂN HỆ API TRONG FINMIND                                     |
+-------------------------------------------------------------------------------------------------------------+
| 1. AUTH & SESSION       : Quản lý người dùng, phân quyền RBAC, theo dõi lịch sử nghiên cứu, Watchlist.      |
| 2. COMPANIES & MARKET   : Tra cứu thông tin 10 doanh nghiệp, BCTC, chỉ số tài chính, giá EOD, công bố.    |
| 3. RESEARCH COPILOT     : Lõi Q&A Hybrid RAG, Evidence Gate, Claim Citation & Answer Verification.          |
| 4. RETRIEVAL & FUSION   : Endpoint các nhánh tìm kiếm riêng biệt (Structured, Vector, Graph, Hybrid).       |
| 5. KNOWLEDGE GRAPH      : Trực quan hóa và khám phá mạng lưới thực thể quan hệ tối đa 2-hop (Neo4j).        |
| 6. INGESTION & PIPELINE : Nạp dữ liệu, kiểm tra OCR/Chunking, thẩm định số liệu & khu vực cách ly.          |
| 7. CORPUS GOVERNANCE    : Đóng băng phiên bản corpus, tính SHA-256 manifest, lưu trữ snapshot.             |
| 8. FEEDBACK & AUDIT     : Tiếp nhận báo lỗi số liệu/trích dẫn từ chuyên viên, truy vết nguồn gốc.          |
| 9. EVALUATION WORKSPACE : Thực thi benchmark B0-B3 trên Golden Test Set 120 câu, đo đạc chỉ số RAGAS.       |
| 10. SYSTEM & BUDGET OPS : Giám sát Trace, Telemetry, Hạn mức Token Gemini & Kiểm tra sức khỏe dịch vụ.     |
+-------------------------------------------------------------------------------------------------------------+
```

---

### PHÂN HỆ 1: AUTHENTICATION, USERS & WATCHLIST (FR17, FR19, FR22)

#### 1.1. Đăng ký tài khoản

* **Endpoint:** `POST /api/v1/auth/register`
* **Quyền hạn:** Public
* **Mô tả:** Đăng ký người dùng mới với vai trò mặc định `RESEARCHER`.
* **Request Body:**

```json
{
  "email": "analyst@example.com",
  "username": "hung_thai",
  "password": "StrongPassword!2026",
  "full_name": "Thái Quốc Hưng"
}
```

* **Response Body (201 Created):**

```json
{
  "success": true,
  "data": {
    "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "analyst@example.com",
    "username": "hung_thai",
    "full_name": "Thái Quốc Hưng",
    "roles": ["RESEARCHER"],
    "created_at": "2026-10-12T14:30:00.000Z"
  }
}
```

#### 1.2. Đăng nhập hệ thống

* **Endpoint:** `POST /api/v1/auth/login`
* **Quyền hạn:** Public
* **Request Body:**

```json
{
  "username": "hung_thai",
  "password": "StrongPassword!2026"
}
```

* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "d7b92a34-5891-4e0e-9273-01928374a5b6",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "username": "hung_thai",
      "full_name": "Thái Quốc Hưng",
      "roles": ["RESEARCHER", "FINANCIAL_ANALYST"]
    }
  }
}
```

#### 1.3. Lấy thông tin cá nhân hiện tại

* **Endpoint:** `GET /api/v1/auth/me`
* **Quyền hạn:** Authenticated

#### 1.4. Quản lý Watchlist (Danh sách theo dõi)

* **Endpoint:** `GET /api/v1/watchlist` | `POST /api/v1/watchlist` | `DELETE /api/v1/watchlist/{company_id}`
* **Quyền hạn:** Authenticated
* **Request Body (POST):**

```json
{
  "company_id": "11111111-2222-3333-4444-555555555555"
}
```

* **Response Body (200 OK):** Danh sách công ty trong watchlist kèm thông tin vắn tắt (symbol, sector, giá EOD gần nhất).

---

### PHÂN HỆ 2: COMPANIES & MARKET DATA REGISTRY (FR14, FR18)

#### 2.1. Tra cứu danh sách công ty trong phạm vi Corpus

* **Endpoint:** `GET /api/v1/companies`
* **Quyền hạn:** Public / Authenticated
* **Query Parameters:**
  * `query`: Tìm theo ticker hoặc tên (ví dụ: `FPT`, `Vietcombank`)
  * `sector`: `Banking` hoặc `Technology`
  * `exchange`: `HOSE`, `HNX`
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": [
    {
      "company_id": "fpt-0001-uuid",
      "symbol": "FPT",
      "company_name": "Công ty Cổ phần FPT",
      "industry_type": "IT Services & Software",
      "sector": "Technology",
      "exchange": "HOSE",
      "is_active": true,
      "available_periods": ["2023", "2024", "2025", "2026-Q1", "2026-Q2"]
    }
  ]
}
```

#### 2.2. Chi tiết hồ sơ và dữ liệu tài chính chuẩn hóa

* **Endpoint:** `GET /api/v1/companies/{symbol_or_id}`
* **Response Body (200 OK):** Hồ sơ doanh nghiệp, cơ cấu cổ đông lớn, ban lãnh đạo, và các kỳ BCTC đã nạp vào hệ thống.

#### 2.3. Lấy chỉ số tài chính có cấu trúc (Structured Financial Facts)

* **Endpoint:** `GET /api/v1/companies/{symbol_or_id}/facts`
* **Query Parameters:**
  * `metric_codes`: `NII`, `REV`, `PAT`, `ROE`, `ROA` (ngăn cách bởi dấu phẩy)
  * `period_type`: `ANNUAL` hoặc `QUARTERLY`
  * `statement_scope`: `CONSOLIDATED` (Hợp nhất) hoặc `SEPARATE` (Công ty mẹ)
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "symbol": "VCB",
    "statement_scope": "CONSOLIDATED",
    "facts": [
      {
        "metric_code": "NII",
        "metric_name": "Thu nhập lãi thuần",
        "period": "2025",
        "value": 54200.5,
        "unit": "Tỷ VND",
        "audit_status": "AUDITED",
        "locator": {
          "doc_id": "doc-vcb-2025-audited-fs",
          "page": 42,
          "table": "Báo cáo kết quả hoạt động kinh doanh",
          "source_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      }
    ]
  }
}
```

#### 2.4. Dữ liệu giá đóng cửa lịch sử (EOD Price Bars)

* **Endpoint:** `GET /api/v1/companies/{symbol_or_id}/prices`
* **Lưu ý:** Chỉ phục vụ tham chiếu ngữ cảnh, **tuyệt đối không cung cấp chỉ báo kỹ thuật mua/bán**.

---

### PHÂN HỆ 3: CORE RESEARCH COPILOT & GROUNDED Q&A (FR05 - FR13)

Đây là **phân hệ trái tim** của FinMind, hiện thực hóa luồng xử lý: **Intent Routing -> Hybrid Retrieval -> Evidence Gate -> Gemini Grounding -> Citation Engine -> Answer Verification -> Safe Response**.

#### 3.1. Thực hiện truy vấn nghiên cứu (Research Query Endpoint)

* **Endpoint:** `POST /api/v1/copilot/query`
* **Quyền hạn:** Authenticated (`RESEARCHER`, `FINANCIAL_ANALYST`)
* **Headers:**
  * `X-Trace-Id` (Tùy chọn, hệ thống tự cấp mới nếu thiếu)
* **Request Body:**

```json
{
  "question": "Thu nhập lãi thuần của VCB trong năm 2025 và 2024 thay đổi như thế nào, và nguyên nhân chính được ban điều hành giải trình trong báo cáo thường niên là gì?",
  "company_symbols": ["VCB"],
  "configuration": "B3",
  "statement_scope_preference": "CONSOLIDATED",
  "language": "VI",
  "temperature": 0.0
}
```

* **Giải thích tham số:**

  * `configuration`: Chọn cấu hình thực thi:
    * `B0`: Structured Control (chỉ truy xuất SQL facts và công thức deterministic, không gọi LLM tự do).
    * `B1`: Vector RAG (Vector retrieval qua pgvector + Gemini).
    * `B2`: Hybrid Graph-Vector RAG (Vector + Graph Neo4j + Rerank fusion, tắt Gate & Verifier để ablation).
    * `B3`: Full FinMind (Mặc định: Hybrid + Structured + Evidence Gate + Answer Verification).
* **Response Body thành công (200 OK - Answer Released with Citations):**

```json
{
  "success": true,
  "data": {
    "query_id": "3c7b2a9e-63f5-41e9-80aa-3b5678abcdef",
    "question": "Thu nhập lãi thuần của VCB trong năm 2025 và 2024 thay đổi như thế nào...",
    "status": "ANSWERED",
    "configuration": "B3",
    "answer": {
      "summary": "Thu nhập lãi thuần (NII) hợp nhất của Vietcombank (VCB) năm 2025 đạt 54.200,50 tỷ VND, tăng 4,1% so với mức 52.065,80 tỷ VND của năm 2024. Động lực chính đến từ việc mở rộng quy mô tín dụng bán lẻ và quản trị chi phí vốn hiệu quả.",
      "claims": [
        {
          "claim_id": "clm-001",
          "ordinal": 1,
          "claim_text": "Thu nhập lãi thuần hợp nhất năm 2025 của VCB đạt 54.200,50 tỷ VND.",
          "claim_type": "QUANTITATIVE",
          "verification_status": "VERIFIED",
          "citations": [
            {
              "citation_id": "cit-001",
              "evidence_id": "evi-vcb-nii-2025",
              "document_title": "BCTC Hợp nhất Kiểm toán 2025 - VCB",
              "source_url": "https://vietcombank.com.vn/ir/bctc_2025.pdf",
              "source_sha256": "a1b2c3d4e5f6071829...",
              "period": "2025",
              "statement_scope": "CONSOLIDATED",
              "locator": {
                "page": 42,
                "table": "Báo cáo kết quả kinh doanh hợp nhất",
                "row_index": 3
              }
            }
          ]
        },
        {
          "claim_id": "clm-002",
          "ordinal": 2,
          "claim_text": "Tăng trưởng 4,1% so với mức 52.065,80 tỷ VND của năm 2024.",
          "claim_type": "CALCULATION",
          "verification_status": "VERIFIED",
          "calculation_detail": {
            "formula": "(54200.5 - 52065.8) / 52065.8 * 100",
            "computed_value": 4.10,
            "unit": "%"
          },
          "citations": [
            {
              "citation_id": "cit-002",
              "evidence_id": "evi-vcb-nii-2024",
              "document_title": "BCTC Hợp nhất Kiểm toán 2024 - VCB",
              "source_url": "https://vietcombank.com.vn/ir/bctc_2024.pdf",
              "locator": { "page": 40, "table": "Báo cáo kết quả kinh doanh hợp nhất" }
            }
          ]
        },
        {
          "claim_id": "clm-003",
          "ordinal": 3,
          "claim_text": "Ban điều hành giải trình động lực đến từ tăng trưởng tín dụng bán lẻ và kiểm soát chi phí huy động vốn.",
          "claim_type": "FACTUAL",
          "verification_status": "VERIFIED",
          "citations": [
            {
              "citation_id": "cit-003",
              "evidence_id": "chunk-vcb-ar-2025-p15",
              "document_title": "Báo cáo thường niên 2025 - VCB",
              "locator": { "page": 15, "section": "Đánh giá của Ban Tổng giám đốc" }
            }
          ]
        }
      ]
    },
    "evidence_gate": {
      "status": "PASSED",
      "relevance_score": 0.94,
      "stale_check": "PASSED",
      "conflict_check": "NO_CONFLICT",
      "mandatory_branches_present": ["STRUCTURED", "VECTOR"]
    },
    "answer_verification": {
      "status": "PASSED",
      "checked_items": {
        "numerical_accuracy": 1.0,
        "period_consistency": 1.0,
        "unit_consistency": 1.0,
        "statement_scope_consistency": 1.0,
        "citation_coverage": 1.0
      }
    },
    "telemetry": {
      "trace_id": "trace-9876-uuid",
      "latency_total_ms": 2850,
      "latency_breakdown": {
        "intent_routing_ms": 120,
        "structured_retrieval_ms": 35,
        "vector_retrieval_ms": 180,
        "graph_retrieval_ms": 210,
        "evidence_fusion_ms": 45,
        "evidence_gate_ms": 15,
        "gemini_generation_ms": 2100,
        "answer_verification_ms": 145
      },
      "token_usage": {
        "prompt_tokens": 1420,
        "completion_tokens": 310,
        "total_tokens": 1730,
        "model_name": "gemini-1.5-pro"
      }
    }
  }
}
```

* **Response Body khi kích hoạt Từ chối an toàn (200 OK - Safe Fallback Response, FR13):**
  *Khi Evidence Gate không thỏa mãn hoặc Verifier phát hiện dữ liệu không thể chứng minh:*

```json
{
  "success": true,
  "data": {
    "query_id": "3c7b2a9e-63f5-41e9-80aa-3b5678abcdef",
    "question": "Dự báo lợi nhuận sau thuế của VCB trong quý 4 năm 2026 là bao nhiêu?",
    "status": "REFUSED_SAFELY",
    "reason_code": "OUT_OF_SCOPE_PREDICTION",
    "user_message": "FinMind là Research Copilot chỉ cung cấp phân tích dựa trên dữ liệu lịch sử và chứng cứ đã công bố. Hệ thống từ chối đưa ra dự báo giá, dự báo lợi nhuận hoặc khuyến nghị giao dịch theo nguyên tắc an toàn.",
    "partial_data": null,
    "available_evidence": [],
    "suggested_next_steps": "Bạn có thể tra cứu số liệu lợi nhuận thực tế của các kỳ gần nhất đã kiểm toán (2023, 2024, 2025 hoặc 6 tháng đầu năm 2026)."
  }
}
```

#### 3.2. Xem chi tiết thông tin trích dẫn / chứng cứ (Evidence Detail)

* **Endpoint:** `GET /api/v1/evidence/{evidence_id}`
* **Quyền hạn:** Authenticated
* **Mô tả:** Cho phép người dùng click vào trích dẫn trên UI để xem trích đoạn văn bản gốc, trang PDF, bảng số liệu hoặc vị trí đoạn trích trong đồ thị (FR11, OBJ05).
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "evidence_id": "evi-vcb-nii-2025",
    "evidence_type": "STRUCTURED_OBSERVATION",
    "company_symbol": "VCB",
    "metric_code": "NII",
    "canonical_metric_name": "Thu nhập lãi và các khoản thu nhập tương tự thuần",
    "period": "2025",
    "value": 54200500000000,
    "display_value": "54.200,50",
    "unit": "Tỷ VND",
    "statement_scope": "CONSOLIDATED",
    "document": {
      "document_id": "doc-vcb-2025-audited-fs",
      "title": "Báo cáo tài chính hợp nhất kiểm toán năm 2025",
      "source_url": "https://portal.vietcombank.com.vn/ir/bctc_2025_audited.pdf",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "published_at": "2026-03-28"
    },
    "locator": {
      "page_number": 42,
      "table_name": "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT",
      "line_item_vn": "I. Thu nhập lãi thuần",
      "line_number": 3
    },
    "provenance_chain": {
      "ingestion_job_id": "job-8721-abc",
      "validator": "DeterministicFinancialValidator_v2",
      "validated_at": "2026-09-28T10:15:00Z"
    }
  }
}
```

#### 3.3. Quản lý Lịch sử Nghiên cứu cá nhân (FR19, NFR10)

* `GET /api/v1/copilot/history`: Lấy danh sách các câu hỏi gần đây của người dùng.
* `DELETE /api/v1/copilot/history/{query_id}`: Xóa câu hỏi khỏi lịch sử (tuân thủ quyền riêng tư, NFR10).

---

### PHÂN HỆ 4: RETRIEVAL ENGINE & BASELINE SERVICES (FR07, FR08, FR16)

Dành cho việc kiểm thử độc lập các nhánh Retrieval phục vụ nghiên cứu thực nghiệm và so sánh ablation B0, B1, B2.

#### 4.1. Structured Retrieval API (B0 Baseline)

* **Endpoint:** `POST /api/v1/retrieval/structured`
* **Mô tả:** Truy xuất số liệu chính xác từ PostgreSQL bằng câu truy vấn tất định (deterministic lookup & arithmetic).
* **Request Body:**

```json
{
  "symbol": "TCB",
  "metric_codes": ["NII", "NPL_RATIO"],
  "periods": ["2024", "2025"],
  "statement_scope": "CONSOLIDATED"
}
```

#### 4.2. Vector Semantic Retrieval API (B1 Baseline)

* **Endpoint:** `POST /api/v1/retrieval/vector`
* **Mô tả:** Nhúng câu hỏi bằng mô hình `BAAI/bge-m3` (1024 chiều) và tìm kiếm Cosine Similarity trên PostgreSQL/pgvector.
* **Request Body:**

```json
{
  "query": "Chiến lược chuyển đổi số và đầu tư công nghệ ngân hàng",
  "symbol": "MBB",
  "top_k": 5,
  "threshold": 0.65
}
```

#### 4.3. Graph Knowledge Traversal API

* **Endpoint:** `POST /api/v1/retrieval/graph`
* **Mô tả:** Thực hiện Cypher query trên Neo4j, giới hạn tối đa 2 hops từ nút thực thể gốc (FR08, ADR02).
* **Request Body:**

```json
{
  "entity_symbol": "FPT",
  "max_hops": 2,
  "relationship_types": ["SUBSIDIARY_OF", "PARTICIPATES_IN", "AFFECTED_BY_EVENT"]
}
```

#### 4.4. Hybrid Retrieval & Evidence Fusion API (B2 Baseline)

* **Endpoint:** `POST /api/v1/retrieval/hybrid`
* **Mô tả:** Gộp kết quả từ Vector và Graph, chuẩn hóa điểm số về khoảng `[0, 1]`, khử trùng lặp và xếp hạng lại (Reciprocal Rank Fusion / Weighted Fusion) (FR08, ADR06).

---

### PHÂN HỆ 5: KNOWLEDGE GRAPH EXPLORER (FR15)

Cung cấp dữ liệu trực quan hóa đồ thị tri thức mạng lưới thực thể cho giao diện người dùng React Flow.

#### 5.1. Khám phá thực thể xung quanh doanh nghiệp (Max 2 Hops)

* **Endpoint:** `GET /api/v1/graph/explore`
* **Query Parameters:**
  * `symbol`: Ví dụ: `FPT`
  * `depth`: `1` hoặc `2` (Mặc định: 1, giới hạn tối đa 2)
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "center_node": "comp-fpt",
    "nodes": [
      { "id": "comp-fpt", "label": "FPT", "type": "COMPANY", "properties": { "name": "CTCP FPT", "sector": "Technology" } },
      { "id": "comp-frt", "label": "FRT", "type": "COMPANY", "properties": { "name": "FPT Retail" } },
      { "id": "sec-tech", "label": "Công nghệ", "type": "SECTOR" },
      { "id": "ev-ai-center", "label": "Khánh thành AI Center", "type": "EVENT", "properties": { "year": 2025 } }
    ],
    "edges": [
      {
        "id": "rel-001",
        "source": "comp-fpt",
        "target": "comp-frt",
        "type": "ASSOCIATE_COMPANY",
        "properties": { "ownership_percent": 46.5 },
        "evidence_id": "evi-graph-fpt-frt-2025"
      },
      {
        "id": "rel-002",
        "source": "comp-fpt",
        "target": "ev-ai-center",
        "type": "ORGANIZED",
        "evidence_id": "evi-graph-fpt-event-2025"
      }
    ]
  }
}
```

#### 5.2. Kiểm tra bằng chứng liên kết quan hệ đồ thị (Graph Provenance)

* **Endpoint:** `GET /api/v1/graph/edges/{edge_id}/provenance`
* **Mô tả:** Đảm bảo mọi đường nối trong Neo4j đều có căn cứ từ tài liệu đã thẩm định, không có quan hệ do LLM tự bịa đặt.

---

### PHÂN HỆ 6: INGESTION PIPELINE & DATA GOVERNANCE (FR01, FR02, FR03, FR23)

Dành cho `DATA_ENGINEER` và `ADMINISTRATOR` quản lý quá trình nạp tài liệu.

#### 6.1. Quản lý Source Adapters

* `GET /api/v1/admin/sources`: Lấy danh sách nguồn thu thập (HOSE, HNX, IR Portals, Thư viện BCTC).
* `POST /api/v1/admin/sources`: Thêm cấu hình nguồn mới kèm chính sách tần suất crawl.
* `PATCH /api/v1/admin/sources/{source_id}`: Tạm dừng (`pause`) hoặc kích hoạt (`enable`).

#### 6.2. Kích hoạt Ingestion Job

* **Endpoint:** `POST /api/v1/admin/ingest/jobs`
* **Quyền hạn:** `DATA_ENGINEER`, `ADMINISTRATOR`
* **Request Body:**

```json
{
  "source_id": "src-vietstock-or-hose",
  "symbol": "BID",
  "report_type": "FINANCIAL_STATEMENT",
  "year": 2025,
  "quarter": 4,
  "is_audited": true,
  "force_reingest": false
}
```

* **Response Body (202 Accepted):** Trả về `job_id`, trạng thái `PENDING`.

#### 6.3. Quản lý vùng cách ly số liệu (Quarantine Management - FR03, NFR07)

Khi quá trình Ingestion phát hiện số liệu không khớp (lệch đơn vị, số dư không cân, thiếu thông tin kiểm toán), bản ghi sẽ bị đẩy vào **Quarantine**:

* `GET /api/v1/admin/quarantine`: Xem danh sách bản ghi lỗi / nghi vấn.
* `POST /api/v1/admin/quarantine/{record_id}/review`: Quyết định của kỹ sư dữ liệu: `APPROVE_MANUAL`, `REJECT`, hoặc `CORRECT`.

---

### PHÂN HỆ 7: CORPUS GOVERNANCE (FR23, OBJ01)

Dành cho việc đóng băng tập tài liệu trước khi tiến hành benchmark đánh giá.

#### 7.1. Lấy danh sách và trạng thái các phiên bản Corpus

* **Endpoint:** `GET /api/v1/admin/corpus/versions`

#### 7.2. Đóng băng phiên bản Corpus (Corpus Freeze)

* **Endpoint:** `POST /api/v1/admin/corpus/versions/freeze`
* **Quyền hạn:** `ADMINISTRATOR`
* **Request Body:**

```json
{
  "version_label": "v2.1-corpus-frozen-sprint1",
  "description": "Corpus đóng băng gồm 10 mã (5 Banking, 5 Tech) từ 2023 đến Q2/2026."
}
```

* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "corpus_version_id": "corp-v21-uuid",
    "version_label": "v2.1-corpus-frozen-sprint1",
    "manifest_sha256": "8f3b890a424e819b76c8c971...",
    "total_documents": 240,
    "total_chunks": 18500,
    "total_observations": 12800,
    "frozen_at": "2026-09-27T18:00:00Z",
    "status": "FROZEN"
  }
}
```

---

### PHÂN HỆ 8: FACT & CITATION FEEDBACK (FR21)

Cho phép người dùng gắn cờ (report) khi nghi ngờ câu trả lời hoặc trích dẫn chưa chuẩn xác.

#### 8.1. Gửi phản hồi lỗi số liệu / trích dẫn

* **Endpoint:** `POST /api/v1/feedback`
* **Quyền hạn:** Authenticated
* **Request Body:**

```json
{
  "query_id": "3c7b2a9e-63f5-41e9-80aa-3b5678abcdef",
  "citation_id": "cit-001",
  "evidence_id": "evi-vcb-nii-2025",
  "issue_type": "WRONG_NUMBER",
  "comment": "Số liệu NII trên trang 42 là 54.200 tỷ nhưng câu trả lời lại ghi sai đơn vị thành triệu VND."
}
```

* **Response Body (201 Created):** Ghi nhận vào cơ sở dữ liệu `feedback`, hệ thống **tuyệt đối không tự ý ghi đè số liệu vào cơ sở tri thức gốc** mà chờ chuyên viên rà soát.

---

### PHÂN HỆ 9: EVALUATION & BENCHMARK WORKSPACE (FR16, OBJ08)

Hiện thực hóa bộ công cụ đánh giá khoa học so sánh thực nghiệm 4 cấu hình **B0, B1, B2, B3** trên tập **120 câu hỏi Golden Test Set**.

#### 9.1. Lấy danh sách bộ đề Golden Test Set

* **Endpoint:** `GET /api/v1/evaluation/golden-set`
* **Query Parameters:**
  * `split`: `CALIBRATION` (40 câu) hoặc `LOCKED_FINAL` (80 câu)
  * `category`: `NUMERICAL`, `FACTUAL`, `MULTI_HOP`, `COMPARISON`, `INSUFFICIENT_EVIDENCE`, `ADVERSARIAL`

#### 9.2. Kích hoạt đợt chạy đánh giá thực nghiệm (Run Benchmark)

* **Endpoint:** `POST /api/v1/evaluation/runs`
* **Quyền hạn:** `EVALUATOR`, `ADMINISTRATOR`
* **Request Body:**

```json
{
  "run_label": "Eval_Sprint6_Final_LockedSplit_B1_vs_B2_vs_B3",
  "configurations": ["B0", "B1", "B2", "B3"],
  "test_split": "LOCKED_FINAL",
  "corpus_version_id": "corp-v21-uuid",
  "concurrency": 10
}
```

* **Response Body (202 Accepted):** Trả về `run_id`, trạng thái `RUNNING`.

#### 9.3. Lấy báo cáo chỉ số đánh giá (Evaluation Metrics Results - Table 15)

* **Endpoint:** `GET /api/v1/evaluation/runs/{run_id}/metrics`
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "run_id": "run-20261125-01",
    "test_split": "LOCKED_FINAL",
    "total_questions": 80,
    "metrics_by_configuration": {
      "B1_Vector_RAG": {
        "faithfulness": 0.82,
        "context_precision": 0.76,
        "quantitative_correctness": 0.81,
        "citation_correctness": 0.91,
        "citation_coverage": 0.89,
        "retrieval_recall": 0.78,
        "insufficient_data_safety": 0.65,
        "latency_p95_sec": 4.2,
        "avg_tokens_per_query": 1450
      },
      "B2_Hybrid_Graph_Vector": {
        "faithfulness": 0.86,
        "context_precision": 0.84,
        "quantitative_correctness": 0.84,
        "citation_correctness": 0.92,
        "citation_coverage": 0.90,
        "retrieval_recall": 0.88,
        "insufficient_data_safety": 0.68,
        "latency_p95_sec": 6.8,
        "avg_tokens_per_query": 2100
      },
      "B3_Full_FinMind": {
        "faithfulness": 0.93,
        "context_precision": 0.88,
        "quantitative_correctness": 0.98,
        "citation_correctness": 0.97,
        "citation_coverage": 0.98,
        "retrieval_recall": 0.89,
        "insufficient_data_safety": 0.98,
        "latency_p95_sec": 7.9,
        "avg_tokens_per_query": 2250
      }
    },
    "acceptance_status": {
      "quantitative_correctness_passed": true,
      "faithfulness_passed": true,
      "citation_correctness_passed": true,
      "insufficient_data_safety_passed": true,
      "latency_p95_passed": true
    }
  }
}
```

---

### PHÂN HỆ 10: OPERATIONS, AUDIT LOG & BUDGET CONTROL (FR20, NFR01, NFR11)

Dành cho giám sát hạ tầng và kiểm soát chi phí Google Gemini API.

#### 10.1. Kiểm tra ngân sách Token & Chi phí hàng tuần

* **Endpoint:** `GET /api/v1/ops/budget`
* **Response Body (200 OK):**

```json
{
  "success": true,
  "data": {
    "period_start": "2026-10-12T00:00:00Z",
    "period_end": "2026-10-18T23:59:59Z",
    "weekly_token_budget": 5000000,
    "tokens_consumed": 1280000,
    "estimated_cost_vnd": 384000,
    "cost_ceiling_vnd": 1500000,
    "status": "HEALTHY",
    "fail_closed_triggered": false
  }
}
```

#### 10.2. Cập nhật ngưỡng an toàn và hạn mức trần (Fail-closed Control)

* **Endpoint:** `PUT /api/v1/ops/budget`
* **Quyền hạn:** `ADMINISTRATOR`
* **Request Body:**

```json
{
  "cost_ceiling_vnd": 1500000,
  "fail_closed_threshold_percent": 95,
  "max_context_tokens_per_request": 4096
}
```

#### 10.3. Tra cứu vết hệ thống (Trace Inspection)

* **Endpoint:** `GET /api/v1/ops/traces/{trace_id}`
* **Mô tả:** Xem toàn bộ luồng thực thi chi tiết của một truy vấn (routing decision, raw scores từng nhánh, prompt payload, Gemini latency).

#### 10.4. Kiểm tra sức khỏe toàn hệ thống (System Health Check)

* **Endpoint:** `GET /api/v1/health`
* **Response Body (200 OK):**

```json
{
  "status": "OK",
  "services": {
    "fastapi": "healthy",
    "postgresql": "healthy",
    "pgvector": "healthy",
    "neo4j": "healthy",
    "gemini_api": "healthy"
  },
  "active_corpus_version": "v2.1-corpus-frozen-sprint1"
}
```

---

## 4. BẢNG TỔNG HỢP VÀ ĐỐI CHIẾU VỚI PROPOSAL (REQUIREMENTS TRACEABILITY)

Tài liệu API này đáp ứng 100% các yêu cầu chức năng (FR) và phi chức năng (NFR) trong Proposal:

| Nhóm API                    | Phân hệ Endpoint                                | Mã FR / NFR tương ứng                       |
| :--------------------------- | :------------------------------------------------ | :---------------------------------------------- |
| **Auth & Sessions**    | `/api/v1/auth/*`, `/api/v1/watchlist`         | FR17, FR19, FR22, NFR13                         |
| **Companies Registry** | `/api/v1/companies/*`                           | FR14, FR18                                      |
| **Research Copilot**   | `/api/v1/copilot/query`, `/api/v1/evidence/*` | FR05, FR06, FR09, FR10, FR11, FR12, FR13, NFR06 |
| **Retrieval Layers**   | `/api/v1/retrieval/*`                           | FR07, FR08, ADR01, ADR02, ADR04, ADR06          |
| **Knowledge Graph**    | `/api/v1/graph/*`                               | FR15, ADR02                                     |
| **Ingestion Pipeline** | `/api/v1/admin/ingest/*`, `/quarantine/*`     | FR01, FR02, FR03, NFR07, ADR03                  |
| **Corpus Governance**  | `/api/v1/admin/corpus/*`                        | FR23, OBJ01                                     |
| **Feedback System**    | `/api/v1/feedback`                              | FR21                                            |
| **Evaluation RAG**     | `/api/v1/evaluation/*`                          | FR16, OBJ08, NFR03, Table 13-15                 |
| **Ops & Budgeting**    | `/api/v1/ops/*`, `/api/v1/health`             | FR20, NFR01, NFR02, NFR09, NFR11                |

---

## 5. HƯỚNG DẪN TÍCH HỢP CHO ĐỘI NGŨ PHÁT TRIỂN

1. **Frontend (ReactJS / Tailwind CSS):**
   * Sử dụng `X-Trace-Id` được sinh ra từ mỗi câu hỏi để liên kết nút *"Xem nguồn trích dẫn"* (Citation Drawer) và nút *"Báo lỗi số liệu"* (Report Feedback).
   * Tại màn hình Graph Explorer, gọi `GET /api/v1/graph/explore?symbol={TICKER}&depth=2` và liên kết với thư viện `React Flow`.
2. **Backend (FastAPI / LangChain):**
   * Khai báo Routers tương ứng trong thư mục `backend/src/api/routers/`:
     * `copilot.py`, `companies.py`, `retrieval.py`, `graph.py`, `evaluation.py`, `admin.py`.
   * Tuân thủ cơ chế `async/await` với Connection Pool của PostgreSQL và `AsyncGraphDatabase` của Neo4j.
3. **Môi trường triển khai:**
   * Cấu hình đầy đủ biến môi trường trong file `.env` (bao gồm `GEMINI_API_KEY`, `NEO4J_URI`, `POSTGRES_URL`).
