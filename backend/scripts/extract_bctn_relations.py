"""Extract PENDING BCTN relation candidates from a verified 2.1.0 JSON input.

Example from repository root:
  backend/.venv/Scripts/python.exe backend/scripts/extract_bctn_relations.py \
    --input backend/tests/fixtures/wbs03_db_ctg_chunk.json \
    --output backend/.tmp/wbs03-ctg-candidates.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sprint4_runtime.contracts import validate_envelope
from src.sprint4_runtime.relation_extractor import extract_candidates


def main():
    parser = argparse.ArgumentParser(description='WBS03: extract PENDING BCTN company relations')
    parser.add_argument('--input', type=Path, required=True, help='Verified contract 2.1.0 JSON')
    parser.add_argument('--output', type=Path, required=True, help='New candidate JSON file')
    parser.add_argument('--reextract', action='store_true',
                        help='Re-run rules on a previously verified envelope; preserve documents/chunks')
    parser.add_argument('--registry', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'src' / 'sprint4_runtime' / 'company.registry.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; choose a new path')
    payload = json.loads(args.input.read_text(encoding='utf-8'))
    if payload['schema_version'] != '2.1.0':
        parser.error('WBS03 DB input must use contract 2.1.0')
    validate_envelope(payload)
    if not payload['documents'] or any(d.get('source_kind') != 'db' or d.get('doc_type') != 'ANNUAL_REPORT'
                                       for d in payload['documents']):
        parser.error('WBS03 accepts only DB ANNUAL_REPORT documents')
    registry = json.loads(args.registry.read_text(encoding='utf-8'))
    if args.reextract:
        payload = dict(payload, entities=[], mentions=[], relations=[])
    result = extract_candidates(payload, registry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print(f"chunks={len(result['chunks'])} candidates={len(result['relations'])} output={args.output}")


if __name__ == '__main__':
    main()
