"""Step 11 acceptance tests for all 30 Section 6 router fixtures."""

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import hybrid_router as api
from src.retrieval_orchestration.hybrid_router.adapters import AdapterResult
import json
from pathlib import Path

import pytest

from src.retrieval_orchestration.hybrid_router.decision_engine import (
    DecisionEngine,
    ScopeResolver,
    SessionScope,
)
from src.retrieval_orchestration.hybrid_router.schemas import RouterOutput


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src/retrieval_orchestration/hybrid_router/router_fixtures.json"
)
SECTION_6_IDS = (
    *(f"V{i:02d}" for i in range(1, 9)),
    *(f"G{i:02d}" for i in range(1, 7)),
    *(f"B{i:02d}" for i in range(1, 6)),
    *(f"C{i:02d}" for i in range(1, 8)),
    *(f"H{i:02d}" for i in range(1, 5)),
)
FIXTURES = {
    case["id"]: case
    for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["fixtures"]
    if case["id"] in SECTION_6_IDS
}
FIXTURE_RESULTS: dict[str, bool] = {}
REFACTOR_FIXTURES = [
    case
    for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["fixtures"]
    if "refactor" in case.get("tags", [])
]


@dataclass
class StubPredictor:
    scores: tuple[float, float]
    model_version: str = "fixture-model"
    calls: int = 0

    def predict(self, question: str) -> tuple[float, float]:
        self.calls += 1
        return self.scores


def test_section_6_has_exactly_30_unique_cases():
    assert len(SECTION_6_IDS) == 30
    assert len(set(SECTION_6_IDS)) == 30
    assert set(FIXTURES) == set(SECTION_6_IDS)


def test_refactor_fixture_set_covers_all_new_router_categories():
    assert len(REFACTOR_FIXTURES) >= 12
    tags = {tag for case in REFACTOR_FIXTURES for tag in case.get("tags", [])}
    assert {"event", "industry", "macro", "multi_hop", "comparison", "static_info", "vague_time"} <= tags


@pytest.mark.parametrize("case", REFACTOR_FIXTURES, ids=lambda case: case["id"])
def test_refactor_fixtures_route_as_documented(case):
    decision = DecisionEngine(StubPredictor((0.05, 0.95))).decide(case["question"])
    assert decision.route == case["expected_route"]
    if "expected_companies" in case:
        assert decision.scope.companies == case["expected_companies"]
    if "expected_industry" in case:
        assert decision.scope.detected_industry == case["expected_industry"]


def _validate_fixture(case: dict) -> None:
    expected = case["expected"]
    decision = expected["decision"]
    tasks = expected["tasks"]

    if decision in {"SEARCH", "ASK_CLARIFICATION"}:
        payload = {key: value for key, value in expected.items() if key in RouterOutput.model_fields}
        output = RouterOutput.model_validate(payload)
        assert output.execution_mode == "MOCK"
    else:
        assert tasks == []

    if decision != "SEARCH":
        assert tasks == []
        assert case.get("mock_adapter_responses", {}) == {}
    if decision == "ASK_CLARIFICATION":
        assert expected["route"] == "CLARIFY"
        assert expected["missing_fields"]
        assert expected["clarification_question"]
    if expected["route"] == "VECTOR":
        assert [task["adapter"] for task in tasks] == ["CONTENT"]
    if expected["route"] == "GRAPH":
        assert [task["adapter"] for task in tasks] == ["GRAPH"]
    if expected["route"] == "BOTH":
        assert [task["id"] for task in tasks] == ["g1", "v1"]
        assert tasks[1]["depends_on"] == "g1"


@pytest.mark.parametrize("case_id", SECTION_6_IDS)
def test_every_section_6_fixture_obeys_router_contract(case_id, pytestconfig):
    """Run every V/G/B/C/H case and print a visible question summary."""
    try:
        _validate_fixture(FIXTURES[case_id])
    except Exception:
        FIXTURE_RESULTS[case_id] = False
        raise
    else:
        FIXTURE_RESULTS[case_id] = True
    finally:
        if case_id == SECTION_6_IDS[-1]:
            total = len(SECTION_6_IDS)
            passed = sum(FIXTURE_RESULTS.values())
            failed = total - passed
            ratio = passed / total * 100
            reporter = pytestconfig.pluginmanager.get_plugin("terminalreporter")
            reporter.write_sep("=", "HYBRID ROUTER - 30 LEGACY FIXTURE SCHEMA CHECKS")
            reporter.write_line(f"Valid JSON contracts: {passed}/{total}; invalid: {failed}")
            reporter.write_line("These checks validate stored contracts, not routing accuracy.")


