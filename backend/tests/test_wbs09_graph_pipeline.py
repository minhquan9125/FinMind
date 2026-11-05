"""WBS09 merge / review gate / reconcile / retrieval tests; no Neo4j or DB needed."""

from copy import deepcopy
import json
from pathlib import Path
from time import monotonic
import unittest

from backend.src.graph.relation_retrieval import RelationRetrieval
from backend.src.graph_review.gate import ApprovalGate, core
from backend.src.graph_review.models import digest
from backend.src.graph.sprint4_store import BatchResult, prepare_batch
from backend.src.graph.wbs09_pipeline import build_graph_version, merge_envelopes
from backend.src.retrieval_orchestration.hybrid_router.adapters import (
    LiveGraphAdapter, _period_window,
)
from backend.src.retrieval_orchestration.hybrid_router.schemas import RouterTask


BASE = json.loads((Path(__file__).with_name('fixtures') / 'wbs08_graph_contract.json').read_text('utf-8'))
DOC = BASE['documents'][0]['document_id']
VER = BASE['documents'][0]['document_version']
REVIEW = {'status': 'APPROVED', 'reviewer': 'fixture-reviewer', 'reviewed_at': '2025-01-02T10:00:00Z'}
COMPANIES = deepcopy(BASE['entities'])


def envelope(text, entities, relations, chunk_id):
    payload = deepcopy(BASE)
    payload['chunks'] = [{'document_id': DOC, 'document_version': VER, 'chunk_id': chunk_id, 'text': text,
                          'locator': {'page': 1, 'block_id': chunk_id, 'bbox': [0, 0, 10, 10]}}]
    payload['entities'] = deepcopy(entities)
    payload['relations'] = relations
    return payload


def relation(rid, rtype, subject, object_, attributes, quote, chunk_id, as_of='2025-01-01', review=REVIEW):
    return {'relation_id': rid, 'relation_type': rtype, 'subject_id': subject, 'object_id': object_,
            'attributes': attributes, 'temporal': {'as_of': as_of, 'valid_from': None, 'valid_to': None},
            'evidence': [{'document_id': DOC, 'chunk_id': chunk_id, 'quote': quote}],
            'review': dict(review), 'negated': False, 'conditional': False}


def company_env():
    payload = deepcopy(BASE)
    payload['relations'][0]['relation_id'] = 'company:rel-1'
    return payload


def person_env():
    person = {'entity_id': 'person:an', 'entity_type': 'Person', 'canonical_name': 'Nguyễn Văn An',
              'aliases': [], 'resolution_status': 'resolved', 'identity_key': 'person:an', 'attributes': {}}
    text = 'Ông Nguyễn Văn An giữ chức Tổng giám đốc Công ty Alpha.'
    return envelope(text, COMPANIES + [person], [
        relation('person:rel-1', 'HOLDS_ROLE', 'person:an', 'company:alpha',
                 {'position': 'Tổng giám đốc'}, 'Nguyễn Văn An giữ chức Tổng giám đốc', 'p1:b2'),
        relation('person:pending', 'HOLDS_ROLE', 'person:an', 'company:beta', {'position': 'Thành viên'},
                 'Nguyễn Văn An', 'p1:b2', review={'status': 'PENDING', 'reviewer': None, 'reviewed_at': None}),
    ], 'p1:b2')


def event_env():
    event = {'entity_id': 'event:launch', 'entity_type': 'Event', 'canonical_name': 'Ra mắt dịch vụ',
             'aliases': [], 'resolution_status': 'resolved', 'identity_key': 'event:launch',
             'attributes': {'event_type': 'product_launch', 'occurred_at': '2025-01-01'}}
    text = 'Công ty Beta ra mắt dịch vụ mới ngày 2025-01-01.'
    return envelope(text, COMPANIES + [event], [
        relation('event:rel-1', 'INVOLVES', 'event:launch', 'company:beta',
                 {'participant_role': 'organizer'}, 'Công ty Beta ra mắt dịch vụ mới', 'p1:b3'),
    ], 'p1:b3')


