# S5-WBS03.2 — Soạn cụm từ mẫu và bộ câu kiểm thử riêng

Phụ trách: Hồ Phạm Đăng Nhân. Ngày soạn: 10/11/2026. Giờ dự kiến WBS: 4 giờ;
không phải giờ công thực tế đã ghi nhận.

**Trạng thái: đã soạn và kiểm tra cấu trúc; chờ nhóm xác nhận nhãn và review nội dung.**
Được soạn theo bảng nhãn `s5-intent-labels-v1-draft2`, đáp ứng phần chuẩn bị dữ liệu
của 03.2. Chưa vector hóa, chưa đo chất lượng phân loại, chưa tích hợp WebChat.

## File dùng chung

- [library.jsonl](intent-dataset-v1/library.jsonl): 90 câu mẫu, chỉ file này được đưa vào thư viện embedding ở 03.3 sau khi chốt nhãn.
- [test.jsonl](intent-dataset-v1/test.jsonl): 56 câu test và nhãn kỳ vọng; không đưa vào thư viện embedding hay dùng để chỉnh câu mẫu theo kết quả từng câu.
- [manifest.json](intent-dataset-v1/manifest.json): version, checksum dữ liệu và bảng nhãn, trạng thái duyệt, chính sách tách bộ và bảy cặp đối chiếu.
- [Bảng nhãn 03.1](S5-WBS03.1-intent-labels.md): quy tắc giải thích nhãn.
- [Trình kiểm tra dữ liệu](../../backend/scripts/validate_s5_intent_dataset.py): chạy offline bằng Python chuẩn, không gọi dịch vụ ngoài.

JSONL có một đối tượng JSON trên mỗi dòng. Bảng bên dưới được xuất từ hai file này
để review dễ hơn. Khi sửa câu/nhãn, cập nhật JSONL, checksum manifest và bảng review
cùng nhau; không coi bản trình bày này là thư viện thứ hai.
Các file JSON/JSONL có checksum dùng UTF-8 và xuống dòng LF, được cố định bằng
`.gitattributes` để clone trên Windows không làm thay đổi checksum chỉ vì CRLF.

## Số lượng và cách dùng

| Nhãn | Câu mẫu | Test nhãn rõ | Test nhãn rõ nhưng thiếu scope |
|---|---:|---:|---:|
| NUMERIC | 12 | 6 | 1 |
| REPORT_CONTENT | 12 | 6 | 0 |
| NEWS | 12 | 7 | 1 |
| PERSON_ROLE | 12 | 7 | 1 |
| ENTITY_RELATION | 12 | 6 | 0 |
| TREND | 12 | 6 | 0 |
| MIXED | 18 | 6 | 0 |

Ngoài ra có 9 câu test không gán nhãn nghiệp vụ: 3 NEEDS_CONTEXT, 3 OUTSIDE_TAXONOMY,
3 UNRESOLVED. Tổng test = 44 câu rõ + 3 câu rõ nhãn thiếu scope + 9 câu chưa gán nhãn = 56.
Không dùng chín câu null để tính accuracy bảy lớp; báo cáo riêng giới hạn/khả năng
tách khỏi nhãn nghiệp vụ khi task 04.2 triển khai quyết định hỏi lại/fallback.

Thư viện có 30 câu gốc (bốn nhóm mỗi nhãn cơ sở, sáu nhóm MIXED), mỗi nhóm gồm
một bản có dấu, một bản không dấu và một cách viết tắt: 90 dòng không có nghĩa
là 90 ý định/câu gốc độc lập.
Viết tắt mơ hồ được giải nghĩa trong câu; viết tắt chưa rõ để ở test giới hạn.

Bộ test được viết riêng, không sinh từ câu mẫu bằng cách đổi tên công ty/kỳ hoặc
bỏ dấu. Biến thể cùng gốc có chung family_id và giữ cùng split. Kiểm tra tự động
chặn trùng sau bỏ dấu/dấu câu giữa hai bộ, trùng family giữa hai bộ, và việc dùng
lại nguyên văn ví dụ định nghĩa 03.1 làm test. Kiểm tra này không chứng minh mọi
paraphrase ngữ nghĩa đã độc lập; cần người review trước khi chốt bộ.

Cả hai bộ do cùng người/AI hỗ trợ soạn từ quy tắc nhãn. Đây là test tách file để
đánh giá sau, chưa phải đánh giá mù hoặc bộ do reviewer độc lập giữ kín. Không sửa
thư viện sau khi xem lỗi test rồi tiếp tục báo điểm trên cùng bộ như kết quả độc lập;
nếu cần chỉnh, ghi version và bổ sung một bộ chưa dùng cho lượt đánh giá sau.

Công ty niêm yết được dùng làm ví dụ; người/công ty giả định và tình huống tài liệu,
chức vụ, sở hữu không khẳng định tồn tại thật. Task này gán ý định câu hỏi, không
tạo đáp án tài chính hay xác nhận dữ kiện thực tế.

## Trường dữ liệu

