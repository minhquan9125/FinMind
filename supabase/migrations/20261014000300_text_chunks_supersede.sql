-- Chunk ID là "căn cước" của chunk và được evidence/citation trỏ tới (khóa ngoại).
-- Quyết định của leader (phương án B): khi nội dung đổi, KHÔNG đổi chunk_id cũ;
-- tạo chunk mới và đánh dấu chunk cũ là "đã bị thay" để trích dẫn cũ vẫn đúng nội dung lúc đó.
--
-- Thứ tự bắt buộc: chạy file này TRƯỚC khi chạy code mới (db_ingest.py, repository.py),
-- vì code mới dùng cột superseded_at và chỉ mục một phần bên dưới.
BEGIN;

ALTER TABLE public.text_chunks
    ADD COLUMN IF NOT EXISTS superseded_at timestamptz,
    ADD COLUMN IF NOT EXISTS superseded_by_chunk_id uuid;

COMMENT ON COLUMN public.text_chunks.superseded_at IS
    'NULL = chunk còn hiệu lực. Có giá trị = đã bị thay bởi chunk mới (giữ lại để trích dẫn cũ còn đúng).';
COMMENT ON COLUMN public.text_chunks.superseded_by_chunk_id IS
    'chunk_id của chunk thay thế (truy vết phiên bản nội dung).';

-- Khóa vị trí trước đây áp dụng cho mọi hàng, nên không thể giữ chunk cũ cạnh chunk mới
-- ở cùng vị trí. Giờ chỉ bắt buộc duy nhất giữa các chunk còn hiệu lực.
DROP INDEX IF EXISTS public.uq_text_chunks_index_document_chunk;

CREATE UNIQUE INDEX IF NOT EXISTS uq_text_chunks_current_position
    ON public.text_chunks (index_version_id, document_id, chunk_index)
    WHERE superseded_at IS NULL;

COMMIT;
