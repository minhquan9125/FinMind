"""Natural LIVE answers must preserve cited numbers, units and source quotes."""
import asyncio
import copy
import json

import pytest

from src.b1_answering.application.service import complete_retrieval
from src.b1_answering.core.policy import Limits
from src.b1_answering.evidence.citations import CitationError
from src.b1_answering.evidence import grounded
from tests.test_live_research import pack


HEADER = 'Công ty Cổ phần FPT (FPT) | tại cuối quý 2/2026 | Phạm vi: UNKNOWN | Đơn vị: theo từng chỉ tiêu'
QUOTE = 'Tiền và các khoản tương đương tiền (CASH_AND_CASH_EQUIVALENTS): 8,843,161,132,730'
TEXT = 'Cuối quý 2/2026, tiền và tương đương tiền của FPT là 8.843.161.132.730.'


def evidence():
    return {'e1': dict(evidence_id='e1', source_id='s1', chunk_id='c1',
                       source_sha256='a'*64, source_type='BCTC',
                       passage=HEADER+'\n'+QUOTE, locator={'table_id': 'balance'})}


def payload(text=TEXT, quote=QUOTE):
    return {'claims': [dict(text=text, evidence_ids=['e1'],
                           support_quotes=[dict(evidence_id='e1', quote=quote)])]}


SCOPE = {'metric_code': 'CASH_AND_CASH_EQUIVALENTS', 'source_type': 'BCTC'}


def test_natural_answer_uses_numbered_sources_and_keeps_quotes():
    answer = grounded.validate_grounded(payload(), evidence(), SCOPE)
    assert TEXT+' [1]' in answer['draft']
    assert answer['claims'][0]['support_quotes'][0]['quote'] == QUOTE
    assert answer['citations'][0]['citation_number'] == 1
    assert 'chưa xác minh' in answer['draft']


@pytest.mark.parametrize('text', [
    TEXT.replace('8.843.161.132.730', '9.843.161.132.730'),
    TEXT.replace('8.843.161.132.730', '8843.16'),
    TEXT+' Tăng 12% so với cùng kỳ.',
    TEXT+' Giá trị là 8,843 tỷ đồng.',
    TEXT[:-1]+' tỷ.',
    TEXT+' Đây là báo cáo hợp nhất.',
    TEXT+' Đây là báo cáo riêng lẻ.',
    TEXT.replace('FPT', 'SSI'),
    TEXT.replace('quý 2', 'quý 3'),
])
def test_unsupported_facts_fail_closed(text):
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload(text), evidence(), SCOPE)


@pytest.mark.parametrize('change', ['fake_quote', 'unknown_id', 'missing_quote', 'wrong_metric', 'empty'])
def test_invalid_support_fails_closed(change):
    p, ev = payload(), evidence()
    if change == 'fake_quote': p['claims'][0]['support_quotes'][0]['quote'] = 'Có 999 đồng'
    if change == 'unknown_id': p['claims'][0]['support_quotes'][0]['evidence_id'] = 'other'
    if change == 'missing_quote': p['claims'][0]['support_quotes'] = []
    if change == 'wrong_metric': p['claims'][0]['support_quotes'][0]['quote'] = HEADER
    if change == 'empty': p['claims'] = []
    with pytest.raises(CitationError): grounded.validate_grounded(p, ev, SCOPE)


def test_number_and_unit_on_other_metric_cannot_support_answer():
    ev = evidence()
    extra = 'Tổng tài sản (TOTAL_ASSETS): 999 tỷ đồng'
    ev['e1']['passage'] += '\n'+extra
    with pytest.raises(CitationError):
        grounded.validate_grounded(payload('Tiền của FPT là 999 tỷ đồng.', QUOTE+'\n'+extra), ev, SCOPE)


def test_known_unit_and_news_paraphrase_are_allowed():
    ev = evidence()
    ev['e1']['passage'] += ' đồng'
    answer = grounded.validate_grounded(payload(TEXT[:-1]+' đồng.', QUOTE+' đồng'), ev, SCOPE)
    assert answer['status'] == 'DRAFT_READY'
    ev['e1']['source_type'] = 'NEWS'
    ev['e1']['passage'] = 'FPT công bố mở văn phòng mới tại Hà Nội.'
    answer = grounded.validate_grounded(payload('FPT vừa thông báo mở thêm văn phòng tại Hà Nội.', ev['e1']['passage']), ev, {'source_type': 'NEWS'})
    assert answer['status'] == 'DRAFT_READY'


