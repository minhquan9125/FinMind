"""Read-only comparison of one approved contract batch with Neo4j."""

import argparse
import json
from pathlib import Path

from neo4j import GraphDatabase, READ_ACCESS

from backend.scripts.ingest_sprint4_graph import _settings
from backend.src.graph.sprint4_store import prepare_batch


def compare_batch(prepared, version_data, batch_data, graph_rows):
    """Return differences in version, batch, direction and evidence."""
    errors = []
    if version_data is None:
        return ['Graph version does not exist']
    for key, expected in (
        ('status', 'READY'),
        ('corpus_id', prepared['corpus_id']),
        ('index_version_id', prepared['index_version_id']),
    ):
        if version_data.get(key) != expected:
            errors.append(f'Graph version {key} differs')
    if batch_data is None:
        return errors + ['Graph batch does not exist']
    for key, expected in (
        ('graph_version_id', prepared['graph_version_id']),
        ('batch_id', prepared['batch_id']),
        ('input_hash', prepared['input_hash']),
        ('entity_count', len(prepared['entities'])),
        ('relation_count', len(prepared['relations'])),
    ):
        if batch_data.get(key) != expected:
            errors.append(f'Graph batch {key} differs')

    expected_by_id = {row['properties']['relation_id']: row for row in prepared['relations']}
    actual_by_id = {}
    for row in graph_rows:
        relation_id = row['relation'].get('relation_id')
        if relation_id in actual_by_id:
            errors.append(f'Duplicate graph relation: {relation_id}')
        actual_by_id[relation_id] = row
    for relation_id in sorted(expected_by_id.keys() - actual_by_id.keys()):
        errors.append(f'Missing graph relation: {relation_id}')
    for relation_id in sorted(actual_by_id.keys() - expected_by_id.keys()):
        errors.append(f'Unexpected graph relation: {relation_id}')

    for relation_id in sorted(expected_by_id.keys() & actual_by_id.keys()):
        expected = expected_by_id[relation_id]
        actual = actual_by_id[relation_id]
        properties = actual['relation']
        for key in ('subject_key', 'object_key'):
            if actual.get(key) != expected[key]:
                errors.append(f'{relation_id}: {key} differs')
        for key, value in expected['properties'].items():
            if key in ('evidence_json', 'attributes_json'):
                try:
                    same = json.loads(properties.get(key, 'null')) == json.loads(value)
                except (TypeError, ValueError):
                    same = False
            else:
                # Neo4j does not store null properties.
                same = properties.get(key) == value
            if not same:
                errors.append(f'{relation_id}: {key} differs')
    return errors


def main():
    parser = argparse.ArgumentParser(description='Verify a READY Sprint 4 graph batch (read only)')
    parser.add_argument('--input', required=True, type=Path, help='Full approved contract 2.1.0 envelope')
    parser.add_argument('--version', required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--env-file', type=Path, help='Neo4j settings; defaults to repo/backend .env')
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding='utf-8-sig'))
    prepared = prepare_batch(payload, args.version, args.batch_id)
    uri, user, password, database = _settings(args.env_file)
    with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10) as driver:
        driver.verify_connectivity()
        with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
            version_row = session.run('''MATCH (v:GraphVersion {id: $id})
                RETURN properties(v) AS data''', id=args.version).single()
            batch_row = session.run('''MATCH (b:GraphBatch {key: $key})
                RETURN properties(b) AS data''', key=prepared['batch_key']).single()
            rows = list(session.run('''MATCH (s:GraphEntity)-[r:GRAPH_RELATION
                {graph_version_id: $id, source_batch_id: $batch_id}]->(o:GraphEntity)
                RETURN s.key AS subject_key, o.key AS object_key,
                       properties(r) AS relation''', id=args.version, batch_id=args.batch_id))
    errors = compare_batch(prepared, version_row['data'] if version_row else None,
                           batch_row['data'] if batch_row else None, rows)
    print(json.dumps({'graph_version_id': args.version, 'batch_id': args.batch_id,
                      'expected_approved_relations': len(prepared['relations']),
                      'graph_relations': len(rows), 'passed': not errors, 'errors': errors},
                     ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
