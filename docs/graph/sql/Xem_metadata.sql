-- Metadata bổ sung cho các bảng graph hiện có; lọc phiên để tránh đếm lịch sử.
SELECT * FROM graph_metadata.versions
WHERE graph_version_id='6f1504e8-3eef-59e7-9d20-8c5957cb4427';

SELECT a.extraction_id,s.canonical_name AS subject,a.relation_type,
       o.canonical_name AS object,a.payload->>'position' AS position,
       a.payload->>'validation_status' AS source_validation,
       COALESCE(r.decision,'PENDING') AS review_status,r.reason_code,r.note,
       a.payload->>'source_url' AS source_url,
       (SELECT count(*) FROM graph_metadata.source_chunks c
        WHERE c.extraction_id=a.extraction_id) AS source_chunk_count
FROM graph_metadata.assertions a
JOIN graph_metadata.entities s ON s.graph_version_id=a.graph_version_id AND s.entity_id=a.subject_id
JOIN graph_metadata.entities o ON o.graph_version_id=a.graph_version_id AND o.entity_id=a.object_id
LEFT JOIN LATERAL (
 SELECT decision,reason_code,note FROM graph_metadata.reviews
 WHERE extraction_id=a.extraction_id ORDER BY created_at DESC,review_id DESC LIMIT 1
) r ON true
WHERE a.graph_version_id='6f1504e8-3eef-59e7-9d20-8c5957cb4427'
ORDER BY subject,a.relation_type,object;

-- Hàng đợi cách ly theo quyết định mới nhất, không xóa lịch sử review.
WITH latest AS (
 SELECT DISTINCT ON (extraction_id) * FROM graph_metadata.reviews
 ORDER BY extraction_id,created_at DESC,review_id DESC
)
SELECT * FROM latest WHERE decision='QUARANTINED';
