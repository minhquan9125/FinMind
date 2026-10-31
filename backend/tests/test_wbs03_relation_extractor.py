"""Focused contract and wording tests; no database is accessed."""

import unittest

from backend.src.sprint4_runtime.relation_extractor import extract_candidates


REGISTRY = [
    {'entity_id': 'company:alpha', 'entity_type': 'Company', 'canonical_name': 'Alpha Việt',
     'aliases': ['Alpha Việt'], 'ticker_aliases': [], 'identity_key': 'name:alpha viet', 'verified': True},
    {'entity_id': 'company:beta', 'entity_type': 'Company', 'canonical_name': 'Beta Việt',
     'aliases': ['Beta Việt'], 'ticker_aliases': [], 'identity_key': 'name:beta viet', 'verified': True},
]


def envelope(text):
    return {'schema_version': '2.0.0', 'corpus_id': 'test', 'dataset_version': 'test',
            'documents': [{'document_id': 'doc:' + 'a' * 64, 'document_version': 'b' * 64,
                           'source_sha256': 'a' * 64, 'extraction_sha256': 'b' * 64,
                           'source_path': 'test.pdf', 'extraction_path': 'test.json'}],
            'chunks': [{'document_id': 'doc:' + 'a' * 64, 'document_version': 'b' * 64,
                        'chunk_id': 'p1:b1', 'text': text,
                        'locator': {'page': 1, 'block_id': 'p1:b1', 'bbox': [0, 0, 1, 1]}}],
            'entities': [], 'mentions': [], 'relations': []}


