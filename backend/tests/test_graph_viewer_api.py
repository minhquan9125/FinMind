"""WBS15 Graph Viewer API contract tests; fake Neo4j reader and source lookup, no DB."""

import json
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.src.api.routers import graph_viewer
from backend.src.auth.authorization import Principal, current_principal
from backend.src.graph.viewer import GraphViewerReader, SOURCE_SCOPE, SOURCE_TYPES, _source_edge, VersionNotFound, VersionNotReady

V = 'ae47d046-fb4f-579c-8d78-2287770bf8ea'
TCB, TCBS = 'CMP-00e0481af8b436b4645f', 'CMP-322902610d1a878d95d3'
PDF_CHUNK, NEWS_CHUNK = '4d3df972-94af-535a-ad99-fefdc1aa69e1', '11111111-2222-5333-8444-555555555555'
EVIDENCE = [
    {'document_id': '85deaf00-3748-5f3d-95a2-68495dc229fc', 'chunk_id': PDF_CHUNK, 'document_version': 'a' * 64,
     'locator': {'kind': 'db_text_span', 'page': 154}, 'quote': 'TCBS là công ty con'},
    {'document_id': 'news-doc', 'chunk_id': NEWS_CHUNK, 'document_version': 'b' * 64,
     'locator': {'kind': 'db_text_span', 'page': 1}, 'quote': 'tin tức'},
    {'document_id': 'gone', 'chunk_id': 'p1:b1', 'document_version': 'c' * 64,
     'locator': {'page': 3}, 'quote': 'không còn'},
]
EDGE = {'relation_id': 'review:bceddd14', 'relation_type': 'HAS_SUBSIDIARY', 'subject_id': TCB, 'object_id': TCBS,
        'as_of': '2025-12-31', 'valid_from': None, 'valid_to': None, 'attributes': {'consolidation_basis': 'hợp nhất toàn bộ'},
        'evidence': EVIDENCE, 'reviewer': 'Trần Diệu Huyền', 'reviewed_at': '2026-11-02T17:13:40+07:00'}
NODES = {TCB: {'id': TCB, 'type': 'Company', 'label': 'Techcombank', 'aliases': ['TCB'], 'attributes': {}},
         TCBS: {'id': TCBS, 'type': 'Company', 'label': 'Chứng khoán Kỹ Thương', 'aliases': ['TCBS'], 'attributes': {}}}


class FakeReader:
    def __init__(self, status='READY', fail=None, truncated=False):
        self.status, self.fail, self.truncated, self.calls = status, fail, truncated, []

    def _check(self):
        if self.fail:
            raise self.fail

    def versions(self):
        self._check()
        return [{'graph_version_id': V, 'status': 'READY', 'corpus_id': 'c', 'index_version_id': 'i',
                 'contract_version': '2.1.0', 'relation_count': 13}]

    def ready_version(self, version):
        self._check()
        if self.status is None:
            raise VersionNotFound(version)
        if self.status != 'READY':
            raise VersionNotReady(version)
        return {'graph_version_id': version, 'status': 'READY', 'corpus_id': 'c', 'index_version_id': 'i'}

    def nodes(self, version, ids):
        return {i: NODES[i] for i in ids if i in NODES}

    def entities(self, version, q, entity_type, limit):
        self.calls.append(('entities', q))
        if not q:
            items = [dict(n, relation_count=1) for n in NODES.values() if entity_type is None or n['type'] == entity_type]
            return items[:limit], len(items) > limit
        return [dict(NODES[TCB], relation_count=5)] if q in (TCB, 'tech') else [], False

    def neighborhood(self, version, entity_id, **kwargs):
        self.calls.append(('neighborhood', kwargs))
        return ([EDGE] if entity_id == TCB else []), self.truncated

    def relation(self, version, relation_id):
        if relation_id != EDGE['relation_id']:
            return None
        return {'subject_id': TCB, 'object_id': TCBS, 'relation': {
            'relation_id': EDGE['relation_id'], 'relation_type': 'HAS_SUBSIDIARY', 'as_of': '2025-12-31',
            'valid_from': None, 'valid_to': None, 'attributes_json': json.dumps(EDGE['attributes']),
            'evidence_json': json.dumps(EVIDENCE), 'reviewer': 'Trần Diệu Huyền',
            'reviewed_at': '2026-11-02T17:13:40+07:00', 'source_batch_id': 'wbs09:x',
            'corpus_id': 'c', 'index_version_id': 'i'}}