Mỗi câu có id, text, intent_label, source_types, operation, component_intents,
annotation_status, scope_status, annotation_note, split, label_schema_version,
family_id và linguistic_form. operation là mô tả thao tác, không phải enum runtime.
source_types chỉ theo nguồn được yêu cầu hoặc loại nội dung rõ trong câu; không
chép nguồn mặc định của router. Dấu, nguồn, nhiều công ty/kỳ/chỉ tiêu không tự tạo MIXED.

Mọi câu MIXED có ít nhất hai nhãn thành phần cơ sở khác nhau. Câu không phải MIXED
để component_intents=[]. Ví dụ “ai giữ chức” với “xin bài tin bổ nhiệm” được kiểm
thử riêng; việc cần graph hay vector chưa phải đáp án của bộ dữ liệu này.

## Các cặp dễ nhầm trong test

| Cặp | ID | Ranh giới |
|---|---|---|
| C01 | S5-T-002, S5-T-014 | Giá trị cổ tức trong bài tin / tóm tắt chính bài tin |
| C02 | S5-T-013, S5-T-019 | Tìm bài tin miễn nhiệm / hỏi ngày hiệu lực miễn nhiệm |
| C03 | S5-T-012, S5-T-015 | Trích văn bản BCTN / trích văn bản bài tin |
| C04 | S5-T-020, S5-T-025 | Chức vụ của người / sở hữu cổ phần của người |
| C05 | S5-T-003, S5-T-034 | Giá trị và chênh lệch ROE / nhận định xu hướng ROE trên cùng giai đoạn |
| C06 | S5-T-024, S5-T-038 | Chức vụ kèm bằng chứng cùng fact / chức vụ và mục chính sách độc lập trong báo cáo |
| C07 | S5-T-055, S5-T-056 | Cùng bổ nhiệm TGĐ DGC tháng 09/2025: hỏi người nhận chức / xin bài tin |

## Cách kiểm tra lại

