"""The grounding gate must accept a correct, source-bound answer and still reject anything not in the source.

Covers three properties: the cited chunk's own identity line is context for annual reports too; a quote
from a column-interleaved scanned page may follow the source lines instead of being contiguous; and
"tỷ"/"đồng" are units only in a money context.
"""
import pytest

from src.b1_answering.evidence import grounded
from src.b1_answering.evidence.citations import CitationError

ANNUAL_HEADER = 'FPT | Báo cáo thường niên 2024 | PDF trang 80'
# Two columns read line by line: the right-hand column's sentence is on lines 2, 4 and 6.
COLUMNS = '\n'.join([
    ANNUAL_HEADER,
    'Công ty luôn tuân thủ đầy đủ. Theo ủy quyền của ĐHĐCĐ, HĐQT chọn Công ty TNHH',
    'chính xác và đúng thời hạn các',
    'PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài',
    'quy định về công bố thông tin đối với 9.999 cổ đông',
    'chính 2024.',
    'Dòng cuối của cột trái.',
])
SENTENCE = 'Theo ủy quyền của ĐHĐCĐ, HĐQT chọn Công ty TNHH PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài chính 2024.'
SCOPE = {'source_type': 'BCTN', 'metric_code': None}


def annual(passage=COLUMNS, source_type='BCTN'):
    return {'e1': dict(evidence_id='e1', source_id='s1', chunk_id='c1', source_sha256='a' * 64,
                       source_type=source_type, passage=passage, locator={'table_id': 'page'})}


def payload(text, quote):
    return {'claims': [dict(text=text, evidence_ids=['e1'], support_quotes=[dict(evidence_id='e1', quote=quote)])]}


# ---- the chunk's identity line ---------------------------------------------------------------------

def test_an_annual_report_answer_may_name_the_company_and_report_year_of_its_chunk():
    passage = ANNUAL_HEADER + '\n• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'
    answer = grounded.validate_grounded(
        payload('Theo Báo cáo thường niên 2024 của FPT, tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự.',
                '• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'), annual(passage), SCOPE)
    assert answer['status'] == 'DRAFT_READY'


def test_the_usual_abbreviation_of_the_document_kind_is_allowed():
    passage = ANNUAL_HEADER + '\n• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'
    grounded.validate_grounded(payload('Theo BCTN 2024 của FPT, nhân sự nữ chiếm 37,1%.',
                                       '• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'), annual(passage), SCOPE)


@pytest.mark.parametrize('text', [
    'Theo Báo cáo thường niên 2023 của FPT, nhân sự nữ chiếm 37,1%.',     # another report year
    'Theo Báo cáo thường niên 2024 của VCB, nhân sự nữ chiếm 37,1%.',     # another company
    'Theo trang 80, nhân sự nữ chiếm 37,1%.',                              # the page locator is not a fact
    'Nhân sự nữ của FPT chiếm 38,1%.',                                     # another number
])
def test_identity_or_numbers_that_the_chunk_does_not_state_are_still_rejected(text):
    passage = ANNUAL_HEADER + '\n• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload(text, '• Tỷ lệ nhân sự nữ chiếm 37,1% tổng nhân sự;'), annual(passage), SCOPE)


# ---- quotes from column-interleaved scans ------------------------------------------------------------

def test_a_sentence_split_over_interleaved_lines_is_located_and_stored_as_exact_source_text():
    span, pieces = grounded.locate_quote(COLUMNS, SENTENCE, column_ocr=True)
    assert span in COLUMNS and span.startswith('Theo ủy quyền') and span.endswith('chính 2024.')
    assert ' '.join(' '.join(pieces).split()) == SENTENCE
    answer = grounded.validate_grounded(
        payload('Đơn vị kiểm toán độc lập năm 2024 của FPT là Công ty TNHH PwC Việt Nam.', SENTENCE), annual(), SCOPE)
    stored = answer['claims'][0]['support_quotes'][0]['quote']
    assert stored == span and stored in COLUMNS


def test_text_of_the_other_column_inside_the_span_cannot_support_a_claim():
    with pytest.raises(CitationError):       # 9.999 is on a skipped line, not in the quoted words
        grounded.validate_grounded(payload('FPT có 9.999 cổ đông và chọn PwC Việt Nam.', SENTENCE), annual(), SCOPE)


