# Bộ quy tắc gán nhãn sự kiện News FireAnt — 10 mã FinMind

**Bản nháp để mentor duyệt · 26/10/2026 · Không phải kết quả full-load**

## 1. Phạm vi và độ phủ nguồn

10 mã chuẩn FinMind là **BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB**, theo `data_pipeline/financial_data/audit_financial_data.py` và `docs/review/source_register_Quan.md`. Bản này đọc **trực tiếp Supabase**: `corpus-v1` có 234 bài News thuộc manifest (119 CafeF, 115 FireAnt). Trong đó có **34 bài FireAnt duy nhất** gắn ít nhất một trong 10 mã. `symbols` chỉ là nhãn tìm kiếm, không chứng minh công ty là bên tham gia sự kiện. Các JSON cục bộ được dùng để đối chiếu phần bài đã lưu trong repo.

| Mã | Số bài FireAnt gắn mã | Ghi chú |
| --- | ---: | --- |
| BID | 4 | Có bài gắn mã nhưng chưa có sự kiện BID đủ bằng chứng trong mẫu. Bài cổ tức nhắc **BIC**, không phải BID. |
| CMG | 0 | Chưa có News FireAnt trong `corpus-v1`. |
| CTG | 6 | Chủ yếu tin lãi suất, dự báo, giao dịch cổ phiếu; chưa gán sự kiện doanh nghiệp. |
| ELC | 0 | Chưa có News FireAnt trong `corpus-v1`. |
| FPT | 17 | Có sự kiện phát hành cổ phiếu, công bố cơ sở và hợp tác công nghệ; phân biệt FPT với FPT Retail/FPT Shop. |
| ICT | 0 | Chưa có News FireAnt trong `corpus-v1`. |
| ITD | 0 | Chưa có News FireAnt trong `corpus-v1`. |
| MBB | 5 | Có tin giao dịch cổ phiếu đăng ký bởi người nội bộ; không gán giao dịch đó cho MB là bên bán. |
| TCB | 7 | Có tin mua lại, phát hành trái phiếu và phương án tăng vốn được chấp thuận. |
| VCB | 17 | Có tin cổ đông thông qua chủ trương; nhiều bài còn lại là bình luận/dự báo. |

**Giới hạn:** file JSON snapshot `backend/.tmp/corpus-v1.manifest.json` không có trong checkout, nhưng membership đã được kiểm tra qua `corpus_versions → corpus_documents → documents → news_articles` trong Supabase. Bản này là **bộ quy tắc và fixture mẫu**, chưa chạy extractor full-load. News được ghi là nguồn bổ sung chưa có quyết định duyệt cuối trong `docs/review/source_register_Quan.md`.

## 2. Quy tắc quyết định lấy/không lấy

1. Chỉ xét **thân bài News** có `document_id` thuộc `corpus-v1`. Bỏ tiêu đề nhận định, thẻ mã, bình luận người dùng và quảng cáo làm bằng chứng sự kiện.
2. Một ứng viên phải có **chủ thể + hành động cụ thể + đối tượng**. Lưu một `source_span` nguyên văn đủ chứng minh ba thành phần; nếu chủ thể nằm ở câu ngay trước, lưu cả hai câu hoặc đánh dấu cần kiểm tra.
3. Hành động phải thuộc taxonomy bên dưới. Một bài có thể sinh 0, 1 hoặc nhiều sự kiện. Nếu mã chỉ xuất hiện trong danh sách cổ phiếu, dự báo hoặc thông tin nền, không gán công ty làm bên tham gia.
4. **Ngày đăng**, **ngày công bố** và **ngày hành động diễn ra** là ba trường khác nhau. Không lấy ngày đăng thay cho ngày diễn ra. Giữ ngày mơ hồ ở độ hạt gốc (`2026-10`, `2028–2030`), không tự tạo ngày chính xác.
5. Trạng thái mô tả đúng **hành động được gán nhãn**. “Đã công bố kế hoạch” là sự kiện công bố đã xảy ra, còn kế hoạch thực hiện vẫn là dự kiến. Không đổi “thông qua chủ trương” thành “đã thành lập”.
6. Không suy diễn tác động tài chính, quan hệ nhân quả hoặc ngày hoàn tất từ số liệu/nhận định trong bài.
7. Khi nhiều bài nói cùng một hành động, cùng chủ thể, đối tượng và thời điểm, giữ một `event_group_id` với mọi nguồn hỗ trợ. Chi tiết mâu thuẫn được giữ thành các claim riêng, không ghi đè.
8. Nếu thiếu chủ thể, đối tượng hoặc căn cứ trạng thái, gán `REVIEW` thay vì điền theo suy đoán.