def test_live_service_sends_natural_prompt_and_accepts_rewording():
    result = {'status': 'EVIDENCE_READY', 'execution_mode': 'LIVE', 'scope': SCOPE, 'evidence_pack': pack()}
    class Provider:
        async def count_tokens(self, request):
            assert 'support_quotes' in request['generationConfig']['responseJsonSchema']['properties']['claims']['items']['properties']
            assert 'diễn đạt' in request['systemInstruction']['parts'][0]['text']
            return 100

        async def generate(self, request):
            item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
            line = next(line for line in item['passage'].splitlines() if '(CASH_AND_CASH_EQUIVALENTS)' in line)
            return {'model_version': 'test', 'usage': {'input_tokens': 100, 'output_tokens': 30, 'total_tokens': 130},
                    'payload': {'claims': [{'text': 'FPT ghi nhận tiền và tương đương tiền là 100.',
                                           'evidence_ids': [item['evidence_id']],
                                           'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': line}]}]}}
    out = asyncio.run(complete_retrieval('Tiền FPT quý 2/2026?', copy.deepcopy(result), provider=Provider()))
    assert out['answering']['status'] == 'DRAFT_READY'
    manifest = out['answering']['manifest']
    assert manifest['prompt_version'] == 'b1-grounded-v8'
    assert not manifest['components']['extractive_claim_check']
    assert not manifest['components']['b3_answer_verification']
    assert out['answering']['budget']['calls_used'] == 1
    assert '100 VND' in out['answering']['draft']
    assert 'Nguồn chưa' not in out['answering']['draft']
    assert out['answering']['cautions']


def test_prompt_does_not_mutate_shared_schema():
    request = grounded.build_grounded_request('Tiền FPT?', evidence(), Limits.load(), SCOPE)
    request['generationConfig']['responseJsonSchema'].clear()
    other = grounded.build_grounded_request('Tiền FPT?', evidence(), Limits.load(), SCOPE)
    assert other['generationConfig']['responseJsonSchema']['required'] == ['claims']


@pytest.mark.parametrize('word', ['tỷ lệ', 'tỉ lệ', 'tỷ suất', 'tỷ trọng', 'tỷ giá'])
def test_ratio_words_are_not_the_billion_unit(word):
    # "tỷ lệ nợ" is a ratio, not an amount in tỷ đồng; the bare unit still counts.
    assert grounded._units(f'{word} nợ phải trả trên tổng tài sản là 41,54%') == {'%'}
    assert 'ty' in grounded._units(f'{word} nợ là 5 tỷ')


HEALTH = ('Tình hình tài chính FPT kỳ quý 3/2026 (tính từ BCTC đã đối chiếu với file BCTC gốc, dữ liệu FinMind):\n'
          '- Nợ phải trả trên tổng tài sản: 41,54%.\n- ROE: chưa đủ dữ liệu đã xác minh.')


@pytest.mark.parametrize('kind', ['FINANCIAL_HEALTH', 'PRICE_TREND'])
def test_finmind_snapshot_header_supports_period_but_not_other_numbers(kind):
    ev = {'h': dict(evidence_id='h', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type=kind, passage=HEALTH, locator={'period': '2026-Q3'})}
    scope = {'source_type': 'MARKET_ANALYSIS'}
    line = '- Nợ phải trả trên tổng tài sản: 41,54%.'
    ok = {'claims': [dict(text='Quý 3/2026, nợ phải trả trên tổng tài sản của FPT là 41,54%.',
                          evidence_ids=['h'], support_quotes=[dict(evidence_id='h', quote=line)])]}
    assert grounded.validate_grounded(ok, ev, scope)['status'] == 'DRAFT_READY'
    bad = copy.deepcopy(ok)
    bad['claims'][0]['text'] = 'ROE của FPT là 41,54%.'  # ROE line is not quoted
    with pytest.raises(CitationError):
        grounded.validate_grounded(bad, ev, scope)


def test_market_analysis_drops_only_unsupported_claims():
    ev = {'h': dict(evidence_id='h', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type='FINANCIAL_HEALTH', passage=HEALTH, locator={'period': '2026-Q3'})}
    line = '- Nợ phải trả trên tổng tài sản: 41,54%.'
    good = dict(text='Quý 3/2026, nợ phải trả trên tổng tài sản của FPT là 41,54%.',
                evidence_ids=['h'], support_quotes=[dict(evidence_id='h', quote=line)])
    bad = dict(text='ROE của FPT là 99%.', evidence_ids=['h'], support_quotes=[dict(evidence_id='h', quote=line)])
    wrong_id = dict(text='Giá FPT là 1 VND.', evidence_ids=['x'], support_quotes=[dict(evidence_id='x', quote=line)])
    scope = {'source_type': 'MARKET_ANALYSIS'}
    out = grounded.keep_supported_claims({'claims': [bad, good, wrong_id]}, ev, scope)
    assert [c['text'] for c in out['claims']] == [good['text']]
    assert '99%' not in out['draft'] and 'đã bị lược' in out['draft']
    assert grounded.keep_supported_claims({'claims': [bad]}, ev, scope) is None  # nothing left: fail closed
    assert grounded.keep_supported_claims({'claims': [bad, good]}, ev, {'source_type': 'BCTC'}) is None