@pytest.mark.parametrize('quote', [
    SENTENCE.replace('PwC', 'KPMG'),                                                  # a word that is not in the source
    'HĐQT chọn Công ty TNHH quy định về công bố thông tin',                           # skips two lines
    'tuân thủ đầy đủ. PwC Việt Nam là đơn vị kiểm toán',                              # leaves a line before its end
    'HĐQT chọn Công ty TNHH Dòng cuối của cột trái.',                                 # skips many lines
    'PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài chính xác và đúng thời hạn các',   # goes backwards
    'HĐQT chọn Công ty TNHH PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài quy định về công bố thông tin',  # changes column midway
    'chọn Công ty TNHH PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài 9.999 cổ đông',   # enters a line in its middle
])
def test_a_quote_that_does_not_follow_the_source_lines_is_rejected(quote):
    assert grounded.locate_quote(COLUMNS, quote, column_ocr=True) is None
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload('FPT chọn đơn vị kiểm toán.', quote), annual(), SCOPE)


def test_a_quote_cannot_drop_a_short_line_such_as_a_negation():
    passage = ANNUAL_HEADER + '\nBan lãnh đạo công ty\nkhông\nđạt mục tiêu lợi nhuận'
    assert grounded.locate_quote(passage, 'Ban lãnh đạo công ty đạt mục tiêu lợi nhuận', column_ocr=True) is None
    whole = 'Ban lãnh đạo công ty không đạt mục tiêu lợi nhuận'
    span, pieces = grounded.locate_quote(passage, whole, column_ocr=True)
    assert span == 'Ban lãnh đạo công ty\nkhông\nđạt mục tiêu lợi nhuận' and len(pieces) == 3


def test_line_following_quotes_are_only_for_scanned_reports():
    assert grounded.locate_quote(COLUMNS, SENTENCE) is None
    news = annual(source_type='NEWS')
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload('FPT chọn PwC Việt Nam.', SENTENCE), news, {'source_type': 'NEWS'})


def test_a_verbatim_quote_is_returned_unchanged():
    quote = 'PwC Việt Nam là đơn vị kiểm toán độc lập cho năm tài'
    assert grounded.locate_quote(COLUMNS, quote, column_ocr=True) == (quote, [quote])


# ---- units ------------------------------------------------------------------------------------------

@pytest.mark.parametrize('text,expected', [
    ('Tỷ lệ nhân sự nữ chiếm 37,1%.', {'%'}),
    ('Chiến lược được triển khai đồng bộ, đồng thời hội đồng đã thông qua.', set()),
    ('Công ty có tỷ suất sinh lời cao.', set()),
    ('Doanh thu đạt 62.849 tỷ đồng.', {'ty', 'dong'}),
    ('Giá trị là 8,843,161.13 triệu VND.', {'trieu', 'vnd'}),
    ('Mệnh giá 10.000 đồng mỗi cổ phiếu.', {'dong'}),
    ('FPT | Phạm vi: RATIO | Đơn vị: triệu VND, trừ EPS', {'trieu', 'vnd'}),
    ('Đơn vị tính: đồng', {'dong'}),
])
def test_units_are_read_only_in_a_money_context(text, expected):
    assert grounded._units(text) == expected


def test_a_money_unit_missing_from_the_source_is_still_rejected():
    passage = ANNUAL_HEADER + '\nDoanh thu năm 2024 đạt 62.849'
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload('Doanh thu của FPT đạt 62.849 tỷ đồng.', 'Doanh thu năm 2024 đạt 62.849'),
                                   annual(passage), SCOPE)


# ---- row fallback for any labelled metric --------------------------------------------------------------

