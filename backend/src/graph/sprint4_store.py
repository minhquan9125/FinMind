"""Versioned Neo4j writer for approved Sprint 4 extraction contracts.

This store is separate from the financial GraphStore. A graph version is built
from named batches and becomes queryable only after publish() verifies the
complete expected batch list.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from ..sprint4_runtime.contracts import validate_envelope


SCHEMA_FILE = Path(__file__).resolve().parents[2] / 'scripts/init_neo4j_sprint4.cypher'
ENTITY_LABELS = {'Company', 'Person', 'Event'}


class GraphVersionConflict(ValueError):
    """An ID was reused with different content or version metadata."""


@dataclass(frozen=True)
class BatchResult:
    graph_version_id: str
    batch_id: str
    created: bool
    entity_count: int
    relation_count: int


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonempty string')
    return value


def _key(version, local_id):
    """Unambiguous key even when either ID itself contains a colon."""
    return sha256(_json([version, local_id]).encode('utf-8')).hexdigest()


def prepare_batch(payload, graph_version_id, batch_id):
    """Validate the shared contract and project only approved facts."""
    validate_envelope(payload)
    version = _required(graph_version_id, 'graph_version_id')
    batch = _required(batch_id, 'batch_id')
    entities_by_id = {item['entity_id']: item for item in payload['entities']}
    documents = {item['document_id']: item for item in payload['documents']}
    chunks = {(item['document_id'], item['chunk_id']): item for item in payload['chunks']}
    approved = [item for item in payload['relations'] if item['review']['status'] == 'APPROVED']
    used_ids = {id_ for item in approved for id_ in (item['subject_id'], item['object_id'])}
    entities = []
    for id_ in sorted(used_ids):
        item = entities_by_id[id_]
        label = item['entity_type']
        if label not in ENTITY_LABELS:
            raise ValueError('Unsupported entity type')
        properties = {
            'key': _key(version, id_), 'graph_version_id': version,
            'entity_id': id_, 'canonical_name': item['canonical_name'],
            'identity_key': item['identity_key'],
            'aliases_json': _json(item['aliases']),
            'attributes_json': _json(item['attributes']),
        }
        properties['fingerprint'] = sha256(_json(properties).encode('utf-8')).hexdigest()
        entities.append({'label': label, 'properties': properties})
    relations = []
    for item in approved:
        evidence = []
        for source in item['evidence']:
            document = documents[source['document_id']]
            chunk = chunks[(source['document_id'], source['chunk_id'])]
            evidence.append({
                'document_id': source['document_id'], 'chunk_id': source['chunk_id'],
                'document_version': document['document_version'],
                'locator': chunk['locator'], 'quote': source['quote'],
            })
        properties = {
            'key': _key(version, item['relation_id']),
            'graph_version_id': version, 'relation_id': item['relation_id'],
            'relation_type': item['relation_type'],
            'corpus_id': payload['corpus_id'],
            'index_version_id': payload['dataset_version'],
            'source_batch_id': batch,
            'attributes_json': _json(item['attributes']),
            'evidence_json': _json(evidence),
            'as_of': item['temporal']['as_of'],
            'valid_from': item['temporal']['valid_from'],
            'valid_to': item['temporal']['valid_to'],
            'reviewer': item['review']['reviewer'],
            'reviewed_at': item['review']['reviewed_at'],
        }
        properties['fingerprint'] = sha256(_json(properties).encode('utf-8')).hexdigest()
        relations.append({
            'subject_key': _key(version, item['subject_id']),
            'object_key': _key(version, item['object_id']),
            'properties': properties,
        })
    return {
        'graph_version_id': version, 'batch_id': batch,
        'batch_key': _key(version, batch),
        'corpus_id': payload['corpus_id'],
        'index_version_id': payload['dataset_version'],
        'contract_version': payload['schema_version'],
        'input_hash': sha256(_json(payload).encode('utf-8')).hexdigest(),
        'entities': entities, 'relations': relations,
    }


VERSION_CLAIM = '''
MERGE (v:GraphVersion {id: $id})
ON CREATE SET v.corpus_id = $corpus_id, v.index_version_id = $index_version_id,
              v.contract_version = $contract_version, v.status = 'BUILDING'
SET v.write_lock = coalesce(v.write_lock, 0) + 1
RETURN v.corpus_id AS corpus_id, v.index_version_id AS index_version_id,
       v.contract_version AS contract_version, v.status AS status
'''

BATCH_CLAIM = '''
MERGE (b:GraphBatch {key: $key})
ON CREATE SET b.graph_version_id = $graph_version_id, b.batch_id = $batch_id,
              b.input_hash = $input_hash, b.entity_count = $entity_count,
              b.relation_count = $relation_count
RETURN b.input_hash AS input_hash, b.entity_count AS entity_count,
       b.relation_count AS relation_count
'''

ENTITY_WRITE = '''
UNWIND $rows AS row
MERGE (e:GraphEntity:%s {key: row.key})
ON CREATE SET e += row
RETURN count(e) AS count
'''

RELATION_WRITE = '''
UNWIND $rows AS row
MATCH (s:GraphEntity {key: row.subject_key})
MATCH (o:GraphEntity {key: row.object_key})
MERGE (s)-[r:GRAPH_RELATION {key: row.properties.key}]->(o)
ON CREATE SET r += row.properties
RETURN count(r) AS count
'''


class Sprint4GraphStore:
    def __init__(self, driver, *, database='neo4j', batch_size=500):
        if not isinstance(batch_size, int) or not 1 <= batch_size <= 10000:
            raise ValueError('batch_size must be in 1..10000')
        self.driver = driver
        self.database = _required(database, 'database')
        self.batch_size = batch_size
        self._schema_ready = False

    def ensure_schema(self):
        if self._schema_ready:
            return
        statements = [s.strip() for s in SCHEMA_FILE.read_text('utf-8').split(';') if s.strip()]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()
        self._schema_ready = True

    def ingest_batch(self, payload, *, graph_version_id, batch_id):
        prepared = prepare_batch(payload, graph_version_id, batch_id)
        self.ensure_schema()
        with self.driver.session(database=self.database) as session:
            return session.execute_write(self._ingest, prepared)

    def _ingest(self, tx, item):
        # One transaction owns the claim and all writes: failure rolls back the batch.
        version = tx.run(VERSION_CLAIM, id=item['graph_version_id'],
                         corpus_id=item['corpus_id'], index_version_id=item['index_version_id'],
                         contract_version=item['contract_version']).single(strict=True)
        for key in ('corpus_id', 'index_version_id', 'contract_version'):
            if version[key] != item[key]:
                raise GraphVersionConflict(f'Graph version has different {key}')
        existing = tx.run('''MATCH (b:GraphBatch {key: $key}) RETURN properties(b) AS data''',
                          key=item['batch_key']).single()
        if existing is not None:
            data = existing['data']
            if data.get('input_hash') != item['input_hash']:
                raise GraphVersionConflict('Batch ID has different input')
            return BatchResult(item['graph_version_id'], item['batch_id'], False,
                               data['entity_count'], data['relation_count'])
        if version['status'] != 'BUILDING':
            raise GraphVersionConflict('Published graph version is immutable')
        # A global uniqueness constraint guards the batch key; this transaction is
        # retried by the Neo4j driver on transient conflicts.
        claimed = tx.run(BATCH_CLAIM, key=item['batch_key'], graph_version_id=item['graph_version_id'],
                         batch_id=item['batch_id'], input_hash=item['input_hash'],
                         entity_count=len(item['entities']), relation_count=len(item['relations'])).single(strict=True)
        if claimed['input_hash'] != item['input_hash']:
            raise GraphVersionConflict('Batch ID has different input')
        for label in sorted(ENTITY_LABELS):
            rows = [entity['properties'] for entity in item['entities'] if entity['label'] == label]
            for start in range(0, len(rows), self.batch_size):
                block = rows[start:start + self.batch_size]
                found = tx.run('''UNWIND $keys AS key MATCH (e:GraphEntity {key: key})
                                  RETURN e.key AS key, properties(e) AS data''',
                               keys=[row['key'] for row in block])
                fingerprints = {r['key']: r['data'].get('fingerprint') for r in found}
                for row in block:
                    if row['key'] in fingerprints and fingerprints[row['key']] != row['fingerprint']:
                        raise GraphVersionConflict('Entity ID has different content')
                tx.run(ENTITY_WRITE % label, rows=block).consume()
        rows = item['relations']
        for start in range(0, len(rows), self.batch_size):
            block = rows[start:start + self.batch_size]
            found = tx.run('''UNWIND $keys AS key MATCH ()-[r:GRAPH_RELATION {key: key}]->()
                              RETURN r.key AS key, properties(r) AS data''',
                           keys=[row['properties']['key'] for row in block])
            fingerprints = {r['key']: r['data'].get('fingerprint') for r in found}
            for row in block:
                key = row['properties']['key']
                if key in fingerprints and fingerprints[key] != row['properties']['fingerprint']:
                    raise GraphVersionConflict('Relation ID has different content')
            count = tx.run(RELATION_WRITE, rows=block).single(strict=True)['count']
            if count != len(block):
                raise GraphVersionConflict('Relation endpoints missing')
        return BatchResult(item['graph_version_id'], item['batch_id'], True,
                           len(item['entities']), len(item['relations']))

    def publish(self, graph_version_id, *, expected_batch_ids):
        version = _required(graph_version_id, 'graph_version_id')
        expected = list(expected_batch_ids)
        if not expected or any(not isinstance(x, str) or not x.strip() for x in expected):
            raise ValueError('expected_batch_ids must contain nonempty batch IDs')
        if len(expected) != len(set(expected)):
            raise ValueError('Duplicate expected batch ID')
        with self.driver.session(database=self.database) as session:
            return session.execute_write(self._publish, version, expected)

    @staticmethod
    def _publish(tx, version, expected):
        record = tx.run('''MATCH (v:GraphVersion {id: $id})
                           SET v.write_lock = coalesce(v.write_lock, 0) + 1
                           RETURN v.status AS status''', id=version).single()
        if record is None:
            raise ValueError('Graph version does not exist')
        batches = tx.run('''MATCH (b:GraphBatch {graph_version_id: $id})
                            RETURN b.batch_id AS batch_id''', id=version)
        actual = {r['batch_id'] for r in batches}
        if actual != set(expected):
            raise GraphVersionConflict('Batch list differs; graph remains BUILDING')
        if record['status'] == 'READY':
            return False
        if record['status'] != 'BUILDING':
            raise GraphVersionConflict('Unexpected graph status')
        tx.run("MATCH (v:GraphVersion {id: $id}) SET v.status = 'READY'", id=version).consume()
        return True

    def get_ready_relations(self, graph_version_id, *, limit=100):
        version = _required(graph_version_id, 'graph_version_id')
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError('limit must be in 1..1000')
        with self.driver.session(database=self.database) as session:
            records = session.run('''MATCH (v:GraphVersion {id: $id, status: 'READY'})
                MATCH (s:GraphEntity)-[r:GRAPH_RELATION {graph_version_id: $id}]->(o:GraphEntity)
                RETURN s.entity_id AS subject_id, o.entity_id AS object_id,
                       properties(r) AS relation
                ORDER BY r.relation_id LIMIT $limit''', id=version, limit=limit)
            return [
                {'subject_id': record['subject_id'], 'object_id': record['object_id'],
                 **{key: record['relation'].get(key) for key in
                    ('relation_id', 'relation_type', 'evidence_json', 'as_of',
                     'valid_from', 'valid_to')}}
                for record in records
            ]

    def get_version_status(self, graph_version_id):
        version = _required(graph_version_id, 'graph_version_id')
        with self.driver.session(database=self.database) as session:
            record = session.run('''MATCH (v:GraphVersion {id: $id})
                OPTIONAL MATCH (b:GraphBatch {graph_version_id: $id})
                RETURN v.id AS graph_version_id, v.status AS status,
                       v.corpus_id AS corpus_id, v.index_version_id AS index_version_id,
                       collect(b.batch_id) AS batch_ids,
                       sum(b.relation_count) AS recorded_relation_count''', id=version).single()
            return dict(record) if record else None
