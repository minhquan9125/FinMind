import json
from pathlib import Path

root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
path = root / 'manual_visual_review.json'
data = json.loads(path.read_text(encoding='utf-8'))
letter_2024 = '''CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM
ELCOM TECHNOLOGY COMMUNICATIONS CORPORATION
Số: 136/CV-EL

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
THE SOCIALIST REPUBLIC OF VIETNAM
Independence - Freedom - Happiness
Hà Nội, ngày 16 tháng 04 năm 2025
Hanoi, April 16th, 2025

CÔNG BỐ THÔNG TIN ĐỊNH KỲ
PERIODIC INFORMATION DISCLOSURE

Kính gửi:
- Ủy ban Chứng khoán Nhà nước
- Sở Giao dịch Chứng khoán Việt Nam
- Sở Giao dịch Chứng khoán Tp. Hồ Chí Minh
To:
- The State Securities Commission
- Vietnam Stock Exchange
- Ho Chi Minh Stock Exchange

1. Tên tổ chức: Công ty Cổ phần Công nghệ - Viễn thông ELCOM
Name of Corporation: ELCOM Technology Communications Corporation
Mã chứng khoán: ELC / Stock code: ELC
Địa chỉ: Tòa nhà Elcom, phố Duy Tân, p. Dịch Vọng Hậu, quận Cầu Giấy, Tp. Hà Nội
Address: Elcom Building, Duy Tan Street, Dich Vong Hau Ward, Cau Giay District, Hanoi
Điện thoại liên hệ/Tel: +8424.38359359
Fax: +8424.38355884
Email: contact@elcom.com.vn
Website: https://elcom.com.vn

2. Nội dung công bố thông tin:
Báo cáo thường niên năm 2024 / Annual Report 2024

3. Thông tin này đã được công bố trên trang thông tin điện tử của Công ty vào ngày 16/04/2025 tại đường dẫn https://www.elcom.com.vn/co-dong/phieu-thong-tin/.
This information was public on the company's website on April 16th, 2025 as in the link https://www.elcom.com.vn/co-dong/phieu-thong-tin.

Chúng tôi xin cam kết các thông tin công bố trên đây là đúng sự thật và xin chịu trách nhiệm trước Pháp luật về nội dung các thông tin đã được công bố.
We hereby certify that the information provided is true and correct and we bear the full responsibility to the law.

Trân trọng! / Sincerely yours,
Tài liệu đính kèm / Attached documents:
- Báo cáo thường niên 2024 / Annual Report 2024
Đại diện tổ chức / Organization representative
Người được ủy quyền công bố thông tin / Person authorized to disclose information
NGUYỄN ĐỨC THIỆN'''
entries = [
    ('ELC/2024/ELC_2024_500811', 1, letter_2024),
    ('ELC/2024/ELC_2024_500811', 70, letter_2024),
    ('ELC/2024/ELC_2024_500811', 11, '''Báo cáo thường niên 2024 — Thông tin chung — 15–16
ĐỐI TÁC
MẢNG VIỄN THÔNG: IBM; ADVA; Cisco; Fortinet; Oracle; Ribbon; F5; NTEST; Dell; HP; Ciena; Airspan; Nokia.
MẢNG GIAO THÔNG: Kistler; Bosch; Dell; Advantech; Allied Vision; SSI; Smartmicro; Neology; NVIDIA.
MẢNG QUỐC PHÒNG: CommsAudit; CPI; Krotos; FireEye; Elbit Systems.
KHÁCH HÀNG: Bộ Quốc phòng; Bộ Công an; Bộ Giao thông Vận tải; Bộ Nội vụ; Bộ Kế hoạch và Đầu tư; Viettel; Mobifone; Vinaphone; VNPT; EVN; PetroVietnam; Viettel Cambodia; Viettel Myanmar; Viettel Peru; Viettel Mozambique; Viettel Timor Leste; Viettel Tanzania; Viettel Burundi; Golan Telecom; Vietnamobile; Tập đoàn Sơn Hải; VEC; Agribank; VPBank; InterContinental Hotels & Resorts; Hilton; Accor Hotels; Hyatt; Vietnam Airlines; Cảng vụ Hàng không; Taric; Nafoods; N.G Vietnam.'''),
    ('ELC/2024/ELC_2024_500811', 12, '''Báo cáo thường niên 2024 — Thông tin chung — 17–18
CƠ CẤU QUẢN TRỊ VÀ MÔ HÌNH QUẢN LÝ
Công ty Cổ phần Công nghệ - Viễn thông ELCOM hoạt động theo mô hình tổ chức công ty cổ phần. Mô hình quản trị này được xây dựng dựa trên mục tiêu phát triển chiến lược kinh doanh của Công ty, tuân thủ theo các quy định của Pháp luật Việt Nam và các quy định tại Điều lệ Công ty.

ĐẠI HỘI ĐỒNG CỔ ĐÔNG
BAN KIỂM SOÁT
HỘI ĐỒNG QUẢN TRỊ
BAN ĐIỀU HÀNH
CHI NHÁNH, VĂN PHÒNG ĐẠI DIỆN
KHỐI KINH DOANH
KHỐI TRIỂN KHAI
KHỐI NGHIÊN CỨU VÀ PHÁT TRIỂN
KHỐI HỖ TRỢ VẬN HÀNH'''),
    ('ELC/2025/ELC_2025_541948', 1, '''CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM
ELCOM TECHNOLOGY COMMUNICATIONS CORPORATION
Số/No.: 208/2026/CV-ELC

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
THE SOCIALIST REPUBLIC OF VIETNAM
Independence - Freedom - Happiness
Hà Nội, ngày 17 tháng 04 năm 2026
Hanoi, April 17, 2026

CÔNG BỐ THÔNG TIN ĐỊNH KỲ
PERIODIC INFORMATION DISCLOSURE

Kính gửi:
- Ủy ban Chứng khoán Nhà nước
- Sở Giao dịch Chứng khoán Việt Nam
- Sở Giao dịch Chứng khoán Tp. Hồ Chí Minh
To: The State Securities Commission / Vietnam Stock Exchange / Ho Chi Minh Stock Exchange

1. Tên tổ chức: Công ty Cổ phần Công nghệ - Viễn thông ELCOM
Name of Corporation: ELCOM Technology Communications Corporation
Mã chứng khoán: ELC / Stock code: ELC
Địa chỉ: Tòa nhà Elcom, phố Duy Tân, phường Cầu Giấy, Thành phố Hà Nội
Address: Elcom Building, Duy Tan Street, Cau Giay Ward, Hanoi
Điện thoại liên hệ/Tel: +8424.38359359
Fax: +8424.38355884
Email: contact@elcom.com.vn
Website: https://elcom.com.vn

2. Nội dung công bố thông tin / Contents of disclosure:
Báo cáo thường niên năm 2025 / 2025 Annual Report.

3. Thông tin này đã được công bố trên trang thông tin điện tử của Công ty vào ngày 17/04/2026 tại đường dẫn https://www.elcom.com.vn/co-dong/phieu-thong-tin/.
The information has been public on the company's website on April 17th, 2026, as the following link: https://www.elcom.com.vn/co-dong/phieu-thong-tin.

Chúng tôi xin cam kết các thông tin công bố trên đây là đúng sự thật và xin chịu trách nhiệm trước Pháp luật về nội dung các thông tin đã được công bố.
We hereby certify that the information provided is true and correct and we bear the full responsibility to the law.

Trân trọng! / Sincerely yours.'''),
]
existing = {(e['document'], e['page']) for e in data['entries']}
for document, page, value in entries:
    if (document, page) not in existing:
        data['entries'].append({'document': document, 'page': page, 'text': value})
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