ALL = ['company:rel-1', 'person:rel-1', 'event:rel-1']


class FakeSession:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **kwargs):
        return [{'relation_id': r} for r in self.store.loaded]


class FakeStore:
    database = 'neo4j'

    def __init__(self, drop=()):
        self.loaded, self.published, self.drop = [], None, set(drop)
        self.driver = self

    def session(self, database):
        return FakeSession(self)

    def ingest_batch(self, payload, *, graph_version_id, batch_id):
        prepared = prepare_batch(payload, graph_version_id, batch_id)
        self.loaded = [r['properties']['relation_id'] for r in prepared['relations']
                       if r['properties']['relation_id'] not in self.drop]
        return BatchResult(graph_version_id, batch_id, True, len(prepared['entities']), len(prepared['relations']))

    def publish(self, graph_version_id, *, expected_batch_ids):
        self.published = list(expected_batch_ids)
        return True


class MergeTests(unittest.TestCase):
    def test_three_extractors_share_one_contract_and_only_approved_pass(self):
        merged, report = merge_envelopes([company_env(), person_env(), event_env()])
        self.assertEqual({r['relation_type'] for r in merged['relations']},
                         {'COOPERATES_WITH', 'HOLDS_ROLE', 'INVOLVES'})
        self.assertEqual(report['loaded_relation_ids'], sorted(ALL))
        self.assertEqual(report['not_approved'], 2)  # WBS08 pending + person pending
        self.assertEqual(merged['mentions'], [])

    def test_same_fact_from_two_extractors_is_merged_and_keeps_both_sources(self):
        other = company_env()
        other['relations'][0]['relation_id'] = 'company:rel-0'
        other['chunks'][0] = dict(other['chunks'][0], chunk_id='p1:b9',
                                  locator={'page': 1, 'block_id': 'p1:b9', 'bbox': [0, 0, 10, 10]})
        other['relations'][0]['evidence'][0]['chunk_id'] = 'p1:b9'
        other['relations'] = other['relations'][:1]
        merged, report = merge_envelopes([company_env(), other])
        self.assertEqual(len(merged['relations']), 1)
        edge = merged['relations'][0]
        self.assertEqual(edge['relation_id'], 'company:rel-0')
        self.assertEqual(edge, other['relations'][0])  # approved content is never edited
        self.assertEqual(report['merged'][0]['relation_ids'], ['company:rel-0', 'company:rel-1'])
        self.assertEqual(report['merged'][0]['evidence']['company:rel-1'][0]['chunk_id'], 'p1:b1')

    def test_one_relation_id_with_two_report_years_goes_to_wbs06(self):
        later = company_env()
        later['relations'][0]['temporal']['as_of'] = '2026-01-01'
        merged, report = merge_envelopes([company_env(), later])
        self.assertEqual(merged['relations'], [])
        self.assertEqual(report['conflicts'][0]['reason'], 'RELATION_ID_COLLISION')

    def test_disagreeing_attribute_is_a_conflict_not_a_merge(self):
        one = person_env()
        two = person_env()
        two['relations'][0]['relation_id'] = 'person:rel-2'
        two['relations'][0]['attributes']['source_note'] = 'khác'
        merged, report = merge_envelopes([one, two])
        self.assertNotIn('person:rel-1', report['loaded_relation_ids'])
        self.assertEqual(report['conflicts'][0]['reason'], 'ATTRIBUTE_MISMATCH')

    def test_two_positions_are_two_facts(self):
        two = person_env()
        two['relations'][0]['relation_id'] = 'person:rel-2'
        two['relations'] = two['relations'][:1]
        two['relations'][0]['attributes']['position'] = 'Thành viên HĐQT'
        two['relations'][0]['evidence'][0]['chunk_id'] = 'p1:b4'
        two['chunks'][0].update(chunk_id='p1:b4', locator={'page': 1, 'block_id': 'p1:b4', 'bbox': [0, 0, 10, 10]})
        two['chunks'][0]['text'] += ' Ông Nguyễn Văn An cũng là Thành viên HĐQT.'
        merged, report = merge_envelopes([person_env(), two])
        self.assertEqual(report['loaded_relation_ids'], ['person:rel-1', 'person:rel-2'])

    def test_per_document_aliases_are_unioned_not_a_conflict(self):
        other = event_env()
        other['entities'][1]['aliases'] = ['Beta', 'BETA JSC']
        merged, report = merge_envelopes([company_env(), other])
        self.assertEqual(report['conflicts'], [])
        beta = next(e for e in merged['entities'] if e['entity_id'] == 'company:beta')
        self.assertEqual(beta['aliases'], ['BETA JSC', 'Beta'])

    def test_same_entity_id_with_other_identity_is_a_conflict(self):
        other = event_env()
        other['entities'][1]['identity_key'] = 'name:gamma'
        merged, report = merge_envelopes([company_env(), other])
        self.assertEqual({c['reason'] for c in report['conflicts']}, {'ENTITY_CONFLICT'})

    def test_mixed_corpus_versions_are_refused(self):
        other = event_env()
        other['corpus_id'] = 'another-corpus'
        with self.assertRaises(ValueError):
            merge_envelopes([company_env(), other])