Chạy ở thư mục gốc FinMind:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/validate_s5_intent_dataset.py
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_s5_intent_dataset.py -q -p no:cacheprovider
```

Lượt kiểm tra đã đạt: đủ nhãn và ba hình thức ở mỗi nhãn trong cả hai bộ; trường,
trạng thái, nhãn MIXED, checksum, family và trùng sau chuẩn hóa đều hợp lệ.
14 test bảo vệ trình kiểm tra và định dạng file đã qua. Đây là kiểm tra dữ liệu, không phải 14 ca
chứng minh classifier phân loại đúng. 24 ca test router tồn tại trước task này
chưa được sửa; bộ mới không thay runtime nên không chạy lại toàn bộ ứng dụng.

## Điều kiện chuyển bước

Nhân đã chuẩn bị đủ file mẫu/test và kết quả kiểm tra để leader review 03.2.
Nhóm xác nhận nhãn 03.1 và nội dung mẫu/test, rồi đóng version dataset; nếu bảng
nhãn thay đổi phải rà các câu chịu ảnh hưởng và cập nhật pin/checksum tương ứng.
Sau đó mới làm 03.3: tạo vector từ library.jsonl, lưu model/revision và version
thư viện. 04.1 dùng cùng model để đối chiếu câu hỏi với thư viện và trả nhóm/điểm;
việc quyết định route/ngưỡng/hỏi lại nằm ở task sau.

## Kết quả tự review nội dung

Revision hiện tại: s5-intent-dataset-v1-draft3. Đã đọc lại toàn bộ câu và lý do gán
nhãn trước khi gửi review, chưa chạy classifier hoặc xem điểm để chỉnh dữ liệu.

- Bổ sung hai nhóm MIXED còn thiếu trong thư viện: PERSON_ROLE + REPORT_CONTENT
  và NUMERIC + NEWS. Mỗi nhóm có ba hình thức; bộ mẫu tăng từ 84 lên 90 câu.
- Làm rõ C05: lấy ROE và tính chênh lệch khác đánh giá xu hướng ROE, cùng công ty/kỳ.
- C06: xin bằng chứng cho cùng fact chức vụ vẫn PERSON_ROLE; hỏi chức vụ và đọc
  thêm một mục chính sách độc lập là MIXED. Không đổi nhãn chỉ vì yêu cầu trích dẫn.
- Sau phản hồi Hưng: 56 câu test; kiểm tra câu trùng chuẩn hóa/family, thành phần MIXED và checksum đạt.
- Đây là bộ khởi đầu nhỏ do cùng tác giả soạn, chưa phải kết quả nghiệm thu mô hình.
  Leader cần xem lại nhãn kỳ vọng và độ tự nhiên của câu viết tắt; nhóm chưa xác nhận nhãn.

Kết luận nội bộ: đủ để gửi review nội dung 03.2, chưa đóng phiên bản để nghiệm thu
chất lượng phân loại hoặc đưa vào WebChat. Bốn giờ là ước lượng backlog, không phải
số giờ thực tế hoặc bằng chứng thay cho kết quả bàn giao.

## Xử lý nhận xét của Hưng

Đã đối chiếu phản hồi được Nhân chuyển lại với dữ liệu trong repository; không
khẳng định đã kiểm tra một bản sprint5.zip khác. Tiếp thu cả ba góp ý, không có
điểm cần phản bác. Việc không trùng sau chuẩn hóa không chứng minh độc lập ngữ
nghĩa: bản draft2 vẫn có các test quá gần khung mẫu dù kiểm tra cấu trúc đạt.

| Góp ý | Thay đổi ở draft3 |
|---|---|
| T041/L090 và T038/L085 gần cùng khung | Viết lại cả T037–T042, giữ nhãn thành phần. T038 hỏi chức danh người đã nêu và một mục chính sách độc lập; T041 tóm tắt tin mở chi nhánh rồi lập bảng EPS nhiều kỳ. Các câu còn lại chuyển sang đối chiếu nguồn hoặc xác minh quan hệ/đối tượng đã biết thay cho chỉ tìm tập công ty rồi đọc số. |
| Cần cặp cùng sự kiện bổ nhiệm | Thêm C07 với T055/T056: cùng bổ nhiệm TGĐ DGC tháng 09/2025, phân biệt hỏi người nhận chức và tìm bài tin. Giữ C02 miễn nhiệm để không mất ca cũ. |
| Viết tắt/câu sở hữu thiếu tự nhiên | L084 viết đầy đủ “niêm yết”; T042 bỏ cụm dồn NY/XH và đổi tình huống; T025 dùng “nắm bao nhiêu phần trăm cổ phần SSI”. |

Không thay bảng nhãn 03.1, không đổi nhãn để chạy theo router, không xem điểm mô
hình trước khi sửa. Lưu revision và lý do sửa trong manifest; giữ trạng thái chờ
nhóm xác nhận. Các pattern ý định đương nhiên vẫn có thể giống nhau giữa hai bộ;
không tuyên bố đã loại bỏ mọi paraphrase gần nghĩa chỉ nhờ đổi tình huống.

## Toàn bộ câu mẫu để review

ACCENTED = có dấu; UNACCENTED = không dấu; ABBREVIATED = có viết tắt.

### NUMERIC — Số liệu

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-001 | Lợi nhuận trước thuế của BID năm 2024 đạt bao nhiêu? | ACCENTED | — |
| S5-L-002 | Loi nhuan truoc thue cua BID nam 2024 dat bao nhieu? | UNACCENTED | — |
| S5-L-003 | LNTT BID năm 2024 là bn? | ABBREVIATED | — |
| S5-L-004 | Theo BCTN MBB năm 2023, tỷ lệ nợ trên vốn chủ sở hữu là bao nhiêu? | ACCENTED | — |
| S5-L-005 | Theo BCTN MBB nam 2023, ty le no tren von chu so huu la bao nhieu? | UNACCENTED | — |
| S5-L-006 | Đọc tỷ lệ nợ/VCSH MBB 2023 từ BCTN giúp tôi. | ABBREVIATED | — |
| S5-L-007 | Giá đóng cửa CTG ngày 02/11/2026 và 03/11/2026 chênh nhau bao nhiêu? | ACCENTED | — |
| S5-L-008 | Gia dong cua CTG ngay 02/11/2026 va 03/11/2026 chenh nhau bao nhieu? | UNACCENTED | — |
| S5-L-009 | Chênh lệch giá ĐC CTG 02/11/2026 so với 03/11/2026 là bn? | ABBREVIATED | — |
| S5-L-010 | So sánh tổng tài sản trên BCTC hợp nhất năm 2024 của VCB và TCB bằng số chênh lệch. | ACCENTED | — |
| S5-L-011 | So sanh tong tai san tren BCTC hop nhat nam 2024 cua VCB va TCB bang so chenh lech. | UNACCENTED | — |
| S5-L-012 | Tổng TS VCB với TCB chênh bn theo BCTC HN 2024? | ABBREVIATED | — |

### REPORT_CONTENT — Nội dung BCTC/BCTN

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-013 | Tóm tắt mục quản trị rủi ro trong BCTN BID năm 2024. | ACCENTED | — |
| S5-L-014 | Tom tat muc quan tri rui ro trong BCTN BID nam 2024. | UNACCENTED | — |
| S5-L-015 | Tóm tắt QTRR trong BCTN BID 2024. | ABBREVIATED | — |
| S5-L-016 | Giải thích chính sách ghi nhận doanh thu trong thuyết minh BCTC CMG năm 2023. | ACCENTED | — |
| S5-L-017 | Giai thich chinh sach ghi nhan doanh thu trong thuyet minh BCTC CMG nam 2023. | UNACCENTED | — |
| S5-L-018 | Chính sách ghi nhận DT ở thuyết minh BCTC CMG 2023 nói gì? | ABBREVIATED | — |
| S5-L-019 | Tìm báo cáo thường niên của ELC năm 2024 để tôi đọc. | ACCENTED | — |
| S5-L-020 | Tim bao cao thuong nien cua ELC nam 2024 de toi doc. | UNACCENTED | — |
| S5-L-021 | Cho xin BCTN ELC 2024. | ABBREVIATED | — |
| S5-L-022 | Trích nguyên văn mục tiểu sử ông Minh trong BCTN ITD năm 2023 đã chỉ định. | ACCENTED | — |
| S5-L-023 | Trich nguyen van muc tieu su ong Minh trong BCTN ITD nam 2023 da chi dinh. | UNACCENTED | — |
| S5-L-024 | Chép nguyên văn tiểu sử ông Minh ở BCTN ITD 2023. | ABBREVIATED | — |

### NEWS — Tin tức

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-025 | Tìm các bài tin về việc bổ nhiệm Tổng giám đốc TCB trong tháng 10/2026. | ACCENTED | — |
| S5-L-026 | Tim cac bai tin ve viec bo nhiem Tong giam doc TCB trong thang 10/2026. | UNACCENTED | — |
| S5-L-027 | Tìm tin bổ nhiệm TGĐ TCB tháng 10/2026. | ABBREVIATED | — |
| S5-L-028 | Tóm tắt nội dung bài tin về chia cổ tức MBB công bố ngày 01/11/2026. | ACCENTED | — |
| S5-L-029 | Tom tat noi dung bai tin ve chia co tuc MBB cong bo ngay 01/11/2026. | UNACCENTED | — |
| S5-L-030 | Tóm tắt tin chia CT MBB đăng 01/11/2026; CT ở đây là cổ tức. | ABBREVIATED | — |
| S5-L-031 | Điểm các tin thị trường chứng khoán Việt Nam ngày 05/11/2026. | ACCENTED | — |
| S5-L-032 | Diem cac tin thi truong chung khoan Viet Nam ngay 05/11/2026. | UNACCENTED | — |
| S5-L-033 | Điểm tin TTCK VN ngày 05/11/2026. | ABBREVIATED | — |
| S5-L-034 | Chép nguyên văn đoạn thông báo hợp tác trong bài tin BID đăng ngày 28/10/2026. | ACCENTED | — |
| S5-L-035 | Chep nguyen van doan thong bao hop tac trong bai tin BID dang ngay 28/10/2026. | UNACCENTED | — |
| S5-L-036 | Trích NV đoạn hợp tác ở tin BID 28/10/2026; NV = nguyên văn. | ABBREVIATED | — |

### PERSON_ROLE — Chức vụ

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-037 | Theo BCTN TCB năm 2024, ai giữ chức Tổng giám đốc tại thời điểm cuối năm? | ACCENTED | — |
| S5-L-038 | Theo BCTN TCB nam 2024, ai giu chuc Tong giam doc tai thoi diem cuoi nam? | UNACCENTED | — |
| S5-L-039 | Ai là TGĐ TCB cuối năm 2024 theo BCTN? | ABBREVIATED | — |
| S5-L-040 | Ông Nam được BID bổ nhiệm làm Giám đốc tài chính vào ngày nào trong năm 2024? | ACCENTED | — |
| S5-L-041 | Ong Nam duoc BID bo nhiem lam Giam doc tai chinh vao ngay nao trong nam 2024? | UNACCENTED | — |
| S5-L-042 | Ông Nam được bổ nhiệm GĐTC BID ngày nào năm 2024? | ABBREVIATED | — |
| S5-L-043 | Trong BCTN CMG năm 2023, bà Lan được ghi nhận giữ chức vụ nào? | ACCENTED | — |
| S5-L-044 | Trong BCTN CMG nam 2023, ba Lan duoc ghi nhan giu chuc vu nao? | UNACCENTED | — |
| S5-L-045 | Bà Lan giữ CV nào tại CMG theo BCTN 2023? CV nghĩa là chức vụ. | ABBREVIATED | — |
| S5-L-046 | Nhiệm kỳ Chủ tịch Hội đồng quản trị CTG được ghi nhận trong giai đoạn 2020–2024 bắt đầu và kết thúc khi nào? | ACCENTED | — |
| S5-L-047 | Nhiem ky Chu tich Hoi dong quan tri CTG duoc ghi nhan trong giai doan 2020–2024 bat dau va ket thuc khi nao? | UNACCENTED | — |
| S5-L-048 | Nhiệm kỳ CT HĐQT CTG giai đoạn 2020–2024 từ ngày nào tới ngày nào? | ABBREVIATED | — |

### ENTITY_RELATION — Quan hệ

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-049 | Liệt kê các công ty con trực tiếp của MBB tại ngày 31/12/2024. | ACCENTED | — |
| S5-L-050 | Liet ke cac cong ty con truc tiep cua MBB tai ngay 31/12/2024. | UNACCENTED | — |
| S5-L-051 | DS cty con trực tiếp MBB tại 31/12/2024 gồm những bên nào? | ABBREVIATED | — |
| S5-L-052 | Theo BCTN 2024 của TCB, TCB sở hữu bao nhiêu phần trăm vốn công ty An Phú? | ACCENTED | — |
| S5-L-053 | Theo BCTN 2024 cua TCB, TCB so huu bao nhieu phan tram von cong ty An Phu? | UNACCENTED | — |
| S5-L-054 | TCB nắm bn % vốn cty An Phú theo BCTN 2024? | ABBREVIATED | — |
| S5-L-055 | Doanh nghiệp nào là công ty mẹ của công ty Sao Bắc tại ngày 30/06/2024? | ACCENTED | — |
| S5-L-056 | Doanh nghiep nao la cong ty me cua cong ty Sao Bac tai ngay 30/06/2024? | UNACCENTED | — |
| S5-L-057 | Cty mẹ của Sao Bắc tại 30/06/2024 là DN nào? | ABBREVIATED | — |
| S5-L-058 | Những doanh nghiệp nào tham gia sự kiện ký kết hợp tác với BID ngày 15/10/2026? | ACCENTED | — |
| S5-L-059 | Nhung doanh nghiep nao tham gia su kien ky ket hop tac voi BID ngay 15/10/2026? | UNACCENTED | — |
| S5-L-060 | DN nào tham gia sự kiện ký kết HT với BID ngày 15/10/2026? | ABBREVIATED | — |

### TREND — Xu hướng

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-061 | Nhận định xu hướng giá VCB trong các phiên từ 01/10 đến 30/10/2026 dựa trên chuỗi giá. | ACCENTED | — |
| S5-L-062 | Nhan dinh xu huong gia VCB trong cac phien tu 01/10 den 30/10/2026 dua tren chuoi gia. | UNACCENTED | — |
| S5-L-063 | Nhận định XH giá VCB 01–30/10/2026 từ chuỗi giá. | ABBREVIATED | — |
| S5-L-064 | Đánh giá chiều hướng lợi nhuận sau thuế MBB qua các năm 2022, 2023 và 2024 dựa trên BCTC. | ACCENTED | — |
| S5-L-065 | Danh gia chieu huong loi nhuan sau thue MBB qua cac nam 2022, 2023 va 2024 dua tren BCTC. | UNACCENTED | — |
| S5-L-066 | LNST MBB 2022–2024 theo BCTC đang theo XH nào? | ABBREVIATED | — |
| S5-L-067 | Dựa trên giá và biên lợi nhuận của CMG trong năm 2024, nhận định các tín hiệu xu hướng có đồng thuận không. | ACCENTED | — |
| S5-L-068 | Dua tren gia va bien loi nhuan cua CMG trong nam 2024, nhan dinh cac tin hieu xu huong co dong thuan khong. | UNACCENTED | — |
| S5-L-069 | Giá và biên LN CMG năm 2024 cho tín hiệu XH đồng thuận hay trái chiều? | ABBREVIATED | — |
| S5-L-070 | Theo BCTC BID giai đoạn 2021–2024, tăng trưởng doanh thu có ổn định qua thời gian không? | ACCENTED | — |
| S5-L-071 | Theo BCTC BID giai doan 2021–2024, tang truong doanh thu co on dinh qua thoi gian khong? | UNACCENTED | — |
| S5-L-072 | XH tăng trưởng DT BID 2021–2024 theo BCTC có ổn định không? | ABBREVIATED | — |

### MIXED — Kết hợp

| ID | Câu | Hình thức | Thành phần MIXED |
|---|---|---|---|
| S5-L-073 | Xác định công ty liên kết của VCB cuối năm 2024 rồi đọc tổng tài sản 2024 của từng công ty theo BCTC. | ACCENTED | ENTITY_RELATION, NUMERIC |
| S5-L-074 | Xac dinh cong ty lien ket cua VCB cuoi nam 2024 roi doc tong tai san 2024 cua tung cong ty theo BCTC. | UNACCENTED | ENTITY_RELATION, NUMERIC |
| S5-L-075 | Tìm cty LK VCB cuối 2024 rồi đọc tổng TS 2024 từng cty từ BCTC. | ABBREVIATED | ENTITY_RELATION, NUMERIC |
| S5-L-076 | Cho biết ai giữ chức Tổng giám đốc MBB tại 31/12/2024 và liệt kê các bài tin bổ nhiệm vị trí đó trong năm 2024. | ACCENTED | PERSON_ROLE, NEWS |
| S5-L-077 | Cho biet ai giu chuc Tong giam doc MBB tai 31/12/2024 va liet ke cac bai tin bo nhiem vi tri do trong nam 2024. | UNACCENTED | PERSON_ROLE, NEWS |
| S5-L-078 | Ai là TGĐ MBB tại 31/12/2024 và có những tin bổ nhiệm TGĐ nào năm 2024? | ABBREVIATED | PERSON_ROLE, NEWS |
| S5-L-079 | Tóm tắt kế hoạch trong BCTN CTG 2024 và tóm tắt các bài tin về CTG trong tháng 01/2025. | ACCENTED | REPORT_CONTENT, NEWS |
| S5-L-080 | Tom tat ke hoach trong BCTN CTG 2024 va tom tat cac bai tin ve CTG trong thang 01/2025. | UNACCENTED | REPORT_CONTENT, NEWS |
| S5-L-081 | Tóm tắt KH ở BCTN CTG 2024 và tin CTG tháng 01/2025. | ABBREVIATED | REPORT_CONTENT, NEWS |
| S5-L-082 | Tìm các đối tác niêm yết của ELC tại cuối năm 2024 rồi đánh giá xu hướng giá từng doanh nghiệp trong năm đó. | ACCENTED | ENTITY_RELATION, TREND |
| S5-L-083 | Tim cac doi tac niem yet cua ELC tai cuoi nam 2024 roi danh gia xu huong gia tung doanh nghiep trong nam do. | UNACCENTED | ENTITY_RELATION, TREND |
| S5-L-084 | Tìm đối tác niêm yết của ELC cuối 2024 rồi nhận định XH giá từng doanh nghiệp năm 2024. | ABBREVIATED | ENTITY_RELATION, TREND |
| S5-L-085 | Xác định ai được BID bổ nhiệm làm trưởng ban kiểm soát năm 2024 rồi đọc tiểu sử người đó trong BCTN 2024. | ACCENTED | PERSON_ROLE, REPORT_CONTENT |
| S5-L-086 | Xac dinh ai duoc BID bo nhiem lam truong ban kiem soat nam 2024 roi doc tieu su nguoi do trong BCTN 2024. | UNACCENTED | PERSON_ROLE, REPORT_CONTENT |
| S5-L-087 | Tìm người được bổ nhiệm TBKS BID năm 2024 rồi đọc tiểu sử ở BCTN 2024; TBKS = trưởng ban kiểm soát. | ABBREVIATED | PERSON_ROLE, REPORT_CONTENT |
| S5-L-088 | Cho biết lợi nhuận sau thuế CTG năm 2024 và liệt kê bài tin CTG trong tháng 03/2025. | ACCENTED | NUMERIC, NEWS |
| S5-L-089 | Cho biet loi nhuan sau thue CTG nam 2024 va liet ke bai tin CTG trong thang 03/2025. | UNACCENTED | NUMERIC, NEWS |
| S5-L-090 | LNST CTG 2024 là bn và có các tin CTG nào tháng 03/2025? | ABBREVIATED | NUMERIC, NEWS |

## Toàn bộ câu test để review

| ID | Câu | Nhãn kỳ vọng | Thành phần / Lý do phân biệt |
|---|---|---|---|
| S5-T-001 | Trong BCTC riêng của công ty mẹ HPG năm 2023, số dư tiền cuối năm là bao nhiêu? | NUMERIC | Phạm vi công ty mẹ không phải khám phá quan hệ. |
| S5-T-002 | Bài tin KBC ngày 12/08/2025 nêu mức cổ tức tiền mặt bao nhiêu đồng một cổ phiếu? | NUMERIC | Chỉ lấy giá trị từ bài tin, không tóm tắt tin. |
| S5-T-003 | Cho biet ROE cua ACB tung nam 2020–2023 va chenh lech giua nam dau voi nam cuoi la bao nhieu diem phan tram? | NUMERIC | Xin các giá trị và phép trừ hai đầu kỳ, không đánh giá diễn biến. |
| S5-T-004 | Theo BCTC 2023, doanh thu va gia von cua PNJ lan luot la bao nhieu? | NUMERIC | Hai chỉ tiêu cùng một mục tiêu đọc số. |
| S5-T-005 | Giá ĐC SSI ngày 15/09/2025 là bn đồng/cp? | NUMERIC | Giá trị giá tại ngày cụ thể. |
| S5-T-006 | Cho biết EPS và BVPS VNM năm 2023 bằng số. | NUMERIC | Hỏi giá trị chỉ tiêu có viết tắt, không hỏi định nghĩa. |
| S5-T-007 | Đọc và tóm lược phần cam kết phát triển bền vững trong BCTN HPG 2023. | REPORT_CONTENT | Mục tiêu là nội dung định tính của báo cáo. |
| S5-T-008 | Trích nguyên văn đoạn mô tả giao dịch với bên liên quan trong thuyết minh BCTC ACB 2022 đã nêu. | REPORT_CONTENT | Trích đoạn đã định danh, không khám phá tập quan hệ. |
| S5-T-009 | Toi can tai lieu BCTN PNJ nam 2022, hay tim giup. | REPORT_CONTENT | Yêu cầu tìm chính tài liệu. |
| S5-T-010 | Thuyet minh BCTC VNM 2023 mo ta phuong phap khau hao tai san nhu the nao? | REPORT_CONTENT | Đọc phương pháp kế toán, không lấy giá trị tài sản. |
| S5-T-011 | Rút gọn mục đào tạo NLĐ trong BCTN REE 2023; NLĐ là người lao động. | REPORT_CONTENT | Tóm lược mục báo cáo có viết tắt rõ nghĩa. |
| S5-T-012 | Chép nguyên văn dòng ghi CV bà Hoa tại SSI trong BCTN 2022; CV = chức vụ. | REPORT_CONTENT | Chép dòng có sẵn thay vì suy danh tính/chức vụ. |
| S5-T-013 | Có những bài báo nào về quyết định miễn nhiệm Giám đốc tài chính HPG trong tháng 08/2025? | NEWS | Xin tập bài báo nhân sự, không hỏi ngày miễn nhiệm. |
| S5-T-014 | Bài tin KBC ngày 12/08/2025 trình bày việc trả cổ tức tiền mặt như thế nào? Hãy tóm lược bài. | NEWS | Xin nội dung bài tin, khác giá trị cổ tức. |
| S5-T-015 | Chep dung doan gioi thieu ba Hoa trong bai tin SSI dang ngay 03/09/2025. | NEWS | Nguồn bài tin, không phải REPORT_CONTENT. |
| S5-T-016 | Tong hop tin kinh te vi mo tai Viet Nam trong ngay 18/09/2025. | NEWS | Tin thị trường rộng không cần công ty. |
| S5-T-017 | Tìm các tin PNJ đổi CT HĐQT trong Q3/2025. | NEWS | CT HĐQT là chủ đề tin, không tự chuyển PERSON_ROLE. |
| S5-T-018 | Tóm tắt bài tin ACB công bố KQKD Q2/2025, không cần bảng số. | NEWS | KQKD trong bài tin là đối tượng tóm tắt. |
| S5-T-019 | Ngày có hiệu lực quyết định miễn nhiệm Giám đốc tài chính HPG trong tháng 08/2025 là ngày nào? | PERSON_ROLE | Thời điểm chức vụ không phải NUMERIC hoặc xin bài tin. |
| S5-T-020 | Theo bài tin SSI ngày 03/09/2025, bà Hoa được bổ nhiệm giữ chức gì? | PERSON_ROLE | Nguồn là tin nhưng mục tiêu là fact chức vụ. |
| S5-T-021 | BCTN REE 2022 ghi nhan ai phu trach vi tri ke toan truong tai cuoi nam? | PERSON_ROLE | Tìm người ở vai trò lịch sử theo báo cáo. |
| S5-T-022 | Ong Binh dam nhan vai tro nao tai VNM trong nam 2023? | PERSON_ROLE | Người đã biết, hỏi chức vụ tại doanh nghiệp. |
| S5-T-023 | Ai đảm nhiệm PTGĐ PNJ tại 30/06/2023? PTGĐ là phó tổng giám đốc. | PERSON_ROLE | Viết tắt được giải nghĩa rõ. |
| S5-T-024 | Theo BCTN REE 2022, ai được bổ nhiệm làm KTT? Trích câu làm bằng chứng cho câu trả lời; KTT = kế toán trưởng. | PERSON_ROLE | Chỉ xác định chức vụ; trích bằng chứng cho cùng fact không tạo ý định thứ hai. Khác T-038 đọc thêm tiểu sử. |
| S5-T-025 | Cuối năm 2023, bà Hoa nắm bao nhiêu phần trăm cổ phần SSI? | ENTITY_RELATION | Người là chủ sở hữu, không phải hỏi chức vụ. |
| S5-T-026 | Cuối năm 2022, VNM có bao nhiêu doanh nghiệp liên kết trực tiếp? | ENTITY_RELATION | Đếm quan hệ, không phải số liệu tài chính. |
| S5-T-027 | Theo BCTN REE 2023, REE va cong ty Song Xanh co quan he hop tac khong? | ENTITY_RELATION | Xác minh cạnh hợp tác dù nguồn là báo cáo. |
| S5-T-028 | Su kien mo nha may cua HPG ngay 12/05/2025 co nhung doanh nghiep nao tham gia? | ENTITY_RELATION | Hỏi tập thực thể tham gia, không tóm tắt sự kiện. |
| S5-T-029 | DN nào kiểm soát cty Bình Minh tại 31/12/2023? | ENTITY_RELATION | Xác định quan hệ kiểm soát. |
| S5-T-030 | PNJ góp bn % vốn vào cty Hoa Mai cuối 2022? | ENTITY_RELATION | Tỷ lệ góp vốn gắn cạnh sở hữu. |
| S5-T-031 | Dựa trên chuỗi giá SSI từ tháng 01 đến tháng 06/2025, nhận định đà phục hồi có bền qua các tháng không. | TREND | Đánh giá diễn biến nhiều kỳ thay vì lấy một giá. |
| S5-T-032 | Qua BCTC VNM 2020–2023, biên lợi nhuận đang thu hẹp hay mở rộng và vì sao? | TREND | Nhận định xu hướng tài chính có bằng chứng. |
| S5-T-033 | Nhan dinh chieu huong gia va dong tien kinh doanh cua REE qua 2021–2023, hai tin hieu co trai chieu khong? | TREND | Hai tín hiệu cùng phục vụ một nhận định xu hướng. |
| S5-T-034 | Danh gia chieu huong ROE cua ACB qua cac nam 2020–2023: dang cai thien hay suy yeu? | TREND | Cùng chỉ tiêu, công ty và giai đoạn với T-003 nhưng yêu cầu nhận định xu hướng. |
| S5-T-035 | XH thanh khoản giao dịch ACB trong Q1/2025 đang cải thiện hay suy yếu? | TREND | Thanh khoản giao dịch theo chuỗi thuộc diễn biến thị trường. |
| S5-T-036 | LNST PNJ qua 2020–2023 tăng tốc hay chậm lại? Giải thích XH đó. | TREND | Tăng tốc/chậm lại là đánh giá diễn biến. |
| S5-T-037 | Đối chiếu phần quản trị rủi ro trong BCTN VNM 2023 với bài tin VNM ngày 15/02/2024: hai tài liệu nêu những điểm giống và khác nào? | MIXED | REPORT_CONTENT + NEWS. Phải đọc nội dung cả báo cáo lẫn bài tin để đối chiếu; không chỉ tóm tắt hai nguồn tuần tự. |
| S5-T-038 | BCTN REE 2022 ghi bà Mai đảm nhiệm chức danh nào? Báo cáo mô tả chính sách kiểm soát nội bộ ra sao? | MIXED | PERSON_ROLE + REPORT_CONTENT. Một fact chức vụ và một mục chính sách độc lập, không còn khung tìm người bổ nhiệm rồi đọc tiểu sử. Khác T-024 chỉ xin bằng chứng cho cùng fact. |
| S5-T-039 | Can xac nhan HPG kiem soat cong ty Binh Minh tai 31/12/2023 hay khong; dong thoi cho biet von chu so huu tren BCTC rieng HPG nam 2023. | MIXED | ENTITY_RELATION + NUMERIC. Xác minh quan hệ có hai đầu mút đã nêu, kèm chỉ tiêu của HPG; không khám phá công ty rồi lấy số từng công ty. |
| S5-T-040 | Bai tin SSI ngay 10/08/2023 mo ta quyet dinh thay doi nhan su ra sao? Trong nam 2023 ong Binh giu chuc vu nao tai SSI? | MIXED | NEWS + PERSON_ROLE. Đọc một bài tin xác định và trả fact chức vụ của người đã biết, khác khung hỏi người đương nhiệm rồi liệt kê tin. |
| S5-T-041 | Tóm tắt tin ACB mở chi nhánh ngày 20/02/2025; kèm bảng EPS của ACB cho 2022–2023 theo BCTC. | MIXED | NEWS + NUMERIC. Tin về mở chi nhánh và bảng EPS nhiều kỳ là hai sản phẩm độc lập, khác khung LNST rồi xin danh sách tin. |
| S5-T-042 | Cty Hoa Mai có phải đơn vị do PNJ kiểm soát cuối 2023 không, và XH giá PNJ trong Q1/2024 ra sao? | MIXED | ENTITY_RELATION + TREND. Xác minh một cạnh cụ thể kèm xu hướng giá PNJ; không tìm tập công ty con rồi nhận định từng công ty. Dùng cty/XH thay cho dồn NY/XH. |
| S5-T-043 | Còn bên ấy thì sao nhỉ? | null (NEEDS_CONTEXT) | Không có phiên trước để xác định mục tiêu hay đối tượng. Scope: NEEDS_CONTEXT. |
| S5-T-044 | con nguoi do? | null (NEEDS_CONTEXT) | Đại từ không kèm ngữ cảnh đã xác minh. Scope: NEEDS_CONTEXT. |
| S5-T-045 | Cho xem DS đó tiếp. | null (NEEDS_CONTEXT) | DS nghĩa là danh sách; chưa xác định danh sách nào. Scope: NEEDS_CONTEXT. |
| S5-T-046 | DCA hoạt động theo nguyên tắc nào? | null (OUTSIDE_TAXONOMY) | Khái niệm đầu tư được giữ ngoài bảy nhãn bản đầu. Scope: NOT_APPLICABLE. |
| S5-T-047 | FPT kinh doanh linh vuc nao? | null (OUTSIDE_TAXONOMY) | Hồ sơ doanh nghiệp không chỉ rõ nội dung báo cáo. Scope: NOT_APPLICABLE. |
| S5-T-048 | Tóm tắt cuộc trò chuyện của chúng ta. | null (OUTSIDE_TAXONOMY) | Lệnh hội thoại không phải ý định truy xuất bảy nhóm. Scope: NOT_APPLICABLE. |
| S5-T-049 | Việc thay lãnh đạo sẽ ảnh hưởng doanh nghiệp ra sao? | null (UNRESOLVED) | Chưa rõ tác động giá/tài chính hay nội dung khác. Scope: PARTIAL. |
| S5-T-050 | Trich nguyen van muc nghe nghiep trong tai lieu toi dang noi toi. | null (UNRESOLVED) | Không có tài liệu/ngữ cảnh xác định báo cáo hay bài tin. Scope: PARTIAL. |
| S5-T-051 | CT có thay đổi không? | null (UNRESOLVED) | CT có thể là chủ tịch, cổ tức hoặc nghĩa khác. Scope: NEEDS_CONTEXT. |
| S5-T-052 | Tổng nợ phải trả cuối năm 2023 là bao nhiêu? | NUMERIC | Ý định rõ nhưng thiếu doanh nghiệp. Scope: PARTIAL. |
| S5-T-053 | Tim bai tin mien nhiem trong thang 06/2025. | NEWS | Xin bài tin rõ nhưng thiếu đối tượng nhân sự/doanh nghiệp. Scope: PARTIAL. |
| S5-T-054 | Ai là KTT tại 31/12/2023? KTT = kế toán trưởng. | PERSON_ROLE | Ý định chức vụ rõ nhưng thiếu đơn vị. Scope: PARTIAL. |
| S5-T-055 | Ai được bổ nhiệm làm TGĐ DGC trong tháng 09/2025? | PERSON_ROLE | Hỏi người nhận chức trong sự kiện bổ nhiệm, không yêu cầu bài tin. Cùng vai trò, doanh nghiệp và tháng với T-056. |
| S5-T-056 | Tìm bài tin về việc bổ nhiệm TGĐ DGC trong tháng 09/2025. | NEWS | Xin bài tin về cùng sự kiện của T-055, không chỉ xác định người được bổ nhiệm. |
