"""WBS03 BCTN candidates -> per-page DB envelopes; source check only unless --apply."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from person_role_db import dsn
from src.person_role.wbs03_repository import WBS03Repository, build_db_envelope
from src.sprint4_runtime.contracts import validate_envelope


def split_by_section(payload):
    """Group relation evidence by (document, page section).

    The DB intake pins ``document_version`` to one section's source view, so a
    relation with evidence on two pages becomes two copies with the same
    relation_id, each carrying only its own page's evidence.
    """
    chunks = {(c['document_id'], c['chunk_id']): c for c in payload['chunks']}
    groups = {}
    for relation in payload['relations']:
        for evidence in relation['evidence']:
            chunk = chunks[(evidence['document_id'], evidence['chunk_id'])]
            group = groups.setdefault((evidence['document_id'], chunk['locator']['section_index']), {})
            group.setdefault(relation['relation_id'], dict(relation, evidence=[]))['evidence'].append(evidence)
    return groups


async def section_envelope(conn, payload, relations):
    chunk_ids = list(dict.fromkeys(e['chunk_id'] for r in relations for e in r['evidence']))
    actual = await build_db_envelope(conn, payload['corpus_id'], chunk_ids)
    texts = {(c['document_id'], c['chunk_id']): c['text'] for c in payload['chunks']}
    if any(texts.get((c['document_id'], c['chunk_id'])) != c['text'] for c in actual['chunks']):
        raise ValueError('Candidate chunk text differs from the pinned DB source')
    used = {r['subject_id'] for r in relations} | {r['object_id'] for r in relations}
    keys = {(c['document_id'], c['chunk_id']) for c in actual['chunks']}
    return validate_envelope(dict(
        actual,
        entities=[e for e in payload['entities'] if e['entity_id'] in used],
        mentions=[m for m in payload['mentions']
                  if m['entity_id'] in used and (m['document_id'], m['chunk_id']) in keys],
        relations=relations))


async def process(conn, paths, output_dir, apply):
    total = 0
    for path in paths:
        payload = validate_envelope(json.loads(path.read_text(encoding='utf-8')))
        for (document_id, section), group in sorted(split_by_section(payload).items()):
            envelope = await section_envelope(conn, payload, list(group.values()))
            repository = WBS03Repository(conn)
            if apply:
                result = await repository.save(envelope)
            else:
                await repository.verify_sources(envelope)
                result = {'status': 'SOURCE_VERIFIED_DRY_RUN', 'relations': len(envelope['relations']),
                          'database_writes': 0}
            target = output_dir / f'{document_id}.section-{section}.envelope.json'
            with target.open('x', encoding='utf-8') as handle:
                json.dump(envelope, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            total += len(envelope['relations'])
            print(f'document={document_id} section={section} {json.dumps(result)}', flush=True)
    print(f'complete relation_copies={total} apply={apply}')


async def run(args):
    paths = sorted(args.input_dir.glob('*.candidates.json'))
    if not paths:
        raise ValueError('No *.candidates.json in input directory')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(dsn(), timeout=15, command_timeout=90)
    try:
        if args.apply:
            # All envelopes in one transaction: a failure writes nothing.
            async with conn.transaction(isolation='repeatable_read'):
                await conn.execute('SET LOCAL ROLE finmind_graph_writer')
                await process(conn, paths, args.output_dir, True)
        else:
            async with conn.transaction(readonly=True, isolation='repeatable_read'):
                await process(conn, paths, args.output_dir, False)
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description='Save WBS03 BCTN PENDING candidates (dry run by default)')
    parser.add_argument('--input-dir', required=True, type=Path, help='Output of extract_bctn_from_db.py')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='Write EXTRACTED_PENDING drafts to PostgreSQL')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, asyncpg.PostgresError, OSError) as exc:
        parser.exit(1, f'WBS03 save failed: {type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
