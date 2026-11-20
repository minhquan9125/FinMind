# Hướng đầu tư trong chat: kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat nhận ra hướng đầu tư của người dùng (ngắn hạn/kỹ thuật hoặc dài hạn/cơ bản), nhớ hướng đó trong phiên, phân tích theo hướng đó và nói rõ cho người dùng biết.

**Architecture:** Một module mới `investor_focus.py` gom toàn bộ từ khoá và quy tắc nhận diện. `_market_intent` dùng module này để chọn `focus` cho nhánh phân tích. `LiveResearchService.answer` lưu và giữ `scope['_investor_focus']` qua các lượt, giống `_last_question`. `_answer_market` thêm một dòng minh bạch vào đầu câu trả lời phân tích.

**Tech Stack:** Python 3.13, pytest. Không thêm thư viện.

**Spec:** `docs/superpowers/specs/2026-11-19-investor-focus-design.md`

## Global Constraints

- Không biến hướng đầu tư thành khuyến nghị mua/bán. Bộ kiểm intent (`intent_gate.decide` → `INTENT_OUT_OF_SCOPE`) giữ nguyên.
- Không mở rộng điều kiện kích hoạt nhánh phân tích (`trend`/`financial_analysis` trong `_market_intent`).
- Hướng chỉ được **ghi nhớ** khi người dùng tự nêu. Từ khoá trong câu hỏi lẻ chỉ đổi focus cho chính câu đó.
- Câu có từ của cả hai nhóm thì không đổi focus.
- Không commit. User chưa yêu cầu commit, các bước commit được bỏ.
- Chạy test từ thư mục gốc repo: `backend/.venv/Scripts/python.exe -m pytest backend/tests/<file> -q -p no:cacheprovider`.

## Review Focus

1. Viết không dấu ("toi luot song", "dau tu dai han") phải nhận như có dấu. Test ở Task 1.
2. Cụm dễ nhầm ("giá trị giao dịch", "hỗ trợ khách hàng", "cơ bản là") không được nhận thành hướng. Test ở Task 1.
3. Một tin nhắn vừa nêu hướng vừa hỏi ("Tôi đầu tư dài hạn, phân tích VCB") phải lưu hướng **và** trả lời phân tích theo hướng đó, không chỉ trả lời "đã ghi nhận". Test ở Task 3.
4. Câu xin tư vấn có kèm hướng ("Tôi lướt sóng, có nên mua VCB không?") vẫn bị từ chối, nhưng hướng vẫn được lưu cho lượt sau. Test ở Task 3.
5. Một lượt hỏi lại để làm rõ (ASK_CLARIFICATION) hoặc lỗi hạ tầng không được làm mất hướng đã nhớ. Test ở Task 3.

---

### Task 1: Module nhận diện hướng đầu tư

**Files:**
- Create: `backend/src/retrieval_orchestration/investor_focus.py`
- Test: `backend/tests/test_investor_focus.py`

**Interfaces:**
- Produces:
  - `focus_from_words(norm: str) -> str | None`: `'TECHNICAL'`, `'FINANCIAL'` hoặc `None` (không có từ, hoặc có từ của cả hai nhóm). `norm` là chữ đã qua `_fold` (bỏ dấu, chữ thường).
  - `stated_focus(text: str) -> str | None`: `'TECHNICAL'`, `'FINANCIAL'`, `'RESET'` hoặc `None`. Nhận câu người dùng **tự nêu** hướng: có đại từ (tôi/mình/em/anh/chị/tớ) và động từ (đầu tư/hay/thích/theo/chơi/ưu tiên/muốn/là nhà đầu tư) đi kèm từ khoá của một nhóm, hoặc lệnh "phân tích theo hướng …". `'RESET'` cho "phân tích chung", "bỏ hướng đầu tư", "không theo hướng nào".
  - `is_focus_only(text: str) -> bool`: `stated_focus(text)` khác `None` và câu không nhắc công ty nào (alias trong `DEFAULT_COMPANIES` hoặc mã trong `registered_symbols()`).
  - `FOCUS_LABEL = {'TECHNICAL': 'ngắn hạn (kỹ thuật)', 'FINANCIAL': 'dài hạn (cơ bản)'}`.
- Từ khoá: lấy **đúng** danh sách ở mục 1 của spec, viết ở dạng đã bỏ dấu, có ranh giới từ `\b`. `T+` khớp `t\+\d?`; `P/E`, `P/B` khớp `p/?e`, `p/?b`. Cụm dễ nhầm chỉ nhận theo cụm, theo đúng spec.