def test_market_analysis_draft_is_bulleted_under_group_headings():
    ev = {'h': dict(evidence_id='h', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type='FINANCIAL_HEALTH', passage=HEALTH, locator={'period': '2026-Q3'})}
    line = '- Nợ phải trả trên tổng tài sản: 41,54%.'
    def claim(text):
        return dict(text=text, evidence_ids=['h'], support_quotes=[dict(evidence_id='h', quote=line)])
    payload = {'claims': [claim('Tình hình tài chính: nợ phải trả trên tổng tài sản của FPT là 41,54%.'),
                          claim('Tình hình tài chính: nghĩa là phần lớn tài sản được tài trợ bằng vốn chủ.'),
                          claim('Nhận định tổng hợp: chưa đủ dữ liệu để kết luận.')]}
    draft = grounded.validate_grounded(payload, ev, {'source_type': 'MARKET_ANALYSIS'})['draft']
    assert draft.splitlines() == ['Tình hình tài chính:',
                                  '• Nợ phải trả trên tổng tài sản của FPT là 41,54%. [1]',
                                  '• Nghĩa là phần lớn tài sản được tài trợ bằng vốn chủ. [1]',
                                  '', 'Nhận định tổng hợp:', '• Chưa đủ dữ liệu để kết luận. [1]']


def test_unlabelled_claims_are_still_bulleted():
    ev = {'h': dict(evidence_id='h', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type='FINANCIAL_HEALTH', passage=HEALTH, locator={'period': '2026-Q3'})}
    payload = {'claims': [dict(text='Nợ phải trả trên tổng tài sản của FPT là 41,54%.', evidence_ids=['h'],
                               support_quotes=[dict(evidence_id='h', quote='- Nợ phải trả trên tổng tài sản: 41,54%.')])]}
    draft = grounded.validate_grounded(payload, ev, {'source_type': 'MARKET_ANALYSIS'})['draft']
    assert draft == '• Nợ phải trả trên tổng tài sản của FPT là 41,54%. [1]'


def test_analysis_prompt_asks_for_plain_language_and_group_labels():
    from src.b1_answering.core.policy import Limits
    ev = {'h': dict(evidence_id='h', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type='FINANCIAL_HEALTH', passage=HEALTH, locator={'period': '2026-Q3'})}
    text = grounded.build_grounded_request('phân tích fpt', ev, Limits.load(),
                                           {'source_type': 'MARKET_ANALYSIS'})['systemInstruction']['parts'][0]['text']
    assert 'người không chuyên' in text and '"Xu hướng giá:' in text


@pytest.mark.parametrize('claim,source', [('19.150 VND', '19,150 VND'), ('19,150 VND', '19.150 VND'),
                                          ('15.090 đồng/cổ phiếu', '15,090 đồng/cổ phiếu')])
def test_vnd_amounts_match_across_thousand_separators(claim, source):
    assert grounded._numbers(claim) == grounded._numbers(source)


@pytest.mark.parametrize('claim,source', [('8.843 tỷ đồng', '8,843 tỷ đồng'), ('1.5%', '1,5%'), ('19.150', '19,150')])
def test_other_separators_stay_ambiguous(claim, source):
    # Only an amount directly followed by VND/đồng is a whole number of dong; elsewhere '.' may be a decimal point.
    assert grounded._numbers(claim) != grounded._numbers(source)


TREND_LINE = '- Ngắn hạn: Giảm (20 phiên). Lợi suất -14,57%, giá so với SMA20 -7,89%.'


@pytest.mark.parametrize('text,ok', [
    ('Giá thấp hơn mức trung bình 20 phiên 7,89%.', True),
    ('Trong 20 phiên giá giảm 14,57%.', True),
    ('Lợi suất âm 14,57% trong 20 phiên.', True),
    ('Giá cao hơn mức trung bình 20 phiên 7,89%.', False),   # direction flipped
    ('Trong 20 phiên giá tăng 14,57%.', False),
    ('Lợi suất 20 phiên là 14,57%.', False),                # sign silently dropped
])
def test_negative_source_numbers_need_a_downward_word(text, ok):
    ev = {'t': dict(evidence_id='t', source_id='s', chunk_id='c', source_sha256='a'*64,
                    source_type='PRICE_TREND', passage='Xu hướng giá FPT tính đến phiên 2026-11-12:\n' + TREND_LINE,
                    locator={'trading_day': '2026-11-12'})}
    payload = {'claims': [dict(text=text, evidence_ids=['t'], support_quotes=[dict(evidence_id='t', quote=TREND_LINE)])]}
    if ok:
        assert grounded.validate_grounded(payload, ev, {'source_type': 'MARKET_ANALYSIS'})['status'] == 'DRAFT_READY'
    else:
        with pytest.raises(CitationError):
            grounded.validate_grounded(payload, ev, {'source_type': 'MARKET_ANALYSIS'})
