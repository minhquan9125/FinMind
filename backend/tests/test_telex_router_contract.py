"""Independent Vietnamese-to-Telex encoding checks the shared input boundary.

The encoder here derives keys from Unicode diacritics, not from the decoder's
vocabulary or implementation. End-to-end cases retain user-approved routes.
"""
import json
from pathlib import Path
import re
import unicodedata

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import hybrid_router as api
from src.retrieval_orchestration.input_normalization import normalize_user_text, _telex
from src.retrieval_orchestration.retrieval_flow.intent import _fold
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine


CASES = json.loads((Path(__file__).parent / "fixtures/router_acceptance_v2.json").read_text("utf-8"))
CASES += json.loads((Path(__file__).parent / "fixtures/router_language_holdout.json").read_text("utf-8"))
USER_TELEX = "duwj ddoan thij truongf chuwsng khoans sawp towi"
TONES = {"\u0301": "s", "\u0300": "f", "\u0309": "r", "\u0303": "x", "\u0323": "j"}


def encode_word(word, mode):
    if word.isascii():
        return word
    chunks = []
    tone = ""
    last_vowel = None
    for char in word.lower():
        if char == "đ":
            chunks.append("dd")
            continue
        decomposition = unicodedata.normalize("NFD", char)
        base = decomposition[0]
        marks = set(decomposition[1:])
        if "\u0302" in marks:
            base *= 2
        elif "\u0306" in marks:
            base += "w"
        elif "\u031b" in marks:
            base += "w"
        chunks.append(base)
        if decomposition[0] in "aeiouy":
            last_vowel = len(chunks)-1
        for mark in marks:
            if mark in TONES:
                tone = TONES[mark]
    if mode == "infix" and last_vowel is not None:
        chunks[last_vowel] += tone
    else:
        chunks.append(tone if mode != "shape_only" else "")
    encoded = "".join(chunks)
    return encoded.upper() if word.isupper() else encoded


def encode_sentence(text, mode):
    return re.sub(r"[^\W\d_]+", lambda m: encode_word(m[0], mode), text, flags=re.UNICODE)


class Predictor:
    model_version = "telex-adversarial"

    def predict(self, question):
        return .99, .99


@pytest.mark.parametrize("mode", ["suffix", "infix", "shape_only"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["question"])
def test_encoded_approved_sentences_preserve_text_scope_and_route(case, mode):
    raw = encode_sentence(case["question"], mode)
    normalized = normalize_user_text(raw)
    assert _fold(normalized) == _fold(normalize_user_text(case["question"]))
    assert normalize_user_text(normalized) == normalized
    decision = DecisionEngine(Predictor()).decide(raw)
    assert decision.route == case["route"]
    assert decision.scope.companies == case["companies"]
    if decision.tasks:
        assert all(task.params["question"] == raw for task in decision.tasks)


@pytest.mark.parametrize("raw", [
    USER_TELEX,
    "duwj ddoans thij truwowngf chuwngs khoans sawps towis",
    "duw j",  # Unknown word boundaries must not be silently joined.
])
def test_literal_user_input_and_unknown_word_boundaries(raw):
    normalized = normalize_user_text(raw)
    if raw == "duw j":
        assert " " in normalized
        return
    assert normalized == "du doan thi truong chung khoan sap toi"
    assert DecisionEngine(Predictor()).decide(raw).route == "VECTOR"


@pytest.mark.parametrize("raw", [USER_TELEX, USER_TELEX.upper()])
def test_literal_case_is_accepted_through_real_fastapi_validation(monkeypatch, raw):
    monkeypatch.setattr(api, "get_router_engine", lambda: DecisionEngine(Predictor()))
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.router_access] = lambda: None
    with TestClient(app) as client:
        response = client.post("/api/hybrid-router/test", json={"question": raw})
    assert response.status_code == 200
    assert response.json()["route"] == "VECTOR"
    assert response.json()["scope"]["companies"] == []
    assert response.json()["normalized_question"] == "du doan thi truong chung khoan sap toi"


@pytest.mark.parametrize("ticker", ["FPT", "MSN", "MNS", "FOT", "ABC", "LAF", "DDC", "GAS", "DCA", "ETF", "EPS"])
def test_ticker_or_acronym_is_not_spell_corrected(ticker):
    raw = f"giaf {ticker} hom nay"
    normalized = normalize_user_text(raw)
    assert normalized == f"gia {ticker} hom nay"


def test_ids_values_urls_emails_and_money_are_untouched():
    raw = "FPT MNS DCA PROFIT_AFTER_TAX doc_fpt_2026 57,400 15/10/2026 50k 10 tr https://example.com/duwj?q=truongf mail@chuwsng.com"
    assert normalize_user_text(raw) == raw


def test_known_unaccented_words_and_ambiguous_decodings_are_not_guessed():
    assert normalize_user_text("thi truong chung khoan sap toi") == "thi truong chung khoan sap toi"
    assert _telex("mafs", {"mas", "maf"}) == "mafs"


@pytest.mark.parametrize("raw", ["hello world", "cash flow", "after tax", "price close open volume", "bar", "margin ETF DCA"])
def test_english_words_are_not_damaged(raw):
    assert normalize_user_text(raw) == raw