- [ ] **Step 1: Viết test fail** trong `backend/tests/test_investor_focus.py`:
  - `test_words_pick_focus` (parametrize, chạy qua `_fold` từ `retrieval_flow.intent`):
    - "lướt sóng VCB tuần này" → `TECHNICAL`; "toi luot song" → `TECHNICAL`; "RSI và MACD của FPT" → `TECHNICAL`; "vùng hỗ trợ của BID" → `TECHNICAL`.
    - "đầu tư dài hạn" → `FINANCIAL`; "cổ tức VCB" → `FINANCIAL`; "định giá P/E" → `FINANCIAL`; "dau tu gia tri" → `FINANCIAL`.
  - `test_ambiguous_or_mixed_words_pick_nothing`: "giá trị giao dịch hôm nay", "hỗ trợ khách hàng", "cơ bản là vậy", "ngắn hạn và dài hạn" → `None`.
  - `test_stated_focus`: "Tôi đầu tư dài hạn" → `FINANCIAL`; "mình hay lướt sóng" → `TECHNICAL`; "phân tích theo hướng ngắn hạn" → `TECHNICAL`; "phân tích chung" → `RESET`; "xu hướng giá VCB" → `None`, vì đây là câu hỏi, không phải tự nêu.
  - `test_focus_only`: "Tôi đầu tư dài hạn" → `True`; "Tôi đầu tư dài hạn, phân tích VCB" → `False`; "xu hướng VCB" → `False`.
- [ ] **Step 2: Chạy** `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_investor_focus.py -q -p no:cacheprovider`. Kỳ vọng: FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Viết `investor_focus.py`** với các hàm ở mục Interfaces. Import `_fold` từ `.retrieval_flow.intent`; import `DEFAULT_COMPANIES` và `registered_symbols` bên trong hàm, theo cách `conversation_actions.company_switch_question` đang làm, để tránh import vòng.
- [ ] **Step 4: Chạy lại.** Kỳ vọng: PASS.

### Task 2: Chọn focus cho nhánh phân tích

**Files:**
- Modify: `backend/src/retrieval_orchestration/live_research.py`, trong `_market_intent` (khoảng dòng 172–180, chỗ `focus = (...)`).
- Test: `backend/tests/test_market_research.py`, thêm cạnh `test_analysis_questions_carry_their_focus` (khoảng dòng 891).

**Interfaces:**
- Consumes: `focus_from_words` (Task 1).
- Produces: `scope['_market_request']` của câu phân tích có thêm `'focus_source'`, nhận giá trị `'QUESTION'`, `'STATED'` hoặc `'DEFAULT'`.

- [ ] **Step 1: Viết test fail** `test_analysis_focus_uses_words_then_session_focus`, gọi `analyze_live`:
  - `analyze_live('Phân tích VCB cho người lướt sóng')`: focus `TECHNICAL`, `focus_source` `QUESTION`.
  - `analyze_live('Phân tích VCB', {'_investor_focus': {'focus': 'FINANCIAL', 'source': 'STATED'}})`: focus `FINANCIAL`, `focus_source` `STATED`.
  - `analyze_live('Xu hướng giá VCB', {'_investor_focus': {'focus': 'FINANCIAL', 'source': 'STATED'}})`: focus `TECHNICAL`, `focus_source` `QUESTION` (câu hỏi thắng hướng đã nhớ).
  - `analyze_live('Phân tích VCB')`: focus `STOCK`, `focus_source` `DEFAULT`.
- [ ] **Step 2: Chạy test đó.** Kỳ vọng: FAIL.
- [ ] **Step 3: Sửa `_market_intent`.** Thứ tự ưu tiên:
  1. `financial_analysis` → `FINANCIAL`, `QUESTION`.
  2. `explicit_trend` → `TECHNICAL`, `QUESTION`.
  3. `focus_from_words(norm)` → giá trị đó, `QUESTION`.
  4. `(context or {}).get('_investor_focus', {}).get('focus')` → giá trị đó, `STATED`.
  5. Còn lại → `STOCK`, `DEFAULT`.
  
  Không đổi điều kiện `if ((trend or financial_analysis) and ...)`.
- [ ] **Step 4: Chạy** `backend/tests/test_market_research.py`. Kỳ vọng: PASS toàn bộ, kể cả `test_analysis_questions_carry_their_focus` cũ.

### Task 3: Nhớ hướng trong phiên, xác nhận khi chỉ nêu hướng

**Files:**
- Modify: `backend/src/retrieval_orchestration/live_research.py`, `LiveResearchService.answer` (khoảng dòng 1088, cạnh đoạn `company_switch_question` và `_last_question` vừa thêm).
- Test: `backend/tests/test_investor_focus.py`.

**Interfaces:**
- Consumes: `stated_focus`, `is_focus_only`, `FOCUS_LABEL` (Task 1).
- Produces: `result['scope']['_investor_focus'] = {'focus': 'TECHNICAL' | 'FINANCIAL', 'source': 'STATED'}`, giữ qua mọi lượt sau; bị xoá khi `stated_focus` trả `'RESET'`.

