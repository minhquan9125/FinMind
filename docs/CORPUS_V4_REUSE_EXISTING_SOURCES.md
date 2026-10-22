# Corpus-v4: dùng lại nguồn đã có, chỉ thêm phần thiếu

Đây là phương án hiện tại, thay thế kế hoạch thêm 676 bản nguồn. Đã triển khai một metadata root trên Supabase, đọc lại đủ 7.158 chunk và đăng ký index v4 ACTIVE theo phê duyệt triển khai ngày 22/10. Receipt mới trong `outputs/corpus-v4-reuse-audit-20261022/` là trạng thái thực tế; các mục mô phỏng/chờ duyệt bên dưới ghi lại giai đoạn trước.

Hướng dẫn thành viên hiện tại: [CORPUS_V4_QUICK_START.md](CORPUS_V4_QUICK_START.md). Không cần ZIP/snapshot local. Việc đổi cấu hình mặc định chỉ thực hiện sau HTTP smoke và audit evidence Q31–Q39; xem `configuration.json` để biết đã chuyển hay chưa.

Truy vấn tài chính có công ty/kỳ rõ ràng được giới hạn bằng membership corpus và kỳ đó trước khi xếp hạng vector. Nhãn chỉ tiêu nguồn/alias được dùng để tìm các observation ID phù hợp rồi lọc chunk chứa dòng đó. Đây là truy vấn vector có điều kiện, không còn là baseline vector thuần toàn corpus; khi so benchmark phải ghi rõ phiên bản query logic. Không tự chuyển đổi hoặc chứng nhận đơn vị bằng alias.

## Đã kiểm tra trên Supabase

| Nhóm | Số tài liệu v4 | Cách đọc đúng phiên bản |
|---|---:|---|
| Báo cáo tài chính clean | 419 | Đọc đúng payload clean gốc; dùng metadata tên/chỉ tiêu/renderer và quy tắc đơn vị đã chốt |
| Tin tức | 234 | Đọc nội dung bài từ raw_payloads có sẵn; giữ tiêu đề/ngày/symbol của phiên bản khi cần |
| Lịch sử giá cổ phiếu | 6 | Đọc OHLCV từ payload lịch sử đã có; bổ sung indicators cũ vì payload gốc chỉ lưu bars |
| Chỉ số thị trường | 3 | Dùng payload bars lịch sử; bổ sung indicators còn thiếu |
| Hồ sơ doanh nghiệp | 13 | Giữ bộ trường hồ sơ nhỏ tại phiên bản v4 để tên/ngành/sàn không đổi theo bảng live |

Tổng 675 tài liệu. 662 tài liệu đầu dùng lại **43 payload gốc hiện có**. Không thêm bản sao của 72.096 giá trị tài chính, nội dung 234 bài tin hoặc OHLCV lịch sử. 13 bộ trường hồ sơ và indicators là phần lịch sử nhỏ cần bổ sung để đọc ổn định.

9 bài tin ban đầu chưa khớp không phải thiếu toàn bộ nội dung: sau khi dùng đúng tiêu đề/ngày của bản cũ, toàn bộ 234 bài dựng lại được từ raw payload có sẵn. Các payload giá cũ vẫn còn nên không phải ghi đè giá hiện tại.

## Chính xác sẽ đề xuất thêm gì?

**Một bản metadata trong raw_payloads**, 2.428.715 bytes canonical JSON (khoảng 2,43 MB trước overhead JSONB/backup). Nội dung:

- Corpus ID, index ID và manifest hash cần đọc.
- ID/hash của 43 payload gốc đã có.
- Metadata renderer, tiêu đề, tên chỉ tiêu và quy tắc đơn vị. Định nghĩa chỉ tiêu được dùng chung để tránh lặp theo mỗi kỳ; observation ID được suy ra bằng cùng công thức định danh và đã kiểm chứng.
- Danh sách ngày thuộc tập cố định và indicators cần giữ vì payload bars cũ không chứa indicators.
- 13 bộ trường hồ sơ doanh nghiệp của phiên bản cũ.

Không chứa bản sao giá trị BCTC, nội dung bài báo hay OHLCV. Vẫn có chữ trong metadata (nhãn, tên doanh nghiệp, tiêu đề), có các số indicators cần giữ lịch sử. Không thêm chunk_text vào text_chunks. Không thêm bảng/cột.

