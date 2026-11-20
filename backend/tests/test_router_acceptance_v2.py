"""User-approved routing examples, paraphrases and conversation boundaries.

Deliberately adversarial classifier scores verify that business policy wins
without treating offline fixture success as model accuracy.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import hybrid_router as api
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine, SessionScope

CASES = json.loads((Path(__file__).parent / "fixtures/router_acceptance_v2.json").read_text("utf-8"))


class Predictor:
    model_version = "adversarial-test"

    def __init__(self, scores):
        self.scores = scores

    def predict(self, question):
        return self.scores


@pytest.mark.parametrize("scores", [(0.99, 0.01), (0.01, 0.99), (0.99, 0.99), (0.01, 0.01)])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["question"])
def test_approved_routes_ignore_wrong_classifier_bias(case, scores):
    decision = DecisionEngine(Predictor(scores)).decide(case["question"])
    assert decision.route == case["route"]
    assert decision.scope.companies == case["companies"]
    if decision.route == "CLARIFY":
        assert decision.tasks == []
    else:
        assert all(task.params["question"] == case["question"] for task in decision.tasks)
        assert decision.reason_code == "INTENT_POLICY"
        adapters = [task.adapter for task in decision.tasks]
        if decision.route == "VECTOR":
            assert adapters and set(adapters) == {"CONTENT"}
        else:
            assert adapters == {"GRAPH": ["GRAPH"], "BOTH": ["GRAPH", "CONTENT"]}[decision.route]


def test_single_company_followup_uses_context_but_market_and_knowledge_reset_it():
    engine = DecisionEngine(Predictor((0.99, 0.99)))
    context = SessionScope(companies=("FPT",), periods=("2025",), metric_code="REVENUE")
    assert engine.decide("quý 2 lãi bao nhiêu", context=context).scope.companies == ["FPT"]
    for question in ("tt đỏ quá trời giải thích giúp t", "DCA là gì", "ETF là gì"):
        decision = engine.decide(question, context=context)
        assert decision.route == "VECTOR"
        assert decision.scope.companies == []
        assert decision.scope.metric_code is None
    ambiguous = SessionScope(companies=("FPT", "HPG"))
    assert engine.decide("doanh thu bao nhiêu", context=ambiguous).route == "CLARIFY"
    leadership = engine.decide("còn VCB ai là chủ tịch", context=context)
    assert leadership.route == "GRAPH"
    assert leadership.scope.metric_code is None


def test_partial_and_future_periods_preserve_user_intent_without_forcing_a_year():
    engine = DecisionEngine(Predictor((0.99, 0.99)))
    assert engine.decide("dự báo tt tuần sau").scope.periods == ["NEXT_WEEK"]
    assert engine.decide("FPT quý 2 lãi bao nhiêu").scope.periods == ["LATEST_YEAR-Q2"]
    question = "vì sao giá cổ phiếu FPT giảm"
    decision = engine.decide(question)
    assert decision.tasks[0].operation == "analyze_market_drivers"
    assert decision.tasks[0].params["question"] == question


def test_two_turns_keep_context_and_do_not_return_422(monkeypatch):
    monkeypatch.setattr(api, "get_router_engine", lambda: DecisionEngine(Predictor((0.99, 0.99))))
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(hybrid_router_mode="mock"))
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        for case in CASES:
            response = client.post("/api/hybrid-router/test", json={"question": case["question"]})
            assert response.status_code == 200, response.text
            assert response.json()["route"] == case["route"]
        first = client.post("/api/hybrid-router/test", json={"question": "chủ tịch FPT là ai"}).json()
        scope = first["scope"]
        context = {key: scope[key] for key in ("companies", "periods", "metric_code", "detected_industry", "entity_mentions")}
        for endpoint in ("test", "run"):
            response = client.post(f"/api/hybrid-router/{endpoint}", json={
                "question": "thị trường hn sao giảm mạnh", "context": context,
            })
            assert response.status_code == 200, response.text
            assert response.json()["route"] == "VECTOR"
            assert response.json()["scope"]["companies"] == []
