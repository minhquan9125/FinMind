"""Validate fixture evidence using the proposed WBS08 v1 field names."""
from __future__ import annotations

from datetime import date
import json
import math
from pathlib import Path
import re


def load_fixtures() -> dict:
    """Load independent, explicitly synthetic data; never write or call a provider."""
    return json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _error(errors: list[dict], code: str, path: str, message: str) -> None:
    errors.append({"code": code, "path": path, "message": message})


def validate_pack(pack: object) -> list[dict]:
    """Collect schema errors; reject the entire pack on any invalid item.

    E001-E026 identify structural errors; E003 is reserved for legacy use.
    Field names follow WBS08: schema_version and source_sha256.
    """
    errors: list[dict] = []
    if not isinstance(pack, dict):
        return [{"code": "E001", "path": "", "message": "Gói bằng chứng phải là object."}]
    if pack.get("schema_version") != "1.0":
        _error(errors, "E002", "schema_version", "Phiên bản cấu trúc chưa được hỗ trợ.")
    if not _text(pack.get("query_id")):
        _error(errors, "E004", "query_id", "Thiếu mã truy vấn.")
    version = pack.get("data_version")
    if not isinstance(version, dict):
        _error(errors, "E005", "data_version", "Thiếu phiên bản dữ liệu.")
    else:
        if version.get("kind") != "INDEX":
            _error(errors, "E006", "data_version.kind", "Chỉ hỗ trợ phiên index đã xác định.")
        if not _text(version.get("id")) or version["id"].strip().lower() == "latest":
            _error(errors, "E007", "data_version.id", "Thiếu phiên index cụ thể.")
    items = pack.get("items")
    if not isinstance(items, list):
        _error(errors, "E008", "items", "Danh sách bằng chứng phải là mảng.")
        return errors
    seen: set[str] = set()
    for i, item in enumerate(items):
        path = f"items[{i}]"
        if not isinstance(item, dict):
            _error(errors, "E009", path, "Bằng chứng phải là object.")
            continue
        for field, code in (("evidence_id", "E010"), ("chunk_id", "E012"),
                            ("source_id", "E013"), ("passage", "E021")):
            if not _text(item.get(field)):
                _error(errors, code, f"{path}.{field}", "Thiếu nội dung hoặc định danh bắt buộc.")
        identity = item.get("evidence_id")
        if _text(identity):
            if identity in seen:
                _error(errors, "E011", f"{path}.evidence_id", "Mã bằng chứng bị trùng.")
            seen.add(identity)
        sha = item.get("source_sha256")
        if not isinstance(sha, str) or re.fullmatch(r"[a-fA-F0-9]{64}", sha) is None:
            _error(errors, "E014", f"{path}.source_sha256", "Hash nguồn phải có đúng64ký tự hex.")
        if item.get("source_type") not in ("BCTC", "BCTN"):
            _error(errors, "E015", f"{path}.source_type", "Loại nguồn chưa được hỗ trợ.")
        locator = item.get("locator")
        if not isinstance(locator, dict):
            _error(errors, "E016", f"{path}.locator", "Thiếu vị trí nguồn.")
        else:
            if not any(key in locator for key in ("page_number", "table_id")):
                _error(errors, "E017", f"{path}.locator", "Cần vị trí trang hoặc bảng.")
            if "page_number" in locator and (type(locator["page_number"]) is not int or locator["page_number"] < 1):
                _error(errors, "E019", f"{path}.locator.page_number", "Trang phải là số nguyên dương, không phải bool.")
            if "table_id" in locator and not _text(locator["table_id"]):
                _error(errors, "E020", f"{path}.locator.table_id", "Mã bảng không được trống.")
        score = item.get("score")
        if not isinstance(score, dict):
            _error(errors, "E022", f"{path}.score", "Thiếu điểm tương đồng.")
        else:
            if score.get("type") != "COSINE_SIMILARITY":
                _error(errors, "E023", f"{path}.score.type", "Loại điểm chưa được hỗ trợ.")
            value = score.get("value")
            if type(value) not in (int, float) or not -1 <= value <= 1 or not math.isfinite(value):
                _error(errors, "E026", f"{path}.score.value", "Điểm phải là số hữu hạn trong[-1,1], không phải bool.")
    return errors


