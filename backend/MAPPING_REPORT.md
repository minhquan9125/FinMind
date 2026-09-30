  # BÁO CÁO ÁNH XẠ CHỈ TIÊU TÀI CHÍNH (FINANCIAL MAPPING REPORT)
  **Dự án:** FinMind - Nền tảng Phân tích Dữ liệu Tài chính Việt Nam  
**Mã cổ phiếu chuẩn hóa:** `BID` (Ngân hàng TMCP Đầu tư và Phát triển Việt Nam)  
**Tài liệu đối soát chính:** 
  - `docs/BID_BCTC_6T2026_soatxet.pdf` (BCTC Hợp nhất Giữa niên độ soát xét 6 tháng 2026)
  - `docs/BID_BCTC_Q2_2026.pdf` (BCTC Hợp nhất Giữa niên độ Quý II/2026)
- `data/normalized/BID.json` (Dữ liệu crawl chuẩn hóa kỳ 2026-Q2)

## TÌNH TRẠNG CHUẨN HÓA HIỆN TẠI (2026-09-29)

### Đã hoàn thành

- Đã có hai profile mapping theo ngành cho 10 mã: BANK (`BID`, `CTG`, `MBB`, `TCB`, `VCB`) và TECH (`FPT`, `CMG`, `ELC`, `ICT`, `ITD`). TECH chỉ dùng mapping được khai báo trong profile TECH; key lạ không tự rơi về mapping BANK.
- Đã chuẩn hóa các dòng BCTC cốt lõi của Bảng cân đối kế toán, Kết quả hoạt động kinh doanh, Lưu chuyển tiền tệ và các tỷ số đang có trong API. Tên tiếng Việt được đưa vào nội dung RAG; số tiền được đổi sang triệu VND khi dựng nội dung, còn giá trị JSON/API được giữ nguyên. EPS giữ đơn vị VND/cổ phiếu.
- Đã đối chiếu các dòng cốt lõi BANK với BCTC BID và các dòng cốt lõi TECH với BCTC hợp nhất FPT 6T/2026. Phần KQKD/LCTT của FPT được so bằng tổng Q1 + Q2 với số lũy kế 6 tháng trên PDF; Bảng cân đối được so theo số dư cuối kỳ.
- Đã rà key số có giá trị khác 0 trong kỳ mới nhất có trong mỗi JSON chuẩn hóa. Sau khi đối chiếu bổ sung BCTC MBB, BID và CTG 6T/2026, tổng hợp theo ngành và báo cáo là 332/355 key-section đang hoạt động có mapping tường minh; còn 23 key-section chưa xác định được nghĩa. Trong BANK còn 6 key hoạt động chưa chuẩn hóa ngữ nghĩa; TECH còn 17 và được để ngoài cổng nạp dữ liệu trước mắt theo phạm vi hiện tại. Đây là key-section phân biệt theo profile ngành, không phải số trường trong toàn bộ schema API hay độ phủ mọi kỳ lịch sử.

| Ngành | Báo cáo | Có mapping / key hoạt động | Chưa map |
|---|---|---:|---:|
| BANK | Bảng cân đối | 78 / 79 | 1 |
| BANK | Kết quả kinh doanh | 25 / 25 | 0 |
| BANK | Lưu chuyển tiền tệ | 37 / 42 | 5 |
| BANK | Tỷ số | 33 / 33 | 0 |
| TECH | Bảng cân đối | 75 / 88 | 13 |
| TECH | Kết quả kinh doanh | 23 / 24 | 1 |
| TECH | Lưu chuyển tiền tệ | 32 / 35 | 3 |
| TECH | Tỷ số | 29 / 29 | 0 |

### Còn phải xử lý

Các key dưới đây có giá trị khác 0 trong ít nhất một mã thuộc kỳ mẫu mới nhất, nhưng chưa gán mã ngữ nghĩa. Chúng được giữ ở dạng key gốc viết hoa để không làm mất dữ liệu hoặc đoán sai. Danh sách ghi mã có key; mã không ghi nghĩa là không thấy key đó trong kỳ mẫu.

| Ngành / báo cáo | Key chưa map và mã có key |
|---|---|
| BANK / Bảng cân đối | `bsb157` (cả 5 mã BANK; cùng giá trị với `bsb126`, giữ gốc để tránh ghi trùng). |
| BANK / Lưu chuyển tiền tệ | `cfa23` (MBB, TCB); `cfa24` (MBB); `cfa32` (TCB); `cfb64`, `cfb221` (cả 5 mã BANK). |
| TECH / Bảng cân đối | `bsa161` (ELC); `bsa164` (CMG); `bsa175`, `bsa177`, `bsa188`, `bsa79` (cả 5 mã TECH); `bsa40`, `bsa41`, `bsa42` (ELC, ICT); `bsa6`, `bsa7` (ELC); `bsa83` (CMG, ELC, ITD); `bsb108` (CMG, ELC, FPT, ITD). |
| TECH / Kết quả kinh doanh | `isa102` (CMG, FPT). |
| TECH / Lưu chuyển tiền tệ | `cfa104`, `cfa16` (ITD); `cfa27` (ELC, FPT). |

### Vướng mắc và giới hạn kết luận

