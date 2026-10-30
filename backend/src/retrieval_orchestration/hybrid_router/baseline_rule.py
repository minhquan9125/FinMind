"""Offline keyword baseline. No entity parsing, retrieval or model loading."""

from dataclasses import asdict, dataclass
import re
import unicodedata


@dataclass(frozen=True)
class BaselinePrediction:
    needs_graph: int
    needs_content: int
    route: str | None
    reason_code: str
    matched_graph: tuple[str, ...]
    matched_content: tuple[str, ...]
    model_version: str = "keyword-baseline-v1"

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


GRAPH_TERMS = ("cong ty con", "doanh nghiep con", "cong ty me", "so huu", "chu tich")
CONTENT_TERMS = (
    "tong tai san", "tai san", "doanh thu", "loi nhuan", "dong tien",
    "von chu so huu", "no phai tra", "bctc", "bao cao tai chinh",
    "bctn", "bao cao thuong nien", "quan tri rui ro",
)


def classify_by_keywords(resolved_question: str) -> BaselinePrediction:
    """Classify ONLY resolved retrieval questions after intent/scope gates.

    A route is a proposal, never permission to call an adapter. This deliberately
    simple baseline cannot resolve context, capabilities, negation or ambiguity.
    (0, 0) returns route=None; policy must decide what happens next.
    """
    if not isinstance(resolved_question, str) or not resolved_question.strip():
        raise ValueError("A nonempty resolved retrieval question is required")
    text = " " + _normalize(resolved_question) + " "
    graph = tuple(term for term in GRAPH_TERMS if " " + term + " " in text)
    content = tuple(term for term in CONTENT_TERMS if " " + term + " " in text)
    labels = (int(bool(graph)), int(bool(content)))
    route = {(1, 0): "GRAPH", (0, 1): "VECTOR", (1, 1): "BOTH"}.get(labels)
    return BaselinePrediction(*labels, route,
                              "KEYWORD_MATCH" if route else "NO_KEYWORD_MATCH",
                              graph, content)
