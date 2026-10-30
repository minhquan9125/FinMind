"""Contract integration and regression tests; synthetic source explicitly marked."""
from copy import deepcopy
import hashlib
import unittest
from src.person_role.extractor import extract, normalize_and_extract
from src.person_role.contract.contracts import publishable_relations


def fixture(text):
    doc, index = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'
    chunk = '33333333-3333-4333-8333-333333333333'
    names = [('p', 'Person', 'Nguyễn Văn An'), ('c', 'Company', 'FPT'),
             ('p2', 'Person', 'Trần Văn Bình'), ('c2', 'Company', 'VCB')]
    entities, mentions = [], []
    for eid, kind, raw in names:
        if raw not in text:
            continue
        entities.append(dict(entity_id=eid, entity_type=kind, canonical_name=raw,
                             aliases=[raw], resolution_status='resolved', identity_key=eid, attributes={}))
        offset = 0
        while raw in text[offset:]:
            start = text.index(raw, offset)
            mentions.append(dict(mention_id=f'm:{eid}:{start}', entity_id=eid, document_id=doc,
                                 chunk_id=chunk, start=start, end=start+len(raw), raw_name=raw))
            offset = start+len(raw)
    return dict(schema_version='2.1.0', corpus_id='synthetic-test-only', dataset_version=index,
                documents=[dict(source_kind='db', document_id=doc, document_version='a'*64,
                                source_uri='fixture:synthetic', source_sha256='b'*64, index_version_id=index)],
                chunks=[dict(document_id=doc, document_version='a'*64, chunk_id=chunk, text=text,
                             locator=dict(kind='db_text_span', page=1, section_index=0, char_start=0,
                                          char_end=len(text), text_start=0, offset_basis='normalized_section_body',
                                          offset_unit='unicode_codepoint', content_hash=hashlib.sha256(text.encode()).hexdigest()))],
                entities=entities, mentions=mentions, relations=[])


