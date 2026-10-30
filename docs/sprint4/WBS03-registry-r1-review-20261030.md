# WBS03 — registry BCTN r1 và lượt rà mới

Ngày 30/10/2026. Hưng bàn giao `WBS02_REGISTRY_BCTN_20261030_r1.zip`. Đã xác minh **19/19** file theo `MANIFEST.sha256`; registry mới SHA256 `b9701c612afcb6d4694301148980d48b4269d460a200453b96f7f8fdca93ea2d`, giữ 1.430 ID cũ, thêm 10 ID và một alias BIC. File mới được tích hợp có phiên bản tại `backend/src/sprint4_runtime/company.registry.20261030.r1.json`; `company.registry.json` cũ và code resolver/contract của WBS02 không đổi. Hai CLI WBS03 mặc định dùng registry r1, vẫn cho phép `--registry` để thử phiên khác.

Chạy lại **offline** từ 20 envelope BCTN đã xác minh trước đó, thuộc corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`, index `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`. Kết quả mới ở `backend/.tmp/wbs03-registry-r1-20261030/` (local, Git ignore): **17 ứng viên `PENDING`**, 16 đối tượng `resolved`, 1 `unresolved`. Tất cả quote được kiểm là đoạn con của đúng chunk trong JSON. Đây **không** phải lần đọc DB mới, WBS06 approval hay kiểm precision/recall toàn corpus.

| # | Cặp và loại | BCTN, trang; chunk chứng minh | Đối chiếu nguồn | Trạng thái đối tượng / lưu ý |
|---:|---|---|---|---|
| 1 | TCB → TCBS · con | 2025, 39; `b102a5c0-6c8e-54fd-bf09-f9e5234948be` | Hưng ca 1 | Resolved; sơ đồ trang 14 có 79,8% tại 31/12/2025, JSON chưa gắn. |
| 2 | TCB → TechAMC · con | 2025, 160; `c558329f-1d80-5890-8000-d81b2cbe9e75` | Nhân tự đối chiếu snapshot: trang 160 đặt tên pháp lý TechAMC dưới mục “công ty con”; trang 84, chunk `59284ce0-5faf-5401-b237-7db00e01912c`, nhắc phần vốn góp của Techcombank tại TechAMC. | Resolved, vẫn `PENDING`. Ngày 10/11/2025 là ngày nghị quyết, không suy thành ngày bắt đầu quan hệ; chưa xác định tỷ lệ sở hữu. |
| 3 | TCB → TCBS · con | 2024, 32; `b32c6e1a-7d50-5e9a-8036-9b0fe7a59590` | Hưng ca 2 | Resolved; sơ đồ trang 12 có 94,1% tại 31/12/2024. JSON chưa gắn tỷ lệ/ngày; cùng `relation_id` với #1 khi hai năm chưa có temporal. |
| 4 | TCB → TechAMC · con | 2024, 36 và 111; `4690db74-eb51-595e-b467-2c8deaf4a0fa`, `afb131a9-536a-5bdb-85a7-a726ff027c84` | Hưng ca 4 | Resolved bằng alias TechAMC đã xác minh; tên cụt ở trang 36 không còn tạo quan hệ thứ hai. |
| 5 | TCB → TCC · con | 2024, 35; `4ce022d2-27b0-5053-a55b-a9fafd332cb9` | Hưng ca 3 | Resolved; sơ đồ trang 12 có 88,99%, JSON chưa gắn. |
| 6 | BID → BIC · con | 2025, 63; `4298445a-935f-5a25-b965-b21075f2b9f9` | Hưng ca 5 | **Unresolved duy nhất:** tên trong bảng bị tách cột. Hưng xác nhận BIC là `CMP-5b089951c0151837994a`; resolver chung vẫn chặn ticker `BIC` khi chunk không có ngữ cảnh ticker đủ rõ. Không tự vượt rào resolver. |
| 7 | VCB → VCBL · con | 2025, 18; `2ceea344-77ec-52e7-92e3-a5037a1eb64b` | Nhân tự đối chiếu snapshot: trang 18 ghi VCBL do Vietcombank sở hữu 100% vốn; trang 41, chunk `cf13db45-8624-5686-81ea-d19c101b6e93`, liệt kê VCBL là công ty con. | Resolved, vẫn `PENDING`. Tỷ lệ 100% có trong nguồn nhưng JSON ứng viên hiện chưa gắn thuộc tính này. |
| 8 | VCB → VCBL · con | 2024, 19; `f45912ed-4282-5edb-88ce-a43c11c3776b` | Hưng ca 6 | Resolved; nguồn ghi 100%, JSON chưa gắn. |
| 9 | VCB → VCBR · con | 2024, 19; `4da429da-4ebd-5fef-9fad-4054093f8eb5` | Hưng P04 | Resolved; nguồn ghi 100%, JSON chưa gắn. |
| 10 | ELC → Bắc Kạn · liên kết | 2024, 14; `81715bf0-2032-5764-834b-cfefb59d3bc7` | Hưng P03 | Resolved; 42,97% chưa gắn; không suy trực tiếp/gián tiếp. |
| 11 | ELC → VFT · liên kết | 2024, 14; `81715bf0-2032-5764-834b-cfefb59d3bc7` | Hưng registry r1 xác nhận | Resolved; **41,58%** thuộc VFT ở chunk kế tiếp, không lấy 42,97% của Bắc Kạn; JSON chưa gắn. |
| 12 | ELC → Tập đoàn Thương mại Hà Nội · con | 2024, 14; `e3343e86-4b79-54ac-bff5-cc137867284d` | Hưng registry r1 xác nhận | Resolved; 68,68% đúng hàng, JSON chưa gắn. Không đồng nhất với Hapro. |
| 13 | ELC → ElcomPrime · con | 2024, 14; `8aa9e55d-fe91-5107-9147-817842ffa98a` | Hưng P02 | Resolved; 70% chưa gắn. |
| 14 | ELC → Smartek · con gián tiếp | 2024, 14; `e67bc152-bd52-539e-9cde-32ef4bfca7a6` | Hưng ca 8 | Resolved; tên đã bỏ phần giải thích “(Là…”. Không gán 74,4% cho cạnh Datanova → Smartek. |
| 15 | Datanova → Smartek · con | 2024, 14; `e67bc152-bd52-539e-9cde-32ef4bfca7a6` | Hưng ca 8 | **Ứng viên mới**, hai đầu resolved; câu nguồn nói trực tiếp “công ty con của Công ty Cổ phần Datanova Việt Nam”. Chưa suy tỷ lệ/ngày. |
| 16 | ELC → ELCOM Software · con | 2024, 14; `107c2ccc-3f33-5117-a521-7fed698f78a9` | Hưng ca 7 | Resolved; 100% chưa gắn. |
| 17 | ELC → Datanova · con | 2024, 14; `107c2ccc-3f33-5117-a521-7fed698f78a9` | Hưng P01 | Resolved; 93% nằm qua ranh giới chunk, JSON chưa gắn. |

**Bàn giao tiếp:** Hai ca #2 và #7 đã được Nhân tự đối chiếu trên chunk của đúng snapshot BCTN 2025; đây là kiểm chứng ứng viên, không thay thế phê duyệt độc lập của WBS06. Với BIC #6, cần WBS02 chỉ cách nối an toàn alias trong hàng bảng bị trộn cột nếu muốn resolve tự động; hiện giữ `PENDING unresolved` để reviewer đối chiếu tay, không tự cấp ID hay nới quy tắc ticker toàn cục. Huyền/WBS06 quyết định trạng thái và các thuộc tính bắt buộc trước khi publish; registry `verified=true` chỉ xác nhận danh tính, không duyệt quan hệ.

**Giới hạn kỹ thuật:** 17 ứng viên đều chưa có `as_of`/`valid_from`; tỷ lệ được Hưng đối chiếu ở bảng/sơ đồ/chunk khác chưa được WBS03 tự ghép để tránh gán sai. Contract 2.1.0 còn yêu cầu `consolidation_basis`/`accounting_basis` với quan hệ `APPROVED`. Hai phát biểu TCB–TCBS năm 2024 và 2025 hiện chung `relation_id`; không được gộp mất lịch sử khi WBS06/WBS08 xử lý. Bốn cặp âm N01–N04 trong gói đối chiếu trước không xuất cạnh giữa đúng hai đầu; điều này không chứng minh precision toàn corpus.

Kiểm thử code WBS03 sau tích hợp: `py -X utf8 -m unittest backend.tests.test_wbs03_relation_extractor backend.tests.test_wbs03_db_adapter backend.tests.test_wbs03_bctn_source` — **29 test qua**, không truy cập DB. Không chạy migration, không ghi PostgreSQL hay Neo4j.
