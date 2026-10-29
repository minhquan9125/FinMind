"""The adapter preserves the verified CTG sample supplied with contract 2.1.0."""

import hashlib
import json
import unittest
from pathlib import Path

from backend.src.sprint4_runtime.db_adapter import document_envelope
from backend.src.sprint4_runtime.relation_extractor import extract_candidates
from backend.tests.test_wbs03_relation_extractor import REGISTRY


SAMPLE = Path(__file__).with_name('fixtures') / 'wbs03_db_ctg_chunk.json'


class DbAdapterTests(unittest.TestCase):
    def make_row(self):
        payload = json.loads(SAMPLE.read_text(encoding='utf-8'))
        document, chunk = payload['documents'][0], payload['chunks'][0]
        row = {'document_id': document['document_id'], 'title': document['title'],
               'doc_type': document['doc_type'], 'database_document_sha256': document['database_document_sha256'],
               'index_version_id': document['index_version_id'], 'document_version': document['source_sha256'],
               'chunk_id': chunk['chunk_id'],
               'text': chunk['text'], 'content_hash': chunk['locator']['content_hash'],
               'page_number': chunk['locator']['page'], 'char_start': chunk['locator']['char_start'],
               'char_end': chunk['locator']['char_end'],
               'source_binding': {'source_uri': document['source_uri'], 'source_sha256': document['source_sha256']},
               'locator_json': {'pdf_page': chunk['locator']['page'],
                                'reconstruction': {'source_view_sha256': document['document_version'],
                                                   'section_index': chunk['locator']['section_index'],
                                                   'char_start': chunk['locator']['char_start'],
                                                   'char_end': chunk['locator']['char_end']}}}
        return payload, row

    def test_matches_official_sample(self):
        expected, row = self.make_row()
        actual = document_envelope([row], expected['corpus_id'])
        self.assertEqual(actual['chunks'][0]['locator'], expected['chunks'][0]['locator'])
        self.assertEqual(actual['chunks'][0]['text'], expected['chunks'][0]['text'])
        self.assertEqual(actual['chunks'][0]['document_version'], expected['documents'][0]['source_sha256'])
        for key, value in actual['documents'][0].items():
            if key not in ('document_version', 'source_sections'):
                self.assertEqual(value, expected['documents'][0][key])
        self.assertEqual(actual['documents'][0]['source_sections'][0]['source_view_sha256'],
                         expected['documents'][0]['document_version'])
        self.assertEqual(actual['corpus_id'], expected['corpus_id'])

    def test_accepts_two_sections_with_one_document_version(self):
        expected, row = self.make_row()
        other = dict(row, chunk_id='00000000-0000-4000-8000-000000000001',
                     page_number=2, text='CTG | Báo cáo thường niên 2024 | PDF trang 2\nTrang hai.',
                     char_end=len('Trang hai.'),
                     locator_json={'pdf_page': 2,
                                   'reconstruction': {'section_index': 1, 'char_start': 0,
                                                      'char_end': len('Trang hai.'),
                                                      'source_view_sha256': 'f' * 64}})
        other['content_hash'] = hashlib.sha256(other['text'].encode()).hexdigest()
        result = document_envelope([row, other], expected['corpus_id'])
        self.assertEqual(len(result['chunks']), 2)
        self.assertEqual({c['document_version'] for c in result['chunks']}, {row['document_version']})
        self.assertEqual(len(result['documents'][0]['source_sections']), 2)

    def test_rejects_mixed_source_snapshot(self):
        expected, row = self.make_row()
        other = dict(row, document_version='f' * 64)
        with self.assertRaisesRegex(ValueError, 'Mixed document/source snapshot'):
            document_envelope([row, other], expected['corpus_id'])

    def test_rejects_offset_mismatch(self):
        expected, row = self.make_row()
        row['char_end'] += 1
        with self.assertRaisesRegex(ValueError, 'offsets differ'):
            document_envelope([row], expected['corpus_id'])

    def test_db_contract_to_pending_candidate_with_synthetic_text(self):
        expected, row = self.make_row()
        header = row['text'].split('\n', 1)[0]
        body = 'Alpha Việt sở hữu 65% cổ phần Beta Việt.'
        row['text'] = header + '\n' + body
        row['char_end'] = len(body)
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode('utf-8')).hexdigest()
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY)
        self.assertEqual(len(result['relations']), 1)
        self.assertEqual(result['relations'][0]['review']['status'], 'PENDING')
        self.assertEqual(result['relations'][0]['evidence'][0]['chunk_id'], row['chunk_id'])

    def test_issuer_context_for_explicit_subsidiary_heading(self):
        expected, row = self.make_row()
        body = 'công ty con kiểm soát trực tiếp Beta Việt'
        row.update(company_id='00000000-0000-4000-8000-000000000002',
                   issuer_symbol='CTG', issuer_company_name='Alpha Việt',
                   text=row['text'].split('\n', 1)[0] + '\n' + body, char_end=len(body))
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode()).hexdigest()
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY)
        relation = result['relations'][0]
        self.assertEqual((relation['relation_type'], relation['subject_id'], relation['object_id']),
                         ('HAS_SUBSIDIARY', 'company:alpha', 'company:beta'))
        self.assertEqual(relation['attributes']['inference_basis'], 'document_issuer')
        self.assertEqual(relation['review']['status'], 'PENDING')

    def test_issuer_context_requires_verified_registry_identity(self):
        expected, row = self.make_row()
        body = 'công ty con kiểm soát trực tiếp Beta Việt'
        row.update(company_id='00000000-0000-4000-8000-000000000002',
                   issuer_symbol='CTG', issuer_company_name='Tên chưa có trong registry',
                   text=row['text'].split('\n', 1)[0] + '\n' + body, char_end=len(body))
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode()).hexdigest()
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY)
        self.assertEqual(result['relations'], [])

    def test_generic_legal_form_is_not_a_company_endpoint(self):
        expected, row = self.make_row()
        body = 'công ty con kiểm soát gián tiếp Công ty Cổ phần'
        row.update(company_id='00000000-0000-4000-8000-000000000002',
                   issuer_symbol='CTG', issuer_company_name='Alpha Việt',
                   text=row['text'].split('\n', 1)[0] + '\n' + body, char_end=len(body))
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode()).hexdigest()
        generic = {'entity_id': 'company:generic', 'entity_type': 'Company',
                   'canonical_name': 'CÔNG TY CỔ PHẦN', 'aliases': ['Công ty Cổ phần'],
                   'ticker_aliases': [], 'identity_key': 'name:cong ty co phan', 'verified': True}
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY + [generic])
        self.assertEqual(result['relations'], [])

    def test_short_common_alias_is_not_subsidiary(self):
        expected, row = self.make_row()
        body = 'CÁC CÔNG TY CON Quỹ'
        row.update(company_id='00000000-0000-4000-8000-000000000002',
                   issuer_symbol='CTG', issuer_company_name='Alpha Việt',
                   text=row['text'].split('\n', 1)[0] + '\n' + body, char_end=len(body))
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode()).hexdigest()
        misleading = {'entity_id': 'company:fund', 'entity_type': 'Company',
                      'canonical_name': 'Tập đoàn trích lập quỹ khen thưởng, phúc lợi',
                      'aliases': ['Quỹ'], 'ticker_aliases': [],
                      'identity_key': 'name:quy', 'verified': True}
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY + [misleading])
        self.assertEqual(result['relations'], [])

    def test_unresolved_full_legal_name_remains_pending_for_review(self):
        expected, row = self.make_row()
        body = 'Các công ty con kiểm soát gián tiếp Công ty Cổ phần Đầu tư Smortek'
        row.update(company_id='00000000-0000-4000-8000-000000000002',
                   issuer_symbol='CTG', issuer_company_name='Alpha Việt',
                   text=row['text'].split('\n', 1)[0] + '\n' + body, char_end=len(body))
        row['locator_json']['reconstruction']['char_end'] = len(body)
        row['content_hash'] = hashlib.sha256(row['text'].encode()).hexdigest()
        result = extract_candidates(document_envelope([row], expected['corpus_id']), REGISTRY)
        self.assertEqual(len(result['relations']), 1)
        relation = result['relations'][0]
        self.assertEqual(relation['review']['status'], 'PENDING')
        target = next(e for e in result['entities'] if e['entity_id'] == relation['object_id'])
        self.assertEqual(target['resolution_status'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
