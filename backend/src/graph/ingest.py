"""CLI for preflight validation, dry-run and snapshot ingestion."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .adapter import to_graph
from .contract import ContractError, load_dataset, require
from .graph_store import GraphStore


DEFAULT_INPUT = Path(__file__).resolve().parents[3] / "data/normalized"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="JSON file or directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report counts without Neo4j")
    args = parser.parse_args(argv)
    try:
        paths = sorted(args.input.glob("*.json")) if args.input.is_dir() else [args.input]
        require(bool(paths), "Input directory contains no JSON datasets")
        loaded = [(path, load_dataset(path)) for path in paths]
        identities = [(payload["symbol"], payload["dataset_version"]) for _, payload in loaded]
        require(len(set(identities)) == len(identities), "Input contains duplicate dataset identities")
    except (ContractError, OSError) as exc:
        print(f"Input validation failed: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        for path, payload in loaded:
            graph = to_graph(payload, source_file=str(path.resolve()))
            print(json.dumps({"dataset_id": graph.dataset["id"], "checksum": graph.dataset["checksum"],
                              "dry_run": True, "counts": graph.counts()}))
        return 0
    try:
        with GraphStore.from_environment() as store:
            for path, payload in loaded:
                result = store.ingest(payload, source_file=str(path.resolve()))
                print(json.dumps(asdict(result)))
    except ContractError as exc:
        print(f"Graph ingestion failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        # Driver errors may contain connection settings: keep credentials out of output.
        print("Neo4j operation failed; check driver installation, server and environment configuration",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
