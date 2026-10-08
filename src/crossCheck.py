"""Compare Gemini and Tesseract numbers and text."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from util import js_round


NUMBER = re.compile(r"[0-9]{1,3}(?:[.,][0-9]{3})+(?:,[0-9]+)?|[0-9]{4,}")


def number_keys(text: str) -> list[str]:
    keys: dict[str, None] = {}
    for token in NUMBER.findall(text):
        digits = re.sub(r"[^0-9]", "", token)
        if len(digits) >= 4:
            keys[digits] = None
    return list(keys)


def fold_key(text: str) -> str:
    text = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "d")
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).lower())


def dice(a: str, b: str) -> float:
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a == b else 0.0
    grams: dict[str, int] = {}
    for i in range(len(a) - 1):
        gram = a[i:i + 2]
        grams[gram] = grams.get(gram, 0) + 1
    overlap = 0
    for i in range(len(b) - 1):
        gram = b[i:i + 2]
        if grams.get(gram, 0):
            overlap += 1
            grams[gram] -= 1
    return 2 * overlap / (len(a) + len(b) - 2)


def cross_check(gemini: str, tess: str) -> dict[str, Any]:
    gemini_numbers, tess_numbers = number_keys(gemini), number_keys(tess)
    tess_set = set(tess_numbers)
    unverified = [number for number in gemini_numbers if number not in tess_set]
    return {
        "geminiNumbers": len(gemini_numbers), "tessNumbers": len(tess_numbers),
        "numberAgreement": js_round((len(gemini_numbers) - len(unverified)) / len(gemini_numbers), 3)
        if gemini_numbers else 1,
        "unverifiedNumbers": unverified[:50],
        "similarity": js_round(dice(fold_key(gemini), fold_key(tess)), 3),
    }


numberKeys = number_keys
foldKey = fold_key
crossCheck = cross_check
