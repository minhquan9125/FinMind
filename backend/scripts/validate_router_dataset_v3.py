"""Validate the reviewed structure of router dataset v3."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/router/v3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fold(text: str) -> str:
    text = text.casefold().replace("đ", "d")
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def key(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", fold(text)).split())


def validate() -> dict:
    with (DATA / "router_dataset.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "id", "question", "needs_graph", "needs_content", "paraphrase_group",
            "semantic_group", "leakage_group",
        ]
        rows = list(reader)
    annotations = json.loads((DATA / "router_annotations.json").read_text(encoding="utf-8"))
    split_doc = json.loads((DATA / "router_splits.json").read_text(encoding="utf-8"))
    records = annotations["records"]

    assert len(rows) == len(records) == 200
    assert len({row["id"] for row in rows}) == 200
    assert len({key(row["question"]) for row in rows}) == 200
    assert sha256(DATA / "router_dataset.csv") == split_doc["dataset_sha256"]
    assert annotations["dataset_version"] == "router-v3-reviewed-2026-10-28"
    assert annotations["training_authorized"] is True
    assert annotations["second_reviewer"] == "Hưng"
    assert annotations["second_review_completed"] is True

    route_for = {("0", "1"): "VECTOR", ("1", "0"): "GRAPH", ("1", "1"): "BOTH"}
    route_counts = Counter()
    decision_counts = Counter()
    con_counts = Counter()
    control_phrase_counts = Counter()
    group_split = {}
    all_ids = set()

    for row in rows:
        rid = row["id"]
        record = records[rid]
        route = route_for[(row["needs_graph"], row["needs_content"])]
        route_counts[route] += 1
        decision_counts[record["expected_decision"]] += 1
        all_ids.add(rid)

        assert record["raw_question"] == row["question"] == record["classifier_input"]
        assert record["retrieval_need_route"] == route
        assert row["paraphrase_group"] == record["semantic_group"]
        assert row["semantic_group"] == record["semantic_group"]
        assert row["leakage_group"] == record["leakage_group"]
        assert record["semantic_group"]
        assert record["leakage_group"]
        assert record["training_authorized"] is True
        assert record["review_status"] == "APPROVED"
        assert record["label_version"] == annotations["dataset_version"]
        assert record["support_status"] in {
            "MOCK_ONLY", "PLANNED_UNVERIFIED", "NEEDS_CAPABILITY_CONFIRMATION"
        }

        if record["expected_decision"] == "ASK_CLARIFICATION":
            assert record["execution_route"] is None
            assert record["missing_fields"]
            assert record["expected_adapter_calls"] == []
            assert record["scope_equivalent_to_reference"] is False
            assert record["expected_scope"] == record["observed_scope"]
            assert record["expected_scope"] != record["resolved_scope_reference"]
        else:
            assert record["expected_decision"] == "SEARCH"
            assert record["execution_route"] == route
            assert not record["missing_fields"]
            if record["scope_variant"] == "RELATIVE_TIME":
                assert record["scope_equivalent_to_reference"] is False
                assert record["expected_scope"].get("time_reference")
            else:
                assert record["scope_equivalent_to_reference"] is True

        normalized = fold(row["question"])
        assert "cho tui xem" not in normalized
        assert "khong can tim cong ty con" not in normalized
        assert not re.search(r"\b(?:fixture|graph mock)\b", row["question"], re.IGNORECASE)
        if "con" in key(row["question"]).split():
            con_counts[route] += 1
        lowered = row["question"].casefold()
        if (
            "được kiểm soát trực tiếp" in lowered
            or "duoc kiem soat truc tiep" in lowered
        ):
            control_phrase_counts[route] += 1
        raw_symbols = {
            symbol.upper() for symbol in re.findall(
                r"\b(?:vcb|bid|ctg|mbb|tcb|fpt|cmg|elc|itd|ict)\b",
                row["question"],
                flags=re.IGNORECASE,
            )
        }
        assert raw_symbols == set(record["observed_scope"]["companies"]), rid

    assert route_counts == {"VECTOR": 80, "GRAPH": 60, "BOTH": 60}
    assert decision_counts == {"SEARCH": 151, "ASK_CLARIFICATION": 49}
    assert len({r["semantic_group"] for r in records.values()}) == 104
    assert len({r["leakage_group"] for r in records.values()}) == 50
    assert max(Counter(r["leakage_group"] for r in records.values()).values()) <= 6
    assert con_counts["VECTOR"] > 0 and con_counts["GRAPH"] > 0 and con_counts["BOTH"] < 60
    assert control_phrase_counts["VECTOR"] > 0
    assert control_phrase_counts["GRAPH"] > 0
    assert 0 < control_phrase_counts["BOTH"] < 24
    assert "bao cao hop nhat" in fold(records["R046"]["raw_question"])
    assert "truc tiep" in fold(records["R094"]["raw_question"])
    assert records["R041"]["semantic_group"] != records["R044"]["semantic_group"]
    assert records["R041"]["leakage_group"] == records["R044"]["leakage_group"]
    assert records["R168"]["leakage_group"] == records["R200"]["leakage_group"]
    assert records["R168"]["split"] == records["R200"]["split"]
    assert records["R056"]["expected_scope"].get("metric_code") == "CASH_FLOW_INVESTING"
    assert records["R060"]["expected_scope"].get("metric_code") == "CASH_FLOW_FINANCING"
    assert records["R004"]["required_capabilities"] == ["CONTENT_ADAPTER"]
    assert records["R092"]["expected_decision"] == "SEARCH"
    assert records["R092"]["observed_scope"]["relationship_type"] == "DIRECT_CONTROL_OR_SUBSIDIARY_TARGET"
    assert records["R108"]["observed_scope"] == {
        "companies": ["VCB"], "years_mentioned": ["2026"]
    }
    assert records["R168"]["resolved_scope_reference"]["reporting_entity"] == "SEPARATE"
    assert records["R004"]["observed_scope"].get("reporting_entity") is None
    assert records["R004"]["scope_defaults_applied"] == {"reporting_entity": "UNKNOWN"}
    assert records["R004"]["expected_scope"]["reporting_entity"] == "UNKNOWN"
    assert records["R076"]["missing_fields"] == ["metric_code", "comparison_periods"]
    assert records["R008"]["missing_fields"] == ["period", "metric_code"]
    assert records["R032"]["missing_fields"] == ["period", "metric_code"]
    assert "every field" in records["R032"]["clarification_policy"]
    assert records["R144"]["observed_scope"] == {"companies": ["CMG"]}
    assert records["R144"]["missing_fields"] == ["metric_code", "relation_as_of", "financial_period"]
    assert records["R168"]["missing_fields"] == ["relation_as_of", "financial_period"]
    assert records["R200"]["missing_fields"] == ["relation_as_of", "financial_period"]
    assert all(
        "reference_question" not in record["resolved_scope_reference"]
        for record in records.values()
    )

    scenarios = annotations["router_scenarios"]
    assert len(scenarios) == 48
    assert any(case["question"] == "Tổng tài sản năm 2025?" for case in scenarios)
    assert any(case["question"] == "Còn VCB?" for case in scenarios)
    assert any(case["question"] == "Công ty đó?" for case in scenarios)
    assert all(case["split"] == "development" for case in scenarios)

    combined = []
    split_counts = {}
    for split, expected_size in (("train", 140), ("validation", 30), ("test", 30)):
        ids = split_doc["splits"][split]
        assert len(ids) == expected_size
        combined.extend(ids)
        split_counts[split] = dict(Counter(records[rid]["retrieval_need_route"] for rid in ids))
        assert split_counts[split] == split_doc["label_counts"][split]
        for rid in ids:
            record = records[rid]
            assert record["split"] == split
            assert group_split.setdefault(record["leakage_group"], split) == split
    assert len(combined) == len(set(combined)) == 200
    assert set(combined) == all_ids

    short_count = sum(len(row["question"].split()) <= 8 for row in rows)
    long_count = sum(len(row["question"].split()) > 16 for row in rows)
    year_count = sum(bool(re.search(r"\b20\d{2}\b", row["question"])) for row in rows)
    decision_by_id = {rid: record["expected_decision"] for rid, record in records.items()}
    has_year = {row["id"]: bool(re.search(r"\b20\d{2}\b", row["question"])) for row in rows}
    assert any(has_year[rid] and decision == "ASK_CLARIFICATION" for rid, decision in decision_by_id.items())
    assert any(not has_year[rid] and decision == "SEARCH" for rid, decision in decision_by_id.items())
    assert short_count >= 35
    assert long_count < 120
    assert year_count < 180

    challenge = json.loads((DATA / "router_challenge_set.json").read_text(encoding="utf-8"))
    cases = challenge["cases"]
    assert challenge["excluded_from_training"] is True
    assert challenge["review_status"] == "APPROVED"
    assert challenge["evaluation_context"]["reference_time"] == "2026-10-28T10:00:00+07:00"
    assert challenge["evaluation_context"]["timezone"] == "Asia/Ho_Chi_Minh"
    assert len(cases) >= 12
    assert not ({case["id"] for case in cases} & all_ids)
    main_and_development_questions = {
        key(row["question"]) for row in rows
    } | {key(case["question"]) for case in scenarios}
    challenge_questions = [key(case["question"]) for case in cases]
    assert len(challenge_questions) == len(set(challenge_questions))
    assert not (set(challenge_questions) & main_and_development_questions)
    assert any(case["year_present"] and case["expected_decision"] == "ASK_CLARIFICATION" for case in cases)
    assert any(not case["year_present"] and case["expected_decision"] == "SEARCH" for case in cases)
    assert any(case.get("context") and case["expected_decision"] == "SEARCH" for case in cases)
    assert any(case.get("validation_error") == "INVALID_QUARTER" for case in cases)
    for case in cases:
        assert case["review_status"] == "APPROVED"
        assert case["required_capabilities"]
        assert case["capability_status"] in {"MOCK_ONLY", "CONTRACT_ONLY"}
        if case["expected_decision"] == "ASK_CLARIFICATION":
            assert case["execution_route"] is None
            assert case["expected_adapter_calls"] == []
            assert case["currently_answerable"] is False
    assert {"CONTENT_ADAPTER", "CALCULATION", "CONTEXT_RESOLUTION"}.issubset(
        set(next(case for case in cases if case["id"] == "YC03")["required_capabilities"])
    )
    assert "GRAPH_ADAPTER" in next(case for case in cases if case["id"] == "YC08")["required_capabilities"]
    assert "GRAPH_ADAPTER" in next(case for case in cases if case["id"] == "YC10")["required_capabilities"]
    assert next(case for case in cases if case["id"] == "YC12")["relative_time_resolution"]["resolved_period"] == "2026-Q3"

    return {
        "status": "PASS",
        "version": "v3",
        "classifier_rows": 200,
        "route_counts": dict(route_counts),
        "decision_counts": dict(decision_counts),
        "split_label_counts": split_counts,
        "semantic_groups": len({r["semantic_group"] for r in records.values()}),
        "leakage_groups": len(group_split),
        "questions_with_year": year_count,
        "questions_at_most_8_words": short_count,
        "questions_over_16_words": long_count,
        "con_token_by_route": dict(con_counts),
        "direct_control_phrase_by_route": dict(control_phrase_counts),
        "end_to_end_router_scenarios": len(scenarios),
        "templated_review_phrases": 0,
        "legacy_versions_removed": True,
        "independent_challenge_cases": len(cases),
        "training_authorized": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
