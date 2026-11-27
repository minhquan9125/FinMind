"""WBS02 integration using the same reviewed SQLite store lifecycle as production."""

import copy
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest

from src.person_role.extractor import normalize_and_extract
from src.person_role.person_identity import resolve_person_identity
from src.wbs02_person_registry import person_registry as registry

from .test_person_role_extractor import fixture as source_fixture


COMPANIES = Path(__file__).resolve().parents[1] / "resources/person_role/company.registry.json"
PERSON = "Nguyễn Văn An"
ROLE = "Tổng giám đốc"


@pytest.fixture
def reviewed_source(tmp_path):
    payload = source_fixture(f"FPT bổ nhiệm Ông {PERSON} giữ chức {ROLE} từ ngày 01/01/2025.")
    payload.update(entities=[], mentions=[], relations=[])
    companies = json.loads(COMPANIES.read_text(encoding="utf-8"))
    company = next(item["entity_id"] for item in companies if "FPT" in item["aliases"])
    store = tmp_path / "person.registry.sqlite"
    with closing(registry.open_store(store, create=True)) as connection:
        first = registry.ingest(connection, payload)
        assert first["mentions"] >= 1 and first["approved"] == 0
        assert registry.ingest(connection, payload)["added"] == 0
        mention = next(item for item in registry.pending(connection) if item["raw_name"] == PERSON)
        person_id = registry.review(connection, mention["mention_id"], "new", "QA reviewer", "Verified fixture role",
                                    canonical_name=PERSON, company_id=company, position=ROLE,
                                    as_of="2025-01-01", expected_revision=mention["decision_revision"])
        counts = registry.status(connection)
    return payload, store, companies, person_id, mention["mention_id"], counts


def test_reviewed_exact_decision_preserves_source_and_read_only_store(reviewed_source):
    payload, store, companies, person_id, _, counts = reviewed_source
    before = hashlib.sha256(store.read_bytes()).hexdigest()
    original = copy.deepcopy(payload)
    resolved, audit = resolve_person_identity(payload, store, companies)
    assert payload == original
    assert (resolved["documents"], resolved["chunks"]) == (original["documents"], original["chunks"])
    assert [(item["entity_id"], item["canonical_name"]) for item in resolved["entities"]
            if item["entity_type"] == "Person" and item["resolution_status"] == "resolved"] == [(person_id, PERSON)]
    assert audit["registry_counts"] == counts
    assert counts["approved"] == counts["persons"] == 1
    assert audit["relation_approvals_created"] == audit["registry_writes"] == 0
    assert hashlib.sha256(store.read_bytes()).hexdigest() == before


def test_changed_pinned_locator_cannot_reuse_identity_decision(reviewed_source):
    payload, store, *_ = reviewed_source
    payload["chunks"][0]["locator"]["page"] += 1
    with pytest.raises(ValueError, match="pinned snapshot"):
        resolve_person_identity(payload, store)


def test_new_document_with_same_name_does_not_resolve_by_name(reviewed_source):
    payload, store, *_ = reviewed_source
    new_id = str(uuid4())
    payload["documents"][0]["document_id"] = new_id
    payload["chunks"][0]["document_id"] = new_id
    result, _ = resolve_person_identity(payload, store)
    people = [entity for entity in result["entities"] if entity["entity_type"] == "Person"]
    assert people
    assert all(entity["resolution_status"] == "unresolved" for entity in people)


def test_pipeline_preserves_resolved_ids_but_never_approves_relations(reviewed_source):
    payload, store, companies, person_id, *_ = reviewed_source
    result, audit = normalize_and_extract(payload, companies, person_store=store)
    assert audit["person_identity"]["resolved_person_entities"] == 1
    assert any(item["entity_id"] == person_id for item in result["entities"])
    assert result["relations"]
    assert all(relation["review"]["status"] == "PENDING" for relation in result["relations"])


def test_missing_or_foreign_sqlite_is_rejected(tmp_path, reviewed_source):
    payload, *_ = reviewed_source
    with pytest.raises(FileNotFoundError):
        resolve_person_identity(payload, tmp_path / "missing.sqlite")
    foreign = tmp_path / "foreign.sqlite"
    with closing(sqlite3.connect(foreign)) as connection:
        connection.execute("CREATE TABLE unrelated(id integer)")
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_person_identity(payload, foreign)


def test_stale_review_cannot_change_identity_and_reopen_removes_approval(reviewed_source):
    payload, store, _, person_id, mention_id, _ = reviewed_source
    with closing(registry.open_store(store)) as connection:
        old_decisions = registry.export_registry(connection)["decisions"]
        with pytest.raises(ValueError, match="Stale decision revision"):
            registry.review(connection, mention_id, "reopen", "QA reviewer", "Stale request", expected_revision=0)
        assert registry.export_registry(connection)["decisions"] == old_decisions
        registry.review(connection, mention_id, "reopen", "QA reviewer", "Evidence needs review",
                        expected_revision=old_decisions[-1]["seq"])
        reopened = next(item for item in registry.pending(connection) if item["mention_id"] == mention_id)
        assert reopened["decision_revision"] > old_decisions[-1]["seq"]
        assert registry.status(connection)["approved"] == 0
    result, _ = resolve_person_identity(payload, store)
    assert all(entity["entity_id"] != person_id for entity in result["entities"])