class BuildTests(unittest.TestCase):
    def build(self, store, approved, envelopes=None):
        def approve(envelope):  # stands in for graph_review.gate.build_gate
            for r in envelope['relations']:
                if r['review']['status'] == 'APPROVED' and r['relation_id'] not in approved:
                    raise PermissionError('WBS06: exported relation differs from reviewed evidence')
            return ApprovalGate('g-v1', frozenset(approved), digest(envelope), monotonic() + 60)
        return build_graph_version(store, envelopes or [company_env(), person_env(), event_env()],
                                   graph_version_id='g-v1', approve=approve)

    def test_all_checks_pass_then_publish_with_receipt(self):
        store = FakeStore()
        receipt = self.build(store, ALL)
        self.assertEqual(receipt['status'], 'READY')
        self.assertEqual(store.published, [receipt['batch_id']])
        self.assertEqual(receipt['counts']['loaded'], 3)
        self.assertTrue(all(receipt['checks'].values()))

    def test_rerun_uses_same_batch_id(self):
        self.assertEqual(self.build(FakeStore(), ALL)['batch_id'], self.build(FakeStore(), ALL)['batch_id'])

    def test_envelope_approval_missing_from_review_store_blocks_load(self):
        store = FakeStore()
        receipt = self.build(store, ALL[:2])
        self.assertEqual(receipt['status'], 'BUILDING')
        self.assertFalse(receipt['checks']['wbs06_gate'])
        self.assertIn('WBS06', receipt['blocked_reason'])
        self.assertEqual(store.loaded, [])

    def test_gate_bound_to_another_graph_version_blocks_load(self):
        store = FakeStore()
        receipt = build_graph_version(store, [company_env()], graph_version_id='g-v1',
                                      approve=lambda env: ApprovalGate('g-v2', frozenset(ALL), digest(env), monotonic() + 60))
        self.assertFalse(receipt['checks']['wbs06_gate'])
        self.assertEqual(store.loaded, [])

    def test_review_store_approval_absent_from_envelopes_blocks_publish(self):
        store = FakeStore()
        receipt = self.build(store, ALL + ['ghost'])
        self.assertEqual(receipt['status'], 'BUILDING')
        self.assertEqual(receipt['missing_in_envelopes'], ['ghost'])
        self.assertEqual(store.loaded, [])

    def test_neo4j_edge_mismatch_blocks_publish(self):
        store = FakeStore(drop={'person:rel-1'})
        receipt = self.build(store, ALL)
        self.assertFalse(receipt['checks']['neo4j_edges_match_approved'])
        self.assertIsNone(store.published)


