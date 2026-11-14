"""Read-only HTTP routing acceptance check against the running backend.

Run with backend on PYTHONPATH. This tests routes, scopes and HTTP conversation
validation; it does not execute live retrieval or generate financial answers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def ask(url, question, context=None):
    request = Request(url, data=json.dumps({
        "question": question, "context": context,
    }).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=300) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/hybrid-router/test")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    args = parser.parse_args()
    fixtures = args.fixtures or Path(__file__).resolve().parents[1] / "tests/fixtures/router_acceptance_v2.json"
    cases = json.loads(fixtures.read_text("utf-8"))
    results = []
    for case in cases:
        result = ask(args.url, case["question"])
        matches = result.get("route") == case["route"] and result.get("scope", {}).get("companies") == case["companies"]
        results.append({**case, "actual": result, "passed": matches})
    context = None
    conversation = []
    # Switch repeatedly between entity, market, knowledge and portfolio scopes.
    for index in [38, 5, 10, 9, 39, 0, 2, 3, 4, 8]:
        case = cases[index]
        result = ask(args.url, case["question"], context)
        matches = result.get("route") == case["route"] and result.get("scope", {}).get("companies") == case["companies"]
        conversation.append({**case, "actual": result, "passed": matches})
        if result.get("decision") == "SEARCH":
            scope = result["scope"]
            context = {key: scope[key] for key in (
                "companies", "periods", "metric_code", "detected_industry", "entity_mentions"
            )}
    passed = sum(row["passed"] for row in results)
    sequential_passed = sum(row["passed"] for row in conversation)
    report = {"endpoint": args.url, "passed": passed, "total": len(results),
              "conversation_passed": sequential_passed, "conversation_total": len(conversation),
              "cases": results, "conversation": conversation}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(f"Independent questions: {passed}/{len(results)}; conversation: {sequential_passed}/{len(conversation)}")
    if passed != len(results) or sequential_passed != len(conversation):
        for row in results + conversation:
            if not row["passed"]:
                print(json.dumps(row, ensure_ascii=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
