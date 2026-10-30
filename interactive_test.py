"""Interactive client for the backend's warm, shared hybrid router."""

from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROUTER_URL = "http://127.0.0.1:8000/api/hybrid-router/test"


def _ask_backend(question: str, context: dict | None) -> dict:
    body = json.dumps({"question": question, "context": context}).encode("utf-8")
    request = Request(
        ROUTER_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def _next_context(result: dict) -> dict | None:
    if result.get("decision") != "SEARCH":
        return None
    scope = result.get("scope") or {}
    return {
        "companies": scope.get("companies") or [],
        "periods": scope.get("periods") or [],
        "metric_code": scope.get("metric_code"),
        "detected_industry": scope.get("detected_industry"),
        "entity_mentions": scope.get("entity_mentions") or [],
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    context: dict | None = None

    print("FinMind Hybrid Router - End-to-End Interactive Test")
    print("BGE-M3 và classifier được dùng chung trong backend.")
    print("Lệnh: /reset để xóa ngữ cảnh, /exit để thoát.\n")

    while True:
        try:
            question = input("Bạn > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nĐã thoát.")
            break
        if not question:
            continue
        command = question.casefold()
        if command in {"/exit", "/quit", "exit", "quit"}:
            print("Đã thoát.")
            break
        if command in {"/reset", "/new", "/moi"}:
            context = None
            print("Đã xóa ngữ cảnh phiên.\n")
            continue
        try:
            result = _ask_backend(question, context)
            print(f"ROUTE: {result['route']}")
            if result["route"] == "CLARIFY":
                print(f"CÂU HỎI LÀM RÕ: {result['clarification_question']}")
            updated = _next_context(result)
            if updated is not None:
                context = updated
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"LỖI KẾT NỐI BACKEND: {exc}")
        print()


if __name__ == "__main__":
    main()
