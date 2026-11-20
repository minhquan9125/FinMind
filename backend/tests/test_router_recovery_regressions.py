"""Regressions reproduced while recovering the October 30 working tree."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routers import hybrid_router as api
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
from src.retrieval_orchestration.live_research import analyze_live


class Predictor:
    model_version = "recovery-test"

    def predict(self, question):
        return (0.05, 0.95)


@pytest.mark.parametrize("endpoint", ["test", "run"])
def test_interactive_context_is_accepted_and_preserved(monkeypatch, endpoint):
    contexts = []

    class RecordingEngine(DecisionEngine):
        def decide(self, question, *, context=None):
            contexts.append(context)
            return super().decide(question, context=context)

    engine = RecordingEngine(Predictor())
    monkeypatch.setattr(api, "get_router_engine", lambda: engine)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(hybrid_router_mode="mock"))
    app = FastAPI()
    app.include_router(api.router)
    spec = importlib.util.spec_from_file_location(
        "recovered_interactive", Path(__file__).resolve().parents[2] / "interactive_test.py"
    )
    client_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_module)

    with TestClient(app) as client:
        first = client.post("/api/hybrid-router/test", json={"question": "Chủ tịch của FPT là ai"})
        assert first.status_code == 200
        assert first.json()["route"] == "GRAPH"
        context = client_module._next_context(first.json())
        context.update(detected_industry="TECHNOLOGY", entity_mentions=["FPT"])
        second = client.post(f"/api/hybrid-router/{endpoint}", json={
            "question": "cổ đông lớn nhtas của fpt", "context": context,
        })
        assert second.status_code == 200, second.text
        assert second.json()["scope"]["companies"] == ["FPT"]
        assert contexts[-1].detected_industry == "TECHNOLOGY"
        assert contexts[-1].entity_mentions == ("FPT",)


@pytest.mark.parametrize("question", [
    "thị trường hn như nào",
    "thị trường hôm nay như nào",
    "thị trường hn thế nào",
])
def test_daily_digest_paraphrases_agree_across_both_entry_points(question):
    decision = DecisionEngine(Predictor()).decide(question)
    assert decision.route == "VECTOR"
    assert decision.scope.topic == "MARKET_DAILY_DIGEST"
    assert decision.scope.companies == []
    live = analyze_live(question)
    assert live["decision"] == "MARKET_LOOKUP"
    assert live["scope"]["topic"] == "MARKET_DAILY_DIGEST"
    assert live["scope"]["companies"] == []
