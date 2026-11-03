"""WBS09.4: bounded relation retrieval over READY Sprint 4 graph versions only."""

from __future__ import annotations

from datetime import date
import json

from neo4j import Query

MAX_HOPS = 2
MAX_LIMIT = 200
RELATION_TYPES = {'OWNS_SHARES', 'HAS_SUBSIDIARY', 'HAS_ASSOCIATE', 'COOPERATES_WITH',
                  'HOLDS_ROLE', 'APPOINTS', 'DISMISSES', 'INVOLVES'}

# Interval facts overlap the window; snapshot facts (as_of only) must fall inside it.
_IN_WINDOW = '''CASE WHEN r.valid_from IS NULL AND r.valid_to IS NULL
  THEN ($start IS NULL OR r.as_of >= $start) AND ($end IS NULL OR r.as_of <= $end)
  ELSE ($start IS NULL OR r.valid_to IS NULL OR r.valid_to >= $start)
   AND ($end IS NULL OR r.valid_from IS NULL OR r.valid_from <= $end) END'''

QUERY = '''
MATCH (v:GraphVersion) WHERE v.id IN $versions AND v.status = 'READY'
MATCH (s:GraphEntity) WHERE s.graph_version_id = v.id AND s.entity_id IN $entities
MATCH p = (s)-[rs:GRAPH_RELATION*1..%d]-(:GraphEntity)
WHERE all(r IN rs WHERE r.graph_version_id = v.id
          AND ($types IS NULL OR r.relation_type IN $types) AND %s)
RETURN v.id AS graph_version_id,
       [r IN rs | {relation_id: r.relation_id, relation_type: r.relation_type,
                   subject_id: startNode(r).entity_id, subject_name: startNode(r).canonical_name,
                   object_id: endNode(r).entity_id, object_name: endNode(r).canonical_name,
                   as_of: r.as_of, valid_from: r.valid_from, valid_to: r.valid_to,
                   attributes_json: r.attributes_json, evidence_json: r.evidence_json,
                   reviewer: r.reviewer, reviewed_at: r.reviewed_at}] AS path
ORDER BY size(rs), [r IN rs | r.relation_id]
LIMIT $limit
'''


def _day(value, label):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f'{label} must be YYYY-MM-DD')
    return date.fromisoformat(value).isoformat()


def _ids(values, label):
    values = sorted(set(values or ()))
    if not values or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f'{label} must contain nonempty strings')
    return values


class RelationRetrieval:
    def __init__(self, driver, *, database='neo4j', timeout_seconds=5.0):
        if not 0 < timeout_seconds <= 30:
            raise ValueError('timeout_seconds must be in (0, 30]')
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds

    def query(self, entity_ids, *, graph_version_ids, relation_types=None,
              start=None, end=None, hops=1, limit=50):
        """Paths of 1..hops approved edges touching entity_ids, each edge with its sources.

        Unpublished (BUILDING) versions are invisible, so unreviewed or half-loaded
        data cannot leak into answers.
        """
        if hops not in range(1, MAX_HOPS + 1):
            raise ValueError(f'hops must be 1..{MAX_HOPS}')
        if not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f'limit must be 1..{MAX_LIMIT}')
        types = sorted(set(relation_types)) if relation_types else None
        if types and not set(types) <= RELATION_TYPES:
            raise ValueError('Unknown relation type')
        start, end = _day(start, 'start'), _day(end, 'end')
        if start and end and start > end:
            raise ValueError('start must not be after end')
        params = dict(entities=_ids(entity_ids, 'entity_ids'),
                      versions=_ids(graph_version_ids, 'graph_version_ids'),
                      types=types, start=start, end=end, limit=limit)
        # hops is validated above; Cypher cannot parameterise a path length.
        cypher = QUERY % (hops, _IN_WINDOW)
        with self.driver.session(database=self.database) as session:
            rows = list(session.run(Query(cypher, timeout=self.timeout_seconds), **params))
        return [{'graph_version_id': row['graph_version_id'],
                 'relations': [_edge(e) for e in row['path']]} for row in rows]


def _edge(raw):
    edge = dict(raw)
    edge['attributes'] = json.loads(edge.pop('attributes_json'))
    edge['evidence'] = json.loads(edge.pop('evidence_json'))
    return edge