@pytest.mark.parametrize("question,field,reason", [
    ("Tổng tài sản năm 2025?", "companies", "MISSING_SCOPE"),
    ("Tổng tài sản FPT quý 5/2025?", "periods", "INVALID_QUARTER"),
])
def test_c01_c02_c04_stop_before_classifier_and_adapters(question, field, reason):
    predictor = StubPredictor((0.9, 0.9))
    engine = DecisionEngine(predictor)
    result = engine.run(question)
    assert result.decision.route == "CLARIFY"
    assert field in result.decision.missing_fields
    assert result.decision.reason_code == reason
    assert predictor.calls == 0
    assert engine.graph_adapter.calls == []
    assert engine.content_adapter.calls == []


def test_c03_ambiguous_company_does_not_retrieve():
    predictor = StubPredictor((0.9, 0.1))
    engine = DecisionEngine(predictor, resolver=ScopeResolver({"an phat": ("MOCK-A", "MOCK-B")}))
    result = engine.run("Tổng tài sản An Phát năm 2025?")
    assert result.decision.reason_code == "AMBIGUOUS_COMPANY"
    assert predictor.calls == 0
    assert not engine.graph_adapter.calls and not engine.content_adapter.calls


def test_c05_ambiguous_conversation_context_does_not_retrieve():
    context = SessionScope(ambiguous_companies=("FPT", "VCB"))
    engine = DecisionEngine(StubPredictor((0.1, 0.9)))
    result = engine.run("Tổng tài sản công ty đó năm 2025?", context=context)
    assert result.decision.reason_code == "AMBIGUOUS_CONTEXT"
    assert not engine.content_adapter.calls


def test_numeric_company_requests_have_independent_content_tasks():
    engine = DecisionEngine(StubPredictor((0.1, 0.9)))
    result = engine.run("Cho tôi doanh thu FPT năm 2025 và giá VCB mới nhất.")
    assert result.decision.route == "VECTOR"
    assert result.decision.scope.companies == ["FPT", "VCB"]
    assert all(t.adapter == "CONTENT" and t.depends_on is None for t in result.decision.tasks)


def test_complete_scope_with_zero_zero_uses_stronger_label_without_clarifying():
    engine = DecisionEngine(StubPredictor((0.63, 0.64)), threshold=0.65)
    decision = engine.decide("Thông tin FPT năm 2025?")
    assert decision.route == "VECTOR"
    assert decision.decision == "SEARCH"


@pytest.mark.parametrize("question,company,period", [
    ("Tổng tài sản HPG năm 2025?", "HPG", "2025"),
    ("Doanh thu MWG quý 2 năm 2025?", "MWG", "2025-Q2"),
    ("Lợi nhuận sau thuế VNM Q3/2024?", "VNM", "2024-Q3"),
])
def test_complete_questions_support_non_fixture_tickers_and_common_periods(
    question, company, period
):
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide(question)
    assert decision.decision == "SEARCH"
    assert decision.scope.companies == [company]
    assert decision.scope.periods == [period]


@pytest.mark.parametrize("question,period", [
    ("Giá cổ phiếu hôm nay của FPT bao nhiêu?", "CURRENT"),
    ("Thị giá FPT hiện tại là bao nhiêu?", "CURRENT"),
    ("Giá cổ phiếu FPT mới nhất là bao nhiêu?", "LATEST_PUBLISHED_PERIOD"),
])
def test_market_time_references_do_not_request_reporting_period(question, period):
    decision = DecisionEngine(StubPredictor((0.9, 0.1))).decide(question)
    assert decision.decision == "SEARCH"
    assert decision.route == "VECTOR"
    assert decision.scope.companies == ["FPT"]
    assert decision.scope.periods == [period]
    assert decision.scope.metric_code == "STOCK_PRICE"


@pytest.mark.parametrize("question,company,period,metric", [
    ("gia cp fpt hn bn", "FPT", "CURRENT", "STOCK_PRICE"),
    ("giá ck hpg hnay bao nhiêu", "HPG", "CURRENT", "STOCK_PRICE"),
    ("thi gia vinamilk htai", "VNM", "CURRENT", "STOCK_PRICE"),
    ("lnst bidv q2/25 bao nhieu", "BID", "2025-Q2", "PROFIT_AFTER_TAX"),
    ("tong ts vietcombank q3 2024", "VCB", "2024-Q3", "TOTAL_ASSETS"),
    ("vcsh hoa phat nam 2025", "HPG", "2025", "TOTAL_EQUITY"),
])
def test_unaccented_aliases_and_chat_abbreviations(
    question, company, period, metric
):
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide(question)
    assert decision.decision == "SEARCH"
    assert decision.scope.companies == [company]
    assert decision.scope.periods == [period]
    assert decision.scope.metric_code == metric