def test_the_row_fallback_names_a_catalog_metric_as_its_source_row_does():
    header = 'Công ty Cổ phần FPT (FPT) | Báo cáo Kết quả hoạt động kinh doanh | quý 2/2026 (riêng quý) | Phạm vi: INCOME_STATEMENT | Đơn vị: theo từng chỉ tiêu'
    row = 'Lãi cơ bản trên cổ phiếu (BASIC_EARNINGS_PER_SHARE): 1,507 VND/cổ phiếu'
    evidence = {'e1': dict(evidence_id='e1', source_id='s1', chunk_id='c1', source_sha256='a' * 64, source_type='BCTC',
                           passage=header + '\n' + row, locator={'table_id': 'income'})}
    scope = dict(source_type='BCTC', metric_code='BASIC_EARNINGS_PER_SHARE', companies=['FPT'], periods=['2026-Q2'],
                 measure_basis='STANDALONE_QUARTER', reporting_entity='UNKNOWN')
    answer = grounded.source_row_fallback(evidence, scope, reason_code='UNSUPPORTED_CLAIM')
    assert answer['draft'].startswith('FPT ghi nhận lãi cơ bản trên cổ phiếu trong quý 2/2026 là 1,507 VND/cổ phiếu.')
    assert answer['claims'][0]['support_quotes'][0]['quote'] == row


# ---- one unverifiable claim does not discard the verified ones ------------------------------------------

def two_claims(second_text, second_quote):
    first = dict(text='Đơn vị kiểm toán độc lập năm 2024 của FPT là Công ty TNHH PwC Việt Nam.', evidence_ids=['e1'],
                 support_quotes=[dict(evidence_id='e1', quote=SENTENCE)])
    second = dict(text=second_text, evidence_ids=['e1'], support_quotes=[dict(evidence_id='e1', quote=second_quote)])
    return {'claims': [first, second]}


@pytest.mark.parametrize('text,quote', [
    ('Ý kiến kiểm toán là chấp nhận toàn phần tại ngày 31 tháng 12 năm 2024.', 'Dòng cuối của cột trái.'),   # numbers not in the quote
    ('Phí kiểm toán là 5 tỷ đồng.', 'Một câu không có trong tài liệu.'),                                       # quote not in the source
])
def test_a_document_answer_keeps_verified_claims_and_says_that_something_was_left_out(text, quote):
    answer = grounded.validate_grounded(two_claims(text, quote), annual(), SCOPE)
    assert len(answer['claims']) == 1 and 'PwC Việt Nam' in answer['draft']
    assert text not in answer['draft']
    assert any('không hiển thị' in caution for caution in answer['cautions'])


def test_an_answer_with_no_verified_claim_is_still_rejected():
    payload_ = {'claims': [dict(text='Phí kiểm toán là 5 tỷ đồng.', evidence_ids=['e1'],
                                support_quotes=[dict(evidence_id='e1', quote='Một câu không có trong tài liệu.')])]}
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload_, annual(), SCOPE)


@pytest.mark.parametrize('source_type', ['BCTC', 'NEWS'])
def test_statement_rows_and_news_stay_all_or_nothing(source_type):
    with pytest.raises(CitationError):
        grounded.validate_grounded(two_claims('Phí kiểm toán là 5 tỷ đồng.', 'Một câu không có trong tài liệu.'),
                                   annual(source_type=source_type), {'source_type': source_type})


# ---- the model finds nothing in the passages ---------------------------------------------------------------

class SilentProvider:
    async def count_tokens(self, request): return 100
    async def generate(self, request):
        return {'model_version': 'test', 'usage': {'input_tokens': 100, 'output_tokens': 5, 'total_tokens': 105},
                'payload': {'claims': []}}


def compose(source_type):
    import asyncio
    from src.b1_answering.application.service import complete_retrieval
    from tests.test_live_research import pack
    result = {'status': 'EVIDENCE_READY', 'execution_mode': 'LIVE', 'evidence_pack': pack(),
              'scope': {'source_type': source_type, 'metric_code': None, 'companies': ['FPT'], 'periods': ['2024']}}
    return asyncio.run(complete_retrieval('Câu hỏi về tài liệu của FPT?', result, provider=SilentProvider()))


def test_no_answer_in_the_passages_is_reported_as_such_for_document_questions():
    from src.retrieval_orchestration.live_research import render_live_response
    out = compose('BCTN')
    assert (out['answering']['status'], out['answering']['reason_code']) == ('INSUFFICIENT_EVIDENCE', 'NOT_STATED_IN_SOURCE')
    assert render_live_response(out) == 'Các đoạn tài liệu tìm được không nêu thông tin được hỏi.'


def test_statement_questions_keep_their_existing_handling_of_an_empty_draft():
    assert compose('BCTC')['answering']['reason_code'] != 'NOT_STATED_IN_SOURCE'
