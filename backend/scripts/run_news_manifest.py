"""WBS16 staging runner. Fixture needs no DB; full requires a scoped WBS09.5 handoff."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.documents.news_batch_runner import read_json, run


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--articles', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mode', choices=['fixture', 'full'], required=True)
    p.add_argument('--receipt', type=Path)
    p.add_argument('--candidates', type=Path)
    p.add_argument('--postgres-inventory', type=Path)
    p.add_argument('--neo4j-inventory', type=Path)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--retry-errors', action='store_true')
    p.add_argument('--limit', type=int, help='Stop after this many articles; continue with --resume')
    args = p.parse_args(argv)
    try:
        report = run(read_json(args.manifest), read_json(args.articles), args.output,
            mode=args.mode, receipt=read_json(args.receipt) if args.receipt else None,
            candidates=read_json(args.candidates) if args.candidates else None,
            resume=args.resume, retry_errors=args.retry_errors, limit=args.limit,
            postgres=read_json(args.postgres_inventory) if args.postgres_inventory else None,
            neo4j=read_json(args.neo4j_inventory) if args.neo4j_inventory else None)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        reason = str(exc) if re.fullmatch('[A-Z0-9_]+', str(exc)) else 'INPUT_VALIDATION_OR_IO_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'reason': reason,
                          'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['staging_complete'] and report['database_reconciliation']['status'] != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