@pytest.mark.parametrize("question,route", [
    ("Tin tức FPT mới nhất", "VECTOR"),
    ("Báo cáo tài chính FPT năm 2025", "VECTOR"),
    ("Doanh thu FPT năm 2025", "VECTOR"),
    ("Ai là chủ tịch FPT năm 2025?", "GRAPH"),
    ("FPT sở hữu công ty nào năm 2025?", "GRAPH"),
    ("Doanh thu công ty con của FPT năm 2025?", "BOTH"),
])
def test_business_intent_guardrails_override_wrong_classifier_bias(question, route):
    wrong_scores = (0.95, 0.05) if route == "VECTOR" else (0.05, 0.95)
    decision = DecisionEngine(StubPredictor(wrong_scores)).decide(question)
    assert decision.route == route


@pytest.mark.parametrize("question", [
    "Vì sao hôm nay giá cổ phiếu FPT giảm?",
    "nguyen nhan gia cp fpt hn giam la gi",
    "Phân tích tác động khiến thị giá FPT hiện tại biến động",
])
def test_causal_market_questions_use_content_without_graph(question):
    decision = DecisionEngine(StubPredictor((0.05, 0.95))).decide(question)
    assert decision.route == "VECTOR"
    assert [task.adapter for task in decision.tasks] == ["CONTENT"]
    assert decision.tasks[0].params["question"] == question


def test_person_plus_document_question_uses_both():
    question = (
        "Ai đang là chủ tịch của FPT vậy, trong năm 2025 ông ấy có chia sẻ gì "
        "về kế hoạch làm AI của công ty không?"
    )
    decision = DecisionEngine(StubPredictor((0.95, 0.05))).decide(question)
    assert decision.route == "BOTH"


def test_short_market_chat_sets_stock_price_metric():
    decision = DecisionEngine(StubPredictor((0.95, 0.05))).decide("giá msn hn là bn")
    assert decision.route == "VECTOR"
    assert decision.scope.companies == ["MSN"]
    assert decision.scope.periods == ["CURRENT"]
    assert decision.scope.metric_code == "STOCK_PRICE"


@pytest.mark.parametrize('question', [
    'Hom nay thi truong co bien dong gi?',
    'TTCK hom nay co gi moi?',
    'Chung khoan hom nay co gi hot?',
    'Thi truong hom nay co do lua hay rung lac khong?',
    'tt hn co bien gi?',
    'VNI nay co drama gi?',
])
def test_daily_market_digest_routes_to_content_without_company(question):
    decision = DecisionEngine(StubPredictor((0.05, 0.95))).decide(question)
    assert decision.route == "VECTOR"
    assert decision.scope.topic == "MARKET_DAILY_DIGEST"
    assert decision.scope.companies == []
    assert decision.tasks[0].operation == "find_daily_market_digest"


@pytest.mark.parametrize("question,period", [
    ("giá FPT tháng này", "CURRENT_MONTH"),
    ("gia fpt thang truoc", "PREVIOUS_MONTH"),
    ("giá FPT tuần này", "CURRENT_WEEK"),
    ("gia fpt tuan truoc", "PREVIOUS_WEEK"),
])
def test_router_accepts_relative_market_ranges(question, period):
    decision = DecisionEngine(StubPredictor((0.9, 0.1))).decide(question)
    assert decision.route == "VECTOR"
    assert decision.scope.periods == [period]
    assert decision.scope.metric_code == "STOCK_PRICE"


def test_comparison_accepts_two_companies_and_defaults_to_overall_when_metric_missing():
    engine = DecisionEngine(StubPredictor((0.1, 0.9)))
    resolved = engine.decide("So sánh doanh thu FPT và CMG năm 2025")
    assert resolved.route == "VECTOR"
    assert resolved.scope.companies == ["FPT", "CMG"]
    unclear = engine.decide("So sánh FPT và CMG năm 2025")
    assert unclear.route == "BOTH"
    assert unclear.scope.topic == "OVERALL_COMPARISON"
    assert unclear.missing_fields == []


