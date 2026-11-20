"""Checks for the read-only comparison used after graph publishing."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from backend.scripts.verify_sprint4_graph import compare_batch
from backend.src.graph.sprint4_store import prepare_batch


FIXTURE = Path(__file__).with_name('fixtures') / 'wbs08_graph_contract.json'


def graph_sample():
    payload = json.loads(FIXTURE.read_text(encoding='utf-8'))
    prepared = prepare_batch(payload, 'graph-v1', 'fixture-report')
    version = {'status': 'READY', 'corpus_id': prepared['corpus_id'],
               'index_version_id': prepared['index_version_id']}
    batch = {'graph_version_id': prepared['graph_version_id'],
             'batch_id': prepared['batch_id'], 'input_hash': prepared['input_hash'],
             'entity_count': len(prepared['entities']),
             'relation_count': len(prepared['relations'])}
    rows = [{'subject_key': r['subject_key'], 'object_key': r['object_key'],
             'relation': {k: v for k, v in r['properties'].items() if v is not None}}
            for r in prepared['relations']]
    return prepared, version, batch, rows


class VerifyGraphTests(unittest.TestCase):
    def test_matching_approved_relation_passes(self):
        prepared, version, batch, rows = graph_sample()
        self.assertEqual(len(rows), 1)  # The PENDING relation was excluded.
        self.assertEqual(compare_batch(prepared, version, batch, rows), [])

    def test_reversed_direction_and_changed_evidence_fail(self):
        prepared, version, batch, rows = graph_sample()
        rows = deepcopy(rows)
        rows[0]['subject_key'], rows[0]['object_key'] = rows[0]['object_key'], rows[0]['subject_key']
        rows[0]['relation']['evidence_json'] = '[]'
        errors = compare_batch(prepared, version, batch, rows)
        self.assertTrue(any('subject_key differs' in error for error in errors))
        self.assertTrue(any('object_key differs' in error for error in errors))
        self.assertTrue(any('evidence_json differs' in error for error in errors))

    def test_missing_and_extra_relations_fail(self):
        prepared, version, batch, rows = graph_sample()
        self.assertTrue(any('Missing graph relation' in error
                            for error in compare_batch(prepared, version, batch, [])))
        extra = deepcopy(rows[0])
        extra['relation']['relation_id'] = 'unexpected'
        self.assertTrue(any('Unexpected graph relation' in error
                            for error in compare_batch(prepared, version, batch, rows + [extra])))

    def test_building_version_or_changed_batch_fails(self):
        prepared, version, batch, rows = graph_sample()
        version['status'] = 'BUILDING'
        batch['input_hash'] = 'changed'
        errors = compare_batch(prepared, version, batch, rows)
        self.assertTrue(any('status differs' in error for error in errors))
        self.assertTrue(any('input_hash differs' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
