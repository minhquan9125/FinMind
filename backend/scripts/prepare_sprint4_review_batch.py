"""Build one offline WBS08 batch from the signed WBS06 V4 ZIP.

The ZIP and its individual reviewed envelopes are never modified. This script
does not connect to PostgreSQL or Neo4j and does not publish a graph version.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from backend.src.graph.sprint4_store import prepare_batch


def build_batch(package: Path, candidates: Path, graph_version_id: str, batch_id: str):
    original = json.loads(candidates.read_text(encoding="utf-8"))
    original_ids = {item["relation_id"] for item in original["candidates"]}
    with ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("decision") != "APPROVED" or manifest.get("wbs06_decision_final") is not True:
            raise ValueError("WBS06 package is not a final approved decision")
        items = manifest["items"]
        if not items:
            raise ValueError("WBS06 package contains no reviewed relations")
        envelopes = []
        for item in items:
            filename = item["envelope_file"]
            if Path(filename).name != filename:
                raise ValueError("Invalid envelope filename")
            raw = archive.read(f"envelopes/{filename}")
            if sha256(raw).hexdigest() != item["v4_sha256"]:
                raise ValueError(f"Envelope hash differs: {filename}")
            envelope = json.loads(raw)
            if len(envelope["relations"]) != 1:
                raise ValueError(f"Expected one reviewed relation: {filename}")
            relation = envelope["relations"][0]
            if (item["original_candidate_id"] not in original_ids
                    or relation["relation_id"] != item["reviewed_relation_id"]
                    or relation["review"]["status"] != "APPROVED"
                    or not relation["review"].get("reviewer")
                    or not relation["review"].get("reviewed_at")
                    or envelope["corpus_id"] != original["corpus_id"]
                    or envelope["dataset_version"] != original["index_version_id"]):
                raise ValueError(f"Review identity or source version differs: {filename}")
            envelopes.append(envelope)

    first = envelopes[0]
    combined = {key: first[key] for key in ("schema_version", "corpus_id", "dataset_version")}
    keys = {
        "documents": lambda item: item["document_id"],
        "chunks": lambda item: (item["document_id"], item["chunk_id"]),
        "entities": lambda item: item["entity_id"],
        "mentions": lambda item: item["mention_id"],
        "relations": lambda item: item["relation_id"],
    }
    for kind, get_key in keys.items():
        rows = OrderedDict()
        for envelope in envelopes:
            if any(envelope[key] != first[key] for key in ("schema_version", "corpus_id", "dataset_version")):
                raise ValueError("Envelope versions differ")
            for item in envelope[kind]:
                key = get_key(item)
                if key not in rows:
                    rows[key] = item.copy()
                elif kind == "entities":
                    existing = rows[key]
                    if any(existing[field] != value for field, value in item.items() if field != "aliases"):
                        raise ValueError(f"Conflicting entity identity: {key}")
                    # Aliases vary by source section. Keep their union for one
                    # canonical entity; never change relation IDs or evidence.
                    existing["aliases"] = sorted(set(existing["aliases"]) | set(item["aliases"]))
                elif rows[key] != item:
                    raise ValueError(f"Conflicting {kind} ID: {key}")
        combined[kind] = list(rows.values())

    if len(combined["relations"]) != len(items):
        raise ValueError("Duplicate reviewed relation ID")
    prepared = prepare_batch(combined, graph_version_id, batch_id)
    if len(prepared["relations"]) != len(items):
        raise ValueError("Not all reviewed relations projected to graph edges")
    report = {
        "package_sha256": sha256(package.read_bytes()).hexdigest(),
        "graph_version_id": graph_version_id,
        "batch_id": batch_id,
        "corpus_id": combined["corpus_id"],
        "index_version_id": combined["dataset_version"],
        "input_hash": prepared["input_hash"],
        "approved_relation_count": len(prepared["relations"]),
        "unique_entity_count": len(prepared["entities"]),
        "source_manifest_application_load_allowed": manifest.get("application_load_allowed"),
        "source_manifest_review_store_recorded": manifest.get("review_store_recorded"),
        "database_writes": 0,
    }
    return combined, report


def main():
    parser = argparse.ArgumentParser(description="Prepare approved Sprint 4 graph batch offline")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    payload, report = build_batch(args.package, args.candidates, args.version, args.batch_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "approved-batch.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "preflight.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