@pytest.mark.parametrize("question", [
    "Cong ty FPT hoat dong trong linh vuc gi?",
    "FPT thuoc nganh nao?",
])
def test_company_profile_does_not_require_a_reporting_period(question):
    decision = DecisionEngine(StubPredictor((0.9, 0.1))).decide(question)
    assert decision.decision == "SEARCH"
    assert decision.route == "GRAPH"
    assert decision.scope.companies == ["FPT"]
    assert decision.scope.periods == []
    assert decision.scope.topic == "COMPANY_PROFILE"
    assert decision.tasks[0].operation == "find_relationships"


def test_missing_period_defaults_to_latest_available_period():
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide("Tong tai san FPT la bao nhieu?")
    assert decision.decision == "SEARCH"
    assert decision.scope.periods == ["LATEST_AVAILABLE_PERIOD"]


def test_leadership_without_period_routes_graph_at_latest_period():
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide("Ai la chu tich FPT?")
    assert decision.route == "GRAPH"
    assert decision.scope.topic == "RELATIONSHIP_LOOKUP"
    assert decision.scope.periods == ["LATEST_AVAILABLE_PERIOD"]


def test_named_person_event_impact_routes_both_without_fake_ticker():
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide(
        "Pham Hoang Nam bi bat co anh huong den co phieu khong?"
    )
    assert decision.route == "BOTH"
    assert decision.scope.topic == "EVENT_IMPACT"
    assert decision.scope.companies == []
    assert decision.scope.periods == ["LATEST_AVAILABLE_PERIOD"]


@pytest.mark.parametrize("question,route", [
    ("Ai là cổ đông lớn của FPT năm 2025?", "GRAPH"),
    ("Danh sách cổ đông lớn FPT năm 2025", "GRAPH"),
    ("Tình hình FPT dạo này có khởi sắc không?", "VECTOR"),
    ("FPT gần đây có triển vọng thế nào?", "VECTOR"),
])
def test_ownership_and_recent_trends_use_their_respective_sources(question, route):
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide(question)
    assert decision.route == route


@pytest.mark.parametrize("scores,route,task_ids", [
    ((0.1, 0.9), "VECTOR", ["v1"]),
    ((0.9, 0.1), "GRAPH", ["g1"]),
    ((0.9, 0.9), "BOTH", ["g1", "v1"]),
])
def test_locked_threshold_selects_route_and_plan(scores, route, task_ids):
    decision = DecisionEngine(StubPredictor(scores)).decide("Thông tin FPT năm 2025?")
    assert decision.route == route
    assert [task.id for task in decision.tasks] == task_ids


def test_h01_inherits_only_explicit_same_session_reference():
    context = SessionScope(companies=("FPT",), periods=("2025",), metric_code="TOTAL_ASSETS")
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide("Còn VCB?", context=context)
    assert decision.scope.companies == ["VCB"]
    assert decision.scope.periods == ["2025"]
    assert decision.scope.metric_code == "TOTAL_ASSETS"


@pytest.mark.parametrize("case_id,status", [
    ("V04", "NO_DATA"),
    ("V05", "INSUFFICIENT_EVIDENCE"),
    ("G02", "NO_DATA"),
    ("G04", "INSUFFICIENT_EVIDENCE"),
    ("G05", "SYSTEM_UNAVAILABLE"),
    ("G06", "INSUFFICIENT_EVIDENCE"),
])
def test_vector_and_graph_mock_failures_remain_distinct(case_id, status):
    scores = (0.1, 0.9) if case_id.startswith("V") else (0.9, 0.1)
    question = "Tổng tài sản FPT năm 2025?" if case_id.startswith("V") else "Công ty con FPT năm 2025?"
    result = DecisionEngine(StubPredictor(scores)).run(question, fixture_case=case_id)
    assert result.status == status
    assert result.adapter_results[0].provenance == "MOCK/FIXTURE"


@pytest.mark.parametrize("case_id,status,expected_calls", [
    ("B01", "OK", (1, 1)),
    ("B02", "NO_DATA", (1, 0)),
    ("B03", "INSUFFICIENT_EVIDENCE", (1, 1)),
    ("B04", "INSUFFICIENT_EVIDENCE", (1, 1)),
    ("B05", "SYSTEM_UNAVAILABLE", (1, 1)),
])
def test_both_workflow_order_coverage_and_failures(case_id, status, expected_calls):
    engine = DecisionEngine(StubPredictor((0.9, 0.9)))
    result = engine.run("Doanh thu công ty con FPT năm 2025?", fixture_case=case_id)
    assert result.status == status
    assert (len(engine.graph_adapter.calls), len(engine.content_adapter.calls)) == expected_calls
    if expected_calls[1]:
        assert engine.content_adapter.calls[0]["dependency_task_id"] == "g1"


