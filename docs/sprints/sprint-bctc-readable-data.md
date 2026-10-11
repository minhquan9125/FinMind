# Sprint: Hoàn thiện pipeline cào dữ liệu tài chính

**Phạm vi:** Chỉ `data_pipeline/financial_data` và dữ liệu do pipeline tạo trong `data/raw`, `data/normalized`.  
**Thời lượng đề xuất:** 2 tuần (10 ngày làm việc).  
**Mục tiêu:** Cào, chuẩn hóa và kiểm tra dữ liệu giá cùng BCTC cho 10 mã cổ phiếu; giữ dữ liệu nguồn để truy nguyên và tạo đầu ra nhất quán, dễ kiểm tra.

## Hiện trạng làm đầu vào

- Pipeline hiện cào 10 mã: BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB.
- Nguồn giá: ENTRADE; nguồn BCTC và tỷ số: Vietcap VCI.
- Mỗi mã có dữ liệu giá, tỷ số tài chính, Kết quả kinh doanh, Bảng cân đối kế toán và Lưu chuyển tiền tệ.
- Dữ liệu chuẩn hóa hiện có các kỳ nhìn chung từ 2018-Q1 đến 2026-Q2; một số mã hoặc nhóm dữ liệu có kỳ thiếu.
- Một số chỉ tiêu còn mang mã nguồn như `bsa54`, `bsa55`, `isa1`; pipeline cần có từ điển tên trường đã xác minh để người kiểm tra hiểu được nội dung. Key chưa rõ nghĩa phải được giữ nguyên và đánh dấu, không tự đoán.

## Backlog sprint

### 1. Chốt hợp đồng dữ liệu đầu vào/đầu ra — 2 điểm

**Việc cần làm:**

- Rà soát cấu trúc payload API của giá, tỷ số và ba báo cáo tài chính.
- Chốt các trường metadata chung: mã cổ phiếu, kỳ báo cáo, loại kỳ, nguồn, thời điểm cào.
- Chốt đầu ra raw và normalized; không làm mất field của nguồn khi chuẩn hóa.

**Tiêu chí nghiệm thu:**

- Mỗi mã có file raw và normalized tương ứng.
- JSON hợp lệ, UTF-8; `NaN`/`Infinity` được biểu diễn an toàn theo schema đã chọn.
- Kỳ quý và kỳ năm được phân biệt nhất quán.

### 2. Làm ổn định bước thu thập dữ liệu — 3 điểm

**Việc cần làm:**

- Chạy collector cho 10 mã và năm nhóm dữ liệu: giá, tỷ số, KQKD, cân đối, lưu chuyển tiền.
- Ghi nhận lỗi độc lập theo mã và nhóm dữ liệu; lỗi một nguồn không làm dừng toàn bộ lượt cào.
- Kiểm tra retry, timeout và hành vi khi API trả rỗng hoặc báo lỗi.
- Không ghi đè bản normalized tốt gần nhất nếu lần cào mới thiếu một nhóm bắt buộc.

**Tiêu chí nghiệm thu:**

- Kết quả chạy cho biết rõ từng mã/nhóm thành công, thất bại hay rỗng.
- Có thể chạy lại riêng hoặc toàn bộ theo giao diện CLI hiện có.
- Lỗi nguồn được lưu trong log/báo cáo, không bị coi nhầm là dữ liệu bằng 0.

### 3. Chuẩn hóa nhưng bảo toàn dữ liệu nguồn — 3 điểm

**Việc cần làm:**

- Chuẩn hóa key kỳ báo cáo và kiểu dữ liệu của từng nhóm.
- Giữ riêng bản raw; bản normalized chỉ đổi cấu trúc/kiểu dữ liệu đã quy định.
- Thêm từ điển tên trường tiếng Việt cho các key đã được xác minh trong phạm vi BCTC.
- Khi key chưa được xác minh, lưu nguyên key nguồn và đưa vào danh sách cần rà soát.
- Ghi rõ đơn vị: giá trị tiền, tỷ lệ và EPS không dùng chung một cách quy đổi.

**Tiêu chí nghiệm thu:**

- Có thể truy ngược mỗi giá trị normalized về key và giá trị raw tương ứng.
- Tên trường chỉ được gán khi có căn cứ từ tài liệu nguồn hoặc tài liệu thuật ngữ.
- Key lạ không bị xóa, gộp hoặc gán nghĩa từ một ngành khác.
- EPS vẫn được ghi nhận theo VND/cổ phiếu; không quy đổi thành tiền triệu.

### 4. Tăng kiểm tra chất lượng và độ phủ — 4 điểm

**Việc cần làm:**

- Kiểm tra đủ 10 mã và đủ nhóm dữ liệu sau mỗi lượt pipeline.
- Báo cáo số bản ghi và khoảng kỳ cho từng mã/nhóm.
- Kiểm tra ngày giao dịch trùng, OHLC bất hợp lệ, kỳ báo cáo trùng hoặc thiếu.
- Kiểm tra các trường tổng chính trên Bảng cân đối khi đủ dữ liệu: tổng tài sản, tổng nợ phải trả, vốn chủ sở hữu và tổng nguồn vốn.
- Tách rõ null, zero, thiếu bản ghi và key chưa có nhãn.

**Tiêu chí nghiệm thu:**

- Báo cáo audit nêu lỗi/cảnh báo theo mã, nhóm và kỳ; không chỉ báo một trạng thái chung.
- Bản ghi bị loại có lý do và khóa bản ghi để tra cứu.
- Không tự sửa số liệu BCTC để làm cho phương trình cân đối khớp.

### 5. Đối soát dữ liệu mẫu — 3 điểm

**Việc cần làm:**

- Chọn tối thiểu một mã BANK và một mã TECH để đối chiếu KQKD, cân đối và lưu chuyển tiền với dữ liệu nguồn cùng mã/kỳ/phạm vi.
- Đối chiếu số quý riêng với số quý riêng; nếu tài liệu chỉ có số lũy kế thì ghi rõ phép cộng các quý dùng để so sánh.
- Ghi lại key nguồn, nhãn đã xác minh, đơn vị và sai khác.

**Tiêu chí nghiệm thu:**

- Có báo cáo đối soát cho các mã mẫu và danh sách key đã/ chưa xác minh.
- Sai khác được báo cáo, không bị âm thầm làm tròn hoặc sửa.
- Không kết luận phạm vi hợp nhất/riêng nếu payload nguồn không cung cấp metadata đó.

## Kết quả cần bàn giao

- Collector, normalizer và auditor trong `data_pipeline/financial_data` chạy theo cùng một schema.
- Bộ dữ liệu raw/normalized cho 10 mã có báo cáo lượt chạy và thống kê độ phủ.
- Từ điển tên trường BCTC đã xác minh; danh sách key còn chưa rõ nghĩa.
- Báo cáo đối soát dữ liệu mẫu cùng các giới hạn đã biết.

## Ngoài phạm vi

- Backend, giao diện, Supabase và RAG.
- OCR/trích xuất PDF báo cáo thường niên.
- Thêm nguồn dữ liệu mới hoặc thêm mã cổ phiếu.
- Đoán nhãn cho key Vietcap chưa được xác minh.

## Definition of Done

- Pipeline xử lý đủ 10 mã và tạo raw/normalized theo schema thống nhất.
- Audit cho biết rõ độ phủ và vấn đề chất lượng từng mã/nhóm/kỳ.
- Các tên trường đã xác minh có căn cứ; key chưa rõ vẫn được bảo toàn.
- Có đối soát mẫu, ghi rõ nguồn và đơn vị.
