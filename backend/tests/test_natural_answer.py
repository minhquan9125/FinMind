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
    assert manifest['prompt_version'] == 'b1-grounded-v7'
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
