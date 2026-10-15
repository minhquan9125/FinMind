from src.documents.batch_embeddings import EMBEDDING_DIM, embed_chunks


class FakeEmbedder:
    def __init__(self, fail_text=None):
        self.fail_text = fail_text
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        if self.fail_text and any(self.fail_text in text for text in texts):
            raise RuntimeError("temporary model error")
        return [[0.1] * EMBEDDING_DIM for _ in texts]


def chunk(chunk_id, text):
    return {"chunk_id": chunk_id, "text": text, "locator": {"source": "fixture"}}


def test_successful_batch_returns_one_vector_per_chunk():
    embedder = FakeEmbedder()
    result = embed_chunks([chunk("c1", "good one"), chunk("c2", "good two")], embedder, batch_size=2)

    assert [item["chunk"]["chunk_id"] for item in result.succeeded] == ["c1", "c2"]
    assert all(len(item["embedding"]) == EMBEDDING_DIM for item in result.succeeded)
    assert result.failed == []
    assert embedder.calls == [["good one", "good two"]]


def test_bad_chunk_isolated_and_other_chunks_are_not_duplicated():
    embedder = FakeEmbedder(fail_text="bad")
    chunks = [chunk("c1", "good one"), chunk("c2", "bad text"), chunk("c3", "good three")]
    result = embed_chunks(chunks, embedder, batch_size=3, max_retries=2)

    assert [item["chunk"]["chunk_id"] for item in result.succeeded] == ["c1", "c3"]
    assert len({item["chunk"]["chunk_id"] for item in result.succeeded}) == 2
    assert result.failed == [{
        "chunk_id": "c2", "attempts": 3, "retryable": True,
        "error": "RuntimeError: temporary model error",
    }]
    assert embedder.calls.count(["good one"]) == 1
    assert embedder.calls.count(["good three"]) == 1
    assert embedder.calls.count(["bad text"]) == 3


def test_empty_text_and_duplicate_id_are_reported_without_model_calls():
    embedder = FakeEmbedder()
    result = embed_chunks([
        chunk("c1", "   "), chunk("c2", "valid"), chunk("c2", "duplicate"),
    ], embedder)

    assert [item["chunk"]["chunk_id"] for item in result.succeeded] == ["c2"]
    assert [item["error"] for item in result.failed] == [
        "chunk text is empty or invalid", "duplicate chunk_id; duplicate input ignored",
    ]
    assert embedder.calls == [["valid"]]


def test_wrong_dimension_is_reported_without_retry():
    class WrongDimensionEmbedder:
        def embed_texts(self, texts):
            return [[0.1] * 384 for _ in texts]

    result = embed_chunks([chunk("c1", "valid")], WrongDimensionEmbedder())

    assert result.succeeded == []
    assert result.failed == [{
        "chunk_id": "c1", "attempts": 1, "retryable": False,
        "error": f"expected {EMBEDDING_DIM} dimensions, got 384",
    }]
