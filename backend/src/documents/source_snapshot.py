"""Fail-closed access to immutable indexed source snapshots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .chunk_reconstruction import ReconstructionError
from .corpus_manifest import sha256


class SourceSnapshot:
    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("schema_version") != "finmind-source-snapshot-v1":
            raise ValueError("Unsupported source snapshot schema")
        if payload.get("immutable") is not True or payload.get("database_writes") is not False:
            raise ValueError("Source snapshot must be immutable and read-only")
        self.source_snapshot_id = str(payload["source_snapshot_id"])
        self.documents: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for document in payload["documents"]:
            key = (str(document["source_table"]), str(document["source_id"]))
            if key in self.documents:
                raise ValueError("Duplicate source document in snapshot")
            chunks = document["chunks"]
            for chunk in chunks:
                text = chunk["text"]
                if hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk["content_hash"]:
                    raise ValueError("Snapshot chunk content hash mismatch")
                locator = chunk.get("locator")
                if not isinstance(locator, dict):
                    raise ValueError("Snapshot chunk locator is missing")
                if locator.get("source_table") != key[0] or str(locator.get("source_id")) != key[1]:
                    raise ValueError("Snapshot locator source mismatch")
            self.documents[key] = list(chunks)

    def resolve(self, locator: dict[str, Any], expected_hash: str) -> str:
        source_key = (str(locator.get("source_table")), str(locator.get("source_id")))
        chunks = self.documents.get(source_key)
        if chunks is None:
            raise ReconstructionError("SOURCE_SNAPSHOT_MISSING", "Source is absent from immutable snapshot")
        matches = [chunk for chunk in chunks if chunk.get("content_hash") == expected_hash.strip()]
        if len(matches) != 1:
            raise ReconstructionError("SOURCE_CHANGED", "Snapshot does not contain the indexed chunk")
        chunk = matches[0]
        saved = chunk["locator"]
        if (saved.get("row_keys") != locator.get("row_keys")
                or saved.get("reconstruction") != locator.get("reconstruction")):
            raise ReconstructionError("SOURCE_CHANGED", "Snapshot locator differs from indexed locator")
        text = chunk["text"]
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != expected_hash.strip():
            raise ReconstructionError("HASH_MISMATCH", "Snapshot text differs from indexed hash")
        return text


def load_source_snapshot(path: str | Path) -> SourceSnapshot:
    snapshot_path = Path(path)
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot = SourceSnapshot(payload)
        if payload.get("release_manifest_sha256"):
            # The release manifest is bound by the artifact producer; the
            # embedded snapshot itself remains the runtime trust boundary.
            if not isinstance(payload["release_manifest_sha256"], str):
                raise ValueError("Invalid release manifest binding")
        return snapshot
    except ReconstructionError:
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ReconstructionError("INVALID_SOURCE_SNAPSHOT", "Invalid immutable source snapshot") from exc