- Key của Vietcap như `bsa...`, `bsb...`, `cfa...`, `cfb...` là mã nhà cung cấp, không tự mang nghĩa. PDF CafeF hiện có phần lớn là ảnh quét; báo cáo trích xuất hiện ghi nhận 10.355 trang cần OCR. Vì vậy chưa thể gán tên đáng tin cậy hàng loạt chỉ từ text extraction hiện có.
- Đối chiếu Bảng cân đối/KQKD: dòng BANK bổ sung khớp PDF MBB 6T/2026 (trang 3-5 cho Bảng cân đối; trang 6 cho KQKD) và BID 6T/2026 (trang PDF 8-10, trang in 4-6). `isb38` khớp “Tổng thu nhập hoạt động” của MBB ở cả số quý II và lũy kế 6 tháng. `bsb126` = `bsb158 + bsb131` và `bsb132` = `bsb179 + bsb185 + bsb186` ở cả 5 ngân hàng; các tổng này được đặt tên là tổng/subtotal, không nhầm thành một dòng gốc in riêng trên PDF. `bsb157` trùng `bsb126` ở cả 5 mã nên giữ gốc.
- Đối chiếu LCTT: tại MBB, các key vừa thêm có số Q1+Q2 khớp từng dòng BCTC hợp nhất 6T/2026 (PDF trang 7-8); ví dụ `cfb49` = tăng/giảm tiền gửi và cho vay TCTD khác (-2.742.775 triệu đồng), `cfb52` = tăng/giảm cho vay khách hàng và mua nợ (-143.317.496 triệu đồng), `cfb75` = lãi đã thu (60.253.967 triệu đồng), `cfb81` = chi nhân viên/quản lý/công vụ (-11.656.408 triệu đồng). Tại BID, `cfb51` khớp dòng công cụ phái sinh/tài sản tài chính khác (-755.982 triệu đồng) và `cfb67` khớp tiền chi thanh lý/nhượng bán TSCĐ (-962 triệu đồng) trên PDF trang 12-13 (trang in 8-9). Tại CTG, `cfa37` khớp điều chỉnh ảnh hưởng thay đổi tỷ giá đến tiền và tương đương tiền (-23.535 triệu đồng; PDF trang 10, trang in 7). `cfa23` và `cfa24` chỉ khớp tổng một dòng đầu tư trên PDF MBB nên chưa thể xác định riêng từng key; `cfb221` trùng giá trị `cfb79` ở cả 5 ngân hàng trong Q1+Q2/2026 nên chưa map để tránh ghi trùng. `cfb64` khớp `cfa18 - cfb65` ở cả 5 ngân hàng nhưng không có nhãn dòng riêng trên PDF, nên giữ chưa map. `cfa32` của TCB chưa map vì tổng Q1+Q2 không khớp dòng cổ tức trả trên PDF TCB.
- Cần đối chiếu từng key chưa map với trang BCTC cùng mã, cùng kỳ, cùng phạm vi hợp nhất/riêng. Nếu dòng chỉ nằm trong thuyết minh hoặc không xuất hiện trong PDF tham chiếu thì cần nhãn từ metadata/từ điển Vietcap; chưa có nhãn thì tiếp tục giữ key gốc.
- Không gộp các key chỉ vì trùng giá trị ở một công ty/kỳ. Ví dụ `bsa188` bằng `bsa163` tại FPT Q2 nhưng khác ở CMG. `cfa27` đã được xác nhận là tiền thu từ phát hành cổ phiếu trong profile BANK; key `cfa27` của TECH vẫn chưa xác minh và không kế thừa mapping BANK. `bsb108` chỉ được xác nhận là chứng khoán HTM trong mapping BANK, chưa có bằng chứng áp dụng cùng nghĩa cho TECH.
- Chưa rà đủ mọi kỳ lịch sử và mọi key null/0 của API. Chưa tuyên bố toàn bộ taxonomy API đã chuẩn hóa. BCTN và News ngoài phạm vi trạng thái BCTC này.

### Kết luận gate BCTC

