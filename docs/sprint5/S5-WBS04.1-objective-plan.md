# Điều kiện theo taxonomy — vòng phát triển 3, 12/11/2026

Đóng băng trước chạy vòng này. V1 support thất bại; V2 sửa T038 nhưng chỉ nhận
đúng một trong sáu ca ROLE+REPORT ở controls vì head hay nhầm chính sách rủi ro
thành TREND. 32 controls và 42 new-check nay đều đã xem, dùng development/hồi quy.
Không gọi kết quả vòng 3 trên chúng là kiểm thử mới độc lập.

Giữ nguyên classifier/vector và điểm gốc. Thêm bộ điều kiện rõ từ taxonomy:
- REPORT_CONTENT: nguồn báo cáo (BCTN/BCTC/báo cáo thường niên/tài chính/báo cáo),
  thao tác mô tả/giải thích/tóm tắt/trích/chép, chủ đề chính sách/chiến lược/kế hoạch/
  cam kết/rủi ro/tiểu sử/định hướng; không có mục tiêu bài tin/bài báo/thông báo.
- PERSON_ROLE: câu hỏi ai kèm chức danh/giữ chức/bổ nhiệm, hoặc hỏi chức danh/chức
  vụ nào, hoặc hỏi thời điểm bổ nhiệm/miễn nhiệm; không phải thao tác trích nguyên
  văn và không có mục tiêu bài tin/bài báo/thông báo.
- Nếu cùng một phần khớp cả hai loại thì coi mơ hồ, không ép về một nhãn.
- Chỉ một phần yêu cầu rõ loại: đề xuất loại đó; nhiều phần có ít nhất hai loại
  rõ khác nhau: đề xuất MIXED. Nếu không đủ điều kiện, dùng nguyên V2 consensus.

Đây là semantic guard có phạm vi hẹp, không phải model mới hoặc luật theo ticker,
tên người, năm, ID/câu đầy đủ. Không sửa gold hoặc scores. Confidence luôn null,
raw ranking giữ nguyên; không tự chọn tuyến/áp ngưỡng cũ.

Điều kiện: T038 đúng; cả 24 controls cốt lõi ROLE/REPORT/COMBINED/EVIDENCE đúng;
không làm hỏng thêm ca classifier/V2 đang đúng trên bất kỳ tập đã xem nào, gồm 42
câu new-check đã dùng; không hồi quy các ca baseline đúng trên bộ cũ. Nếu không đạt
thì báo thất bại, không điều chỉnh điều kiện hoặc xóa ca lỗi để ghi đạt.
