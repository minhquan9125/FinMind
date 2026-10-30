"""Run from backend: python -m src.retrieval_orchestration.hybrid_router.evaluate_baseline."""
import argparse
import json
from pathlib import Path

from .baseline_rule import classify_by_keywords
from .schemas import RouterOutput


def evaluate(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = [case["id"] for case in data["fixtures"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate fixture IDs")
    failures, samples = [], {}
    eligible_count = 0
    for case in data["fixtures"]:
        expected = case["expected"]
        if expected["decision"] in {"SEARCH", "ASK_CLARIFICATION"}:
            fields = RouterOutput.model_fields
            RouterOutput.model_validate({k:v for k,v in expected.items() if k in fields})
        elif expected["tasks"]:
            raise ValueError("A bypass/failure case contains retrieval tasks")
        evaluation = case["classifier_evaluation"]
        if not evaluation["eligible"]:
            continue
        eligible_count += 1
        text = evaluation["input"]
        labels = tuple(evaluation["labels"])
        if text in samples and samples[text][0] != labels:
            raise ValueError("Conflicting labels for the same resolved question")
        samples[text] = (labels, expected["route"])
        prediction = classify_by_keywords(text)
        if (prediction.needs_graph, prediction.needs_content) != labels:
            failures.append({"id":case["id"],"expected":expected["route"],"predicted":prediction.route})

    rows = [(labels, classify_by_keywords(text)) for text,(labels,_) in samples.items()]
    metrics = {}
    for index, label in enumerate(("needs_graph", "needs_content")):
        truth = [labels[index] for labels,_ in rows]
        predicted = [getattr(p,label) for _,p in rows]
        tp = sum(t == 1 and p == 1 for t,p in zip(truth,predicted))
        fp = sum(t == 0 and p == 1 for t,p in zip(truth,predicted))
        fn = sum(t == 1 and p == 0 for t,p in zip(truth,predicted))
        metrics[label] = {"support":sum(truth),"tp":tp,"fp":fp,"fn":fn,
                          "precision":tp/(tp+fp) if tp+fp else 0.0,
                          "recall":tp/(tp+fn) if tp+fn else 0.0,
                          "f1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0}
    exact = sum((p.needs_graph,p.needs_content) == labels for labels,p in rows)
    return {"evaluation_kind":"DEVELOPMENT_ONLY_NOT_HOLDOUT",
            "total_fixtures":len(ids),"contract_checks":"PASS",
            "eligible_fixture_count":eligible_count,"unique_resolved_inputs":len(rows),
            "unique_exact_match_count":exact,
            "unique_exact_match_ratio":exact/len(rows) if rows else None,
            "per_label_unique_input_metrics":metrics,"fixture_mismatches":failures,
            "limitations":"No adapter execution or upstream intent/context verification. Exact-string deduplication does not remove all paraphrase/template correlation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).with_name("router_fixtures.json"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.fixtures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
