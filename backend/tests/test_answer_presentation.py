"""Currency formatting changes display only; source quotes and amounts stay exact."""
import copy
import asyncio
import json

import pytest

from src.b1_answering.application import presentation
from src.b1_answering.evidence.grounded import validate_grounded
from tests.test_natural_answer import evidence, payload, SCOPE, QUOTE, TEXT


def test_default_style_adds_vnd_and_hides_source_cautions():
    ev = evidence()
    bound = validate_grounded(payload(), ev, SCOPE)
    original = copy.deepcopy(bound)
    result = presentation.present_answer(bound, ev, SCOPE)
    assert '8.843.161.132.730 VND' in result['draft']
    assert 'chưa xác minh' not in result['draft']
    assert 'chưa xác định' not in result['draft']
    assert result['cautions'] == original['cautions']
    assert result['claims'] == original['claims']
    assert result['citations'] == original['citations']
    assert bound == original
    assert result['presentation']['unit_annotations'][0]['origin'] == 'CONFIGURED_DEFAULT'
    assert result['presentation']['unit_annotations'][0]['source_unit_verified'] is False


@pytest.mark.parametrize('unit', ['triệu VND', 'tỷ VND', 'VND', 'USD', 'triệu USD'])
def test_explicit_source_unit_preserved_without_conversion(unit):
    ev = evidence()
    ev['e1']['passage'] += ' '+unit
    draft = validate_grounded(payload(TEXT, QUOTE+' '+unit), ev, SCOPE)
    result = presentation.present_answer(draft, ev, SCOPE)
    assert f'8.843.161.132.730 {unit}' in result['draft']
    annotation = result['presentation']['unit_annotations'][0]
    assert annotation['origin'] == 'SOURCE'
    assert annotation['source_unit_verified'] is True


def test_unit_is_not_added_to_quarter_or_year_when_value_is_small():
    ev = evidence()
    quote = QUOTE.replace('8,843,161,132,730', '2')
    ev['e1']['passage'] = ev['e1']['passage'].replace(QUOTE, quote)
    text = 'Trong quý 2 năm 2026, FPT ghi nhận tiền và tương đương tiền là 2.'
    # The validated payload is independent of presentation's date detection.
    draft = {'draft': text+' [1]', 'claims': [{'text': text, 'evidence_ids': ['e1'],
             'support_quotes': [{'evidence_id': 'e1', 'quote': quote}]}],
             'citations': [{'evidence_id': 'e1', 'citation_number': 1}], 'cautions': []}
    result = presentation.present_answer(draft, ev, SCOPE)
    assert 'quý 2 năm 2026' in result['draft']
    assert 'là 2 VND.' in result['draft']


def test_existing_currency_is_not_duplicated():
    ev = evidence()
    ev['e1']['passage'] += ' VND'
    bound = validate_grounded(payload(TEXT[:-1]+' VND.', QUOTE+' VND'), ev, SCOPE)
    result = presentation.present_answer(bound, ev, SCOPE)
    assert result['draft'].count('VND') == 1
    assert 'VND VND' not in result['draft']


def test_user_debt_example_keeps_number_and_citation():
    ev = evidence()
    ev['e1']['passage'] = ('FPT | tại cuối quý 1/2026 | Phạm vi: UNKNOWN | Đơn vị: theo từng chỉ tiêu\n'
                           'Tổng nợ phải trả (TOTAL_LIABILITIES): 28,464,058,214,856')
    text = 'Tổng nợ phải trả của FPT tại cuối quý 1/2026 là 28,464,058,214,856.'
    quote = ev['e1']['passage'].splitlines()[1]
    scope = {'source_type': 'BCTC', 'metric_code': 'TOTAL_LIABILITIES'}
    draft = validate_grounded(payload(text, quote), ev, scope)
    result = presentation.present_answer(draft, ev, scope)
    assert result['draft'] == text[:-1]+' VND. [1]'


def test_news_and_unknown_metrics_do_not_get_assumed_currency():
    ev = evidence()
    draft = validate_grounded(payload(), ev, SCOPE)
    assert presentation.present_answer(draft, ev, {'source_type': 'NEWS'})['draft'] == draft['draft']
    other = presentation.present_answer(draft, ev, {'source_type': 'BCTC', 'metric_code': 'EPS'})
    assert 'VND' not in other['draft']


def test_optional_style_can_show_cautions_or_disable_default_currency():
    style = presentation.AnswerStyle(default_financial_currency='', show_source_cautions=True)
    ev = evidence()
    draft = validate_grounded(payload(), ev, SCOPE)
    result = presentation.present_answer(draft, ev, SCOPE, style=style)
    assert 'VND' not in result['draft']
    assert 'chưa xác minh' in result['draft']


def test_header_unit_applies_to_amount_without_making_it_base_vnd():
    ev = evidence()
    ev['e1']['passage'] = ev['e1']['passage'].replace('Đơn vị: theo từng chỉ tiêu', 'Đơn vị: triệu VND, trừ EPS')
    draft = validate_grounded(payload(), ev, SCOPE)
    result = presentation.present_answer(draft, ev, SCOPE)
    assert '8.843.161.132.730 triệu VND' in result['draft']
    assert result['presentation']['unit_annotations'][0]['origin'] == 'SOURCE'


@pytest.mark.parametrize('fields', [
    {'default_financial_currency': 'bad'}, {'show_source_cautions': 'false'}, {'version': 'unknown'},
])
def test_invalid_presentation_config_is_rejected(fields):
    with pytest.raises(ValueError): presentation.AnswerStyle(**fields)


def test_caution_only_model_output_cannot_become_a_blank_successful_answer():
    from src.b1_answering.application.service import complete_retrieval
    from tests.test_live_research import pack
    class Provider:
        async def count_tokens(self, request): return 100
        async def generate(self, request):
            item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
            line = next(line for line in item['passage'].splitlines() if '(CASH_AND_CASH_EQUIVALENTS)' in line)
            return {'model_version': 'test', 'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120},
                    'payload': {'claims': [{'text': 'Nguồn chưa xác minh đơn vị của chỉ tiêu.',
                    'evidence_ids': [item['evidence_id']], 'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': line}]}]}}
    result = {'status': 'EVIDENCE_READY', 'execution_mode': 'LIVE', 'scope': SCOPE, 'evidence_pack': pack()}
    output = asyncio.run(complete_retrieval('Tiền FPT?', result, provider=Provider()))
    assert output['answering']['status'] != 'DRAFT_READY'
    assert output['answering']['message']