- [ ] **Step 1: Viết test fail.** Dùng engine giả có sẵn trong test (`SequenceEngine` hoặc `LiveResearchService` với provider giả, như `tests/test_chat_priority_fixes.py`):
  - `test_focus_only_message_is_acknowledged_without_retrieval`: `answer('Tôi đầu tư dài hạn', sid, {})` trả `reason_code == 'INVESTOR_FOCUS_SET'`, `message == 'Đã ghi nhận: các phân tích sau sẽ theo hướng dài hạn (cơ bản). Muốn đổi, hãy nói “phân tích theo hướng ngắn hạn” hoặc “phân tích chung”.'`, `scope['_investor_focus'] == {'focus': 'FINANCIAL', 'source': 'STATED'}`, và không có truy xuất nào.
  - `test_focus_survives_following_turns`: một lượt kết thúc bằng `ASK_CLARIFICATION` hoặc `SYSTEM_UNAVAILABLE` vẫn giữ `_investor_focus` trong scope.
  - `test_reset_clears_focus`: `answer('phân tích chung', sid, {'_investor_focus': {...}})` trả scope không còn `_investor_focus`, kèm `message == 'Đã bỏ hướng đầu tư đã ghi nhận; các phân tích sau sẽ trình bày chung.'`.
  - `test_statement_with_question_answers_with_that_focus`: "Tôi đầu tư dài hạn, phân tích VCB": không trả lời bằng câu xác nhận; scope của kết quả có `_investor_focus` FINANCIAL.
  - `test_advice_still_refused_but_focus_kept`: "Tôi lướt sóng, có nên mua VCB không?" trả `reason_code == 'INTENT_OUT_OF_SCOPE'`, và scope vẫn có `_investor_focus` TECHNICAL.
- [ ] **Step 2: Chạy.** Kỳ vọng: FAIL.
- [ ] **Step 3: Sửa `answer`.**
  - Trước `_answer_turn`: tính `stated = stated_focus(question)` và cập nhật một bản sao của `context` (`'RESET'` thì bỏ khoá `_investor_focus`).
  - Nếu `is_focus_only(question)` hoặc `stated == 'RESET'`: trả ngay dict cùng dạng với nhánh `GREETING` (`b1_decision='ACKNOWLEDGE'`, `status='GREETING'`, `reason_code='INVESTOR_FOCUS_SET'` hoặc `'INVESTOR_FOCUS_CLEARED'`), message đúng như trong test, `scope` là context đã cập nhật.
  - Sau `_answer_turn`: nếu context có `_investor_focus` mà `result['scope']` chưa có thì chép sang.
- [ ] **Step 4: Chạy** `test_investor_focus.py` và `test_chat_priority_fixes.py`. Kỳ vọng: PASS.

### Task 4: Dòng minh bạch trong câu trả lời phân tích

**Files:**
- Modify: `backend/src/retrieval_orchestration/live_research.py`, `_answer_market`, ngay sau `out = await complete_retrieval(...)` (khoảng dòng 1478).
- Test: `backend/tests/test_market_research.py`.

**Interfaces:**
- Consumes: `FOCUS_LABEL` (Task 1); `focus` và `focus_source` trong `_market_request` (Task 2).

- [ ] **Step 1: Viết test fail** `test_analysis_answer_states_its_focus`. Dựa theo `test_financial_focus_without_verified_bctc_says_so`:
  - Với `focus_source == 'STATED'`, draft bắt đầu bằng `'Phân tích theo hướng dài hạn (cơ bản), theo bạn đã nêu. Muốn đổi, hãy nói “phân tích theo hướng ngắn hạn” hoặc “phân tích chung”.\n\n'`.
  - Với `focus_source == 'QUESTION'`, đoạn đầu là `'Phân tích theo hướng ngắn hạn (kỹ thuật), theo câu hỏi của bạn.\n\n'`.
  - Với focus `STOCK`, draft không thay đổi.
- [ ] **Step 2: Chạy.** Kỳ vọng: FAIL.
- [ ] **Step 3: Thêm dòng vào đầu `out['answering']['draft']`** khi `status == 'DRAFT_READY'`, `source_type == 'MARKET_ANALYSIS'` và focus thuộc `FOCUS_LABEL`. Câu chữ đúng như trong test. Dòng chèn sau khi đã kiểm trích dẫn, giống các ghi chú cuối đang có.
- [ ] **Step 4: Chạy toàn bộ test chat** (lệnh lọc file `chat|research|market|intent|router|answer|live|news|summary|conversation|presentation|render|citation`). Kỳ vọng: không có lỗi mới ngoài 22 lỗi cũ (18 `test_financial_health_db` cần DB 15434, 4 `test_article_intent` do upstream).

### Task 5: Kiểm chứng trên chat thật

- [ ] **Step 1:** Khởi động lại backend (`uvicorn src.main:app`, port 8000), đợi `/api/health` báo `research_warmup` ready.
- [ ] **Step 2:** Chạy lại 70 câu: `api_run.py` → `outputs/s5_chat_eval_vcb_bid_20261118/run04/`. Chấm bằng `run02/score.py` (đổi đường dẫn). Kỳ vọng: số câu Đạt không thấp hơn `run03`.
- [ ] **Step 3:** Chạy 3 hội thoại tay qua API rồi lưu kết quả vào `run04/focus_dialogs.json`:
  - (a) "Tôi đầu tư dài hạn" → "Phân tích VCB": lượt 2 mở đầu bằng dòng "theo bạn đã nêu", nhóm đầu là "Tình hình tài chính".
  - (b) "mình hay lướt sóng" → "Phân tích BID": nhóm đầu là "Xu hướng giá".
  - (c) "phân tích chung" → "Phân tích VCB": không có dòng hướng.
