# Phân tích BCTC độc lập với giá

Mục tiêu: xem từng chỉ tiêu doanh nghiệp tăng/giảm theo kỳ tương đương và đứng ở đâu trong nhóm đối chiếu có dữ liệu. Kết quả không phải dự báo giá hoặc kết luận mạnh nhất toàn ngành.

## Dùng lại trong backend/Chat

```python
from backend.src.financial.health_store import canonical_rows
from backend.src.financial.health import analyze_company
from backend.src.financial.peers import compare_peers

facts = canonical_rows(records)  # records: snapshot rows của audit_financial_inputs.py
analysis = analyze_company(facts, symbol="FPT", period="2026-Q2")
# compare_peers cần list analyses cùng kỳ, nguồn/basis đã kiểm tra.
```

Import `src.financial...` khi chạy trong thư mục backend cũng được; không tự đăng ký router/API hay sửa Chat đang được người khác phát triển. Hợp đồng chi tiết ở `CONTRACT.md`.

## Chạy báo cáo

Từ gốc repo, dùng snapshot chỉ đọc đã có:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -B backend/scripts/report_financial_health.py --snapshot outputs/sprint5/financial-health-20261112/observations.json --output outputs/sprint5/financial-health-20261112/report-q2 --period 2026-Q2
```

Bỏ `--period` để dùng kỳ gần nhất của từng mã; lúc đó TCBQ3 chưa có các peerQ3 trong snapshot và không được mượnQ2 để xếp hạng. `report.json` giữ evidence observation/payload/hash/locator, `report.md` trình bày tóm tắt và nguyên nhân thiếu. Lệnh report không kết nối DB/provider, không sửa input.

## Chỉ tiêu

- TECH: tăng doanh thu/lợi nhuận/CFO cùng kỳ; biên lợi nhuận; nợ/tài sản; ROE/ROA đã rõ định nghĩa.
- BANK: tăng thu nhập hoạt động/lợi nhuận; ROE/ROA/NIM; grossNPL/grossloans%; CIR. Không dùng CFO/leverage phi tài chính để chấm ngân hàng.
- Peer: median của ít nhất3mã ngoài target, cùng ngành/kỳ thực/scope/basis/định nghĩa tỷ số; ghi danh sách dùng/loại. Chênh lệch là điểm phần trăm; đòn bẩy/NPL/CIR thấp hơn có chiều thuận, không phải mọi số cao đều tốt.

`complete` chỉ khi phần áp dụng có đủ điều kiện; `provisional` khi đã có số tính được nhưng nguồn/độ phủ chưa đủ; `insufficient_data` khi chưa có số so sánh an toàn. Nguồn PENDING không tự thành APPROVED.

## Dữ liệu hiện tại

Snapshot thật có1752fact chọn lọc/10mã, nhưng chưa đủ metadata xác minh đơn vị/kỳ/hợp nhất/restatement để phát kết luận mạnh/yếu. Report đang thể hiện thiếu trung thực; đây không phải số0 hoặc doanh nghiệp không tăng trưởng. Xem `DATA-READINESS.md` để biết dữ liệu thực và ví dụ FPT đổi hợp nhất2026.

Không sửa unit/scope gốc để làm cho chỉ số tính được. Bước dữ liệu tiếp là đối soát các fact với đúng BCTC/cột so sánh đã điều chỉnh, thêm metadata có bằng chứng vào đầu vào đã review; không ghi đè lịch sử hoặc đoán thông tin từ độ lớn con số.
