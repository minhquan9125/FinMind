# Huyen tasks on backup-demo v2 ? 16/11/2026

Scope authorized in chat: update 04.2, 07.1 and 04.3 for the existing demo v2; push only Huyen changes. No edits or imports from another branch to Nhan/Hung files.

Design: retain legacy APIs for historical contract regression; add explicit v2 APIs using the installed 11-label producer. Recheck rule evidence against the current question using installed v2 rules, never trust classifier confidence as calibrated. Server chooses routes; provider schema matches the deployed gate (no route or period). Preserve verified scope and fail closed. Default direct rules enabled, server may turn them off; model-only proposals always fallback. No cosine calibration is claimed.

Plan:
- [x] Add failing v2 routing and provider contract tests.
- [x] Implement v2 APIs in Huyen modules only; remove unavailable v1 producer dependencies from legacy fixture tests without claiming real-producer validation.
- [x] Move acceptance CLI to installed v2 API/artifact, preserve historical v1 gold, clearly separate development regression from independent acceptance.
- [x] Run Huyen and existing v2/chat regression tests plus project collection; report limitations honestly.
- [x] Verify changed-file allowlist against latest origin/backup-demo, fast-forward and push backup-demo without force.

Compatibility is module-level. Existing live chat remains on Hung intent_gate_v2; wiring new APIs into chat is outside these tasks. No provider network calls in tests. Giữ nguyên code Nhân/Hưng.


## API bàn giao

```python
from src.retrieval_orchestration.intent_routing import decide_intent_route_v2
from src.retrieval_orchestration.intent_fallback_contract import (
    prepare_fallback_request_v2, validate_fallback_response_v2,
)

# classification: kết quả classify_intent của Nhân đã có trên demo.
# company_ticker và period do tầng scope xác minh; không lấy từ AI.
result = decide_intent_route_v2(classification, question=question,
    company_ticker=verified_ticker, period=verified_period)
prepared = prepare_fallback_request_v2(result, question=question)
if prepared['need_fallback']:
    # Runner 07.2 chịu trách nhiệm gọi provider và deadline thật.
    validated = validate_fallback_response_v2(provider_json,
        request=prepared['request'], **prepared['validation_context'])
```

- Giao diện cũ `decide_intent_route`, `prepare_fallback_request`, `validate_fallback_response` giữ contract 7 nhãn để hồi quy lịch sử. Giao diện có hậu tố `_v2` dùng đúng 11 nhãn. Không đổi ngầm contract của caller cũ.
- Quyết định v2: SEARCH với MARKET/VECTOR/GRAPH/BOTH; SESSION; REFUSE; ASK_CLARIFICATION; NEED_FALLBACK. Cờ server `allow_direct_rules=False` chỉ tắt đường trực tiếp, không cho AI bỏ qua yêu cầu hạn chế.
- MIXED cần thành phần xác minh; có thành phần bị hạn chế thì REFUSE, có chỉ dẫn hội thoại chưa phân giải thì không tự tìm kiếm. Câu nối tiếp vẫn hỏi lại để tầng phiên phân giải; API này chưa nhận context đã xác minh.
- NEWS có bộ lọc kỳ lưu trữ đã xác minh đi VECTOR; NEWS không có bộ lọc kỳ đi MARKET. Không tự trích hoặc đoán kỳ. PRICE luôn MARKET theo yêu cầu v2.
- JSON provider chỉ có intent_label/confidence/reason/extracted_company như gate đang chạy; route do server tính và period giữ nguyên từ request. AI không được thêm scope chưa xác minh. Ngưỡng 0,60 là điểm tự báo, không phải xác suất đã hiệu chỉnh.
- Trace có source RULES/CLASSIFIER/AI, reason_code; model_ranking/model_top_1_score/model_score_gap ghi riêng, không gán điểm model cho bằng chứng luật. Không dùng ngưỡng cosine 0,65/0,08 của v1 cho v2.
- Không thay `intent_gate_v2.py`, `intent_v2_classifier.py`, `intent_v2_rules.py`, code chat, dữ liệu mẫu/nhãn/vector/weights hoặc requirements. Chat hiện vẫn dùng gate của Hưng; đưa module task lên demo không đồng nghĩa đã thay wiring Chat bằng API mới.

## Kiểm chứng và giới hạn

- BGE-M3 thật đã chạy 110 câu DEVELOPMENT v2: 110/110 khớp nhãn và thành phần, 0 lỗi giao diện, hash đầu vào trước/sau giữ nguyên. Kết quả `outputs/s5_huyen_v2_20261116/run01`.
- Báo cáo Excel 6 sheet giữ điểm model thật, quyết định thật và ca sai. CLI dùng API/artifact v2 có sẵn, không phụ thuộc module V7 nghỉ dùng. Bộ 80 câu v1 giữ nguyên trong router-acceptance-v1; không sửa gold cũ để tăng điểm.
- Đây là bộ DEVELOPMENT công khai đã được dùng trong phát triển, không phải test kín. Độ đúng tuyến trên bộ câu mới và nghiệm thu đầy đủ 04.3 vẫn CHƯA ĐƯỢC CHỨNG MINH. `full_043_acceptance=NOT_ESTABLISHED`.
- Coverage policy được đo riêng từ unit/contract tests; không lấy fallback thành công làm nhãn phân loại đúng. Số liệu cuối ghi tại `verification.json`.
- Lượt toàn backend ở snapshot trung gian: 3876 passed, 70 failed, 30 skipped, 2 xfailed. Có lỗi môi trường thiếu PIL, PostgreSQL test 127.0.0.1:15434 không kết nối được và 5 lỗi WBS02. Không ghi toàn backend PASS; không sửa các task đó trong đợt này. Bộ task/intent/chat liên quan được chạy lại ở snapshot cuối.
- Chưa gọi Gemini, chưa kiểm E2E Chat, chưa hiệu chỉnh ngưỡng embedding v2, chưa tạo hoặc phát hành bộ test kín. Không đưa model, cache vector, .venv hoặc log trung gian vào commit.

Chạy lại (từ FinMind):

```powershell
$env:PYTHONPATH='backend'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.venv/Scripts/python.exe backend/scripts/evaluate_s5_router.py --output outputs/s5_huyen_v2_20261116/run02
```

Phần cuối còn cần nhóm thực hiện theo phân công: Hưng nối API mới nếu thay gate, bộ test kín và gold tuyến độc lập cho 04.3, chốt ngưỡng v2 sau calibration. Những phần này không được báo đã hoàn thành chỉ từ kết quả merge.