## 3. Taxonomy khởi đầu cần mentor chốt

| `event_type` | Điều kiện lấy | Không lấy khi |
| --- | --- | --- |
| `APPROVAL` | Cơ quan/cổ đông thông qua **một phương án/chủ trương cụ thể**. | Chỉ có đề xuất hoặc bài nói về lợi ích có thể có. |
| `DISCLOSURE` | Doanh nghiệp công bố một báo cáo/quyết định/thông báo xác định. | Đồng nhất hành vi công bố với việc cơ sở đã hoàn tất khi nội dung báo cáo không có. |
| `SECURITY_ISSUANCE` | Bài xác nhận phát hành/phân phối một đợt chứng khoán cụ thể. | Chỉ mới duyệt hồ sơ hoặc lên kế hoạch phát hành. |
| `SECURITY_REPURCHASE` | Bài xác nhận mua lại/tất toán lô chứng khoán cụ thể. | Chỉ nói dự định mua lại. |
| `DIVIDEND_OR_SHARE_DELIVERY` | Có hành động hoặc lịch trả cổ tức/chuyển giao cổ phiếu cụ thể. | Chỉ dự báo lợi tức hoặc tỷ suất. |
| `AGREEMENT_SIGNED` | Xác nhận ký hợp đồng/thỏa thuận với đối tượng xác định. | Chỉ tìm cơ hội hợp tác hoặc dự kiến ký. |
| `COLLABORATION` | Bài xác nhận một quan hệ hợp tác cụ thể đã bắt đầu, nhưng không nhất thiết có hợp đồng được công bố. | Chỉ mới trao đổi định hướng hoặc tìm cơ hội; khi đó có thể ghi `REVIEW`, không gán `AGREEMENT_SIGNED`. |
| `FACILITY_ESTABLISHMENT` | Thành lập/công bố thành lập cơ sở xác định. | Nói chung về xây dựng năng lực, vị thế hay chiến lược. |
| `FACILITY_EXPANSION` | Mở rộng cơ sở/hạ tầng xác định. | “Mở rộng vai trò/vị thế” là nhận định. |
| `FACILITY_COMPLETION` | Nguồn nói rõ một cơ sở xác định đã hoàn thiện hoặc đưa vào vận hành. | Chỉ có kế hoạch hoặc ngày công bố thành lập. |
| `INSIDER_TRADE_REGISTRATION` | Cá nhân nội bộ đăng ký mua/bán lượng cổ phiếu và khoảng thời gian cụ thể. | Ghi giao dịch đăng ký thành giao dịch đã khớp; gán doanh nghiệp là bên mua/bán thay cá nhân. |
| `PERSONNEL_CHANGE` | Bổ nhiệm/miễn nhiệm một người vào vị trí xác định. | Chỉ nhắc chức danh hiện tại. |
| `CANCELLATION_OR_DELAY` | Nguồn nói rõ một kế hoạch/sự kiện bị hủy hoặc hoãn. | Chỉ chưa thấy tin hoàn tất. |

`event_type` là nhãn hành động; `status` là trường riêng: `OCCURRED`, `PLANNED`, `CANCELLED`, `UNCONFIRMED`. Các mã nhãn ở đây là **đề xuất**, chưa phải enum đã được mentor duyệt. Cần chốt thêm có lấy sự kiện ở cấp cổ phiếu thị trường, công bố kết quả kinh doanh và thay đổi lãi suất hay không; bản nháp này ưu tiên **sự kiện doanh nghiệp**.

## 4. Mẫu đầu ra cho mỗi sự kiện

