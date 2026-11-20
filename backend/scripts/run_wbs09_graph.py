"""WBS09 CLI: merge extractor envelopes, gate on WBS06 review store, load/publish, query.

build --dry-run touches nothing. Without it: reads PostgreSQL (review store and
sources, read-only transaction) and writes only to the configured Neo4j.
"""

import argparse
import asyncio
import json
from pathlib import Path

from neo4j import GraphDatabase

from backend.scripts.ingest_sprint4_graph import _settings
from backend.src.graph.relation_retrieval import RelationRetrieval
from backend.src.graph.sprint4_store import Sprint4GraphStore
from backend.src.graph.wbs09_pipeline import build_graph_version, merge_envelopes

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / 'backend/src/sprint4_runtime/company.registry.20261030.r1.json'


def _read(path):
    return json.loads(Path(path).read_text('utf-8'))


async def _gate(graph_version_id, envelope, registry_path):
    import asyncpg
    from backend.src.core.config import get_settings
    from backend.src.graph_review.engine import IdentityRegistry, ReviewEngine
    from backend.src.graph_review.gate import build_gate
    from backend.src.graph_review.repository import PostgresReviewStore
    from backend.src.graph_review.sources import PostgresSourceReader

    registry = IdentityRegistry(_read(registry_path))
    connection = await asyncpg.connect(get_settings().database_url, timeout=15, statement_cache_size=0)
    try:
        async with connection.transaction(readonly=True, isolation='repeatable_read'):
            engine = ReviewEngine(PostgresSourceReader(connection), registry)
            return await build_gate(PostgresReviewStore(connection), engine, graph_version_id, envelope)
    finally:
        await connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file')
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--input', action='append', required=True, help='Contract 2.1.0 envelope; repeat per extractor')
    build.add_argument('--version', required=True, help='Review-store graph_version_id (UUID); also the Neo4j version')
    build.add_argument('--registry', default=str(DEFAULT_REGISTRY))
    build.add_argument('--receipt', required=True)
    build.add_argument('--dry-run', action='store_true')
    query = sub.add_parser('query')
    query.add_argument('--version', action='append', required=True)
    query.add_argument('--entity', action='append', required=True)
    query.add_argument('--type', action='append')
    query.add_argument('--start')
    query.add_argument('--end')
    query.add_argument('--hops', type=int, default=1)
    query.add_argument('--limit', type=int, default=50)
    args = parser.parse_args(argv)

    if args.command == 'build':
        envelopes = [_read(p) for p in args.input]
        if args.dry_run:
            _, report = merge_envelopes(envelopes)
            result = {k: report[k] for k in ('input_relations', 'not_approved', 'loaded_relation_ids',
                                             'merged', 'conflicts')}
        else:
            uri, user, password, database = _settings(args.env_file)
            with GraphDatabase.driver(uri, auth=(user, password)) as driver:
                result = build_graph_version(
                    Sprint4GraphStore(driver, database=database), envelopes,
                    graph_version_id=args.version,
                    approve=lambda envelope: asyncio.run(_gate(args.version, envelope, args.registry)))
        Path(args.receipt).write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        keys = ('input_relations', 'not_approved', 'loaded_relation_ids') if args.dry_run else (
            'status', 'counts', 'checks', 'blocked_reason')
        print(json.dumps({k: result[k] for k in keys}, ensure_ascii=False))
        return 0 if args.dry_run or result['status'] == 'READY' else 1

    uri, user, password, database = _settings(args.env_file)
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        rows = RelationRetrieval(driver, database=database).query(
            args.entity, graph_version_ids=args.version, relation_types=args.type,
            start=args.start, end=args.end, hops=args.hops, limit=args.limit)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