File cụ thể: outputs/corpus-v4-reuse-audit-20261022/reuse-root.proposed.json. Tóm tắt và dung lượng: reuse-summary.json. Kế hoạch cũ 676 bản nguồn / 15,6 MB bị thay thế, không áp dụng song song.

## Backend đọc thế nào?

1. Tìm vector trong đúng corpus/index, lấy locator và hash chunk.
2. Đọc bản metadata liên kết đúng index; kiểm tra checksum/UUID và corpus đã đăng ký.
3. Lấy payload gốc bằng payload_id cụ thể, kiểm tra stored hash và semantic hash. Không lấy latest.
4. Dựng nguồn theo renderer/metadata đã chốt; áp dụng đúng đơn vị theo release, không tự gán đơn vị cho số khác.
5. Đối chiếu fingerprint toàn phần báo cáo, membership dòng, vị trí và hash nội dung chunk trước khi trả chữ.

Thiếu nguồn hoặc nguồn bị thay đổi thì chặn lỗi rõ ràng, không tự thay bằng bảng live hoặc snapshot local. Thành viên chỉ cần code, kết nối DB và cấu hình corpus/source backend đồng bộ, không cần ZIP.

## Bảo toàn nguồn cho các lần cào sau

Phát hiện crawler sink trước đây bật STABLE_PAYLOAD_IDS=True, có thể ghi đè raw_payloads theo đường dẫn file. Đã sửa source code để:

- Mỗi nội dung mới dùng ID có content digest; không ghi đè bản gốc cũ.
- Payload có cùng ID thì DO NOTHING và đọc lại kiểm tra URI/hash/nội dung; xung đột sẽ bị từ chối.
- Các bảng giá/tin live vẫn có thể cập nhật như trước; corpus cũ đọc payload đã pin, không phụ thuộc bản live.

Chưa chạy crawler sau thay đổi này. Đây là thay đổi hành vi cho các lần ingest mới, không sửa lại payload cũ. Mỗi thay đổi nguồn sẽ giữ phiên bản mới nên dung lượng tăng theo số lần nội dung đổi; retention phải thống nhất với thời gian hỗ trợ corpus. Nếu nhóm xóa nguồn sau 30 ngày thì corpus tham chiếu nguồn đó cũng không thể tiếp tục cam kết đọc lịch sử nếu không giữ nguồn ở nơi khác.

## Kiểm thử đã đạt

- Rà 675 tài liệu với dữ liệu Supabase bằng SELECT READ ONLY.
- Hai client mô phỏng độc lập: mỗi client đọc payload gốc thật lấy từ DB và dựng đúng **7.158/7.158 chunk**.
- Metadata root và registry v4 trong phép thử là bản đề xuất mô phỏng, không được INSERT. Snapshot chỉ là chuẩn so sánh của chương trình kiểm thử; runtime reader không đọc file snapshot.
- 49 tests nguồn dùng lại/nguồn chung/snapshot/hash/API đạt, gồm từ chối nguồn sai và kiểm tra crawler không ghi đè payload cũ.
- Chưa phải test hai máy production hoặc API đang phục vụ người dùng: bản metadata và đăng ký v4 chưa được duyệt để triển khai.

Evidence: audit.json, financial-metadata.proposed.json, news-reuse.json, price-reuse.json, index-reuse.json, reuse-summary.json, verification.json trong thư mục outputs/corpus-v4-reuse-audit-20261022.

## Phần còn phải duyệt và kiểm tra trước khi bật

1. Ingest vector v4 hoàn tất và audit đủ 7.158 vector/hash/locator.
2. Bạn duyệt **một bản metadata nêu trên**, thay cho 676 bản nguồn; cần ghi append-only với khóa chống URI trùng và đọc lại xác minh. Không có apply script được chạy trong công việc này.
3. Đăng ký/kích hoạt v4 và kiểm tra nguồn chung trước khi đổi default, theo phạm vi bạn duyệt riêng.
4. Chuyển SOURCE_READ_BACKEND=supabase và corpus/hash v4, khởi động lại; chạy npm run check:sources rồi test API Q31–Q39, bsa90 và hồi quy upload trên máy thành viên.

Không coi việc có metadata local hoặc test mô phỏng đạt là đã triển khai xong. Không bỏ hash guard, thay đơn vị, hay thay chính sách citation để ép test trả 200.
