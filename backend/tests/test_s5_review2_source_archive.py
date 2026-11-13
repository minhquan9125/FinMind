"""Retired consumer snapshots must not occupy or trust Huyen's module path."""
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_s5_intent_review2 as audit


ROUTING = 'backend/src/retrieval_orchestration/intent_routing.py'
SEMANTIC = 'backend/src/retrieval_orchestration/intent_semantic_requests.py'


def test_only_retired_consumer_sources_and_original_auditor_are_archived():
    assert set(audit.ARCHIVED_SOURCES) == {
        ROUTING, 'backend/src/retrieval_orchestration/intent_handoff.py',
        'backend/scripts/audit_s5_intent_review2.py',
    }
    assert audit.source_path(SEMANTIC) == audit.ROOT / SEMANTIC


def test_future_huyen_consumer_does_not_replace_frozen_experiment(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    archived = audit.source_path(ROUTING)
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b'original experiment')
    current = tmp_path / ROUTING
    current.parent.mkdir(parents=True)
    current.write_bytes(b'Huyen owns this module after merge')
    audit.verify_sources({ROUTING: hashlib.sha256(archived.read_bytes()).hexdigest()})


def test_tampered_archive_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    path = audit.source_path(ROUTING)
    path.parent.mkdir(parents=True)
    path.write_bytes(b'tampered')
    with pytest.raises(AssertionError, match='intent_routing'):
        audit.verify_sources({ROUTING: hashlib.sha256(b'original').hexdigest()})


def test_active_nhan_source_still_has_to_match_frozen_hash(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, 'ROOT', tmp_path)
    path = tmp_path / SEMANTIC
    path.parent.mkdir(parents=True)
    path.write_bytes(b'changed semantic logic')
    with pytest.raises(AssertionError, match='intent_semantic_requests'):
        audit.verify_sources({SEMANTIC: hashlib.sha256(b'original logic').hexdigest()})
