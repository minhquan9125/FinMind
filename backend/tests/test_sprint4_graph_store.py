"""WBS08 projection and publish safety tests; no Neo4j connection needed."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from backend.src.graph.sprint4_store import (
    GraphVersionConflict, Sprint4GraphStore, _key, prepare_batch,
)


FIXTURE = Path(__file__).with_name('fixtures') / 'wbs08_graph_contract.json'


def sample():
    return json.loads(FIXTURE.read_text('utf-8'))


class Result:
    def __init__(self, rows):
        self.rows = rows

    def single(self, strict=False):
        if strict and len(self.rows) != 1:
            raise ValueError('Expected one row')
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)

    def consume(self):
        return None


class PublishTx:
    def __init__(self, status, batch_ids):
        self.status = status
        self.batch_ids = batch_ids
        self.wrote_ready = False

    def run(self, query, **kwargs):
        if 'RETURN v.status AS status' in query:
            return Result([{'status': self.status}]) if self.status else Result([])
        if 'RETURN b.batch_id AS batch_id' in query:
            return Result([{'batch_id': x} for x in self.batch_ids])
        if "SET v.status = 'READY'" in query:
            self.wrote_ready = True
            return Result([])
        raise AssertionError(query)


class IngestTx:
    """Small transaction double for the idempotence/conflict branches."""

    def __init__(self):
        self.version = None
        self.batches = {}
        self.entities = {}
        self.relations = {}

    def run(self, query, **kwargs):
        if 'MERGE (v:GraphVersion' in query:
            if self.version is None:
                self.version = {k: kwargs[k] for k in
                                ('corpus_id', 'index_version_id', 'contract_version')}
                self.version['status'] = 'BUILDING'
            return Result([self.version])
        if 'MATCH (b:GraphBatch {key: $key}) RETURN' in query:
            return Result([{'data': self.batches[kwargs['key']]}]) if kwargs['key'] in self.batches else Result([])
        if 'MERGE (b:GraphBatch' in query:
            key = kwargs['key']
            self.batches.setdefault(key, {k: kwargs[k] for k in
                                          ('input_hash', 'entity_count', 'relation_count')})
            return Result([self.batches[key]])
        if 'RETURN e.key AS key' in query:
            return Result([{'key': k, 'data': self.entities[k]}
                           for k in kwargs['keys'] if k in self.entities])
        if 'MERGE (e:GraphEntity:' in query:
            for row in kwargs['rows']:
                self.entities.setdefault(row['key'], row)
            return Result([{'count': len(kwargs['rows'])}])
        if 'RETURN r.key AS key' in query:
            return Result([{'key': k, 'data': self.relations[k]}
                           for k in kwargs['keys'] if k in self.relations])
        if 'MERGE (s)-[r:GRAPH_RELATION' in query:
            for row in kwargs['rows']:
                self.relations.setdefault(row['properties']['key'], row['properties'])
            return Result([{'count': len(kwargs['rows'])}])
        raise AssertionError(query)


class GraphStoreTests(unittest.TestCase):
    def test_projection_uses_only_approved_and_keeps_source(self):
        prepared = prepare_batch(sample(), 'graph-v1', 'report-1')
        self.assertEqual(len(prepared['entities']), 2)
        self.assertEqual(len(prepared['relations']), 1)
        relation = prepared['relations'][0]
        self.assertEqual(relation['properties']['relation_id'], 'relation:approved-1')
        self.assertEqual(relation['properties']['source_batch_id'], 'report-1')
        evidence = json.loads(relation['properties']['evidence_json'])
        self.assertEqual(evidence[0]['chunk_id'], 'p1:b1')
        self.assertEqual(evidence[0]['locator']['page'], 1)
        self.assertEqual(evidence[0]['document_version'], 'b' * 64)

    def test_keys_cannot_collide_when_ids_contain_colons(self):
        self.assertNotEqual(_key('a:b', 'c'), _key('a', 'b:c'))

    def test_version_and_batch_affect_identity(self):
        one = prepare_batch(sample(), 'graph-v1', 'report-1')
        again = prepare_batch(sample(), 'graph-v1', 'report-1')
        other_version = prepare_batch(sample(), 'graph-v2', 'report-1')
        self.assertEqual(one, again)
        self.assertNotEqual(one['relations'][0]['properties']['key'],
                            other_version['relations'][0]['properties']['key'])

    def test_unapproved_only_creates_no_entities_or_edges(self):
        payload = sample()
        payload['relations'] = payload['relations'][1:]
        prepared = prepare_batch(payload, 'graph-v1', 'report-1')
        self.assertEqual(prepared['entities'], [])
        self.assertEqual(prepared['relations'], [])

    def test_invalid_approved_relation_is_rejected_by_shared_contract(self):
        payload = deepcopy(sample())
        payload['relations'][0]['review']['reviewer'] = None
        with self.assertRaises(ValueError):
            prepare_batch(payload, 'graph-v1', 'report-1')

    def test_publish_requires_exact_batch_list(self):
        tx = PublishTx('BUILDING', ['report-1'])
        with self.assertRaises(GraphVersionConflict):
            Sprint4GraphStore._publish(tx, 'graph-v1', ['report-1', 'report-2'])
        self.assertFalse(tx.wrote_ready)
        self.assertTrue(Sprint4GraphStore._publish(tx, 'graph-v1', ['report-1']))
        self.assertTrue(tx.wrote_ready)

    def test_ingest_same_batch_is_noop_and_changed_input_conflicts(self):
        store = Sprint4GraphStore(driver=None)
        tx = IngestTx()
        prepared = prepare_batch(sample(), 'graph-v1', 'report-1')
        first = store._ingest(tx, prepared)
        self.assertTrue(first.created)
        self.assertEqual(len(tx.relations), 1)
        second = store._ingest(tx, prepared)
        self.assertFalse(second.created)
        self.assertEqual(len(tx.relations), 1)
        changed = deepcopy(prepared)
        changed['input_hash'] = 'changed'
        with self.assertRaises(GraphVersionConflict):
            store._ingest(tx, changed)

    def test_published_version_rejects_new_batch(self):
        store = Sprint4GraphStore(driver=None)
        tx = IngestTx()
        store._ingest(tx, prepare_batch(sample(), 'graph-v1', 'report-1'))
        tx.version['status'] = 'READY'
        with self.assertRaises(GraphVersionConflict):
            store._ingest(tx, prepare_batch(sample(), 'graph-v1', 'report-2'))


if __name__ == '__main__':
    unittest.main()