Mapping BANK đủ để chạy thử nạp dữ liệu: 173/179 key-section có mapping ngữ nghĩa. Sáu key còn lại vẫn được giữ dưới key nguồn để không mất dữ liệu: `bsb157` và `cfb221` trùng key đã ánh xạ; `cfb64` là subtotal không có nhãn riêng trên PDF; `cfa23`/`cfa24` chỉ đối chiếu được với một dòng đầu tư gộp; `cfa32` của TCB chưa khớp PDF. Dry-run loader đã chạy thành công trên 5 JSON BANK: 834 financial reports và 155.554 observations dự kiến (42 kỳ/mã); không kết nối hoặc ghi database. TECH chưa thuộc đợt nạp này; 17 key TECH chưa xác minh sẽ xử lý sau.

  ---

  ## 0. KẾT QUẢ CHUẨN HÓA BCTC CHO 10 MÃ (BANK + TECH)

  Phần ban đầu của báo cáo dưới đây mô tả profile **BANK**, đã đối soát BID. Đã bổ sung profile **TECH** và áp dụng lựa chọn mapping theo `industry` trên payload chuẩn hóa. Phạm vi lần này chỉ là BCTC qua API Vietcap; PDF CafeF là tài liệu đối chiếu, không phải đầu vào OCR hay nguồn dữ liệu chính.

  ### Bằng chứng đối chiếu TECH

  - PDF tham chiếu: `data/references/cafef/pdfs/FPT/FPT_financial_2026_Q2_6a8946580763ddca1c4addbb_B_o_c_o_t_i_ch_nh_h_p_nh_t_qu_2_n_m_2026_so_t_x_t.pdf`, BCTC hợp nhất giữa niên độ 6 tháng 2026 soát xét của FPT.
  - Bảng cân đối: đối chiếu số dư tại 30/06/2026 với các trang in 4–7. Báo cáo KQKD và LCTT đối chiếu tại các trang in 8–10.
  - Với KQKD/LCTT, PDF trình bày số lũy kế 6 tháng trong khi API trả số riêng từng quý. Cộng Q1 + Q2 của API cho các dòng đã rà khớp số 6 tháng trên PDF. Không cộng số dư Bảng cân đối.
  - Đã đối chiếu các dòng chính của Bảng cân đối, KQKD và LCTT; chưa gán nghĩa cho các key Vietcap chưa đủ căn cứ.

  ### Mapping TECH đã xác nhận

  | Báo cáo | Key API | Mã chuẩn |
  |---|---|---|
  | Cân đối | `bsa1`–`bsa21` (các key có trong feed) | `CURRENT_ASSETS`, `CASH_AND_CASH_EQUIVALENTS`, `CASH`, `CASH_EQUIVALENTS`, `SHORT_TERM_FINANCIAL_INVESTMENTS_NET`, các khoản phải thu, tồn kho, thuế và tài sản ngắn hạn tương ứng |
  | Cân đối | `bsa23`, `bsa24`, `bsa27`–`bsa38`, `bsa43`, `bsa45`–`bsa52` | tài sản dài hạn, phải thu dài hạn, TSCĐ/khấu hao, đầu tư dài hạn, lợi thế thương mại và tài sản dài hạn khác |
  | Cân đối | `bsa53`–`bsa96` (các key có trong feed), `bsa108`, `bsa163`, `bsa165`, `bsa167`, `bsa178`, `bss136` | tổng tài sản/nợ/VCSH, nợ ngắn hạn và dài hạn, vốn, lợi nhuận giữ lại kỳ hiện tại, doanh thu chưa thực hiện, xây dựng dở dang và cổ tức phải trả |
  | KQKD | `isa1`–`isa14`, `isa18`, `isa23`, `isa24` | doanh thu, giảm trừ, giá vốn, lợi nhuận gộp/hoạt động/lợi nhuận khác, thuế hoãn lại và EPS |
  | LCTT | `cfa1`–`cfa7`, `cfa10`–`cfa15`, `cfa17`, `cfa21`–`cfa24`, `cfa29`–`cfa32`, `cfa37` | điều chỉnh HĐKD, thay đổi vốn lưu động, thuế/lãi đã trả, các luồng đầu tư/tài chính và ảnh hưởng tỷ giá |

  Các key dùng chung như `bsa53`, `isa16`–`isa24`, `cfa9`, `cfa18`–`cfa20`, `cfa25`–`cfa26`, `cfa34`–`cfa36`, `cfa38` được khai báo rõ trong từng profile. Key TECH không khai báo sẽ không rơi ngược vào nhãn BANK. Bản đồ đầy đủ, chính xác từng key → mã nằm trong `backend/src/financial/mapping.py`.

  `cfa27`, `bsa188` và `bsb108` chưa được đưa vào mapping vì chưa xác minh được nghĩa theo profile TECH. `bsa188` có giá trị bằng `bsa163` ở FPT nhưng khác ở CMG, nên không thể gộp dựa trên một mã. `bsb108` có số dư khác 0 ở nhiều mã TECH nhưng chỉ được xác minh là chứng khoán HTM trong profile BANK; TECH không được tự kế thừa nhãn đó. Các key chưa ánh xạ giữ nguyên dạng uppercase. JSON raw và normalized vẫn giữ key Vietcap gốc để truy nguyên.

  Theo quy ước T120–T121 của tài liệu thuật ngữ, `isa23` và `isa24` là EPS tính theo VND/cổ phiếu, không phải số tiền triệu VND. Nội dung RAG đã được sửa để giữ nguyên đơn vị trên mỗi cổ phiếu và hiển thị nhãn tiếng Việt theo glossary cạnh mã chuẩn. API Vietcap không cung cấp trường xác định BCTC hợp nhất hay riêng; do đó không thể khẳng định phạm vi này chỉ từ JSON API. Khi đối chiếu, phải dùng tài liệu cùng phạm vi (PDF FPT ở trên là hợp nhất); không trộn báo cáo riêng với hợp nhất.

  ### Áp dụng theo ngành và độ phủ dữ liệu

  `get_code(field, section, industry)` dùng profile riêng theo ngành. Với TECH, chỉ các key được khai báo tường minh mới được chuẩn hóa; key còn lại không rơi ngược về mapping BANK mà được giữ uppercase. Nhãn tiếng Việt chuẩn trong `METRIC_LABELS_VI` lấy từ glossary để nội dung RAG chứa cả mã metric lẫn tên dễ đọc. Cả `json_to_text`/`financial_json_to_pages` và `load_to_supabase.py` đều truyền `industry`, nên mã chuẩn được dùng nhất quán khi tạo nội dung RAG, khai báo metrics và ghi observations. Nội dung RAG đổi số tiền sang triệu VND nhưng giữ nguyên VND/cổ phiếu cho EPS; giá trị gốc trong JSON và Supabase không bị đổi đơn vị.

  Đã rà metadata của 10 JSON normalized: `BID`, `CTG`, `MBB`, `TCB`, `VCB` là BANK; `FPT`, `CMG`, `ELC`, `ICT`, `ITD` là TECH. Độ phủ được hiểu là số **key số có mapping** trên tổng key số của một kỳ API mẫu; các key chi tiết chưa xác minh vẫn giữ nguyên, không xem là lỗi chuẩn hóa. Mapping BANK trong phần dưới là báo cáo BID hiện hữu, profile TECH là phần bổ sung theo PDF FPT. Vì API không gửi phạm vi hợp nhất/riêng và mapper chưa gắn nhãn nguồn cho từng key còn dư, đây là mapping đã xác nhận cho các dòng cốt lõi, chưa phải từ điển đầy đủ cho mọi trường API.

  ---

  ## 1. TỔNG QUAN VÀ MỤC TIÊU CHẤT LƯỢNG (MỨC A)

  * **Tiêu chuẩn Mức A:** Tập trung ánh xạ **100% các chỉ tiêu tài chính cốt lõi** trên 4 báo cáo chính:
    1. Bảng Cân đối kế toán (Balance Sheet)
    2. Báo cáo Kết quả hoạt động kinh doanh (Income Statement)
    3. Báo cáo Lưu chuyển tiền tệ (Cash Flow Statement)
    4. Bộ Chỉ số tài chính (Financial Ratios)
  * Các chỉ tiêu chi tiết chuyên sâu trong thuyết minh hoặc các mã phụ không có trên mặt báo cáo chính được **giữ nguyên mã gốc viết hoa** (ví dụ `isa45 -> ISA45`, `bsa178 -> BSA178`) để đảm bảo không bịa thông tin và tránh xung đột khóa.
  * **Độ chính xác:** Đạt **100%** đối với toàn bộ các mã đã ánh xạ (sai số số liệu $\le 0.05\%$).
  * **Ràng buộc hệ thống:** Không có 2 key nào bị map về cùng 1 mã; tất cả các mã đều có độ dài $\le 50$ ký tự (khớp định dạng cột `observations.code` trong cơ sở dữ liệu).

  ---

  ## 2. THỐNG KÊ TAXONOMY BAN ĐẦU (LƯU LẠI, KHÔNG DÙNG LÀM COVERAGE HIỆN TẠI)

  Bảng dưới đây là thống kê từ giai đoạn BID ban đầu: đếm cả key Vietcap không có giá trị hoặc không hoạt động trong kỳ. Bảng không bao gồm đầy đủ mapping profile TECH và các mapping LCTT BANK bổ sung ở phần trên. Dùng bảng tình trạng hiện tại ở đầu tài liệu để đọc coverage của 10 mã; không dùng tỷ lệ 17,7% dưới đây làm tỷ lệ chuẩn hóa hiện tại.

  | Phân hệ (Section) | Tổng số key | Đã map (HIGH) | Đã map (MEDIUM) | Giữ nguyên gốc (LOW) | Tỷ lệ ánh xạ |
  |---|:---:|:---:|:---:|:---:|:---:|
  | **Bảng Cân đối kế toán (`balance_sheet`)** | 331 | 51 | 1 | 279 | **15.7%** |
  | **Kết quả kinh doanh (`income_statement`)** | 181 | 25 | 0 | 156 | **13.8%** |
  | **Lưu chuyển tiền tệ (`cash_flow_statement`)** | 225 | 11 | 0 | 214 | **4.9%** |
  | **Chỉ số tài chính (`ratios`)** | 54 | 48 | 4 | 2 | **96.3%** |
  | **TỔNG CỘNG** | **791** | **135** | **5** | **651** | **17.7%** |

  *Ghi chú lịch sử: các con số này không chứng minh mọi dòng chính của tất cả 10 mã/ngành đã được đối chiếu; xem phần tình trạng hiện tại và danh sách key chưa map ở đầu tài liệu.*

  ---

  ## 3. DANH SÁCH ÁNH XẠ CHI TIẾT THEO TỪNG BÁO CÁO

  ### 3.1. Bảng Cân đối kế toán (`balance_sheet`)

  | Key (JSON) | Mã chuẩn hóa (Code) | Tên chỉ tiêu tiếng Việt | Giá trị verify (Triệu VND) | Tham chiếu BCTC | Độ tin cậy |
  |---|---|---|---|:---:|:---:|
  | `bsa2` | `CASH_AND_GOLD` | Tiền mặt, vàng bạc, đá quý | 12.509.838 | Trang 8, Mục I | **HIGH** |
  | `bsb97` | `DEPOSITS_AT_CENTRAL_BANK` | Tiền gửi tại Ngân hàng Nhà nước | 117.294.507 | Trang 8, Mục II | **HIGH** |
  | `bsb98` | `DEPOSITS_LOANS_OTHER_BANKS` | Tiền gửi & cho vay các TCTD khác | 458.253.061 | Trang 8, Mục III | **HIGH** |
  | `bsb258` | `DEPOSITS_AT_OTHER_BANKS` | Tiền gửi tại các TCTD khác | 445.646.196 | Trang 8, Mục III.1 | **HIGH** |
  | `bsb259` | `LOANS_TO_OTHER_BANKS` | Cho vay các TCTD khác | 12.677.150 | Trang 8, Mục III.2 | **HIGH** |
  | `bsb260` | `PROVISION_LOANS_OTHER_BANKS` | Dự phòng rủi ro tiền gửi & cho vay TCTD | (70.285) | Trang 8, Mục III.3 | **HIGH** |
  | `bsb99` | `TRADING_SECURITIES` | Chứng khoán kinh doanh thuần | 24.701.404 | Trang 8, Mục IV | **HIGH** |
  | `bsb100` | `TRADING_SECURITIES_GROSS` | Chứng khoán kinh doanh nguyên giá | 24.758.606 | Trang 8, Mục IV.1 | **HIGH** |
  | `bsb101` | `PROVISION_TRADING_SECURITIES` | Dự phòng giảm giá chứng khoán kinh doanh | (57.202) | Trang 8, Mục IV.2 | **HIGH** |
  | `bsb102` | `DERIVATIVES_ASSETS` | Công cụ phái sinh & TS tài chính khác | 755.982 | Trang 8, Mục V | **HIGH** |
  | `bsb103` | `CUSTOMER_LOANS_NET` | Cho vay khách hàng thuần | 2.467.112.319 | Trang 8, Mục VI | **HIGH** |
  | `bsb104` | `CUSTOMER_LOANS_GROSS` | Dư nợ cho vay khách hàng nguyên giá | 2.501.807.043 | Trang 8, Mục VI.1 | **HIGH** |
  | `bsb105` | `CUSTOMER_LOANS_PROVISION` | Dự phòng rủi ro cho vay khách hàng | (34.694.724) | Trang 8, Mục VI.2 | **HIGH** |
  | `bsb106` | `INVESTMENT_SECURITIES` | Chứng khoán đầu tư thuần | 274.907.315 | Trang 8, Mục VII | **HIGH** |
  | `bsb107` | `SECURITIES_AVAILABLE_FOR_SALE` | Chứng khoán đầu tư sẵn sàng để bán (AFS) | 174.011.299 | Trang 8, Mục VII.1 | **HIGH** |
  | `bsb108` | `SECURITIES_HELD_TO_MATURITY` | Chứng khoán đầu tư giữ đến ngày đáo hạn (HTM) | 100.956.425 | Trang 8, Mục VII.2 | **HIGH** |
  | `bsb109` | `PROVISION_INVESTMENT_SECURITIES` | Dự phòng giảm giá chứng khoán đầu tư | (60.409) | Trang 8, Mục VII.3 | **HIGH** |
  | `bsa43` | `LONG_TERM_INVESTMENTS` | Góp vốn, đầu tư dài hạn | 4.681.899 | Trang 8, Mục VIII | **HIGH** |
  | `bsa45` | `INVESTMENTS_IN_ASSOCIATES_JV` | Đầu tư vào công ty liên doanh, liên kết | 4.603.155 | Trang 8, VIII.1 + VIII.2 | **HIGH** |
  | `bsa276` | `JV_INVESTMENTS` | Vốn góp liên doanh | 3.423.613 | Trang 8, Mục VIII.1 | **HIGH** |
  | `bsa277` | `ASSOCIATES_INVESTMENTS` | Đầu tư vào công ty liên kết | 1.179.542 | Trang 8, Mục VIII.2 | **HIGH** |
  | `bsa46` | `OTHER_LONG_TERM_INVESTMENTS` | Góp vốn, đầu tư dài hạn khác | 182.941 | Trang 8, Mục VIII.3 | **HIGH** |
  | `bsa47` | `PROVISION_LONG_TERM_INVESTMENTS` | Dự phòng giảm giá đầu tư dài hạn | (104.197) | Trang 8, Mục VIII.4 | **HIGH** |
  | `bsa29` | `FIXED_ASSETS` | Tài sản cố định | 12.790.868 | Trang 8, Mục IX | **HIGH** |
  | `bsa30` | `TANGIBLE_FIXED_ASSETS` | Tài sản cố định hữu hình | 7.242.139 | Trang 8, Mục IX.1 | **HIGH** |
  | `bsa31` | `TANGIBLE_FA_GROSS` | Nguyên giá TSCĐ hữu hình | 17.979.666 | Trang 8, Mục IX.1.a | **HIGH** |
  | `bsa32` | `TANGIBLE_FA_DEPRECIATION` | Hao mòn TSCĐ hữu hình | (10.737.527) | Trang 8, Mục IX.1.b | **HIGH** |
  | `bsa36` | `INTANGIBLE_FIXED_ASSETS` | Tài sản cố định vô hình | 5.548.729 | Trang 8, Mục IX.2 | **HIGH** |
  | `bsa37` | `INTANGIBLE_FA_GROSS` | Nguyên giá TSCĐ vô hình | 8.824.302 | Trang 8, Mục IX.2.a | **HIGH** |
  | `bsa38` | `INTANGIBLE_FA_DEPRECIATION` | Hao mòn TSCĐ vô hình | (3.275.573) | Trang 8, Mục IX.2.b | **HIGH** |
  | `bsb110` | `OTHER_ASSETS` | Tài sản Có khác | 67.833.661 | Trang 8, Mục X | **HIGH** |
  | `bsa53` | `TOTAL_ASSETS` | TỔNG TÀI SẢN | 3.440.840.854 | Trang 8, Tổng TS | **HIGH** |
  | `bsb111` | `DUE_TO_GOVT_AND_CENTRAL_BANK` | Các khoản nợ Chính phủ và NHNN | 236.367.270 | Trang 9, Mục B.I | **HIGH** |
  | `bsb112` | `DUE_TO_AND_BORROWINGS_FROM_BANKS`| Tiền gửi và vay các TCTD khác | 372.325.267 | Trang 9, Mục B.II | **HIGH** |
  | `bsb270` | `DEPOSITS_FROM_OTHER_BANKS` | Tiền gửi của các TCTD khác | 332.257.415 | Trang 9, Mục B.II.1 | **HIGH** |
  | `bsb271` | `BORROWINGS_FROM_OTHER_BANKS` | Vay các TCTD khác | 40.067.852 | Trang 9, Mục B.II.2 | **HIGH** |
  | `bsb113` | `CUSTOMER_DEPOSITS` | Tiền gửi của khách hàng | 2.261.489.130 | Trang 9, Mục B.III | **HIGH** |
  | `bsb115` | `FUNDS_GRANTS_TRUSTS` | Vốn tài trợ, ủy thác đầu tư | 11.588.851 | Trang 9, Mục B.V | **HIGH** |
  | `bsb116` | `VALUABLE_PAPERS_ISSUED` | Phát hành giấy tờ có giá | 301.731.655 | Trang 9, Mục B.VI | **HIGH** |
  | `bsb117` | `OTHER_LIABILITIES` | Các khoản nợ khác | 58.555.395 | Trang 9, Mục B.VII | **HIGH** |
  | `bsb272` | `ACCRUED_EXPENSES_PAYABLE` | Các khoản lãi, phí phải trả | 39.647.968 | Trang 9, Mục B.VII.1 | **HIGH** |
  | `bsb274` | `OTHER_PAYABLES_AND_LIABILITIES` | Các khoản phải trả và công nợ khác | 18.841.838 | Trang 9, Mục B.VII.3 | **HIGH** |
  | `bsa54` | `TOTAL_LIABILITIES` | TỔNG NỢ PHẢI TRẢ | 3.242.057.568 | Trang 9, Tổng Nợ | **HIGH** |
  | `bsa80` | `CHARTER_CAPITAL` | Vốn điều lệ | 72.800.652 | Trang 9, Mục VIII.1.a | **HIGH** |
  | `bsa81` | `SHARE_PREMIUM` | Thặng dư vốn cổ phần | 26.309.607 | Trang 9, Mục VIII.1.b | **HIGH** |
  | `bsa82` | `OTHER_CAPITAL` | Vốn khác | 1.127.596 | Trang 9, Mục VIII.1.c | **HIGH** |
  | `bsa85` | `FX_DIFFERENCE` | Chênh lệch tỷ giá hối đoái | (455.949) | Trang 9, Mục VIII.3 | **HIGH** |
  | `bsa90` | `RETAINED_EARNINGS` | Lợi nhuận chưa phân phối | 59.497.817 | Trang 9, Mục VIII.4 | **HIGH** |
  | `bsa210` | `MINORITY_INTEREST_EQUITY` | Lợi ích của cổ đông không kiểm soát | 5.733.452 | Trang 9, Mục VIII.5 | **HIGH** |
  | `bsa78` | `OWNERS_EQUITY` | TỔNG VỐN CHỦ SỞ HỮU | 198.783.286 | Trang 9, Tổng VCSH | **HIGH** |
  | `bsa96` | `TOTAL_LIABILITIES_EQUITY` | TỔNG NỢ PHẢI TRẢ VÀ VCSH | 3.440.840.854 | Trang 9, Tổng cộng | **HIGH** |
  | `bsa178` | `BSA178` | Lợi nhuận chưa phân phối (Trùng bsa90) | 59.497.817 | Giữ nguyên gốc | **LOW** |

  ---

  ### 3.2. Báo cáo Kết quả hoạt động kinh doanh (`income_statement`)

  | Key (JSON) | Mã chuẩn hóa (Code) | Tên chỉ tiêu tiếng Việt | Giá trị Q2/2026 (Triệu VND) | Tham chiếu BCTC Q2 | Độ tin cậy |
  |---|---|---|---|:---:|:---:|
  | `isb25` | `INTEREST_INCOME` | Thu nhập lãi và các khoản tương tự | 49.659.834 | Trang 7, Chỉ tiêu 1 | **HIGH** |
  | `isb26` | `INTEREST_EXPENSE` | Chi phí lãi và các chi phí tương tự | (31.855.603) | Trang 7, Chỉ tiêu 2 | **HIGH** |
  | `isb27` | `NET_INTEREST_INCOME` | Thu nhập lãi thuần | 17.804.231 | Trang 7, Chỉ tiêu I | **HIGH** |
  | `isb28` | `FEE_COMMISSION_INCOME` | Thu nhập từ hoạt động dịch vụ | 3.614.586 | Trang 7, Chỉ tiêu 3 | **HIGH** |
  | `isb29` | `FEE_COMMISSION_EXPENSE` | Chi phí hoạt động dịch vụ | (1.654.803) | Trang 7, Chỉ tiêu 4 | **HIGH** |
  | `isb30` | `NET_FEE_COMMISSION_INCOME` | Lãi thuần từ hoạt động dịch vụ | 1.959.783 | Trang 7, Chỉ tiêu II | **HIGH** |
  | `isb31` | `NET_FX_GAIN` | Lãi thuần từ kinh doanh ngoại hối | 708.376 | Trang 7, Chỉ tiêu III | **HIGH** |
  | `isb32` | `NET_TRADING_SECURITIES_GAIN` | Lãi thuần từ mua bán chứng khoán KD | 136.120 | Trang 7, Chỉ tiêu IV | **HIGH** |
  | `isb33` | `NET_INVESTMENT_SECURITIES_GAIN`| Lãi thuần từ mua bán chứng khoán ĐT | 16.631 | Trang 7, Chỉ tiêu V | **HIGH** |
  | `isb34` | `OTHER_OPERATING_INCOME` | Thu nhập từ hoạt động khác | 3.721.513 | Trang 7, Chỉ tiêu 5 | **HIGH** |
  | `isb35` | `OTHER_OPERATING_EXPENSE` | Chi phí hoạt động khác | (869.901) | Trang 7, Chỉ tiêu 6 | **HIGH** |
  | `isb36` | `NET_OTHER_OPERATING_INCOME` | Lãi thuần từ hoạt động khác | 2.851.612 | Trang 7, Chỉ tiêu VI | **HIGH** |
  | `isb37` | `DIVIDEND_INCOME` | Thu nhập từ góp vốn, mua cổ phần | 161.165 | Trang 7, Chỉ tiêu VII | **HIGH** |
  | `isb39` | `TOTAL_OPERATING_EXPENSES` | Tổng chi phí hoạt động | (7.484.712) | Trang 7, Chỉ tiêu VIII | **HIGH** |
  | `isb40` | `OPERATING_PROFIT_BEFORE_PROVISION`| LN thuần trước chi phí dự phòng RR tín dụng | 16.153.206 | Trang 7, Chỉ tiêu IX | **HIGH** |
  | `isb41` | `CREDIT_LOSS_PROVISION` | Chi phí dự phòng rủi ro tín dụng | (5.820.288) | Trang 7, Chỉ tiêu X | **HIGH** |
  | `isa16` | `PROFIT_BEFORE_TAX` | Tổng lợi nhuận trước thuế | 10.332.973 | Trang 7, Chỉ tiêu XI | **HIGH** |
  | `isa17` | `TAX_EXPENSE_CURRENT` | Chi phí thuế TNDN hiện hành | (2.038.057) | Trang 7, Chỉ tiêu 7 | **HIGH** |
  | `isa19` | `TAX_EXPENSE_TOTAL` | Tổng chi phí thuế TNDN | (2.038.057) | Trang 7, Chỉ tiêu XII | **HIGH** |
  | `isa20` | `PROFIT_AFTER_TAX` | Lợi nhuận sau thuế | 8.294.916 | Trang 7, Chỉ tiêu XIII | **HIGH** |
  | `isa21` | `MINORITY_INTEREST` | Lợi ích của cổ đông không kiểm soát | (148.660) | Trang 7, Chỉ tiêu XIV | **HIGH** |
  | `isa22` | `PARENT_NET_PROFIT` | Lợi nhuận thuần thuộc Ngân hàng mẹ | 8.146.256 | Trang 7, Chỉ tiêu XV | **HIGH** |

  ---

  ### 3.3. Báo cáo Lưu chuyển tiền tệ (`cash_flow_statement`)

  *Kiểm chứng logic khớp phương trình kế toán: $CFA_{KD} + CFA_{ĐT} + CFA_{TC} = CFA_{Thuần}$*
  * $-24.471.221 + (-747.536) + 2.840.220 = -22.378.537$

  | Key (JSON) | Mã chuẩn hóa (Code) | Tên chỉ tiêu tiếng Việt | Giá trị Q2/2026 (Triệu VND) | Tham chiếu BCTC | Độ tin cậy |
  |---|---|---|---|:---:|:---:|
  | `cfa9` | `OPERATING_PROFIT_BEFORE_WC` | LCTT từ HĐKD trước thay đổi vốn lưu động | 17.672.138 | Trang 12, Mục I | **HIGH** |
  | `cfa18` | `CASH_FLOW_OPERATING` | Lưu chuyển tiền thuần từ HĐ kinh doanh | (24.471.221) | Trang 12, Lưu chuyển HĐKD | **HIGH** |
  | `cfa19` | `PURCHASE_FIXED_ASSETS` | Tiền chi mua sắm tài sản cố định | (914.316) | Trang 13, Mục II.1 | **HIGH** |
  | `cfa20` | `PROCEEDS_DISPOSAL_FA` | Tiền thu thanh lý, nhượng bán TSCĐ | 1.922 | Trang 13, Mục II.2 | **HIGH** |
  | `cfa25` | `DIVIDENDS_RECEIVED` | Cổ tức và lợi nhuận được chia | 165.750 | Trang 13, Mục II.4 | **HIGH** |
  | `cfa26` | `CASH_FLOW_INVESTING` | Lưu chuyển tiền thuần từ HĐ đầu tư | (747.536) | Trang 13, Lưu chuyển HĐĐT | **HIGH** |
  | `cfa34` | `CASH_FLOW_FINANCING` | Lưu chuyển tiền thuần từ HĐ tài chính | 2.840.220 | Trang 13, Lưu chuyển HĐTC | **HIGH** |
  | `cfa35` | `NET_CASH_FLOW` | Lưu chuyển tiền thuần trong kỳ | (22.378.537) | Trang 13, LCTT thuần trong kỳ | **HIGH** |
  | `cfa36` | `CASH_EQUIVALENTS_BEGIN` | Tiền và tương đương tiền đầu kỳ | 544.528.992 | Trang 13, Đầu kỳ | **HIGH** |
  | `cfa38` | `CASH_EQUIVALENTS_END` | Tiền và tương đương tiền cuối kỳ | 522.150.455 | Trang 13, Cuối kỳ | **HIGH** |
  | `cfa43` | `TAX_PAID` | Tiền thuế TNDN đã thực nộp trong kỳ | (1.702.854) | Trang 12, Thuyết minh 25 | **HIGH** |

  ---

  ### 3.4. Chỉ số tài chính (`ratios`)

  *Phủ kín 52/54 chỉ số (đạt 96.3%):*
  * **Định giá:** `pe` -> `PE`, `pb` -> `PB`, `ps` -> `PS`, `marketCap` -> `MARKET_CAP`, `numberOfSharesMktCap` -> `NUMBER_OF_SHARES_MKT_CAP`, `dividendYield` -> `DIVIDEND_YIELD`, `priceToCashFlow` -> `PRICE_TO_CASH_FLOW`, `evToEbitda` -> `EV_TO_EBITDA`.
  * **Hiệu quả:** `roe` -> `ROE`, `roa` -> `ROA`, `roic` -> `ROIC`, `grossMargin` -> `GROSS_MARGIN`, `preTaxProfitMargin` -> `PRE_TAX_MARGIN`, `afterTaxProfitMargin` -> `AFTER_TAX_MARGIN`, `ebit` -> `EBIT`, `ebitda` -> `EBITDA`.
  * **Đặc thù Ngân hàng:**
    * `netInterestMargin` -> `NIM`
    * `cir` -> `CIR`
    * `costToIncome` -> `COST_TO_INCOME` *(đã phân tách để tránh trùng lặp)*
    * `casaRatio` -> `CASA_RATIO`
    * `ldrLoanDepositRatio` -> `LDR`
    * `npl` -> `NPL_RATIO`
    * `loansLossReservesToNPLs` -> `LLR_TO_NPLS`
    * `loansLossReserveToLoans` -> `LLR_TO_LOANS`
    * `provisionToOutstandingLoans` -> `PROVISION_TO_LOANS`
    * `loansGrowth` -> `LOANS_GROWTH`
    * `depositGrowth` -> `DEPOSIT_GROWTH`
    * `car` -> `CAR`
  * **Nhóm Vietcap nội bộ (MEDIUM):** `nob66` -> `NOB66`, `nob69` -> `NOB69`, `nob70` -> `NOB70`, `bsb113` -> `BSB113`.

  ---

  ## 4. TOP 10 KEY MEDIUM / UNMAPPED CẦN REVIEW THỦ CÔNG KHI CẦN MỞ RỘNG

  Khi dự án muốn mở rộng độ phủ từ các chỉ tiêu chính sang các chỉ tiêu phụ sâu hơn trong thuyết minh, dưới đây là top 10 key có tần suất xuất hiện cao cần review:

  1. **`bsa178`** (`59.497.817 triệu`): Bằng giá trị với `bsa90` (`RETAINED_EARNINGS`), hiện đang giữ `BSA178` để tránh trùng lặp.
  2. **`bsb114`** (`0` hoặc `null`): Nằm giữa `bsb113` (Tiền gửi khách hàng) và `bsb115` (Vốn tài trợ ủy thác), thường là chỉ tiêu *Công cụ tài chính phái sinh nợ*.
  3. **`nob66`** (`455.008.933 triệu`): Một tỷ lệ tổng hợp thuộc nhóm tiền gửi/cho vay do Vietcap tự tính toán nội bộ.
  4. **`nob69`** (`5.517.595 triệu`): Chỉ số quy mô nội bộ của Vietcap.
  5. **`nob70`** (`10.371.497 triệu`): Chỉ số quy mô nội bộ của Vietcap.
  6. **`cfa1`** đến **`cfa8`**: Các dòng chi tiết cấu thành nên `cfa9` (LCTT trước thay đổi VLĐ: thu nhập lãi nhận được, chi phí lãi đã trả,...).
  7. **`cfa10`** đến **`cfa17`**: Các biến động chi tiết tài sản hoạt động (tăng giảm cho vay, tiền gửi TCTD,...).
  8. **`isb38`**: Dòng nằm trước `isb39` (Tổng chi phí HĐ), thường là chi phí quản lý công vụ phân tách.
  9. **`isa1`** đến **`isa15`**: Bảng KQKD mẫu chung cho doanh nghiệp sản xuất (Vietcap để trống trên báo cáo ngân hàng).
  10. **`bsa1`** đến **`bsa28`**: Các tài khoản tài sản ngắn hạn đặc thù của doanh nghiệp sản xuất (trên ngân hàng được thay thế bằng hệ `bsb97`-`bsb110`).

  ---

  ## 5. HƯỚNG DẪN KIỂM THỬ VÀ TÍCH HỢP

  Để chạy kiểm thử tự động toàn bộ logic mapping và kiểm tra tính toàn vẹn với `BID.json`:

  ```powershell
  cd backend
  python -m src.financial.mapping
  ```

  Kết quả xác thực thành công:
  ```text
  ======================================================================
  [TEST] RUNNING VERIFICATION FOR src/financial/mapping.py
  ======================================================================
    [OK] BALANCE_SHEET       :  52 mapped keys. Max length: 32 chars.
    [OK] INCOME_STATEMENT    :  25 mapped keys. Max length: 33 chars.
    [OK] CASH_FLOW           :  11 mapped keys. Max length: 26 chars.
    [OK] RATIOS              :  52 mapped keys. Max length: 26 chars.
    [OK] get_code() function passed all unit tests.

  [INFO] Found BID.json at: D:\finmind\data\normalized\BID.json

  [REPORT] COVERAGE & MAPPING STATS ON BID.JSON:
  Section                | Total Keys | Mapped   | Fallback | Rate    
  -----------------------------------------------------------------
  balance_sheet          | 331        | 52       | 279      |   15.7%
  income_statement       | 181        | 25       | 156      |   13.8%
  cash_flow_statement    | 225          | 11       | 214      |    4.9%
  ratios                 | 54         | 52       | 2        |   96.3%

  [SUCCESS] ALL TESTS PASSED SUCCESSFULLY!
  ```