```json
{
  "event_group_id": "stable-key-or-null",
  "event_type": "SECURITY_ISSUANCE",
  "status": "OCCURRED",
  "subject": {"symbol": "FPT", "name": "CTCP FPT", "role": "issuer"},
  "participants": [{"name": "cổ đông FPT", "role": "recipient"}],
  "object": "đợt phân phối cổ phiếu từ nguồn vốn chủ sở hữu",
  "published_at": "2026-09-29T13:57:00+07:00",
  "announced_at": null,
  "event_time": null,
  "event_time_precision": "unknown",
  "evidence": [{"source": "fireant", "url": "https://fireant.vn/bai-viet/fpt-co-gan-182-000-co-dong-khoi-ngoai-con-nam-28-5-von/42002502", "source_span": "đã phân phối thành công hơn 171,4 triệu cổ phiếu"}],
  "review_reason": null
}
```

`event_time = null` ở ví dụ này vì bài chỉ nói “đợt phát hành vừa qua”; ngày báo cáo công bố và ngày bài đăng không phải ngày hoàn tất phân phối.

## 5. Ví dụ đã đối chiếu với bài FireAnt cục bộ

| Mã | Bài và bằng chứng ngắn trong thân bài | Nhãn, trạng thái | Ngày hành động | Vai trò và ghi chú |
| --- | --- | --- | --- | --- |
| FPT | [42002502](https://fireant.vn/bai-viet/fpt-co-gan-182-000-co-dong-khoi-ngoai-con-nam-28-5-von/42002502): “đã phân phối thành công hơn 171,4 triệu cổ phiếu” | `SECURITY_ISSUANCE`, `OCCURRED` | Không rõ ngày hoàn tất | FPT là bên phát hành/phân phối; cổ đông là bên nhận. |
| FPT | Cùng [bài 42002502](https://fireant.vn/bai-viet/fpt-co-gan-182-000-co-dong-khoi-ngoai-con-nam-28-5-von/42002502): “dự kiến được chuyển giao trong tháng 10/2026” | `DIVIDEND_OR_SHARE_DELIVERY`, `PLANNED` | `2026-10` | Cổ phiếu mới là đối tượng; không khẳng định đã chuyển giao. |
| FPT | [41982847](https://fireant.vn/bai-viet/fpt-bao-cao-ket-qua-dot-phat-hanh-co-phieu-de-tang-von-co-phan-tu-nguon-von-chu-so-huu/41982847): FPT công bố báo cáo kết quả đợt phát hành. | `DISCLOSURE`, `OCCURRED` | Ngày công bố 28/09/2026 | Bài FireAnt chỉ có một câu mở đầu, không đủ chi tiết để tự tạo **thêm** một đợt phát hành khác. Có thể hỗ trợ cùng nhóm với 42002502 sau khi đối chiếu tài liệu gốc. |
| FPT | [41982848](https://fireant.vn/bai-viet/fpt-thong-bao-thay-doi-so-luong-co-phieu-co-quyen-bieu-quyet-dang-luu-hanh/41982848): FPT thông báo thay đổi số cổ phiếu có quyền biểu quyết. | `DISCLOSURE`, `OCCURRED` | Ngày thông báo 28/09/2026 | Chưa có số mới/số cũ trong thân bài lưu; không tự suy ra lượng thay đổi. |
| FPT | [42260639](https://fireant.vn/bai-viet/fpt-va-hanh-trinh-lam-chu-cong-nghe-loi/42260639): bài nêu FPT đã hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam. | `FACILITY_COMPLETION`, `OCCURRED` | Không rõ ngày hoàn thiện | Hai cơ sở là đối tượng; không dùng ngày đăng 14/10/2026 làm ngày hoàn thiện. |
| FPT | Cùng [bài 42260639](https://fireant.vn/bai-viet/fpt-va-hanh-trinh-lam-chu-cong-nghe-loi/42260639): bài nêu hợp tác với NARMA Inc. về UAV từ tháng 8/2026. | `COLLABORATION`, `OCCURRED` | `2026-08` | FPT và NARMA là hai bên hợp tác; bài không nói rõ đã ký hợp đồng, nên không gán `AGREEMENT_SIGNED`. |
| TCB | [42051495](https://fireant.vn/bai-viet/tcb-techcombank-tat-toan-2-lo-trai-phieu-sau-1-nam-phat-hanh/42051495): bài nêu TCB mua lại toàn bộ TCB12517 và tất toán TCB12518. | `SECURITY_REPURCHASE`, `OCCURRED` | 30/09/2026 | Techcombank là bên mua lại; hai mã trái phiếu là đối tượng. Có thể lưu một nhóm giao dịch với hai đối tượng hoặc hai record liên kết. |
| TCB | Cùng [bài 42051495](https://fireant.vn/bai-viet/tcb-techcombank-tat-toan-2-lo-trai-phieu-sau-1-nam-phat-hanh/42051495): bài nêu phát hành mã TCBL12615. | `SECURITY_ISSUANCE`, `OCCURRED` | 28/09/2026 | Đây là đợt khác, không gộp với hai lô mua lại. |
| TCB | Cùng [bài 42051495](https://fireant.vn/bai-viet/tcb-techcombank-tat-toan-2-lo-trai-phieu-sau-1-nam-phat-hanh/42051495): bài nêu kế hoạch phát hành cổ phiếu trả cổ tức và ESOP. | `SECURITY_ISSUANCE`, `PLANNED` | Điều kiện/thời hạn nêu trong bài; chưa có ngày cố định | Hai phương án là hai ứng viên riêng; không ghi đã phát hành. |
| TCB | [42265600](https://fireant.vn/bai-viet/tai-chinh-doanh-nghiep-24-7-techcombank-duoc-chap-thuan-tang-von-fpt-thuc-day-hop-tac-luong-tu/42265600): bài nêu Ngân hàng Nhà nước chấp thuận phương án tăng vốn của Techcombank. | `APPROVAL`, `OCCURRED` | Không rõ ngày chấp thuận chính xác | NHNN là bên phê duyệt, TCB là bên được phê duyệt. **Đợt phát hành cổ phiếu vẫn chưa được xác nhận hoàn tất.** |
| MBB | [42119992](https://fireant.vn/bai-viet/chung-khoan-hom-nay-6-10-6-doanh-nghiep-giao-dich-co-phieu-so-luong-lon/42119992): bà Nguyễn Thị Thuỷ đăng ký bán 113.000 cổ phiếu MBB. | `INSIDER_TRADE_REGISTRATION`, `PLANNED` | Khoảng 06/10–04/11/2026 | Bà Thuỷ là bên đăng ký bán; MBB là tổ chức phát hành cổ phiếu, **không phải bên bán**. |
| MBB, VCB | [42033692](https://fireant.vn/bai-viet/ngan-hang-viet-tim-co-hoi-ket-noi-he-sinh-thai-trong-san-choi-tai-chinh-quoc-te/42033692): cổ đông đã thông qua chủ trương thành lập ngân hàng tại VIFC. | `APPROVAL`, `OCCURRED` | Mùa ĐHĐCĐ 2026; thiếu ngày cụ thể | Tạo một record cho MB và một cho Vietcombank. Cổ đông là bên thông qua; ngân hàng là bên có phương án. **Không** gán `FACILITY_ESTABLISHMENT/OCCURRED`. |
| BID | [42088805](https://fireant.vn/bai-viet/lich-chot-quyen-tra-co-tuc-trong-tuan-tu-ngay-5-10-9-10-ty-le-cao-nhat-65/42088805): lịch cổ tức nói về **BIC**. | `NO_EVENT_FOR_BID` | — | BIC không đồng nhất với BID; nhãn BID của bài không đủ để tạo sự kiện BID. |

## 6. Gợi ý kiểm thử batch

- **Dương tính:** 42002502, 42051495, 42033692, 42119992, 42260639, 42265600.
- **Âm tính:** bài chỉ dự báo lợi nhuận/giá cổ phiếu, bài nhận định “mở rộng vai trò”, bài nói về FPT Retail hoặc BIC nhưng gắn FPT/BID.
- **Bất định:** 41982847 và 41982848 do nội dung lưu quá ngắn; cần tài liệu gốc trước khi suy ra số lượng/ngày hoàn tất.
- **Không chạy full-load trong task này:** dùng bộ nhãn làm fixture mẫu, chốt taxonomy với mentor rồi bàn giao interface batch cho WBS16.

### Thuật toán triển khai gợi ý

```text
Input: danh sách article_id thuộc corpus-v1
1. Lấy bài; chia thân bài thành các câu/đoạn, giữ offset và URL.
2. Sinh ứng viên: luật động từ + tên riêng; tùy chọn mô hình AI để nhận thêm cách diễn đạt lạ.
3. Với mỗi ứng viên, chọn event_type từ enum trên và trích subject/action/object/status/time.
4. Validator bắt buộc: source_span là chuỗi con thật của thân bài; actor/object có căn cứ;
   ngày không vượt độ chính xác của nguồn; trạng thái không được mạnh hơn lời nguồn.
5. Entity resolver map tên công ty sang đúng mã; phân biệt FPT/FRT, BID/BIC,
   doanh nghiệp/người nội bộ/cơ quan phê duyệt.
6. Dedupe theo actor + event_type + object + thời gian; giữ mọi evidence và claim mâu thuẫn.
7. Record không đạt validator -> REVIEW hoặc NO_EVENT, không tự điền.
Output: 0..n sự kiện mỗi bài + lỗi/review_reason theo article_id.
```

**AI là tùy chọn**, không phải điều kiện để bắt đầu. Có thể làm bộ luật trước. Nếu dùng AI, chỉ cho AI đề xuất ứng viên theo schema cố định; validator trong code mới quyết định record có được xuất hay không.

Phụ lục bên dưới liệt kê toàn bộ **34 URL FireAnt trong `corpus-v1`** gắn ít nhất một trong 10 mã và kết quả sàng lọc sơ bộ. `REVIEW` có nghĩa cần đọc nguồn/tài liệu gốc sâu hơn, không phải đã xác nhận sự kiện.

## Phụ lục — danh sách 34 bài để kiểm tra độ phủ

| Bài FireAnt | Ngày đăng | Mã được gắn trong 10 mã | Sàng lọc | Lý do |
| --- | --- | --- | --- | --- |
| [42265600](https://fireant.vn/bai-viet/tai-chinh-doanh-nghiep-24-7-techcombank-duoc-chap-thuan-tang-von-fpt-thuc-day-hop-tac-luong-tu/42265600) | 2026-10-14 | FPT, TCB | YES/REVIEW | TCB được chấp thuận tăng vốn; FPT–Pasqal mới trao đổi định hướng, chưa có hợp đồng xác nhận. |
| [42264060](https://fireant.vn/bai-viet/fpt-co-phieu-fpt-ve-day-3-nam-ho-room-ngoai-hon-20/42264060) | 2026-10-14 | FPT | NO | Diễn biến giá cổ phiếu và room ngoại; không có hành động doanh nghiệp phù hợp taxonomy này. |
| [42260639](https://fireant.vn/bai-viet/fpt-va-hanh-trinh-lam-chu-cong-nghe-loi/42260639) | 2026-10-14 | FPT | YES | FPT hoàn thiện AI Factory, hợp tác NARMA, thành lập viện nghiên cứu; cần tách từng việc. |
| [42257818](https://fireant.vn/bai-viet/fpt-con-bi-cuc-cua-co-dong-fpt-3-tuan-khong-thay-mau-xanh-thi-gia-roi-xuong-vung-day-gan-3-nam/42257818) | 2026-10-13 | FPT | NO | Bài về giá cổ phiếu và tâm lý cổ đông. |
| [42257775](https://fireant.vn/bai-viet/fpt-co-phieu-fpt-tiep-da-lao-doc-von-hoa-boc-hoi-gan-73-000-ty-dong-ke-tu-dau-nam/42257775) | 2026-10-13 | FPT | NO | Bài về giá cổ phiếu/vốn hóa, không gán tác động cho sự kiện công ty. |
| [42119992](https://fireant.vn/bai-viet/chung-khoan-hom-nay-6-10-6-doanh-nghiep-giao-dich-co-phieu-so-luong-lon/42119992) | 2026-10-06 | MBB | YES | Người nội bộ MBB đăng ký bán cổ phiếu; chưa chứng minh đã bán. |
| [42088805](https://fireant.vn/bai-viet/lich-chot-quyen-tra-co-tuc-trong-tuan-tu-ngay-5-10-9-10-ty-le-cao-nhat-65/42088805) | 2026-10-05 | BID | NO | Bài cổ tức nhắc BIC, không phải sự kiện của BID. |
| [42051767](https://fireant.vn/bai-viet/lai-suat-vietinbank-cao-nhat-gui-300-trieu-dong-nhan-36-trieu-dong-tien-lai/42051767) | 2026-10-01 | CTG | NO | Bảng lãi suất hiện hành và phép tính tiền lãi; chưa có thay đổi lãi suất được xác nhận. |
| [42051495](https://fireant.vn/bai-viet/tcb-techcombank-tat-toan-2-lo-trai-phieu-sau-1-nam-phat-hanh/42051495) | 2026-10-01 | TCB | YES | TCB mua lại và phát hành các lô trái phiếu khác nhau; có thêm phương án cổ phiếu dự kiến. |
| [42045685](https://fireant.vn/bai-viet/doanh-nghiep-ganh-no-hang-chuc-nghin-ty-dong-dang-phai-xoay-tien-ra-sao/42045685) | 2026-10-01 | VCB | NO | Trọng tâm là nợ của doanh nghiệp khác; VCB không phải chủ thể sự kiện rõ. |
| [42034031](https://fireant.vn/bai-viet/cho-vay-du-an-bat-dong-san-ngan-hang-thiet-ke-ty-le-va-phuong-thuc-cap-von-linh-hoat/42034031) | 2026-10-01 | VCB | NO | Phân tích/đề xuất tín dụng bất động sản, không có hành động VCB cụ thể. |
| [42033824](https://fireant.vn/bai-viet/chung-khoan-1-10-vn-index-co-the-lui-ve-1-730-1-750-diem/42033824) | 2026-10-01 | VCB | NO | Dự báo và nhận định VN-Index; VCB được nhắc như nguồn phân tích. |
| [42033692](https://fireant.vn/bai-viet/ngan-hang-viet-tim-co-hoi-ket-noi-he-sinh-thai-trong-san-choi-tai-chinh-quoc-te/42033692) | 2026-10-01 | VCB | YES | Cổ đông Vietcombank đã thông qua chủ trương tại VIFC; MB cũng được nêu trong thân bài dù không có tag MBB. |
| [42029445](https://fireant.vn/bai-viet/mb-mo-rong-vai-tro-ket-noi-dong-von/42029445) | 2026-09-30 | MBB, VCB | NO | Bài tổng hợp vai trò và mục tiêu dài hạn của MB; không biến nhận định thành một sự kiện. |
| [42023216](https://fireant.vn/bai-viet/ndn-nha-da-nang-bi-phat-thue-sap-chi-hon-50-ty-dong-tra-co-tuc/42023216) | 2026-09-30 | MBB | NO | Sự kiện chính thuộc NDN, không thuộc MBB. |
| [42018894](https://fireant.vn/bai-viet/chung-khoan-thoi-lai-suat-cao-goi-ten-pvs-bsr-va-diem-sang-vcb/42018894) | 2026-09-30 | VCB | NO | Nhận định cổ phiếu và triển vọng, không có hành động VCB cụ thể. |
| [42019987](https://fireant.vn/bai-viet/nhieu-ngan-hang-duoc-du-bao-tang-lai/42019987) | 2026-09-30 | CTG, TCB, VCB | NO | Dự báo lợi nhuận ngân hàng, chưa phải kết quả công bố. |
| [42011573](https://fireant.vn/bai-viet/tang-truong-loi-nhuan-doanh-nghiep-niem-yet-quy-iii-du-bao-giam-toc/42011573) | 2026-09-30 | CTG, VCB | NO | Dự báo lợi nhuận doanh nghiệp, không xác nhận sự kiện các ngân hàng. |
| [42011455](https://fireant.vn/bai-viet/du-bao-loi-nhuan-doanh-nghiep-quy-iii-tang-truong-phuc-hoi-va-giam/42011455) | 2026-09-30 | MBB, VCB | NO | Dự báo lợi nhuận quý III, chưa phải kết quả công bố. |
| [42010979](https://fireant.vn/bai-viet/vcb-vietcombank-dong-hanh-kien-tao-nen-tang-phat-trien-ben-vung-cho-thi-truong-von/42010979) | 2026-09-29 | VCB | NO | Bài quan điểm/định hướng thị trường vốn; chưa xác định hành động đơn lẻ. |
| [42010904](https://fireant.vn/bai-viet/nhung-ngan-hang-co-the-lai-tren-10-000-ty-dong-trong-quy-iii/42010904) | 2026-09-29 | BID, CTG, MBB, TCB, VCB | NO | Ước tính lợi nhuận của SSI, không phải kết quả đã công bố. |
| [42009303](https://fireant.vn/bai-viet/khoi-ngoai-noi-dai-chuoi-ban-rong-dong-co-phieu-van-hut-tien/42009303) | 2026-09-29 | TCB, VCB | NO | Giao dịch thị trường/khối ngoại; không gán doanh nghiệp là bên mua bán. |
| [42008611](https://fireant.vn/bai-viet/mot-co-phieu-ngan-hang-duoc-mua-rong-dot-bien-400-ty-dong-trong-phien-29-9/42008611) | 2026-09-29 | CTG, FPT, VCB | NO | Tự doanh giao dịch cổ phiếu; FPT/CTG/VCB không phải chủ thể giao dịch. |
| [42007944](https://fireant.vn/bai-viet/ssi-du-bao-ket-qua-kinh-doanh-quy-3-2026-cua-42-doanh-nghiep-masan-viglacera-tang-bang-lan-sacombank-du-bao-giam-45/42007944) | 2026-09-29 | CTG, FPT, VCB | NO | Dự báo kết quả kinh doanh của SSI Research. |
| [42002502](https://fireant.vn/bai-viet/fpt-co-gan-182-000-co-dong-khoi-ngoai-con-nam-28-5-von/42002502) | 2026-09-29 | FPT | YES | FPT đã phân phối cổ phiếu; chuyển giao cổ phiếu mới còn dự kiến. |
| [41999984](https://fireant.vn/bai-viet/tin-vui-cho-fpt-shop-dien-may-xanh-the-gioi-di-dong-viettel-store/41999984) | 2026-09-29 | FPT | NO | Bảng xếp hạng nhà bán lẻ; FPT Shop/FPT Retail không tự đồng nhất với CTCP FPT. |
| [41987121](https://fireant.vn/bai-viet/quy-ngoai-ty-usd-chang-ai-ngo-hoa-phat-fpt-the-gioi-di-dong-lai-roi-xuong-muc-dinh-gia-thap-nhu-vay/41987121) | 2026-09-28 | FPT | NO | Ý kiến của quỹ về định giá cổ phiếu. |
| [41982847](https://fireant.vn/bai-viet/fpt-bao-cao-ket-qua-dot-phat-hanh-co-phieu-de-tang-von-co-phan-tu-nguon-von-chu-so-huu/41982847) | 2026-09-28 | FPT | YES/REVIEW | FPT công bố báo cáo kết quả; thân bài quá ngắn để tự suy thêm chi tiết phát hành. |
| [41982848](https://fireant.vn/bai-viet/fpt-thong-bao-thay-doi-so-luong-co-phieu-co-quyen-bieu-quyet-dang-luu-hanh/41982848) | 2026-09-28 | FPT | YES/REVIEW | FPT thông báo thay đổi số cổ phiếu có quyền biểu quyết; thiếu số liệu trong thân bài lưu. |
| [41975594](https://fireant.vn/bai-viet/viet-nam-nang-hang-thi-truong-chung-khoan-co-hoi-va-thach-thuc-nao-cho-doanh-nghiep-viet/41975594) | 2026-09-28 | BID, FPT, VCB | NO | Nâng hạng thị trường là sự kiện cấp thị trường, không phải hành động của BID/FPT/VCB. |
| [41967912](https://fireant.vn/bai-viet/mbs-du-bao-kqkd-quy-3-2026-nganh-ban-le-the-gioi-di-dong-va-fpt-retail-tiep-tuc-but-pha-hai-ten-tuoi-tang-truong-dot-bien-3-chu-so/41967912) | 2026-09-28 | FPT | NO | Dự báo FPT Retail (FRT), không phải sự kiện của CTCP FPT. |
| [41966777](https://fireant.vn/bai-viet/du-bao-ket-qua-kinh-doanh-quy-3-2026-cua-nhom-tieu-dung-ban-le/41966777) | 2026-09-27 | FPT | NO | Dự báo ngành bán lẻ và FPT Retail (FRT). |
| [41637696](https://fireant.vn/bai-viet/ctck-chi-ten-10-co-phieu-trien-vong-trong-thang-9/41637696) | 2026-08-31 | BID, FPT, TCB, VCB | NO | Danh sách khuyến nghị/triển vọng cổ phiếu. |
| [41407346](https://fireant.vn/bai-viet/ctck-diem-ten-10-co-phieu-trien-vong-tich-cuc-phu-hop-de-xuong-tien-nam-giu-trung-dai-han/41407346) | 2026-08-12 | FPT, TCB, VCB | NO | Danh sách khuyến nghị đầu tư, không phải sự kiện doanh nghiệp. |
