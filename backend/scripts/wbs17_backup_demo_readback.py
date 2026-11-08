"""Read-only graph/source smoke check of an isolated backup-demo snapshot.

Loads existing local connection settings without printing credentials. Does not
publish, approve, repair or change any database record.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


async def check(snapshot: Path, root: Path, output: Path):
    from dotenv import dotenv_values
    for env_path in (root / '.env', root / 'backend/.env'):
        for key, value in dotenv_values(env_path, interpolate=False).items():
            if value is not None:
                os.environ[key] = value
    sys.path.insert(0, str(snapshot / 'backend'))
    sys.path.insert(0, str(snapshot))
    from src.graph.graph_store import GraphStore
    from src.graph.viewer import GraphViewerReader, SOURCE_SCOPE
    from src.core.config import get_settings
    from src.graph_review.sources import PostgresSourceReader, compare_source
    from src.graph_review.models import Evidence
    import asyncpg

    settings = get_settings()
    result = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'level': 'LIVE_READ_ONLY_GRAPH_AND_POSTGRES',
              'gemini_configured': bool(settings.gemini_api_key.get_secret_value()),
              'free_tier_confirmed': settings.b1_gemini_free_tier_confirmed,
              'ui_e2e': 'NOT_RUN', 'versions': []}
    store = GraphStore.from_environment()
    conn = None
    try:
        reader = GraphViewerReader(store.driver, database=store.database)
        versions = await asyncio.to_thread(reader.versions)
        result['ready_versions'] = len(versions)
        dsn = settings.database_url
        if hasattr(dsn, 'get_secret_value'):
            dsn = dsn.get_secret_value()
        conn = await asyncpg.connect(str(dsn), timeout=10, command_timeout=15)
        logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            source_reader = PostgresSourceReader(conn)
            for meta in versions:
                version = meta['graph_version_id']
                record = {'meta': meta, 'sample_only': True}
                entities, truncated = await asyncio.to_thread(reader.entities, version, '', None, 3)
                record['entities'] = entities
                record['entities_truncated'] = truncated
                if entities:
                    edges, edge_truncated = await asyncio.to_thread(
                        reader.neighborhood, version, entities[0]['id'], hops=1,
                        relation_types=None, start=None, end=None, limit=5)
                    record['sample_edges'] = edges
                    record['edges_truncated'] = edge_truncated
                    checks = []
                    for edge in edges:
                        for ref in edge['evidence']:
                            chunk_id = ref['chunk_id']
                            import uuid
                            try:
                                ident = uuid.UUID(chunk_id)
                            except ValueError:
                                checks.append({'chunk_id': chunk_id, 'result': 'NON_DB_FIXTURE_ID'})
                                continue
                            row = await conn.fetchrow('''SELECT t.chunk_id::text, t.document_id::text,
                                t.superseded_at, d.sha256, d.source_url
                                FROM text_chunks t JOIN documents d USING(document_id)
                                WHERE t.chunk_id=$1''', ident)
                            check = {'chunk_id': chunk_id, 'exists': row is not None,
                                'active': row is not None and row['superseded_at'] is None,
                                'document_matches': row is not None and row['document_id'] == ref['document_id'],
                                'source_url_present': row is not None and bool(row['source_url'])}
                            # Annual evidence pins the whole source snapshot, not
                            # documents.sha256. Use the canonical reconstruction.
                            try:
                                corpus = ref.get('corpus_id') or meta.get('corpus_id')
                                source = await source_reader.read_current(chunk_id, corpus)
                                if all(k in ref for k in Evidence.model_fields):
                                    evidence = Evidence.model_validate({k: ref[k] for k in Evidence.model_fields})
                                    compare_source(evidence, source)
                                else:
                                    matches = (source.active and source.document_id == ref['document_id']
                                        and source.document_version == ref['document_version']
                                        and source.locator == ref['locator']
                                        and bool(ref['quote'].strip()) and ref['quote'] in source.text)
                                    if not matches:
                                        raise ValueError('Stored reference differs from canonical source')
                                check['canonical_replay'] = 'PASS'
                            except Exception as exc:
                                check['canonical_replay'] = 'FAIL'
                                check['replay_reason'] = getattr(exc, 'code', type(exc).__name__)
                            checks.append(check)
                    record['source_metadata_checks'] = checks
                    record['scope'] = 'SOURCE_DOCUMENT_ONLY' if meta.get('serving_scope') == SOURCE_SCOPE else 'GLOBAL_APPROVED_GRAPH'
                result['versions'].append(record)
    except Exception as exc:
        result['error_type'] = type(exc).__name__  # Never serialize connection errors/DSNs.
    finally:
        if conn is not None:
            await conn.close()
        store.close()
    result['limitations'] = ['Bounded sample, not full-load reconciliation.',
        'Canonical replay verifies source hashes/locator/quote membership, not LLM answers.',
        'Source-person assertions do not prove current office or global identity.']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), 'utf-8')
    print(json.dumps({'output': str(output), 'ready_versions': result.get('ready_versions'),
                      'sampled_versions': len(result['versions']), 'error_type': result.get('error_type')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(check(args.snapshot.resolve(), Path(__file__).resolve().parents[2], args.output))
