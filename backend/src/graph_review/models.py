from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICY_VERSION = "wbs06-evidence-v1"
Status = Literal["APPROVED", "PENDING", "REJECTED"]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Entity(StrictModel):
    entity_id: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    canonical_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    identity_key: str | None = None
    resolution_status: Literal["resolved", "ambiguous", "unresolved"] = "unresolved"


class Evidence(StrictModel):
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    corpus_id: str = Field(min_length=1)
    index_version_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    locator: dict
    quote: str = Field(min_length=1)


class Candidate(StrictModel):
    candidate_id: str = Field(min_length=1)
    group: Literal["company", "person", "event"]
    relation_type: str = Field(min_length=1)
    subject: Entity
    object: Entity
    evidence: list[Evidence] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    temporal: dict[str, str | None] = Field(default_factory=dict)
    assertion_status: str | None = None
    conflicts: list[dict | str] = Field(default_factory=list)
    extractor_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def attribute_types(self):
        for key in ("position", "cooperation_scope", "consolidation_basis", "accounting_basis",
                    "holding_basis", "participant_role", "event_type"):
            value = self.attributes.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError("Invalid attribute type: " + key)
        errors = self.extractor_metadata.get("input_errors", [])
        if not isinstance(errors, list) or any(not isinstance(code, str) for code in errors):
            raise ValueError("input_errors must be a list of codes")
        return self


@dataclass(frozen=True)
class VerifiedSource:
    """Produced by a trusted reader, not deserialized from candidate JSON."""
    document_id: str
    document_version: str
    chunk_id: str
    corpus_id: str
    index_version_id: str
    source_sha256: str
    content_hash: str
    locator: dict
    text: str
    active: bool = True
    verification_mode: str = "LIVE"


class ReviewResult(StrictModel):
    candidate_id: str
    candidate_sha256: str
    policy_version: str = POLICY_VERSION
    status: Status
    reasons: list[str]
    source_verified: bool = False
    verification_mode: Literal["LIVE", "FIXTURE", "UNVERIFIED"] = "UNVERIFIED"
    checked_at: datetime
    checks: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_reasons(self):
        if self.status == "APPROVED" and self.reasons:
            raise ValueError("APPROVED requires reasons=[]")
        prefix = {"PENDING": "WARN_", "REJECTED": "ERR_"}.get(self.status)
        if prefix and (not self.reasons or any(not r.startswith(prefix) for r in self.reasons)):
            raise ValueError("Review reasons do not match status")
        return self

    @property
    def load_allowed(self) -> bool:
        return self.status == "APPROVED" and self.source_verified and self.verification_mode == "LIVE"

    def publish_allowed(self, graph_status: str) -> bool:
        return self.load_allowed and graph_status == "READY"


class SourceProblem(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