def check_evidence(pack: dict, scope: dict, registry: dict) -> list[dict]:
    """Fail closed on binding/scope/coverage conflicts; never choose by score.

    E101 missing record; E102 company; E103 period; E104 metric/topic;
    E105 basis; E106 entity; E107 unit; E108 source; E109 hash;
    E110 locator; E111 passage; E112 source ID; E113 conflicting values;
    E114 coverage; E115 missing scope/record metadata; E116 index mismatch.
    UNKNOWN is resolved only by one explicitly identified evidence entity.
    """
    if not isinstance(scope, dict) or not isinstance(registry, dict):
        return [{"code": "E115", "path": "scope", "message": "Thiếu phạm vi hoặc registry đáng tin cậy."}]
    companies, periods = scope.get("companies"), scope.get("periods")
    lists_valid = all(isinstance(values, list) and values and all(_text(v) for v in values)
                      for values in (companies, periods))
    if not lists_valid:
        return [{"code": "E115", "path": "scope", "message": "Cần công ty và kỳ được xác định."}]
    try:
        if any(date.fromisoformat(p).isoformat() != p for p in periods):
            raise ValueError("ISO date required")
    except ValueError:
        return [{"code": "E115", "path": "scope.periods", "message": "Kỳ không hợp lệ."}]
    if (scope.get("source_type") not in ("BCTC", "BCTN")
            or scope.get("reporting_entity") not in ("UNKNOWN", "CONSOLIDATED", "PARENT")
            or scope.get("measure_basis") not in ("POINT_IN_TIME", "FULL_YEAR", "STANDALONE_QUARTER", "YTD", "NOT_APPLICABLE")
            or not (_text(scope.get("metric_code")) or _text(scope.get("topic")))
            or ("unit" in scope and not _text(scope["unit"]))):
        return [{"code": "E115", "path": "scope", "message": "Thiếu chỉ tiêu, chủ đề hoặc loại phạm vi bắt buộc."}]
    errors = validate_pack(pack)
    if errors:
        return errors
    covered: set[tuple[str, str]] = set()
    fact_values: dict[tuple, str] = {}
    entities: set[str] = set()
    units: set[str] = set()
    for i, item in enumerate(pack["items"]):
        path = f"items[{i}]"
        record = registry.get(item["chunk_id"])
        if not isinstance(record, dict):
            _error(errors, "E101", path, "Không tìm thấy metadata bằng chứng.")
            continue
        required = ("index_version", "company", "period_end", "measure_basis", "reporting_entity",
                    "unit", "source_type", "source_id", "source_sha256", "passage", "value_token")
        if (any(not _text(record.get(key)) for key in required)
                or record["reporting_entity"] not in ("CONSOLIDATED", "PARENT")
                or not isinstance(record.get("locator"), dict)
                or any(record.get(k) is not None and not _text(record[k]) for k in ("metric_code", "topic"))):
            _error(errors, "E115", path, "Metadata nguồn chưa đủ để xác minh.")
            continue
        before = len(errors)
        for field, code in (("source_sha256", "E109"), ("locator", "E110"),
                            ("passage", "E111"), ("source_id", "E112"), ("source_type", "E108")):
            if item[field] != record[field]:
                _error(errors, code, f"{path}.{field}", "Bằng chứng không khớp registry nguồn.")
        if record["index_version"] != pack["data_version"]["id"]:
            _error(errors, "E116", path, "Bằng chứng không thuộc phiên index đang dùng.")
        if record["company"] not in companies:
            _error(errors, "E102", path, "Bằng chứng không thuộc công ty đang hỏi.")
        if record["period_end"] not in periods:
            _error(errors, "E103", path, "Bằng chứng không đúng kỳ đang hỏi.")
        for key, code in (("metric_code", "E104"), ("topic", "E104"),
                          ("measure_basis", "E105"), ("source_type", "E108"), ("unit", "E107")):
            if scope.get(key) is not None and record.get(key) != scope[key]:
                _error(errors, code, path, "Metadata không khớp phạm vi truy vấn.")
        if scope["reporting_entity"] != "UNKNOWN" and record["reporting_entity"] != scope["reporting_entity"]:
            _error(errors, "E106", path, "Loại báo cáo không khớp.")
        entities.add(record["reporting_entity"])
        units.add(record["unit"])
        key = tuple(record.get(k) for k in ("company", "period_end", "metric_code", "topic",
                                          "reporting_entity", "measure_basis", "unit"))
        if key in fact_values and fact_values[key] != record["value_token"]:
            _error(errors, "E113", path, "Các bằng chứng cùng phạm vi có giá trị mâu thuẫn.")
        fact_values[key] = record["value_token"]
        if len(errors) == before:
            covered.add((record["company"], record["period_end"]))
    if len(entities) > 1:
        _error(errors, "E106", "items", "Chưa có loại báo cáo thống nhất; không tự chọn.")
    if len(units) > 1:
        _error(errors, "E107", "items", "Các bằng chứng khác đơn vị; không tự quy đổi.")
    missing = sorted({(c, p) for c in companies for p in periods} - covered)
    if missing:
        _error(errors, "E114", "coverage", "Chưa đủ bằng chứng cho mọi công ty và kỳ yêu cầu.")
    return errors