def test_shadow_records_prediction_without_changing_live_or_calling_adapters():
    engine = DecisionEngine(StubPredictor((0.9, 0.9)))
    record = engine.shadow(
        "Thông tin FPT năm 2025?",
        request_id="request-shadow-001",
        live_decision="SEARCH",
        live_route="VECTOR",
    )
    assert record.execution_mode == "SHADOW"
    assert record.live_decision == "SEARCH" and record.live_route == "VECTOR"
    assert record.predicted_route == "BOTH"
    assert record.request_id == "request-shadow-001"
    assert record.model_version == "fixture-model"
    assert record.adapter_calls == 0
    assert not engine.graph_adapter.calls and not engine.content_adapter.calls


# Regression checks for the eight router scope/plan review findings.

class Predictor:
    model_version = "scope-review-fixture"

    def predict(self, question):
        raise AssertionError("These explicit intents must not need the classifier")


def engine(**kwargs):
    return DecisionEngine(Predictor(), resolver=ScopeResolver(reference_date=date(2026, 11, 5)), **kwargs)


def test_numeric_comparison_does_not_wait_for_graph():
    e = engine()
    result = e.run("So sánh doanh thu FPT và VCB năm 2025")
    assert result.decision.route == "VECTOR"
    assert not e.graph_adapter.calls
    assert [c["params"]["companies"] for c in e.content_adapter.calls] == [["FPT"], ["VCB"]]


@pytest.mark.parametrize("question,periods", [
    ("Doanh thu FPT quý 1 và quý 2 năm 2025", ["2025-Q1", "2025-Q2"]),
    ("Doanh thu FPT quý 4 năm 2024 và quý 1 năm 2025", ["2024-Q4", "2025-Q1"]),
    ("Doanh thu FPT năm 2025 quý 1 và quý 2", ["2025-Q1", "2025-Q2"]),
])
def test_every_quarter_is_preserved_in_scope_and_execution(question, periods):
    e = engine()
    result = e.run(question)
    assert result.decision.scope.periods == periods
    assert [c["params"]["periods"] for c in e.content_adapter.calls] == [[p] for p in periods]


@pytest.mark.parametrize("question,entity,basis", [
    ("Doanh thu hợp nhất FPT năm 2025", "CONSOLIDATED", "FULL_YEAR"),
    ("Doanh thu riêng lẻ FPT riêng quý 2 năm 2025", "PARENT", "STANDALONE_QUARTER"),
    ("Doanh thu hợp nhất FPT lũy kế quý 2 năm 2025", "CONSOLIDATED", "YTD"),
    ("Tổng tài sản riêng lẻ VCB năm 2025", "PARENT", "POINT_IN_TIME"),
])
def test_reporting_scope_reaches_task_params(question, entity, basis):
    result = engine().decide(question)
    assert result.scope.reporting_entity == entity
    assert result.scope.measure_basis == basis
    assert result.tasks[0].params["reporting_entity"] == entity
    assert result.tasks[0].params["measure_basis"] == basis


def test_quarter_basis_is_not_guessed_from_reporting_entity():
    result = engine().decide("Doanh thu hợp nhất FPT quý 2 năm 2025")
    assert result.scope.measure_basis is None


class LiveRecorder:
    def __init__(self, adapter, data=()):
        self.adapter = adapter
        self.data = data
        self.calls = []

    def execute(self, task, *, dependency=None):
        self.calls.append((task, dependency))
        return AdapterResult(task.id, self.adapter, "OK", "RECORDED", data=self.data,
                             provenance="LIVE/GRAPH" if self.adapter == "GRAPH" else "LIVE/VECTOR")


def test_previous_year_uses_fixed_vietnam_calendar():
    assert engine().decide("Doanh thu FPT năm ngoái").scope.periods == ["2025"]
    assert engine().decide("Doanh thu FPT quý 1 năm ngoái").scope.periods == ["2025-Q1"]


def test_previous_quarter_crosses_calendar_year():
    e = DecisionEngine(Predictor(), resolver=ScopeResolver(reference_date=date(2026, 1, 2)))
    assert e.decide("Doanh thu FPT quý trước").scope.periods == ["2025-Q4"]


