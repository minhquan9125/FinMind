import hashlib
import unittest
import json
from pathlib import Path
from src.person_role.review import review_source


def review(text):
    return review_source(text, dict(content_hash=hashlib.sha256(text.encode()).hexdigest(),
        corpus_version_id='test',index_version_id='test',document_id='doc',chunk_id='chunk',
        page_number=None,locator_json={'symbol':'FPT'}))


class ReviewTests(unittest.TestCase):
    def test_adjacent_honorifics_never_glue_people(self):
        from src.person_role.review import names
        text='Ông Lê Hoàng Tùng Ông Nguyễn Mạnh Hùng Thành viên HĐQT'
        self.assertEqual([text[s:e] for s,e in names(text)],['Lê Hoàng Tùng','Nguyễn Mạnh Hùng'])

    def test_exact_names_and_positions_without_swallowing_title(self):
        text='Ông Nguyễn Văn An Tổng Giám đốc; Bà Trần Thị Bình Kế toán trưởng (miễn nhiệm từ 19/05/2023)'
        items=review(text)
        self.assertEqual([r['person_raw'] for r in items],['Nguyễn Văn An','Trần Thị Bình'])
        self.assertEqual(items[1]['proposed_stage'],'DISMISSED')
        for r in items:
            e=r['evidence']
            self.assertEqual(text[e['start']:e['end']],e['quote'])
            s=r['person_span'];self.assertEqual(text[s['start']:s['end']],r['person_raw'])
            s=r['position_span'];self.assertEqual(text[s['start']:s['end']],r['position_raw'])
            self.assertFalse(r['publish_allowed'])
            self.assertIsNone(r['organization_canonical_id'])

    def test_request_and_actual_resignation_differ(self):
        for phrase,stage in [('xin từ nhiệm','RESIGNATION_REQUESTED'),('từ nhiệm','RESIGNED')]:
            item=review(f'Bà Trần Thị Bình Kế toán trưởng {phrase} từ ngày 1 tháng 11 năm 2024')[0]
            self.assertEqual(item['proposed_stage'],stage)
            self.assertEqual(item['date_mentions'][0]['proposed_date'],'2024-11-01')

    def test_does_not_invent_missing_year_or_page(self):
        r=review('Ông Nguyễn Văn An Phó TGĐ bổ nhiệm từ 22/9')[0]
        self.assertEqual(r['position_code'],'DEPUTY_CEO')
        self.assertEqual(r['date_mentions'],[])
        self.assertIsNone(r['evidence']['page'])

    def test_multiple_positions_marked(self):
        r=review('Ông Nguyễn Văn An Giám đốc tài chính kiêm Kế toán trưởng')[0]
        self.assertIn('MULTIPLE_POSITIONS_IN_WINDOW',r['limitations'])

    def test_compound_roles_each_have_exact_span(self):
        text='Ông Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc'
        items=review(text)
        self.assertEqual([i['position_code'] for i in items],['BOARD_MEMBER','DEPUTY_CEO'])
        self.assertEqual(len({i['review_item_id'] for i in items}),2)
        for item in items:
            span=item['position_span']
            self.assertEqual(text[span['start']:span['end']],item['position_raw'])

    def test_compound_event_not_transferred_to_other_position(self):
        items=review('Ông Nguyễn Văn An Thành viên HĐQT/Phó Tổng Giám đốc (miễn nhiệm từ 19/05/2023)')
        self.assertEqual([i['proposed_stage'] for i in items],['ROLE_AT_SOURCE_TIME','DISMISSED'])
        self.assertEqual(items[0]['date_mentions'],[])
        self.assertIn('COMPOUND_ROLE_EVENT_SCOPE_REQUIRES_REVIEW',items[0]['limitations'])

    def test_other_company_title_not_assigned_to_person(self):
        items=review('Ông Nguyễn Văn An Tổng Giám đốc Công ty FPT; Kế toán trưởng Công ty ELC')
        self.assertEqual(len(items),1)

    def test_hash_mismatch_blocks(self):
        with self.assertRaises(ValueError):
            review_source('changed',{'content_hash':'0'*64})

    def test_no_person_no_item(self):
        self.assertEqual(review('Quy định đề cử thành viên HĐQT'),[])

    def test_deterministic(self):
        text='Ông Nguyễn Văn An là Tổng giám đốc FPT'
        self.assertEqual(review(text),review(text))

    def real(self, sample_id):
        path=Path(__file__).resolve().parents[2]/'outputs/person-role-step1-2-20261028/real_source_samples.json'
        if not path.exists():
            self.skipTest('Prepared real source fixture is not distributed with this checkout')
        sample=next(s for s in json.loads(path.read_text('utf-8'))['samples'] if s['sample_id']==sample_id)
        return review_source(sample['chunk_text'],sample['source'])

    def test_real_ocr_dismissal_does_not_leak_to_next_row(self):
        items=self.real('PR-02')
        minh=next(r for r in items if r['person_raw']=='Đặng Thị Thanh Minh')
        thien=next(r for r in items if r['person_raw']=='Nguyễn Đức Thiện')
        self.assertEqual(minh['proposed_stage'],'DISMISSED')
        self.assertNotEqual(thien['proposed_stage'],'DISMISSED')

    def test_real_request_attaches_to_named_applicant(self):
        items=self.real('PR-05')
        self.assertEqual([(r['person_raw'],r['proposed_stage']) for r in items],
                         [('Phạm Thị Thơm','RESIGNATION_REQUESTED')])

    def test_real_two_people_have_distinct_events(self):
        items=self.real('PR-18')
        self.assertEqual([(r['person_raw'],r['proposed_stage']) for r in items],
                         [('Nguyễn Thị Minh Hiếu','DISMISSED'),('Nguyễn Thị Minh Hiếu','DISMISSED'),
                          ('Nguyễn Thị Thu Hằng','APPOINTED')])

    def test_real_policy_has_no_named_role(self):
        for sid in ['PR-10','PR-11','PR-12','PR-13','PR-14','PR-20']:
            with self.subTest(sample=sid):self.assertEqual(self.real(sid),[])


if __name__=='__main__':unittest.main()
