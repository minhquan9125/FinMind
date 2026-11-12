# Hợp đồng thử nghiệm chấm ý định — 12/11/2026

Không thay API đang chạy. Bản local chưa có source 04.2 của Huyền sử dụng bộ bảy
nhãn mới; `hybrid_router/intent_policy.py` hiện có là policy khác. Không tuyên bố
đã thêm guard hoặc sửa policy thật phía Huyền.

| Cấu hình | ranking_policy | score_type | Dùng ngưỡng cũ? |
|---|---|---|---|
| Baseline | cosine-max-per-label-v1 | COSINE_SIMILARITY_NOT_PROBABILITY | Có, chỉ mô phỏng như trước |
| Centroid | cosine-family-centroid-v1 | COSINE_SIMILARITY_NOT_PROBABILITY | Không; khác phân bố và policy |
| Linear | intent-linear-v1 | CLASSIFIER_PROBABILITY_UNCALIBRATED | Không; loại điểm mới |

Các đầu ra đều lưu groups xếp hạng, model/revision và câu hỏi gốc, runtime_enabled=false.
Lưu đủ bảy nhóm để đo top-1/3/5; payload top-3 hiện tại của Huyền không đổi.
Ví dụ mẫu cosine vẫn là bằng chứng truy ngược riêng của baseline, không phải điểm
tin cậy của nhãn classifier. Không lấy nhãn từ classifier rồi gắn score/gap cũ.

`baseline_policy` trong module thử nghiệm chỉ nhận đúng cặp baseline policy/type,
từ chối centroid/classifier trước khi áp 0,65/0,08. Guard này không được gọi từ
router thật: cần đối chiếu source 04.2 trước tích hợp, không tự đoán consumer.

Đo tuyến ở ứng viên chỉ ánh xạ argmax nhãn không có ngưỡng và phải ghi rõ như vậy.
Không báo accepted/fallback bằng cách áp ngưỡng cosine vào probability mới. Nếu
ứng viên qua điều kiện chất lượng, bước calibration cần tập riêng và hợp đồng
điểm được kiểm chứng trước khi đề nghị nối vào router.
