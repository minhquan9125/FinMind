"""Step 11 acceptance tests for all 30 Section 6 router fixtures."""

from dataclasses import dataclass
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
            reporter.write_sep("=", "HYBRID ROUTER - BÁO CÁO 30 CÂU MỤC 6")
            reporter.write_line(f"Tổng số câu kiểm thử : {total}")
            reporter.write_line(f"Số câu đúng          : {passed}")
            reporter.write_line(f"Số câu sai           : {failed}")
            reporter.write_line(f"Tỷ lệ đúng           : {ratio:.2f}%")


@pytest.mark.parametrize("question,field,reason", [
    ("Tổng tài sản năm 2025?", "companies", "MISSING_SCOPE"),
    ("Lợi nhuận FPT?", "metric_code", "MISSING_SCOPE"),
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


def test_c06_mixed_intents_asks_user_to_split_request():
    engine = DecisionEngine(StubPredictor((0.1, 0.9)))
    result = engine.run("Cho tôi doanh thu FPT năm 2025 và giá VCB mới nhất.")
    assert result.decision.reason_code == "UNSUPPORTED_MIXED_INTENTS"
    assert result.decision.tasks == []


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
def test_causal_market_questions_use_both_with_analysis_tasks(question):
    decision = DecisionEngine(StubPredictor((0.05, 0.95))).decide(question)
    assert decision.route == "BOTH"
    assert [task.operation for task in decision.tasks] == [
        "expand_market_context", "analyze_market_drivers"
    ]


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
    assert resolved.route == "BOTH"
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
    assert decision.route == "VECTOR"
    assert decision.scope.companies == ["FPT"]
    assert decision.scope.periods == []
    assert decision.scope.topic == "COMPANY_PROFILE"
    assert decision.tasks[0].operation == "find_company_profile"


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


@pytest.mark.parametrize("question", [
    "Ai là cổ đông lớn của FPT năm 2025?",
    "Danh sách cổ đông lớn FPT năm 2025",
    "Tình hình FPT dạo này có khởi sắc không?",
    "FPT gần đây có triển vọng thế nào?",
])
def test_ownership_evidence_and_recent_trend_questions_use_both(question):
    decision = DecisionEngine(StubPredictor((0.1, 0.9))).decide(question)
    assert decision.route == "BOTH"


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