def test_coverage_resolver_cannot_pass_symbolic_period_to_live():
    recorder = LiveRecorder("CONTENT")
    e = engine(content_adapter=recorder, period_resolver=lambda task: ["LATEST_AVAILABLE_PERIOD"])
    assert e.run("Doanh thu FPT kỳ mới nhất").reason_code == "PERIOD_RESOLUTION_REQUIRED"
    assert recorder.calls == []


@pytest.mark.parametrize("question,adapter", [
    ("Doanh thu FPT kỳ mới nhất", "CONTENT"),
    ("Chủ tịch VCB là ai", "GRAPH"),
])
def test_live_latest_requires_coverage_before_any_adapter_call(question, adapter):
    recorder = LiveRecorder(adapter)
    e = engine(**{"content_adapter" if adapter == "CONTENT" else "graph_adapter": recorder})
    assert e.run(question).reason_code == "PERIOD_RESOLUTION_REQUIRED"
    assert recorder.calls == []
    e.period_resolver = lambda task: ["2025"]
    assert e.run(question).status == "OK"
    assert recorder.calls[0][0].params["periods"] == ["2025"]


def test_followup_roundtrips_http_context_and_keeps_topic_operation_filters(monkeypatch):
    monkeypatch.setattr(api, "get_router_engine", engine)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(hybrid_router_mode="mock"))
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        first = client.post("/api/hybrid-router/test", json={"question": "Nhân sự FPT năm 2025"}).json()
        context = {k: v for k, v in first["scope"].items() if k in api.RouterContextPayload.model_fields}
        for endpoint in ("test", "run"):
            response = client.post(f"/api/hybrid-router/{endpoint}", json={
                "question": "Có thể liệt kê ra không?", "context": context})
            assert response.status_code == 200
            result = response.json()
            assert result["route"] == "GRAPH"
            for key in ("companies", "periods", "topic", "operation"):
                assert result["scope"][key] == first["scope"][key]
        assert client.post("/api/hybrid-router/test", json={
            "question": "Có thể liệt kê ra không?"}).json()["route"] == "CLARIFY"
        assert client.post("/api/hybrid-router/test", json={
            "question": "DCA là gì", "context": context}).json()["scope"]["companies"] == []


@pytest.mark.parametrize("question,event,relation", [
    ("FPT bổ nhiệm ai năm 2025?", "APPOINTED", "APPOINTS"),
    ("FPT miễn nhiệm ai năm 2025?", "DISMISSED", "DISMISSES"),
    ("Ai xin từ nhiệm ở FPT năm 2025?", "RESIGNATION_REQUESTED", "REQUESTS_RESIGNATION"),
    ("Ai từ nhiệm ở FPT năm 2025?", "RESIGNED", "RESIGNS"),
])
def test_personnel_event_stage_is_explicit(question, event, relation):
    result = engine().decide(question)
    assert result.route == "GRAPH"
    assert result.scope.event_type == event
    assert result.tasks[0].params["relation_types"] == [relation]


def test_person_mention_is_not_a_guessed_company():
    result = engine().decide("Nguyễn Mạnh Hải là ai?")
    assert result.route == "GRAPH"
    assert result.scope.companies == []
    assert result.scope.person_name == "nguyen manh hai"
    assert result.scope.entity_mentions == ["nguyen manh hai"]


def test_role_filter_is_specific_and_deputy_is_not_chair():
    for question, position in [("Chủ tịch VCB là ai?", "BOARD_CHAIR"),
                               ("Phó chủ tịch VCB là ai?", "DEPUTY_BOARD_CHAIR")]:
        result = engine().decide(question)
        assert result.route == "GRAPH"
        assert result.tasks[0].params["position_code"] == position
        assert result.tasks[0].params["relation_types"] == ["HOLDS_ROLE"]


def test_graph_paths_without_ticker_mapping_never_become_vector_company_ids():
    graph = LiveRecorder("GRAPH", ({"path": ["PERSON-1", "CMP-1"]},))
    content = LiveRecorder("CONTENT")
    e = engine(graph_adapter=graph, content_adapter=content)
    result = e.run("Doanh thu công ty con FPT năm 2025")
    assert result.reason_code == "GRAPH_COMPANY_MAPPING_REQUIRED"
    assert content.calls == []
    graph.data = ({"resolved_companies": ["CMG", "ELC"]},)
    result = e.run("Doanh thu công ty con FPT năm 2025")
    assert result.status == "OK"
    assert [call[0].params["resolved_companies"] for call in content.calls] == [["CMG"], ["ELC"]]
    assert [call[1].data for call in content.calls] == [({"company_id": "CMG"},), ({"company_id": "ELC"},)]


