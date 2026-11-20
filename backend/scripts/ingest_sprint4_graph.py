"""Local WBS08 CLI. It writes only to the configured Neo4j database."""

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from neo4j import GraphDatabase

from backend.src.graph.sprint4_store import Sprint4GraphStore


def _settings(env_file=None):
    root = Path(__file__).resolve().parents[2]
    values = {}
    paths = (Path(env_file),) if env_file else (root / '.env', root / 'backend' / '.env')
    for path in paths:
        if path.is_file():
            values.update(dotenv_values(path, interpolate=False, encoding='utf-8-sig'))
    def value(name, default=''):
        return os.environ.get(name) or values.get(name) or default
    uri = value('NEO4J_URI')
    user = value('NEO4J_USER') or value('NEO4J_USERNAME')
    password = value('NEO4J_PASSWORD')
    database = value('NEO4J_DATABASE', 'neo4j')
    if not uri or not user or not password:
        raise ValueError('Set NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD in backend/.env')
    return uri, user, password, database


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sprint 4 approved graph writer')
    parser.add_argument('--env-file', type=Path, help='Neo4j connection settings; defaults to repo/backend .env')
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest')
    ingest.add_argument('--input', required=True)
    ingest.add_argument('--version', required=True)
    ingest.add_argument('--batch-id', required=True)
    publish = sub.add_parser('publish')
    publish.add_argument('--version', required=True)
    publish.add_argument('--expected-batch', action='append', required=True)
    status = sub.add_parser('status')
    status.add_argument('--version', required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input).read_text('utf-8-sig')) if args.command == 'ingest' else None
    uri, user, password, database = _settings(args.env_file)
    with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10) as driver:
        driver.verify_connectivity()
        store = Sprint4GraphStore(driver, database=database)
        if args.command == 'ingest':
            result = store.ingest_batch(payload, graph_version_id=args.version, batch_id=args.batch_id)
            output = vars(result)
        elif args.command == 'publish':
            output = {'graph_version_id': args.version,
                      'published': store.publish(args.version, expected_batch_ids=args.expected_batch)}
        else:
            output = store.get_version_status(args.version)
    print(json.dumps(output, ensure_ascii=False, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
