# Lọc mã theo dữ kiện: kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Câu hỏi "mã/doanh nghiệp/công ty nào đang tăng/phát triển/ngon/đáng đầu tư" trả về danh sách mã xếp theo dữ kiện (xu hướng giá, tăng trưởng BCTC), tính từ DB, không qua Gemini.

**Architecture:** Module mới `screening.py` gồm hàm nhận diện câu hỏi và hàm dựng câu trả lời (thuần, dễ test). `LiveResearchService._answer_turn` gọi module này trước bước kiểm intent. Dữ liệu đọc qua `self.market.trend_reader` / `self.market.health_reader` (đã có) và `self.prices.symbols()`.

**Tech Stack:** Python 3.13, pytest.

**Spec:** `docs/superpowers/specs/2026-11-19-stock-screening-design.md`

## Global Constraints

- Không gọi Gemini; mọi số liệu lấy nguyên từ `get_price_trend` và `get_financial_health`.
- Không thêm câu miễn trừ cuối danh sách.
- Không commit (user chưa yêu cầu).
- Test chạy từ thư mục gốc: `backend/.venv/Scripts/python.exe -m pytest backend/tests/<file> -q -p no:cacheprovider`.

## Review Focus

1. Câu có tên một công ty cụ thể ("FPT đang phát triển tốt không") không được coi là câu lọc. Test ở Task 1.
2. "nên mua VCB không" vẫn bị từ chối, không biến thành danh sách. Test ở Task 1.
3. Một mã đọc lỗi không làm hỏng cả câu trả lời. Test ở Task 2.
4. Không mã nào đạt điều kiện thì ghi rõ "Chưa có…", không trả danh sách rỗng. Test ở Task 1.
5. Viết không dấu ("ma nao dang tang") vẫn nhận. Test ở Task 1.

---

### Task 1: Module `screening.py`

**Files:**
- Create: `backend/src/retrieval_orchestration/screening.py`
- Test: `backend/tests/test_screening.py`

**Interfaces:**
- Produces:
  - `is_screening_question(text: str, symbols: set[str]) -> bool`
  - `render_screen(trends: dict[str, dict], healths: dict[str, dict], as_of: str, focus: str | None, skipped: int = 0) -> str`
  - `HORIZONS = (('20', 'ngắn hạn'), ('60', 'trung hạn'), ('200', 'dài hạn'))`

- [ ] **Step 1: Viết test fail.**
  - Nhận đúng: "h mã nào đang xu hướng", "mã nào đang phát triển tốt", "hiện tại mã nào đang ngon để đầu tư", "doanh nghiệp nào đang tăng trưởng", "công ty nào tốt", "ma nao dang tang".
  - Không nhận: "FPT đang phát triển tốt không", "nên mua VCB không", "giá VCB hôm nay", "mã nào là của Vietcombank".
  - `render_screen`: mã có nhãn `UP` ở khung 20 phiên được liệt kê, xếp theo lợi suất giảm dần, dạng `FPT (+6,2% trong 20 phiên, giá trên SMA20 3,1%)`. Khung không có mã nào thì ghi "Chưa có mã nào có xu hướng tăng dài hạn (200 phiên) theo dữ liệu.". Không có BCTC tăng trưởng thì ghi "Chưa đủ số liệu BCTC đã đối chiếu để so sánh tăng trưởng cùng kỳ.". `focus='FINANCIAL'` thì nhóm BCTC đứng trước. Dòng đầu là `Lọc theo dữ kiện đến ngày 18/11/2026:`. Không có chữ "không chịu trách nhiệm".
- [ ] **Step 2: Chạy, kỳ vọng FAIL.**
- [ ] **Step 3: Cài đặt.**
  - Chủ thể: `(?:ma|co phieu|doanh nghiep|cong ty)\s+nao|nhung ma|cac ma`.
  - Từ trạng thái: `dang tang|xu huong|phat trien|tang truong|ngon|tot|manh|khoe|dang dau tu|nen dau tu|trien vong`.
  - Câu có token khớp `symbols` hoặc alias trong `DEFAULT_COMPANIES` thì không phải câu lọc.
  - Số hiển thị theo kiểu Việt (dấu phẩy thập phân, 1 chữ số lẻ).
- [ ] **Step 4: Chạy, kỳ vọng PASS.**

### Task 2: Nối vào chat

**Files:**
- Modify: `backend/src/retrieval_orchestration/live_research.py`, trong `_answer_turn`, ngay sau nhánh `_GREETING` và trước `news_reference`.
- Test: `backend/tests/test_screening.py`

**Interfaces:**
- Consumes: Task 1; `self.prices.symbols()`; `self.market.trend_reader(symbol)`; `self.market.health_reader(symbol)`.
- Produces: kết quả dạng `dict(status='EVIDENCE_READY', reason_code='SCREENING_READY', b1_decision='SCREENING', answering={'status': 'DRAFT_READY', 'draft': <render_screen>, 'claims': [], 'citations': [], 'manifest': {'response_mode': 'SCREENING'}}, scope=context)`, cùng dạng với nhánh `PRICE_ANALYTICS`.

- [ ] **Step 1: Viết test fail.** Dùng `LiveResearchService` với `prices` giả (`symbols()` trả `{'FPT', 'VCB'}`) và `market` giả (`trend_reader` / `health_reader` async).
  - "mã nào đang tăng" trả `reason_code == 'SCREENING_READY'`, draft chứa `FPT`.
  - `trend_reader` lỗi với một mã: vẫn trả danh sách, draft có câu `(Bỏ qua 1 mã do chưa đọc được dữ liệu.)`.
  - Có `context['_investor_focus']` FINANCIAL: nhóm BCTC đứng trước.
- [ ] **Step 2: Chạy, kỳ vọng FAIL.**
- [ ] **Step 3: Cài đặt.** Đọc song song bằng `asyncio.gather(..., return_exceptions=True)`. Dùng `as_of` lớn nhất trong các kết quả trend.
- [ ] **Step 4: Chạy toàn bộ test chat.** Kỳ vọng: không có lỗi mới ngoài 4 lỗi cũ của `test_article_intent`.

### Task 3: Kiểm chứng trên chat thật

- [ ] Khởi động lại backend, hỏi qua API 3 câu: "h mã nào đang xu hướng", "mã nào đang phát triển tốt", "hiện tại mã nào đang ngon để đầu tư". Mỗi câu phải trả về danh sách có lý do và nguồn.
