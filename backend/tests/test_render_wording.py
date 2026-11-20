from src.retrieval_orchestration.live_research import render_live_response, vietnamese_numbers


def test_english_grouping_becomes_vietnamese():
    assert vietnamese_numbers('13,788,503.46 triệu VND') == '13.788.503,46 triệu VND'
    assert vietnamese_numbers('4,500.00') == '4.500,00'


def test_ambiguous_or_plain_numbers_untouched():
    for text in ('1,234', '61,09 nghìn', '0.2829', 'năm 2025, quý 2'):
        assert vietnamese_numbers(text) == text


def _draft(mode, text):
    return {'answering': {'status': 'DRAFT_READY', 'draft': text, 'manifest': {'response_mode': mode}}}


def test_render_converts_financial_but_not_price_answers():
    assert render_live_response(_draft('B1', '1,000,000.50 triệu VND')) == '1.000.000,50 triệu VND'
    assert render_live_response(_draft('PRICE_ANALYTICS', '1,000,000.50')) == '1,000,000.50'


def test_graph_not_stated_has_specific_wording():
    result = {'status': 'EVIDENCE_READY', 'hybrid_router': {'route': 'GRAPH'},
              'answering': {'status': 'INSUFFICIENT_EVIDENCE', 'reason_code': 'NOT_STATED_IN_SOURCE', 'message': 'x'}}
    assert 'quan hệ' in render_live_response(result)
    result['hybrid_router'] = {'route': 'VECTOR'}
    assert render_live_response(result) == 'x'


import asyncio

from src.retrieval_orchestration.live_research import LiveResearchService


class _Retriever:
    def __init__(self, available): self.available = available
    async def corpus_companies(self): return self.available


def test_company_missing_from_corpus_is_reported_before_asking_for_a_metric():
    service = LiveResearchService(_Retriever(['VCB', 'FPT']))
    result = asyncio.run(service.answer('Công ty XYZ có doanh thu bao nhiêu', 's1'))
    assert result['reason_code'] == 'COMPANY_NOT_IN_CORPUS' and 'XYZ' in result['message']


def test_known_company_still_asked_for_metric():
    service = LiveResearchService(_Retriever(['VCB', 'FPT']))
    result = asyncio.run(service.answer('Công ty FPT có doanh thu bao nhiêu', 's2'))
    assert result['reason_code'] != 'COMPANY_NOT_IN_CORPUS'