async def fake_lookup(chunk_ids):
    return {PDF_CHUNK: {'chunk_id': PDF_CHUNK, 'doc_type': 'ANNUAL_REPORT', 'title': 'TCB — BCTN 2025',
                        'source_url': 'https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/TCB_Baocaothuongnien_2025.pdf'},
            NEWS_CHUNK: {'chunk_id': NEWS_CHUNK, 'doc_type': 'NEWS', 'title': 'Tin', 'source_url': 'https://fireant.vn/bai-viet/x/1'}}


def client(reader, auth=True):
    app = FastAPI()
    app.include_router(graph_viewer.router)
    app.dependency_overrides[graph_viewer.get_graph_reader] = lambda: reader
    app.dependency_overrides[graph_viewer.get_ticker_map] = lambda: {TCB: 'TCB', TCBS: 'TCBS'}
    app.dependency_overrides[graph_viewer.get_source_lookup] = lambda: fake_lookup
    if auth:
        app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset({'RESEARCHER'}))
    return TestClient(app)


class GraphViewerApiTests(unittest.TestCase):
    def test_requires_login(self):
        self.assertEqual(client(FakeReader(), auth=False).get('/api/graph/versions').status_code, 401)

    def test_versions(self):
        body = client(FakeReader()).get('/api/graph/versions').json()
        self.assertEqual(body['versions'][0]['relation_count'], 13)

    def test_entity_search_resolves_ticker_through_registry(self):
        reader = FakeReader()
        body = client(reader).get('/api/graph/entities', params={'graph_version_id': V, 'q': 'tcb'}).json()
        self.assertEqual(reader.calls[0], ('entities', TCB))
        self.assertEqual(body['items'][0]['ticker'], 'TCB')

    def test_entity_list_without_keyword_is_scoped_and_bounded(self):
        class Reader(FakeReader):
            def entities(self, version, q, entity_type, limit):
                self.list_scope = (version, q, entity_type, limit)
                return super().entities(version, q, entity_type, limit)
        reader = Reader()
        response = client(reader).get('/api/graph/entities', params={
            'graph_version_id': V, 'type': 'Company', 'limit': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(reader.list_scope, (V, '', 'Company', 1))
        body = response.json()
        self.assertEqual(body['meta']['graph_version_id'], V)
        self.assertEqual(len(body['items']), 1)
        self.assertTrue(body['truncated'])

    def test_neighborhood_shape_matches_contract(self):
        reader = FakeReader()
        res = client(reader).get('/api/graph/neighborhood', params={
            'graph_version_id': V, 'entity_id': TCB, 'relation_type': 'HAS_SUBSIDIARY',
            'from': '2025-01-01', 'to': '2025-12-31'})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['meta']['graph_version_id'], V)
        self.assertFalse(body['meta']['truncated'])
        self.assertEqual({n['id'] for n in body['nodes']}, {TCB, TCBS})
        edge = body['edges'][0]
        self.assertEqual((edge['id'], edge['source'], edge['target']), ('review:bceddd14', TCB, TCBS))
        self.assertEqual(edge['temporal']['as_of'], '2025-12-31')
        self.assertEqual(edge['evidence_count'], 3)
        self.assertEqual(edge['evidence_preview']['page'], 154)
        kwargs = reader.calls[-1][1]
        self.assertEqual((kwargs['hops'], kwargs['relation_types'], kwargs['start']), (2, ['HAS_SUBSIDIARY'], '2025-01-01'))

    def test_empty_neighborhood_keeps_root(self):
        NODES['CMP-lonely'] = {'id': 'CMP-lonely', 'type': 'Company', 'label': 'Lonely', 'aliases': [], 'attributes': {}}
        try:
            body = client(FakeReader()).get('/api/graph/neighborhood', params={'graph_version_id': V, 'entity_id': 'CMP-lonely'}).json()
        finally:
            del NODES['CMP-lonely']
        self.assertEqual(([n['id'] for n in body['nodes']], body['edges']), (['CMP-lonely'], []))

    def test_truncated_flag(self):
        body = client(FakeReader(truncated=True)).get('/api/graph/neighborhood', params={'graph_version_id': V, 'entity_id': TCB}).json()
        self.assertTrue(body['meta']['truncated'])

    def test_error_codes(self):
        cases = [
            (FakeReader(), {'entity_id': 'CMP-unknown'}, 404, 'ENTITY_NOT_FOUND'),
            (FakeReader(status='BUILDING'), {'entity_id': TCB}, 409, 'GRAPH_VERSION_NOT_READY'),
            (FakeReader(status=None), {'entity_id': TCB}, 404, 'GRAPH_VERSION_NOT_FOUND'),
            (FakeReader(fail=ServiceUnavailable('down')), {'entity_id': TCB}, 503, 'GRAPH_UNAVAILABLE'),
            (FakeReader(fail=Neo4jError._hydrate_neo4j(code='Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration', message='t')),
             {'entity_id': TCB}, 504, 'GRAPH_TIMEOUT'),
            (FakeReader(), {'entity_id': TCB, 'relation_type': 'KNOWS'}, 400, 'INVALID_PARAMETER'),
            (FakeReader(), {'entity_id': TCB, 'from': '2025-13-01'}, 400, 'INVALID_PARAMETER'),
            (FakeReader(), {'entity_id': TCB, 'from': '2025-02-01', 'to': '2025-01-01'}, 400, 'INVALID_PARAMETER'),
        ]
        for reader, params, status, code in cases:
            res = client(reader).get('/api/graph/neighborhood', params={'graph_version_id': V, **params})
            self.assertEqual((res.status_code, res.json()['detail']['code']), (status, code), params)
        res = client(FakeReader()).get('/api/graph/neighborhood', params={'graph_version_id': V, 'entity_id': TCB, 'hops': 3})
        self.assertEqual(res.status_code, 422)

    def test_relation_detail_keeps_locator_and_never_invents_news_page(self):
        body = client(FakeReader()).get('/api/graph/relations/review:bceddd14', params={'graph_version_id': V}).json()
        self.assertEqual(body['relation']['review']['reviewer'], 'Trần Diệu Huyền')
        self.assertEqual(body['relation']['extraction']['source_batch_id'], 'wbs09:x')
        pdf, news, gone = body['evidence']
        self.assertEqual(pdf['locator'], EVIDENCE[0]['locator'])
        self.assertEqual(pdf['open'], {'status': 'AVAILABLE', 'kind': 'PDF_PAGE', 'page': 154, 'reason': None,
                                       'url': 'https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/TCB_Baocaothuongnien_2025.pdf'})
        self.assertEqual((news['open']['kind'], news['open']['page']), ('WEB_ARTICLE', None))
        self.assertEqual((gone['open']['status'], gone['open']['reason']), ('UNAVAILABLE', 'DOCUMENT_NOT_FOUND'))

    def test_unknown_relation(self):
        res = client(FakeReader()).get('/api/graph/relations/nope', params={'graph_version_id': V})
        self.assertEqual((res.status_code, res.json()['detail']['code']), (404, 'RELATION_NOT_FOUND'))


class FakeRetrieval:
    def __init__(self, paths):
        self.paths, self.limit = paths, None

    def query(self, entity_ids, **kwargs):
        self.limit = kwargs['limit']
        return self.paths[:kwargs['limit']]


class ReaderTests(unittest.TestCase):
    def test_source_versions_must_be_ready_before_reading_nodes(self):
        reader = GraphViewerReader(driver=None)
        reader._run = lambda cypher, **kw: ([{'graph_version_id': 'source', 'status': 'BUILDING', 'serving_scope': SOURCE_SCOPE}]
                                           if 'SourcePersonGraphVersion' in cypher else [])
        with self.assertRaises(VersionNotReady):
            reader.nodes('source', ['person'])

    def test_new_source_versions_are_discovered_without_cached_ids(self):
        reader = GraphViewerReader(driver=None)
        published = []
        reader._run = lambda cypher, **kw: list(published) if 'SourcePersonGraphVersion' in cypher else []
        self.assertEqual(reader.versions(), [])
        published.append({'graph_version_id': 'new-publication', 'status': 'READY', 'serving_scope': SOURCE_SCOPE})
        self.assertEqual(reader.versions()[0]['graph_version_id'], 'new-publication')

    def test_source_contract_direction_evidence_and_time_are_preserved(self):
        for kind in SOURCE_TYPES:
            row = {'subject_id': 'company' if kind in ('APPOINTS', 'DISMISSES') else 'person',
                   'object_id': 'person' if kind in ('APPOINTS', 'DISMISSES') else 'company',
                   'relation': {'key': 'claim:'+kind, 'relation_type': kind, 'evidence_json': json.dumps(EVIDENCE),
                                'source_report_year': '2025', 'identity_scope': 'SOURCE_OCCURRENCE',
                                'time_scope': 'SOURCE_DOCUMENT_NOT_CURRENT_OFFICE', 'source_review_status': 'APPROVED_IN_SOURCE_REPORT'}}
            edge = _source_edge(row)
            self.assertEqual((edge['subject_id'], edge['object_id']), (row['subject_id'], row['object_id']))
            self.assertEqual(edge['evidence'], EVIDENCE)
            self.assertEqual((edge['as_of'], edge['valid_from'], edge['valid_to']), (None, None, None))
            self.assertEqual(edge['review_status'], 'SOURCE_REVIEWED')

    def test_source_report_year_cannot_satisfy_effective_date_filter(self):
        reader = GraphViewerReader(driver=None)
        reader.ready_version = lambda version: {'serving_scope': SOURCE_SCOPE}
        reader._run = lambda *a, **kw: self.fail('must not infer calendar dates')
        self.assertEqual(reader.neighborhood('source', 'person', hops=2, relation_types=None,
                                            start='2025-01-01', end=None, limit=50), ([], False))

    def test_source_api_does_not_translate_symbol_to_global_entity_id(self):
        reader = FakeReader()
        reader.ready_version = lambda version: {'graph_version_id': version, 'status': 'READY', 'serving_scope': SOURCE_SCOPE}
        response = client(reader).get('/api/graph/entities', params={'graph_version_id': V, 'q': 'TCB'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(reader.calls[-1], ('entities', 'TCB'))
        self.assertEqual(response.json()['meta']['serving_scope'], SOURCE_SCOPE)

    def test_source_only_predicates_rejected_for_global_contract(self):
        response = client(FakeReader()).get('/api/graph/neighborhood', params={
            'graph_version_id': V, 'entity_id': TCB, 'relation_type': 'REQUESTS_RESIGNATION'})
        self.assertEqual(response.status_code, 400)

    def test_neighborhood_asks_one_extra_path_to_detect_truncation_and_dedups_edges(self):
        reader = GraphViewerReader(driver=None)
        reader.ready_version = lambda version: {'graph_version_id': version, 'status': 'READY'}
        reader.retrieval = FakeRetrieval([{'graph_version_id': V, 'relations': [EDGE]}] * 3)
        edges, truncated = reader.neighborhood(V, TCB, hops=2, relation_types=None, start=None, end=None, limit=2)
        self.assertEqual((reader.retrieval.limit, len(edges), truncated), (3, 1, True))


if __name__ == '__main__':
    unittest.main()
