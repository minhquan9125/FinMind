from src.text_analysis import (
    idf_weights,
    raw_words,
    term_frequencies,
    tokenize,
    tokenize_with_trace,
)


def test_raw_words_splits_on_punctuation_and_lowercases():
    assert raw_words("Ngân hàng VCB, quý 3/2026!") == ["ngân", "hàng", "vcb", "quý", "3", "2026"]


def test_tokenize_drops_stopwords_and_single_chars():
    tokens = tokenize("the bank report is good and it is a")
    assert "the" not in tokens
    assert "is" not in tokens
    assert "a" not in tokens
    assert "bank" in tokens
    assert "report" in tokens


def test_tokenize_with_trace_marks_removed_reason():
    trace = tokenize_with_trace("a the bank")
    reasons = {t.word: (t.kept, t.reason) for t in trace}
    assert reasons["a"] == (False, "too short (1 character)")
    assert reasons["the"] == (False, "stopword")
    assert reasons["bank"] == (True, None)


def test_idf_is_lower_for_more_common_terms():
    tf_list, df, _ttf = term_frequencies(
        [
            "revenue increased this quarter",
            "revenue decreased this quarter",
            "profit margin improved",
        ]
    )
    idf = idf_weights(df, doc_count=3)
    # "revenue"/"quarter" appear in 2/3 chunks, "profit" in 1/3 -> profit is rarer
    assert idf["profit"] > idf["revenue"]
    assert len(tf_list) == 3
