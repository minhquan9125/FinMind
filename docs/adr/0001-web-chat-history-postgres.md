# ADR-0001: Lưu lịch sử web chat trong Supabase theo chủ sở hữu

Date:2026-10-24. Status:accepted. Deciders:user yêu cầu chuyển khỏi file, Codex triển khai.

## Context

Tài khoản hiện ởpublic.users và JWT do backend tự phát. Lịch sử web từng ở JSON theoowner/session trên một máy. User yêu cầu lưu/truy vấn Supabase và không ghi JSON nữa, đồng thời không cho tài khoản đọc lẫn lịch sử. Phải giữ UI/API/revision và nội dung/nguồn/ngữ cảnh cũ.

## Decision

Dùng schema research_chat với conversations/messages, FKuser và FKghép owner/session. Mọi customerDBoperation dùng roleNOLOGIN/NOBYPASSRLS riêng và transaction-localowner; ENABLE/FORCERLS kiểm tra chủ sở hữu ngoài ownerfilter của backend. Giải phóng connection khi chờengine, dùng lease+revision cóCAS và commit atomic. Nhập archive9phiên/188tin một lần, giữ nguồn nguyên và không filefallback. Hướng dẫn/quyền/khôi phục tại [POSTGRES_HISTORY](../../backend/src/retrieval_orchestration/notes/POSTGRES_HISTORY.md).

## Alternatives considered

- JSONfiles tiếp: đơn giảnoffline, nhưng user không muốn máy local là nguồn lịch sử, triển khai đa máy khó.
- Chỉ filterowner trongapp bằng adminrole: ítsetup nhưng queryquênfilter có thểlộ dữ liệu; thêmRLSrole thực thi được ởDB.
- SupabaseAuth/auth.uid(): thuận nếu đổi hệauth, nhưng hệ thống cóJWT/users/Googlelogin riêng; chuyểnAuth ngoài scope.
- Giữ DBrowlock/transaction quaLLM: chốngrace đơn giản nhưng có thể giữpool trong10phút, ảnh hưởngauth/tài liệu/người khác.

## Consequences

Lịch sử bền qua restart/máy khác; role/contextpool được test với hai tài khoản. Cần migration/grant chuẩn, DB khả dụng, giới hạn lease và operatorbackup. Admin DB vẫn có quyền vận hành; không dùng adminquery trực tiếp chocustomerAPI. Khôngdropdata khirollback; JSONarchive khôngchứa chat mới sau chuyển đổi.
