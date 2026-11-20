"""Checks for the WBS34 audit's evidence boundary; no database access."""

import hashlib

from scripts.audit_vector_e2e import check_chunks


def sample(position=0, text="FPT đã phân phối 171,4 triệu cổ phiếu"):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    row = {
        "chunk_id": f"chunk-{position}", "chunk_index": position,
        "document_id": "document-1", "index_version_id": "index-1",
        "content_hash": digest, "dimensions": 1024,
    }
    source = {
        "text": text,
        "locator_json": {
            "source_table": "news_articles", "source_id": "article-1",
            "reconstruction": {"chunk_index": position, "document_id": "source-document-1"},
        },
    }
    return row, source


def check(rows, sources):
    return check_chunks(rows, sources, document_id="document-1", index_id="index-1",
                        source_id="article-1", dimensions=1024)


def test_valid_reconstructed_chunks():
    first, first_source = sample()
    second, second_source = sample(1)
    assert check([first, second], [first_source, second_source]) == []


def test_duplicate_position_and_wrong_dimension_are_reported():
    first, first_source = sample()
    second, second_source = sample(0)
    second["chunk_id"] = "another-id"
    second["dimensions"] = 384
    problems = check([first, second], [first_source, second_source])
    assert "DUPLICATE_OR_MISSING_CHUNK_POSITION" in problems
    assert "WRONG_VECTOR_DIMENSION" in problems


def test_changed_source_text_is_rejected():
    row, source = sample()
    source["text"] = "Nội dung đã bị sửa"
    assert "CHUNK_HASH_MISMATCH" in check([row], [source])


def test_missing_source_or_wrong_locator_is_rejected():
    row, source = sample()
    assert "SOURCE_RECONSTRUCTION_COUNT_MISMATCH" in check([row], [])
    source["locator_json"]["source_id"] = "another-article"
    assert "WRONG_SOURCE_LOCATOR" in check([row], [source])