class RelationExtractorTests(unittest.TestCase):
    def test_ownership_direction_and_percent(self):
        result = extract_candidates(envelope('Alpha Việt sở hữu 65,5% cổ phần Beta Việt.'), REGISTRY)
        self.assertEqual(len(result['relations']), 1)
        relation = result['relations'][0]
        self.assertEqual((relation['relation_type'], relation['subject_id'], relation['object_id']),
                         ('OWNS_SHARES', 'company:alpha', 'company:beta'))
        self.assertEqual(relation['attributes']['ownership_percent'], '65.5')
        self.assertEqual(relation['review']['status'], 'PENDING')
        self.assertEqual(relation['evidence'][0]['quote'], result['chunks'][0]['text'])

    def test_subsidiary_reverse_direction(self):
        result = extract_candidates(envelope('Beta Việt là công ty con của Alpha Việt.'), REGISTRY)
        self.assertEqual([(r['relation_type'], r['subject_id'], r['object_id']) for r in result['relations']],
                         [('HAS_SUBSIDIARY', 'company:alpha', 'company:beta')])

    def test_associate_reverse_direction(self):
        result = extract_candidates(envelope('Beta Việt là công ty liên kết của Alpha Việt.'), REGISTRY)
        self.assertEqual(result['relations'][0]['relation_type'], 'HAS_ASSOCIATE')
        self.assertEqual(result['relations'][0]['subject_id'], 'company:alpha')

    def test_cooperation_symmetric_and_deduplicated(self):
        result = extract_candidates(envelope('Beta Việt hợp tác với Alpha Việt. Alpha Việt hợp tác với Beta Việt.'), REGISTRY)
        self.assertEqual(len(result['relations']), 1)
        relation = result['relations'][0]
        self.assertEqual((relation['subject_id'], relation['object_id']), ('company:alpha', 'company:beta'))
        self.assertEqual(len(relation['evidence']), 2)

    def test_cooperation_after_both_names(self):
        result = extract_candidates(envelope('Alpha Việt và Beta Việt đã ký thỏa thuận hợp tác phân phối.'), REGISTRY)
        self.assertEqual(result['relations'][0]['relation_type'], 'COOPERATES_WITH')

    def test_ownership_percent_after_company_and_explicit_day(self):
        result = extract_candidates(envelope('Alpha Việt sở hữu Beta Việt với tỷ lệ 65.5% kể từ 2024-01-02.'), REGISTRY)
        self.assertEqual(result['relations'][0]['attributes']['ownership_percent'], '65.5')
        self.assertEqual(result['relations'][0]['temporal']['as_of'], '2024-01-02')

    def test_no_relation_for_negation_plan_or_cooccurrence(self):
        for text in ('Alpha Việt không sở hữu Beta Việt.',
                     'Alpha Việt dự kiến hợp tác với Beta Việt.',
                     'Alpha Việt luôn giữ vị thế tiên phong trước Beta Việt.',
                     'Alpha Việt nắm giữ vị thế của Beta Việt.',
                     'Alpha Việt sở hữu lợi thế cạnh tranh tiên phong.',
                     'Alpha Việt về Chủ sở hữu – Beta Việt trong năm 2024.',
                     'Alpha Việt và Beta Việt cùng xuất hiện trong báo cáo.'):
            with self.subTest(text=text):
                self.assertEqual(extract_candidates(envelope(text), REGISTRY)['relations'], [])

    def test_unknown_name_not_promoted_to_relation(self):
        self.assertEqual(extract_candidates(envelope('Alpha Việt hợp tác với Gamma Việt.'), REGISTRY)['relations'], [])

    def test_appositive_code_uses_document_abbreviation(self):
        registry = REGISTRY + [
            {'entity_id': 'company:bank', 'entity_type': 'Company',
             'canonical_name': 'Ngân hàng TMCP Đầu tư Alpha', 'aliases': ['Ngân hàng TMCP Đầu tư Alpha'],
             'ticker_aliases': [], 'identity_key': 'name:bank', 'verified': True},
            {'entity_id': 'company:bic', 'entity_type': 'Company',
             'canonical_name': 'Tổng Công ty Cổ phần Bảo hiểm Alpha', 'aliases': ['BIC'],
             'ticker_aliases': ['BIC'], 'identity_key': 'name:bic', 'verified': True}]
        text = ('Ngân hàng TMCP Đầu tư Alpha (BIDV) công bố.\n'
                'Hợp đồng bảo hiểm trách nhiệm (BIC- Công ty con của BIDV)')
        result = extract_candidates(envelope(text), registry)
        self.assertEqual([(r['relation_type'], r['subject_id'], r['object_id']) for r in result['relations']],
                         [('HAS_SUBSIDIARY', 'company:bank', 'company:bic')])
        self.assertEqual(result['relations'][0]['evidence'][0]['quote'], 'BIC- Công ty con của BIDV')
        # Without the document's own "(BIDV)" definition the owner is unknown.
        self.assertEqual(extract_candidates(envelope('(BIC- Công ty con của BIDV)'), registry)['relations'], [])

    def test_passive_owner_with_percent(self):
        registry = REGISTRY + [{'entity_id': 'company:vcbl', 'entity_type': 'Company',
                                'canonical_name': 'Công ty TNHH Cho thuê Alpha', 'aliases': ['VCBL'],
                                'ticker_aliases': [], 'identity_key': 'name:vcbl', 'verified': True},
                               {'entity_id': 'company:alpha2', 'entity_type': 'Company',
                                'canonical_name': 'Alphabank', 'aliases': ['Alphabank'],
                                'ticker_aliases': [], 'identity_key': 'name:alphabank', 'verified': True}]
        cases = {'VCBL là công ty con do Alphabank nắm giữ 87,5% vốn.': ('HAS_SUBSIDIARY', '87.5'),
                 'VCBL là Công ty do Alphabank sở hữu 100% vốn.': ('OWNS_SHARES', '100')}
        for text, (kind, percent) in cases.items():
            with self.subTest(text=text):
                relation, = extract_candidates(envelope(text), registry)['relations']
                self.assertEqual((relation['relation_type'], relation['subject_id'], relation['object_id']),
                                 (kind, 'company:alpha2', 'company:vcbl'))
                self.assertEqual(relation['attributes']['ownership_percent'], percent)
        blocked = 'VCBL không còn là công ty con do Alphabank sở hữu 100% vốn.'
        self.assertEqual(extract_candidates(envelope(blocked), registry)['relations'], [])

    def test_cooperation_between_exactly_two_named_parties(self):
        relation, = extract_candidates(envelope('Dự án hợp tác giữa Alpha Việt và Beta Việt triển khai.'),
                                       REGISTRY)['relations']
        self.assertEqual((relation['relation_type'], relation['subject_id'], relation['object_id']),
                         ('COOPERATES_WITH', 'company:alpha', 'company:beta'))
        self.assertEqual(relation['evidence'][0]['quote'], 'hợp tác giữa Alpha Việt và Beta Việt')
        joint, = extract_candidates(envelope('Công ty liên doanh giữa Alpha Việt với Beta Việt.'),
                                    REGISTRY)['relations']
        self.assertEqual(joint['attributes'], {'cooperation_scope': 'liên doanh'})
        for text in ('hợp tác giữa hai bên.',
                     'liên doanh giữa Alpha Việt, Beta Việt và Gamma.',
                     'liên doanh giữa Alpha Việt và Beta Việt và Gamma.',
                     'hợp tác giữa Alpha Việt và Beta Việt Holdings.',
                     'Dự kiến hợp tác giữa Alpha Việt và Beta Việt.'):
            with self.subTest(text=text):
                self.assertEqual(extract_candidates(envelope(text), REGISTRY)['relations'], [])

    def test_common_alias_does_not_become_company_relation(self):
        misleading = {'entity_id': 'company:pioneer', 'entity_type': 'Company',
                      'canonical_name': 'Công ty Cổ phần Công nghệ Tiên Phong',
                      'aliases': ['tiên phong'], 'ticker_aliases': [],
                      'identity_key': 'name:tien phong', 'verified': True}
        result = extract_candidates(envelope('Alpha Việt sở hữu lợi thế cạnh tranh tiên phong.'),
                                    REGISTRY + [misleading])
        self.assertEqual(result['relations'], [])


if __name__ == '__main__':
    unittest.main()