def test_person_content_question_retains_explicit_company_instead_of_path_ids():
    graph = LiveRecorder("GRAPH", ({"path": ["PERSON-1", "CMP-1"]},))
    content = LiveRecorder("CONTENT")
    e = engine(graph_adapter=graph, content_adapter=content)
    result = e.run("Chủ tịch FPT chia sẻ gì về chiến lược năm 2025?")
    assert result.status == "OK"
    assert content.calls[0][0].params["companies"] == ["FPT"]


@pytest.mark.parametrize("question", [
    "Doanh thu FPT quý 5", "FPT quý 0", "FPT Q9",
    "Doanh thu FPT quý 1 năm 2025 và quý 5 năm 2025",
    "Doanh thu FPT quý 1 và quý 0 năm 2025",
])
def test_every_explicit_invalid_quarter_stops_before_retrieval(question):
    e = engine()
    result = e.run(question)
    assert result.decision.route == "CLARIFY"
    assert result.reason_code == "INVALID_QUARTER"
    assert not e.graph_adapter.calls and not e.content_adapter.calls


@pytest.mark.parametrize("question,expected", [
    ("FPT năm 2024 quý 1 và năm 2025 quý 2", ["2024-Q1", "2025-Q2"]),
    ("FPT quý 4 năm 2024 và quý 1 năm 2025", ["2024-Q4", "2025-Q1"]),
    ("FPT năm 2025 quý 1 và quý 2", ["2025-Q1", "2025-Q2"]),
    ("FPT Q1/24 và Q2/25", ["2024-Q1", "2025-Q2"]),
])
def test_quarter_year_attachment_in_both_orders(question, expected):
    assert ScopeResolver().resolve(question).scope.periods == expected


@pytest.mark.parametrize("question,expected", [
    ("So sánh doanh thu FPT năm 2024 và VCB năm 2025", [("FPT", "2024"), ("VCB", "2025")]),
    ("So sánh doanh thu FPT quý 1 năm 2024 và VCB quý 2 năm 2025", [("FPT", "2024-Q1"), ("VCB", "2025-Q2")]),
    ("Doanh thu FPT quý 1 và quý 2 năm 2025 và VCB quý 3 năm 2024", [("FPT", "2025-Q1"), ("FPT", "2025-Q2"), ("VCB", "2024-Q3")]),
    ("So sánh doanh thu FPT và VCB năm 2025", [("FPT", "2025"), ("VCB", "2025")]),
])
def test_company_period_bindings_survive_the_plan_and_adapter_calls(question, expected):
    e = engine()
    result = e.run(question)
    assert result.decision.route == "VECTOR"
    actual = [(call["params"]["companies"][0], call["params"]["periods"][0]) for call in e.content_adapter.calls]
    assert actual == expected


def test_missing_local_company_period_does_not_create_extra_pairs():
    decision = engine().decide("So sánh doanh thu FPT năm 2024 và VCB")
    assert decision.route == "CLARIFY"
    assert decision.tasks == []


def test_parent_report_and_parent_company_lookup_are_different_intents():
    report = engine().decide("Doanh thu công ty mẹ FPT năm 2025")
    assert report.route == "VECTOR"
    assert report.tasks[0].params["reporting_entity"] == "PARENT"
    relation = engine().decide("Công ty mẹ của FPT là ai?")
    assert relation.route == "GRAPH"
    assert relation.scope.reporting_entity is None
    report = engine().decide("BCTC công ty mẹ FPT năm 2025")
    assert report.route == "VECTOR"
    assert report.scope.reporting_entity == "PARENT"


def test_comparing_reporting_entities_keeps_two_separate_tasks():
    e = engine()
    result = e.run("So sánh doanh thu hợp nhất và riêng lẻ FPT năm 2025")
    assert result.decision.scope.reporting_entity is None
    assert result.decision.scope.reporting_entities == ["CONSOLIDATED", "PARENT"]
    assert [c["params"]["reporting_entity"] for c in e.content_adapter.calls] == ["CONSOLIDATED", "PARENT"]


def test_personnel_followup_changes_company_without_losing_filters():
    e = engine()
    first = e.decide("Chủ tịch FPT năm 2025 là ai?")
    from src.retrieval_orchestration.hybrid_router.decision_engine import SessionScope
    values = {k: v for k, v in first.scope.model_dump().items() if k in SessionScope.__dataclass_fields__}
    next_turn = e.decide("Còn VCB?", context=SessionScope(**values))
    assert next_turn.route == "GRAPH"
    assert next_turn.scope.companies == ["VCB"]
    assert next_turn.scope.periods == ["2025"]
    assert next_turn.scope.position_code == "BOARD_CHAIR"