class PersonRoleTests(unittest.TestCase):
    def test_repair_names_keeps_source_and_relations_consistent(self):
        from src.person_role.name_repair import repair_person_names
        data=fixture('FPT bổ nhiệm Ông Nguyễn Văn An Tổng Giám đốc.')
        data.update(entities=[],mentions=[],relations=[])
        from src.person_role.contract.entities import normalize
        data.update(normalize(data['chunks']))
        original=deepcopy(data)
        fixed,audit=repair_person_names(data,['Nguyễn Văn An'])
        people=[e for e in fixed['entities'] if e['entity_type']=='Person']
        self.assertEqual([e['aliases'] for e in people],[['Nguyễn Văn An']])
        self.assertEqual(data,original)
        self.assertEqual(fixed['chunks'],data['chunks'])
        self.assertFalse(audit['source_text_changed'])
        self.assertEqual(repair_person_names(fixed,['Nguyễn Văn An'])[0],fixed)

    def test_unverified_person_is_not_renamed_by_guess(self):
        from src.person_role.name_repair import repair_person_names
        data=fixture('Ông Nguyễn Văn An Tổng Giám đốc.')
        fixed,_=repair_person_names(data,[])
        self.assertFalse([e for e in fixed['entities'] if e['entity_type']=='Person'])

    def test_review_envelope_valid_pending_and_never_published(self):
        from src.person_role.review import review_source,build_review_envelope
        text='FPT | BCTN | trang 1\nÔng Nguyễn Văn An Tổng giám đốc (bổ nhiệm từ 1/1/2024)'
        data=fixture(text);data.update(entities=[],mentions=[],relations=[])
        chunk=data['chunks'][0];loc=chunk['locator'];loc.update(text_start=text.index('\n')+1,char_end=len(text)-text.index('\n')-1)
        source=dict(content_hash=loc['content_hash'],corpus_version_id=data['corpus_id'],
                    index_version_id=data['dataset_version'],document_id=chunk['document_id'],chunk_id=chunk['chunk_id'],
                    page_number=1,locator_json={'symbol':'FPT'})
        items=review_source(text,source)
        result,audit=build_review_envelope(data,items)
        self.assertEqual(len(result['relations']),1)
        self.assertEqual(result['relations'][0]['relation_type'],'APPOINTS')
        self.assertEqual(result['relations'][0]['review']['status'],'PENDING')
        self.assertFalse(result['relations'][0]['attributes']['organization_link_verified'])
        self.assertEqual(publishable_relations(result),[])
        self.assertEqual([e['aliases'] for e in result['entities'] if e['entity_type']=='Person'],[['Nguyễn Văn An']])
        self.assertEqual(build_review_envelope(data,items),(result,audit))
        items[0]['position_raw']='wrong'
        with self.assertRaises(ValueError):build_review_envelope(data,items)

    def test_review_request_not_coerced_to_contract_holds_role(self):
        from src.person_role.review import review_source,build_review_envelope
        text='FPT | BCTN\nÔng Nguyễn Văn An Tổng giám đốc xin từ nhiệm'
        data=fixture(text);data.update(entities=[],mentions=[],relations=[])
        chunk=data['chunks'][0];loc=chunk['locator'];loc.update(text_start=text.index('\n')+1,char_end=len(text)-text.index('\n')-1)
        source=dict(content_hash=loc['content_hash'],corpus_version_id=data['corpus_id'],index_version_id=data['dataset_version'],
                    document_id=chunk['document_id'],chunk_id=chunk['chunk_id'],page_number=1,locator_json={'symbol':'FPT'})
        items=review_source(text,source)
        self.assertEqual(items[0]['proposed_stage'],'RESIGNATION_REQUESTED')
        self.assertEqual(build_review_envelope(data,items)[0]['relations'],[])

    def test_role_heading_not_resolved_to_wrong_company(self):
        from src.person_role.extractor import scoped_registry
        registry=[dict(entity_id='wrong-org',entity_type='Company',canonical_name='Tập đoàn Hoa Sen',
                       identity_key='name:hoa-sen',verified=True,aliases=['HĐQT','Hoa Sen'])]
        original=deepcopy(registry)
        cleaned,excluded=scoped_registry(registry)
        self.assertEqual(registry,original)
        self.assertEqual(cleaned[0]['aliases'],['Hoa Sen'])
        self.assertEqual(excluded[0]['alias'],'HĐQT')
        data=fixture('Ông Nguyễn Văn An là Chủ tịch HĐQT.')
        data.update(entities=[],mentions=[],relations=[])
        result,_=normalize_and_extract(data,registry)
        self.assertNotIn('wrong-org',[e['entity_id'] for e in result['entities']])

    def test_shared_normalizer_and_identity_preservation(self):
        data = fixture('Công ty FPT bổ nhiệm Ông Nguyễn Văn An giữ chức Tổng giám đốc.')
        data.update(entities=[], mentions=[], relations=[])
        result, _ = normalize_and_extract(data)
        from src.person_role.contract.entities import normalize
        normalized = normalize(data['chunks'])
        self.assertEqual(result['entities'], normalized['entities'])
        self.assertEqual(result['mentions'], normalized['mentions'])
        with self.assertRaises(ValueError):
            normalize_and_extract(result)

    def test_appointment_direction_and_raw_title(self):
        data = fixture('FPT bổ nhiệm ông Nguyễn Văn An giữ chức Phó Tổng giám đốc từ 3/8/2026.')
        original = deepcopy(data)
        result, audit = extract(data)
        self.assertEqual(data, original)
        r, = result['relations']
        self.assertEqual((r['relation_type'], r['subject_id'], r['object_id']), ('APPOINTS', 'c', 'p'))
        self.assertEqual(r['attributes']['position'], 'Phó Tổng giám đốc')
        self.assertEqual(r['attributes']['position_code'], 'DEPUTY_CEO')
        self.assertEqual(r['attributes']['effective_date_proposed'], '2026-08-03')
        self.assertIsNone(r['temporal']['valid_from'])
        self.assertEqual(publishable_relations(result), [])
        self.assertEqual(audit['candidate_count'], 1)

    def test_holds_at_source_not_current(self):
        result, _ = extract(fixture('Ông Nguyễn Văn An là Chủ tịch HĐQT FPT.'))
        r, = result['relations']
        self.assertEqual((r['relation_type'], r['subject_id'], r['object_id']), ('HOLDS_ROLE', 'p', 'c'))
        self.assertEqual(r['attributes']['event_stage'], 'ROLE_AT_SOURCE_TIME')
        self.assertIsNone(r['temporal']['as_of'])

    def test_dismissal_direction(self):
        result, _ = extract(fixture('FPT miễn nhiệm ông Nguyễn Văn An khỏi chức Kế toán trưởng.'))
        self.assertEqual(result['relations'][0]['relation_type'], 'DISMISSES')

    def test_uncertain_phrases_abstain(self):
        for phrase in ['xin từ nhiệm', 'đơn từ nhiệm', 'dự kiến bổ nhiệm', 'nếu bổ nhiệm',
                       'sẽ bổ nhiệm', 'không bổ nhiệm', 'chưa bổ nhiệm', 'đề cử', 'ứng cử']:
            with self.subTest(phrase=phrase):
                result, audit = extract(fixture(f'FPT {phrase} ông Nguyễn Văn An chức Tổng giám đốc.'))
                self.assertFalse(result['relations'])
                self.assertEqual(audit['abstentions'][0]['reason'], 'UNCONFIRMED_OR_NEGATED')

    def test_actual_resignation_not_dismissal_or_holds(self):
        result, audit = extract(fixture('Ông Nguyễn Văn An từ nhiệm chức Tổng giám đốc FPT.'))
        self.assertFalse(result['relations'])
        self.assertEqual(audit['abstentions'][0]['reason'], 'RESIGNATION_REQUIRES_EVENT_CONTRACT')

    def test_ambiguity(self):
        for text in ['FPT bổ nhiệm Nguyễn Văn An và Trần Văn Bình chức Tổng giám đốc.',
                     'FPT và VCB bổ nhiệm Nguyễn Văn An chức Tổng giám đốc.',
                     'FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc kiêm Kế toán trưởng.',
                     'FPT bổ nhiệm chức Tổng giám đốc.', 'Nguyễn Văn An giữ chức Tổng giám đốc.']:
            with self.subTest(text=text):
                self.assertFalse(extract(fixture(text))[0]['relations'])

    def test_two_explicit_independent_clauses(self):
        text = 'FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc; VCB miễn nhiệm Trần Văn Bình chức Kế toán trưởng'
        result, _ = extract(fixture(text))
        self.assertEqual(len(result['relations']), 2)
        for r in result['relations']:
            quote = r['evidence'][0]['quote']
            a = r['attributes']
            self.assertEqual(text[a['evidence_start']:a['evidence_end']], quote)

    def test_invalid_and_multiple_dates(self):
        for tail in ['từ 31/2/2026', 'từ 1/1/2026 đến từ 2/2/2026']:
            self.assertFalse(extract(fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc '+tail))[0]['relations'])

    def test_missing_year_not_inferred(self):
        r = extract(fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc từ 22/9.'))[0]['relations'][0]
        self.assertIsNone(r['attributes']['effective_date_proposed'])

    def test_deterministic_and_existing_review_protected(self):
        data = fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc.')
        self.assertEqual(extract(data), extract(data))
        result, _ = extract(data)
        with self.assertRaises(ValueError):
            extract(result)

    def test_tampered_text_or_hash_rejected(self):
        data = fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc.')
        data['chunks'][0]['locator']['content_hash'] = 'f'*64
        with self.assertRaises(ValueError):
            extract(data)

    def test_no_fake_page(self):
        data = fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc.')
        data['chunks'][0]['locator']['page'] = None
        with self.assertRaises(ValueError):
            extract(data)

    def test_header_company_not_attributed_to_body(self):
        text = 'FPT báo cáo\nNguyễn Văn An giữ chức Tổng giám đốc.'
        data = fixture(text)
        loc = data['chunks'][0]['locator']
        loc.update(text_start=text.index('\n')+1, char_end=len(text)-text.index('\n')-1)
        self.assertFalse(extract(data)[0]['relations'])

    def test_unresolved_never_published(self):
        data = fixture('FPT bổ nhiệm Nguyễn Văn An chức Tổng giám đốc.')
        data['entities'][0].update(resolution_status='unresolved', canonical_name=None, identity_key=None)
        result, _ = extract(data)
        self.assertEqual(publishable_relations(result), [])
        result['relations'][0]['review'].update(status='APPROVED', reviewer='tester', reviewed_at='2026-10-28T00:00:00Z')
        with self.assertRaises(ValueError):
            publishable_relations(result)


if __name__ == '__main__':
    unittest.main()
