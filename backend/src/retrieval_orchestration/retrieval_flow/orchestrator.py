"""Fixture-only retrieval orchestration; no network, database or answer generation."""
from __future__ import annotations

import asyncio
import copy
import math
import time

from .contracts import check_evidence, load_fixtures, validate_pack
from .intent import analyze


class FixtureRetriever:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def retrieve(self, scope: dict, query_id: str, index_version: str) -> dict:
        self.calls.append({"scope": copy.deepcopy(scope), "query_id": query_id, "index_version": index_version})
        fixtures = load_fixtures()
        if index_version != fixtures["index_version"]:
            raise ValueError("Unknown fixture index")
        # Exact scope match only. Never choose by similarity or alter financial scope.
        selected = fixtures["packs"]["empty"]
        for name in ("valid_metric", "valid_compare", "valid_annual"):
            pack = fixtures["packs"][name]
            if not check_evidence(pack, scope, fixtures["registry"]):
                selected = pack
                break
        result = copy.deepcopy(selected)
        result["query_id"] = query_id
        return result


class FixtureReferenceResolver:
    def __init__(self, store: dict | None = None) -> None:
        self.store = copy.deepcopy(store or {})
        self.calls: list[dict] = []

    async def resolve(self, reference: dict, session_id: str) -> dict | None:
        self.calls.append({"reference": copy.deepcopy(reference), "session_id": session_id})
        key = (session_id, reference.get("answer_id"), reference.get("evidence_id"))
        value = self.store.get(key)
        if not isinstance(value, dict) or any(value.get(k) != reference.get(k) for k in ("answer_id", "evidence_id")):
            return None
        return copy.deepcopy(value)


async def _bounded(awaitable, timeout_seconds: float):
    deadline = time.monotonic() + timeout_seconds
    value = await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    # An adapter that catches cancellation must not turn a late result into success.
    if time.monotonic() > deadline:
        raise TimeoutError()
    return value


async def orchestrate(question, session_id, *, context=None, analyzer=analyze,
                      retriever=None, reference_resolver=None, timeout_seconds=1.0) -> dict:
    result = {"request_id": None, "query_id": None, "execution_mode": "FIXTURE", "b1_decision": None,
              "status": "SYSTEM_UNAVAILABLE", "reason_code": "DEPENDENCY_UNAVAILABLE",
              "message": "Hệ thống tạm thời chưa khả dụng; vui lòng thử lại.", "scope": {},
              "clarification": None, "evidence_pack": None, "errors": []}

    def finish(status: str, code: str, message: str) -> dict:
        result.update(status=status, reason_code=code, message=message)
        return result

    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60:
        return finish("SYSTEM_UNAVAILABLE", "INVALID_TIMEOUT", "Cấu hình thời gian chờ không hợp lệ.")
    try:
        decision = analyzer(question, session_id, context)
        if (not isinstance(decision, dict) or decision.get("session_id") != session_id
                or not isinstance(decision.get("request_id"), str) or not decision["request_id"].strip()):
            return result
        result.update(request_id=decision["request_id"], b1_decision=decision.get("decision"),
                      scope=copy.deepcopy(decision.get("scope", {})),
                      clarification=decision.get("clarification_question"))
        branch = decision.get("decision")
        if branch in ("ASK_CLARIFICATION", "OUT_OF_SCOPE", "UNSUPPORTED", "SYSTEM_UNAVAILABLE"):
            return finish(branch, decision.get("reason_code", "DEPENDENCY_UNAVAILABLE"),
                          decision.get("clarification_question") or "Chưa thể xử lý yêu cầu trong phạm vi này.")
        if branch == "RESOLVE_REFERENCE":
            reference = decision.get("slots", {}).get("reference")
            if not isinstance(reference, dict) or any(not isinstance(reference.get(k), str) or not reference[k].strip()
                                                      for k in ("answer_id", "evidence_id")):
                return finish("OUT_OF_SCOPE", "NO_REFERENCED_EVIDENCE", "Chưa xác minh được tham chiếu.")
            resolver = reference_resolver if reference_resolver is not None else FixtureReferenceResolver()
            try:
                resolved = await _bounded(resolver.resolve(reference, session_id), timeout_seconds)
            except TimeoutError:
                return finish("SYSTEM_UNAVAILABLE", "REFERENCE_TIMEOUT", "Tra nguồn tạm thời không phản hồi; vui lòng thử lại.")
            if (not isinstance(resolved, dict)
                    or any(resolved.get(k) != reference[k] for k in ("answer_id", "evidence_id"))):
                return finish("OUT_OF_SCOPE", "NO_REFERENCED_EVIDENCE", "Chưa xác minh được tham chiếu.")
            result["scope"] = {"reference": copy.deepcopy(resolved)}
            return finish("REFERENCE_READY", "REFERENCE_AVAILABLE", "Đã xác minh tham chiếu giả lập trong phiên.")
        if branch != "SEARCH":
            return finish("SYSTEM_UNAVAILABLE", "INVALID_B1_DECISION", "Bước hiểu câu hỏi chưa trả quyết định hợp lệ.")
        fixtures = load_fixtures()
        index = fixtures["corpus_to_index"].get(decision.get("corpus_version_id"))
        if index != fixtures["index_version"]:
            return finish("SYSTEM_UNAVAILABLE", "VERSION_UNAVAILABLE", "Chưa xác nhận được phiên dữ liệu cho yêu cầu này.")
        result["query_id"] = "fixture-query:" + decision["request_id"]
        adapter = retriever if retriever is not None else FixtureRetriever()
        try:
            pack = await _bounded(adapter.retrieve(copy.deepcopy(result["scope"]), result["query_id"], index), timeout_seconds)
        except TimeoutError:
            return finish("SYSTEM_UNAVAILABLE", "RETRIEVAL_TIMEOUT", "Dịch vụ tìm kiếm tạm thời không phản hồi; vui lòng thử lại.")
        errors = validate_pack(pack)
        if not errors and pack["query_id"] != result["query_id"]:
            errors.append({"code": "QUERY_MISMATCH", "path": "query_id", "message": "Gói không thuộc truy vấn hiện tại."})
        if not errors and pack["data_version"]["id"] != index:
            errors.append({"code": "VERSION_MISMATCH", "path": "data_version.id", "message": "Gói không thuộc phiên index đã chọn."})
        if errors:
            result["errors"] = errors
            return finish("INVALID_EVIDENCE_PACK", "INVALID_EVIDENCE_PACK", "Gói bằng chứng không hợp lệ; chưa thể sử dụng.")
        if not pack["items"]:
            return finish("NO_DATA", "NO_DATA", "Chưa tìm thấy bằng chứng phù hợp trong phạm vi này.")
        errors = check_evidence(pack, result["scope"], fixtures["registry"])
        if errors:
            result["errors"] = errors
            return finish("INSUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE", "Chưa đủ bằng chứng phù hợp để trả lời.")
        result["evidence_pack"] = copy.deepcopy(pack)
        return finish("EVIDENCE_READY", "EVIDENCE_READY", "Bằng chứng giả lập đã sẵn sàng; chưa phải đáp án tài chính.")
    except asyncio.CancelledError:
        raise
    except Exception:
        # Provider/runtime details must not escape into the user-facing envelope.
        result["evidence_pack"] = None
        result["errors"] = []
        return finish("SYSTEM_UNAVAILABLE", "DEPENDENCY_UNAVAILABLE", "Dịch vụ tạm thời gặp lỗi; vui lòng thử lại.")
