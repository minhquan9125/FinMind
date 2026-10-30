"""Read-only WBS03 run: one candidate JSON per annual report in a frozen corpus."""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from src.core.config import get_settings
from src.sprint4_runtime.bctn_source import read_verified_bctn_chunks
from src.sprint4_runtime.db_adapter import document_envelope
from src.sprint4_runtime.relation_extractor import extract_candidates


async def run(args):
    registry = json.loads(args.registry.read_text(encoding='utf-8'))
    conn = await asyncpg.connect(get_settings().database_url, timeout=15, statement_cache_size=0)
    try:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            rows = await read_verified_bctn_chunks(conn, args.corpus_version_id,
                                                   document_id=args.document_id)
    finally:
        await conn.close()
    if not rows:
        raise ValueError('No current annual-report chunks in selected corpus/scope')
    by_document = defaultdict(list)
    for row in rows:
        by_document[row['document_id']].append(row)
    targets = {doc_id: args.output_dir / f'{doc_id}.candidates.json' for doc_id in by_document}
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise ValueError('Output already exists: ' + existing[0])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for doc_id, document_rows in sorted(by_document.items()):
        payload = document_envelope(document_rows, args.corpus_version_id)
        result = extract_candidates(payload, registry)
        target = targets[doc_id]
        with target.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        count = len(result['relations'])
        total += count
        print(f'document={doc_id} chunks={len(document_rows)} pending_candidates={count} output={target}',
              flush=True)
    print(f'complete documents={len(by_document)} verified_chunks={len(rows)} pending_candidates={total}')


def main():
    parser = argparse.ArgumentParser(description='WBS03 BCTN read-only candidate extraction')
    parser.add_argument('--corpus-version-id', required=True)
    parser.add_argument('--document-id', help='Run one complete BCTN; omit for the full corpus')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--registry', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'src' / 'sprint4_runtime' / 'company.registry.20261030.r1.json')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, asyncpg.PostgresError, OSError) as exc:
        parser.exit(1, f'WBS03 failed: {type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
