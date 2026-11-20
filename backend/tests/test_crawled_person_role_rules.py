import unittest,hashlib
from src.person_role.rules_pipeline import extract_record
def run(text,**kw):return extract_record(dict(text=text,symbol='ELC',source_kind='annual_report',**kw))
class PipelineTests(unittest.TestCase):
 def test_compound_roles_and_exact_unicode_offsets(self):
  text='HĐQT\nÔng Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc'
  r=run(text);self.assertEqual([x['position_code'] for x in r['candidates']],['BOARD_MEMBER','DEPUTY_CEO'])
  for x in r['candidates']:
   self.assertEqual(text[x['name_span']['start']:x['name_span']['end']],x['name'])
   self.assertEqual(text[x['position_span']['start']:x['position_span']['end']],x['position_raw'])
   self.assertEqual(text[x['evidence']['start']:x['evidence']['end']],x['evidence']['quote'])
 def test_dismissal_not_current(self):
  r=run('Kế toán trưởng\nBà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023)')['candidates'][0]
  self.assertEqual((r['name'],r['stage'],r['subject'],r['effective_date']),('Đặng Thị Thanh Minh','DISMISSED','ELC','2023-05-19'))
  self.assertFalse(r['current_employment_confirmed'])
 def test_vice_title_not_ceo_or_chair(self):
  r=run('Danh sách\nÔng Nguyễn Văn An Phó Chủ tịch HĐQT')['candidates'][0]
  self.assertEqual(r['position_code'],'DEPUTY_BOARD_CHAIR')
 def test_decision_date_not_effective(self):
  r=run('Danh sách\nÔng Nguyễn Văn An Phó TGĐ bổ nhiệm theo quyết định ngày 18/04/2025')['candidates'][0]
  self.assertIsNone(r['effective_date']);self.assertEqual(r['date_mentions'][0]['meaning'],'DECISION_DATE')
 def test_resignation_request_is_not_dismissal(self):
  r=run('Danh sách\nBà Phạm Thị Thơm Thành viên BKS xin từ nhiệm từ 01/11/2025')['candidates'][0]
  self.assertEqual(r['stage'],'RESIGNATION_REQUESTED')
 def test_invalid_calendar_date_quarantined(self):
  r=run('Danh sách\nÔng Nguyễn Văn An Tổng Giám đốc bổ nhiệm từ 31/02/2025')
  self.assertFalse(r['candidates']);self.assertEqual(r['quarantine'][0]['reason'],'INVALID_OR_AMBIGUOUS_DATE')
 def test_no_year_invention(self):
  r=run('Danh sách\nÔng Nguyễn Văn An Tổng Giám đốc bổ nhiệm từ 22/9')['candidates'][0]
  self.assertIsNone(r['effective_date'])
 def test_mixed_people_not_nearest_name(self):
  r=run('HĐQT\nÔng Lê Hoàng Tùng Ông Nguyễn Mạnh Hùng Thành viên HĐQT')
  self.assertFalse(r['candidates']);self.assertEqual(r['quarantine'][0]['reason'],'NO_UNIQUE_PERSON_IN_ROW')
 def test_news_article_ticker_not_company_proof(self):
  r=extract_record(dict(symbol='FPT',source_kind='news',text='Ông Nguyễn Anh Tuấn Phó Tổng Giám đốc Techcombank'))
  self.assertFalse(r['candidates'])
 def test_structured_news_row(self):
  r=extract_record(dict(symbol='TCB',source_kind='news',person='Phan Thị Hải Yến',position='Phó Tổng Giám đốc',
   event='bổ nhiệm từ 01/11/2026',organization_verified=True,as_of='2026-10-30'))['candidates'][0]
  self.assertEqual(r['stage'],'APPOINTED_FUTURE');self.assertIsNone(r['pdf_page'])
 def test_historical_bio_quarantined(self):
  self.assertFalse(run('HĐQT\nÔng Nguyễn Văn An từng giữ chức Tổng Giám đốc')['candidates'])
 def test_deterministic_and_no_false_approval(self):
  text='Danh sách\nÔng Nguyễn Văn An Tổng Giám đốc'
  self.assertEqual(run(text),run(text));self.assertEqual(run(text)['candidates'][0]['validation_status'],'RULE_MATCHED')
 def test_bad_layout_blocks(self):
  self.assertEqual(run('HĐQT\nÔng Nguyễn Văn An Tổng Giám đốc',layout_uncertain=True)['quarantine'][0]['reason'],'UNRESOLVED_LAYOUT')
 def test_wrong_hash_rejected(self):
  with self.assertRaises(ValueError):run('test',content_hash='0'*64)
 def test_future_does_not_infer_from_report_year(self):
  r=run('Danh sách\nÔng Nguyễn Văn An Tổng Giám đốc bổ nhiệm từ 01/11/2026',reporting_year=2024)['candidates'][0]
  self.assertEqual(r['effective_date'],'2026-11-01')
 def test_unsupported_structured_role_visible_in_audit(self):
  r=extract_record(dict(person='Nguyễn Văn An',position='Giám đốc Khối ABC',symbol='ELC',source_kind='annual_report'))
  self.assertEqual(r['quarantine'][0]['reason'],'UNSUPPORTED_POSITION')
 def test_compound_dismissal_needs_event_scope(self):
  r=run('HĐQT\nÔng Nguyễn Văn An Thành viên HĐQT/Phó Tổng Giám đốc miễn nhiệm từ 01/01/2025')
  self.assertFalse(r['candidates']);self.assertEqual(r['quarantine'][0]['reason'],'COMPOUND_ROLE_EVENT_SCOPE_UNCLEAR')
 def test_swallowed_title_in_structured_name_rejected(self):
  r=extract_record(dict(person='Đặng Thị Thanh Minh Kế',position='Kế toán trưởng',symbol='ELC',source_kind='annual_report'))
  self.assertEqual(r['quarantine'][0]['reason'],'TITLE_OR_HONORIFIC_INSIDE_STRUCTURED_NAME')
 def test_short_biography_date_gap_not_current_role(self):
  r=run('HĐQT\nÔng Nguyễn Văn An 2014–2017 Tổng Giám đốc')
  self.assertFalse(r['candidates']);self.assertEqual(r['quarantine'][0]['reason'],'DATE_OR_NUMBERS_BETWEEN_PERSON_AND_ROLE')
if __name__=='__main__':unittest.main()