def test_latest_coverage_updates_scope_and_exact_adapter_periods():
    content = LiveRecorder("CONTENT")
    e = engine(content_adapter=content, period_resolver=lambda task: ["2025-Q3"])
    result = e.run("Doanh thu FPT kỳ mới nhất")
    assert result.status == "OK"
    assert result.decision.scope.periods == ["2025-Q3"]
    assert content.calls[0][0].params["periods"] == ["2025-Q3"]


def test_api_coverage_is_connected_and_preserves_http_context(monkeypatch):
    async def coverage(task):
        assert task.params["companies"] == ["FPT"]
        return ["2025-Q2"]
    monkeypatch.setattr(api, "_coverage_periods", coverage)
    monkeypatch.setattr(api, "get_router_engine", engine)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        hybrid_router_mode="mock", hybrid_router_index_id="index-fixture", research_corpus_version_id="corpus-fixture"))
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        data = client.post("/api/hybrid-router/test", json={"question": "Doanh thu FPT kỳ mới nhất"}).json()
        assert data["scope"]["periods"] == ["2025-Q2"]
        assert data["period_resolution_required"] is False


def test_live_adapter_never_silently_drops_explicit_reporting_scope():
    from src.retrieval_orchestration.hybrid_router.adapters import LiveContentAdapter
    adapter = LiveContentAdapter(None, None)
    task = engine().decide("Doanh thu riêng lẻ FPT năm 2025").tasks[0]
    result = adapter.execute(task)
    assert result.reason_code == "CONTENT_REPORTING_SCOPE_UNSUPPORTED"
    assert adapter.calls == []


def test_company_period_reporting_entities_remain_bound():
    decision = engine().decide("So sánh doanh thu FPT hợp nhất năm 2024 và VCB riêng lẻ năm 2025")
    assert [(t.params["companies"], t.params["periods"], t.params["reporting_entity"]) for t in decision.tasks] == [
        (["FPT"], ["2024"], "CONSOLIDATED"), (["VCB"], ["2025"], "PARENT")]


def test_coverage_query_is_frozen_corpus_scoped_and_uses_actual_period_rows(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from src.core import db
    from src.retrieval_orchestration.hybrid_router.schemas import RouterTask
    class Connection:
        @asynccontextmanager
        async def transaction(self, **options):
            assert options == {"readonly": True, "isolation": "repeatable_read"}
            yield
        async def fetch(self, sql, *args):
            assert "cd.document_hash=d.sha256" in sql and "cv.status='FROZEN'" in sql
            assert "t.superseded_at IS NULL" in sql and "i.status='ACTIVE'" in sql
            assert args == (None, "corpus-fixture", ["FPT"], ["FINANCIAL_STATEMENT"])
            return [{"period": p} for p in ["2024-YEAR", "2025-Q1", "2025-Q2", "2027-Q9", None]]
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()
    monkeypatch.setattr(db, "get_pool", lambda: Pool())
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        hybrid_router_index_id="", research_corpus_version_id="corpus-fixture"))
    task = RouterTask(id="v1", adapter="CONTENT", operation="find_metric", params={
        "companies": ["FPT"], "periods": ["LATEST_AVAILABLE_PERIOD"]})
    assert asyncio.run(api._coverage_periods(task)) == ["2025-Q2"]
    task.params["periods"] = ["LATEST_YEAR-Q1"]
    assert asyncio.run(api._coverage_periods(task)) == ["2025-Q1"]


def test_scope_aware_content_callback_receives_reporting_and_basis():
    import asyncio
    from src.retrieval_orchestration.hybrid_router.adapters import LiveContentAdapter
    calls = []
    async def scoped(question, company, period, top_k, **filters):
        calls.append((company, period, filters))
        return {"results": []}
    async def check():
        adapter = LiveContentAdapter(None, asyncio.get_running_loop(), scope_search_fn=scoped)
        task = engine().decide("Doanh thu riêng lẻ FPT năm 2025").tasks[0]
        result = await asyncio.to_thread(adapter.execute, task)
        assert result.status == "NO_DATA"
    asyncio.run(check())
    assert calls == [("FPT", "2025", {"reporting_entity": "PARENT", "measure_basis": "FULL_YEAR"})]
