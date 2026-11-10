"""Read-only Neo4j queries behind the WBS15 Graph Viewer API (contract graph-viewer-v1)."""

from __future__ import annotations

import json

from neo4j import Query

from .relation_retrieval import RelationRetrieval

NODE_TYPES = ('Company', 'Person', 'Event')


class VersionNotFound(LookupError):
    pass


class VersionNotReady(LookupError):
    pass


def _node(row):
    return {
        'id': row['entity_id'],
        'type': next((t for t in row['labels'] if t in NODE_TYPES), None),
        'label': row['canonical_name'],
        'aliases': json.loads(row['aliases_json'] or '[]'),
        'attributes': json.loads(row['attributes_json'] or '{}'),
    }


class GraphViewerReader:
    def __init__(self, driver, *, database='neo4j', timeout_seconds=5.0):
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds
        self.retrieval = RelationRetrieval(driver, database=database, timeout_seconds=timeout_seconds)

    def _run(self, cypher, **params):
        with self.driver.session(database=self.database) as session:
            return list(session.run(Query(cypher, timeout=self.timeout_seconds), **params))

    def versions(self):
        rows = self._run('''MATCH (v:GraphVersion {status: 'READY'})
            OPTIONAL MATCH ()-[r:GRAPH_RELATION {graph_version_id: v.id}]->()
            RETURN v.id AS graph_version_id, v.status AS status, v.corpus_id AS corpus_id,
                   v.index_version_id AS index_version_id, v.contract_version AS contract_version,
                   count(r) AS relation_count
            ORDER BY v.id''')
        return [dict(row) for row in rows]

    def ready_version(self, graph_version_id):
        """Return the version meta, or raise: unpublished data never reaches the viewer."""
        rows = self._run('''MATCH (v:GraphVersion {id: $id})
            RETURN v.id AS graph_version_id, v.status AS status, v.corpus_id AS corpus_id,
                   v.index_version_id AS index_version_id''', id=graph_version_id)
        if not rows:
            raise VersionNotFound(graph_version_id)
        meta = dict(rows[0])
        if meta['status'] != 'READY':
            raise VersionNotReady(graph_version_id)
        return meta

    def entities(self, graph_version_id, q, entity_type=None, limit=20):
        rows = self._run('''MATCH (e:GraphEntity {graph_version_id: $v})
            WHERE ($type IS NULL OR $type IN labels(e))
              AND (e.entity_id = $q OR toLower(e.canonical_name) CONTAINS toLower($q)
                   OR toLower(e.aliases_json) CONTAINS toLower($q))
            OPTIONAL MATCH (e)-[r:GRAPH_RELATION {graph_version_id: $v}]-()
            WITH e, count(r) AS relation_count
            RETURN e.entity_id AS entity_id, labels(e) AS labels, e.canonical_name AS canonical_name,
                   e.aliases_json AS aliases_json, e.attributes_json AS attributes_json, relation_count
            ORDER BY relation_count DESC, e.canonical_name LIMIT $limit''',
            v=graph_version_id, q=q, type=entity_type, limit=limit + 1)
        items = [dict(_node(row), relation_count=row['relation_count']) for row in rows]
        return items[:limit], len(items) > limit

    def nodes(self, graph_version_id, entity_ids):
        rows = self._run('''MATCH (e:GraphEntity {graph_version_id: $v}) WHERE e.entity_id IN $ids
            RETURN e.entity_id AS entity_id, labels(e) AS labels, e.canonical_name AS canonical_name,
                   e.aliases_json AS aliases_json, e.attributes_json AS attributes_json''',
            v=graph_version_id, ids=sorted(set(entity_ids)))
        return {row['entity_id']: _node(row) for row in rows}

    def neighborhood(self, graph_version_id, entity_id, *, hops, relation_types, start, end, limit):
        """Paths are capped at limit + 1 so the caller can report truncation."""
        paths = self.retrieval.query([entity_id], graph_version_ids=[graph_version_id],
                                     relation_types=relation_types, start=start, end=end,
                                     hops=hops, limit=limit + 1)
        truncated = len(paths) > limit
        edges = {}
        for path in paths[:limit]:
            for edge in path['relations']:
                edges.setdefault(edge['relation_id'], edge)
        return list(edges.values()), truncated

    def relation(self, graph_version_id, relation_id):
        rows = self._run('''MATCH (s:GraphEntity)-[r:GRAPH_RELATION {graph_version_id: $v, relation_id: $id}]->(o:GraphEntity)
            RETURN s.entity_id AS subject_id, o.entity_id AS object_id, properties(r) AS relation''',
            v=graph_version_id, id=relation_id)
        return dict(rows[0]) if rows else None