class GateCoreTests(unittest.TestCase):
    def test_handoff_candidate_without_assertion_status_matches_envelope_export(self):
        # from_handoff omits assertion_status; from_envelope emits None. Same claim.
        self.assertEqual(digest(core({'candidate_id': 'r', 'extractor_metadata': {'x': 1}})),
                         digest(core({'candidate_id': 'r', 'assertion_status': None})))
        self.assertNotEqual(core({'candidate_id': 'r'}), core({'candidate_id': 'r', 'assertion_status': 'PLANNED'}))


class CaptureSession(FakeSession):
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def run(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.rows


class CaptureDriver:
    def __init__(self, rows=()):
        self.last = CaptureSession(list(rows))

    def session(self, database):
        return self.last


EDGE = {'relation_id': 'r1', 'relation_type': 'HAS_SUBSIDIARY', 'subject_id': 'CMP-TCB',
        'corpus_id': 'corpus-v1', 'index_version_id': 'index-v1',
        'subject_name': 'TCB', 'object_id': 'CMP-TCBS', 'object_name': 'TCBS', 'as_of': '2025-12-31',
        'valid_from': None, 'valid_to': None, 'attributes_json': '{"consolidation_basis":"x"}',
        'evidence_json': json.dumps([{'document_id': DOC, 'chunk_id': 'c1', 'document_version': VER,
                                      'locator': {'page': 3}, 'quote': 'TCBS là công ty con'}]),
        'reviewer': 'r', 'reviewed_at': '2026-01-01T00:00:00Z'}


class RetrievalTests(unittest.TestCase):
    def test_bounds_are_enforced(self):
        retrieval = RelationRetrieval(CaptureDriver())
        for kwargs in ({'hops': 3}, {'limit': 0}, {'limit': 201}, {'relation_types': ['KNOWS']},
                       {'start': '2025-02-01', 'end': '2025-01-01'}, {'graph_version_ids': []}):
            with self.assertRaises(ValueError):
                retrieval.query(['e1'], **{'graph_version_ids': ['g-v1'], **kwargs})
        with self.assertRaises(ValueError):
            RelationRetrieval(CaptureDriver(), timeout_seconds=60)

    def test_query_is_parameterised_ready_only_and_timed(self):
        driver = CaptureDriver([{'graph_version_id': 'g-v1', 'path': [EDGE]}])
        result = RelationRetrieval(driver, timeout_seconds=3).query(
            ['CMP-TCB'], graph_version_ids=['g-v1'], relation_types=['HAS_SUBSIDIARY'],
            start='2025-01-01', end='2025-12-31', hops=2, limit=10)
        query, params = driver.last.calls[0]
        self.assertEqual(query.timeout, 3)
        self.assertIn("v.status = 'READY'", query.text)
        self.assertIn('*1..2', query.text)
        self.assertEqual(params['types'], ['HAS_SUBSIDIARY'])
        self.assertEqual(params['limit'], 10)
        self.assertEqual(result[0]['relations'][0]['evidence'][0]['quote'], 'TCBS là công ty con')


def test_ready_check_requires_every_requested_version():
    driver = CaptureDriver([{'found': 2, 'ready': 1}])
    assert not RelationRetrieval(driver).all_versions_ready(['v1', 'v2'])
    driver = CaptureDriver([{'found': 2, 'ready': 2}])
    assert RelationRetrieval(driver).all_versions_ready(['v1', 'v2'])


class FakeRetrieval:
    def __init__(self, paths):
        self.paths, self.calls = paths, []

    def query(self, entity_ids, **kwargs):
        self.calls.append((entity_ids, kwargs))
        return self.paths


def task(operation, **params):
    return RouterTask(id='g1', adapter='GRAPH', operation=operation, params=params)


class AdapterTests(unittest.TestCase):
    def test_without_retrieval_keeps_old_unavailable_answer(self):
        result = LiveGraphAdapter(store=None).execute(task('find_relationships', companies=['TCB']))
        self.assertEqual(result.reason_code, 'GRAPH_RELATIONSHIPS_NOT_INDEXED')

    def test_relationship_answer_carries_sources(self):
        edge = {k: v for k, v in EDGE.items() if not k.endswith('_json')}
        edge.update(attributes={}, evidence=json.loads(EDGE['evidence_json']))
        fake = FakeRetrieval([{'graph_version_id': 'g-v1', 'relations': [edge]}])
        def verified(paths):
            return ({'chunk_id': 'c1', 'source_verified': True, 'label': 'LIVE/GRAPH'},)
        adapter = LiveGraphAdapter(None, fake, ['g-v1'], {'TCB': 'CMP-TCB'},
                                   verify_sources=verified)
        result = adapter.execute(task('find_subsidiaries', companies=['tcb'], periods=['2025']))
        self.assertEqual(result.status, 'OK')
        self.assertEqual(result.evidence[0]['chunk_id'], 'c1')
        ids, kwargs = fake.calls[0]
        self.assertEqual(ids, ['CMP-TCB'])
        self.assertEqual(kwargs['relation_types'], ('HAS_SUBSIDIARY',))
        self.assertEqual((kwargs['start'], kwargs['end']), ('2025-01-01', '2025-12-31'))

    def test_unknown_ticker_is_no_data(self):
        adapter = LiveGraphAdapter(None, FakeRetrieval([]), ['g-v1'], {})
        self.assertEqual(adapter.execute(task('find_relationships', companies=['XYZ'])).reason_code,
                         'GRAPH_ENTITY_UNRESOLVED')

    def test_partial_or_multiple_company_scope_never_returns_other_company_edges(self):
        retrieval = FakeRetrieval([])
        adapter = LiveGraphAdapter(None, retrieval, ['g-v1'],
                                   {'TCB': 'CMP-TCB', 'ELC': 'CMP-ELC'})
        partial = adapter.execute(task('find_relationships', companies=['TCB', 'UNKNOWN']))
        assert partial.reason_code == 'GRAPH_ENTITY_UNRESOLVED'
        multiple = adapter.execute(task('find_relationships', companies=['TCB', 'ELC']))
        assert multiple.reason_code == 'GRAPH_MULTI_COMPANY_SCOPE_UNSUPPORTED'
        assert retrieval.calls == []

    def test_period_window(self):
        self.assertEqual(_period_window(['2025-Q2']), ('2025-04-01', '2025-06-30'))
        self.assertEqual(_period_window(['2024', '2025-Q1']), ('2024-01-01', '2025-03-31'))
        with self.assertRaises(ValueError):
            _period_window(['latest'])

    def test_invalid_period_cannot_drop_filter_and_return_unscoped_edges(self):
        adapter = LiveGraphAdapter(None, FakeRetrieval([]), ['g-v1'], {'TCB': 'CMP-TCB'})
        result = adapter.execute(task('find_relationships', companies=['TCB'], periods=['2025-Q5']))
        self.assertEqual(result.reason_code, 'GRAPH_UNSUPPORTED_PERIOD')

    def test_graph_timeout_is_distinct_from_empty_graph(self):
        class SlowRetrieval:
            def query(self, *args, **kwargs):
                raise TimeoutError()

        adapter = LiveGraphAdapter(None, SlowRetrieval(), ['g-v1'], {'TCB': 'CMP-TCB'})
        result = adapter.execute(task('find_relationships', companies=['TCB']))
        self.assertEqual(result.reason_code, 'GRAPH_TIMEOUT')
        self.assertEqual(result.status, 'SYSTEM_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
