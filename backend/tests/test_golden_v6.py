"""Golden v6 parsing must not silently reuse v5 questions or gold answers."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_golden_v6 import classify_status, selected_questions
from golden_v6 import DEFAULT_GOLDEN, load_golden_v6


def test_reads_all_draft_questions_without_answers():
    questions = load_golden_v6(DEFAULT_GOLDEN)
    assert [row["id"] for row in questions] == [f"Q{i:02d}" for i in range(1, 41)]
    assert sum(row["kind"] == "vector" for row in questions) == 27
    assert sum(row["kind"] == "calculation" for row in questions) == 9
    assert sum(row["kind"] == "price_row" for row in questions) == 2
    assert sum(row["kind"] == "refusal" for row in questions) == 2
    assert all(set(row) == {"id", "number", "kind", "question"} for row in questions)
    assert classify_status(questions[9]) == "provisional_retrieval"  # Q10 is now news.
    assert classify_status(questions[10]) == "separate_structured_query_not_vector_recall"
    assert classify_status(questions[30]) == "provisional_retrieval"


def test_rejects_missing_or_unknown_ids():
    questions = load_golden_v6(DEFAULT_GOLDEN)
    assert [row["id"] for row in selected_questions(questions, "Q01,Q31")] == ["Q01", "Q31"]
    with pytest.raises(ValueError, match="Unknown Golden IDs"):
        selected_questions(questions, "Q41")
