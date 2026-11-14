"""Questions are understood through shared knowledge (metric catalog, company names, non-company codes),
not through a per-question list. Each test states a general rule with several unrelated examples.
"""
import asyncio

import pytest

from src.financial.mapping import METRIC_LABELS_VI
from src.retrieval_orchestration import metric_vocabulary as vocab
from src.retrieval_orchestration.clarifications import _public_options, resolve_reply
from src.retrieval_orchestration.live_research import LiveResearchService, analyze_live
from src.retrieval_orchestration.retrieval_flow.intent import _fold


def scope(question, context=None):
    return analyze_live(question, context)['scope']


# ---- the vocabulary -----------------------------------------------------------------------------------

def test_every_labelled_catalog_metric_can_be_asked_for_by_its_printed_label():
    missing = [code for code, label in METRIC_LABELS_VI.items() if code not in vocab.find_metrics(_fold(label))]
    # A label owned by a curated alias of another code resolves to that curated code instead.
    assert all(vocab.find_metrics(_fold(METRIC_LABELS_VI[code])) for code in missing)
    assert len(missing) <= 5, missing


@pytest.mark.parametrize('question,code', [
    ('Lãi cơ bản trên cổ phiếu của VCB năm 2024', 'BASIC_EARNINGS_PER_SHARE'),
    ('EPS của FPT quý 2/2026 là bao nhiêu?', 'BASIC_EARNINGS_PER_SHARE'),
    ('Lợi nhuận gộp của CMG năm 2024', 'GROSS_PROFIT'),
    ('Tài sản cố định của FPT quý 2/2026', 'FIXED_ASSETS'),
    ('ROE của FPT quý 2/2026', 'ROE'),
    ('Tổng tài sản của FPT năm 2024', 'TOTAL_ASSETS'),
    ('Số tiền FPT đã chi ra để mua sắm, xây dựng tài sản cố định trong quý 2/2026 là bao nhiêu?', 'PURCHASE_FIXED_ASSETS'),
])
def test_curated_and_catalog_metrics_resolve_to_one_code(question, code):
    result = analyze_live(question)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['metric_code'] == code


@pytest.mark.parametrize('question,code,never', [
    ('Tỷ suất lợi nhuận trên vốn chủ sở hữu của FPT quý 2/2026', 'ROE', 'OWNERS_EQUITY'),
    ('Lợi nhuận sau thuế chưa phân phối của FPT quý 2/2026', 'RETAINED_EARNINGS', 'PROFIT_AFTER_TAX'),
    ('Tổng nợ phải trả và vốn chủ sở hữu của FPT quý 2/2026', 'TOTAL_LIABILITIES_EQUITY', 'OWNERS_EQUITY'),
])
def test_a_metric_name_inside_a_longer_metric_name_is_not_a_second_metric(question, code, never):
    found = vocab.find_metrics(_fold(question))
    assert found == [code] and never not in found


@pytest.mark.parametrize('question', [
    'Lợi nhuận sau thuế thu nhập doanh nghiệp phân bổ cho cổ đông của công ty mẹ FPT năm 2024 là bao nhiêu?',
    'Lợi nhuận sau thuế thuộc về cổ đông công ty mẹ của FPT năm 2024',
    'LNST của cổ đông công ty mẹ FPT năm 2024',
])
def test_profit_of_the_parent_shareholders_is_that_metric_on_the_consolidated_report(question):
    result = scope(question)
    assert result['metric_code'] == 'PARENT_NET_PROFIT'
    assert result['reporting_entity'] != 'PARENT'            # "công ty mẹ" belongs to the metric name


def test_parent_company_outside_a_metric_name_still_selects_the_parent_report():
    result = scope('Lợi nhuận sau thuế của công ty mẹ FPT năm 2024')
    assert (result['metric_code'], result['reporting_entity']) == ('PROFIT_AFTER_TAX', 'PARENT')


def test_balance_sheet_rows_and_ratios_are_point_in_time():
    assert scope('ROE của FPT quý 2/2026')['measure_basis'] == 'POINT_IN_TIME'
    assert scope('Tài sản cố định của FPT quý 2/2026')['measure_basis'] == 'POINT_IN_TIME'
    assert scope('Lợi nhuận gộp của FPT quý 2/2026')['measure_basis'] == 'STANDALONE_QUARTER'


# ---- capital letters are not companies ------------------------------------------------------------------

@pytest.mark.parametrize('question', [
    'Lưu chuyển tiền thuần từ hoạt động kinh doanh (CFO) của FPT trong quý 2/2026 đạt bao nhiêu?',
    'Lãi cơ bản trên cổ phiếu (EPS) của FPT quý 2/2026',
    'Tổng tài sản (TTS) của FPT quý 2/2026',
    'ROE của FPT quý 2/2026',
    'CEO của FPT là ai?',
    'Cổ phiếu FPT niêm yết trên HOSE có vốn điều lệ bao nhiêu?',
])
def test_abbreviations_glosses_and_non_company_codes_are_not_companies(question):
    assert scope(question)['companies'] == ['FPT']


def test_a_registered_symbol_in_brackets_is_still_a_company():
    assert scope('Lợi nhuận sau thuế của Masan (MSN) năm 2024')['companies'] == ['MSN']


def test_an_unknown_capitalised_symbol_still_replaces_the_previous_company():
    previous = scope('Doanh thu thuần FPT năm 2024')
    assert scope('doanh thu thuần XYZ năm 2024', previous)['companies'] == ['XYZ']


@pytest.mark.parametrize('question,symbol', [
    ('Tổng tài sản của Vietcombank năm 2024', 'VCB'),
    ('Doanh thu thuần của Hòa Phát năm 2024', 'HPG'),
    ('Lợi nhuận sau thuế của Vinamilk năm 2024', 'VNM'),
    ('Tổng tài sản của Techcombank quý 2/2026', 'TCB'),
])
def test_a_company_named_by_name_is_resolved_and_never_inherits_the_previous_company(question, symbol):
    previous = scope('Doanh thu thuần MBB năm 2024')
    assert scope(question, previous)['companies'] == [symbol]


# ---- what a statement row cannot answer -------------------------------------------------------------------

@pytest.mark.parametrize('question', [
    'Theo Thuyết minh báo cáo tài chính hợp nhất, doanh thu thuần phát sinh từ thị trường nước ngoài của FPT năm 2024 là bao nhiêu?',
    'Doanh thu thuần của FPT mảng công nghệ năm 2024',
    'Lợi nhuận trước thuế khối viễn thông của FPT năm 2024',
    'Doanh thu thuần trong nước của FPT năm 2024',
    'Lợi nhuận sau thuế của các công ty con của FPT năm 2024',
])
def test_a_metric_restricted_to_part_of_the_business_goes_to_the_annual_report_not_the_total_row(question):
    result = analyze_live(question)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['source_type'] == 'BCTN' and result['scope']['metric_code'] is None


@pytest.mark.parametrize('question', [
    'Doanh thu thuần của FPT năm 2024 là bao nhiêu?',
    'Doanh thu thuần hợp nhất của FPT mang lại trong năm 2024',        # "mang lại" is not "mảng"
    'Lợi nhuận sau thuế của FPT khởi sắc ra sao năm 2024',              # "khởi sắc" is not "khối"
])
def test_an_unrestricted_metric_still_uses_the_statement_row(question):
    assert scope(question)['source_type'] == 'BCTC'


# ---- questions without a metric ----------------------------------------------------------------------------

@pytest.mark.parametrize('question', [
    'Tỷ lệ nhân sự nữ trong tổng quy mô nhân sự của FPT trong năm 2024 là bao nhiêu phần trăm?',
    'Đơn vị kiểm toán độc lập nào đã kiểm toán BCTC hợp nhất năm 2024 của FPT và đưa ra ý kiến loại gì?',
    'FPT có bao nhiêu văn phòng ở nước ngoài trong năm 2024?',
])
def test_a_full_question_without_a_metric_is_answered_from_the_annual_report(question):
    result = analyze_live(question)
    assert (result['decision'], result['scope']['source_type']) == ('SEARCH', 'BCTN')
    assert result['scope']['periods'] == ['2024']


@pytest.mark.parametrize('question', ['FPT quý 2/2026', 'FPT năm 2024', 'cho tôi xem FPT 2024'])
def test_a_bare_company_and_period_still_asks_which_metric(question):
    result = analyze_live(question)
    assert (result['decision'], result['reason_code']) == ('ASK_CLARIFICATION', 'MISSING_METRIC')


def test_an_ambiguous_metric_word_still_offers_its_choices():
    result = analyze_live('nợ của fpt trong quý 2 2026 là bao nhiêu')
    assert result['reason_code'] == 'MISSING_METRIC' and result['scope']['_pending_metric'] == 'DEBT'


# ---- several metrics ----------------------------------------------------------------------------------------

def test_two_metrics_offer_both_with_readable_labels_and_the_choice_resolves():
    result = analyze_live('Lợi nhuận sau thuế thuộc về cổ đông công ty mẹ của FPT quý 2/2026 và Lãi cơ bản trên cổ phiếu (EPS) là bao nhiêu?')
    assert result['reason_code'] == 'MULTIPLE_METRICS'
    assert result['scope']['_metric_candidates'] == ['PARENT_NET_PROFIT', 'BASIC_EARNINGS_PER_SHARE']
    labels = [option['label'] for option in result['clarification_options']]
    assert labels == ['LNST thuộc cổ đông công ty mẹ', 'Lãi cơ bản trên cổ phiếu']
    chosen = analyze_live('2', result['scope'])
    assert chosen['decision'] == 'SEARCH' and chosen['scope']['metric_code'] == 'BASIC_EARNINGS_PER_SHARE'
    assert chosen['scope']['companies'] == ['FPT'] and chosen['scope']['periods'] == ['2026-Q2']


def test_catalog_options_have_a_label_a_code_and_accept_the_label_as_a_reply():
    option = _public_options(['GROSS_MARGIN'])[0]
    assert option['metric_code'] == 'GROSS_MARGIN' and option['label'] == METRIC_LABELS_VI['GROSS_MARGIN']
    context = {'_clarification_state': {'choice_keys': ['ROE', 'GROSS_MARGIN']}}
    assert resolve_reply(_fold(METRIC_LABELS_VI['GROSS_MARGIN']), context) == 'gross_margin'


# ---- a company the corpus does not have ---------------------------------------------------------------------

class EmptyRetriever:
    def __init__(self, available): self.available, self.calls = available, []
    async def retrieve(self, question, scope):
        self.calls.append(scope)
        return dict(schema_version='1.1', query_id='q', items=[])
    async def corpus_companies(self): return self.available


def test_no_report_for_a_company_outside_the_corpus_names_the_companies_it_has():
    retriever = EmptyRetriever(['FPT', 'MBB', 'VCB'])
    result = asyncio.run(LiveResearchService(retriever).answer('Doanh thu thuần của Hòa Phát năm 2024', 'test'))
    assert result['status'] == 'NO_DATA' and result['reason_code'] == 'COMPANY_NOT_IN_CORPUS'
    assert 'HPG' in result['message'] and 'FPT, MBB, VCB' in result['message']
    assert retriever.calls[0]['companies'] == ['HPG']


def test_a_missing_row_of_a_corpus_company_keeps_the_ordinary_no_data_message():
    result = asyncio.run(LiveResearchService(EmptyRetriever(['FPT'])).answer('Doanh thu thuần của FPT năm 2031', 'test'))
    assert result['reason_code'] == 'NO_DATA'


def test_the_corpus_lookup_failing_never_breaks_the_answer():
    class Broken(EmptyRetriever):
        async def corpus_companies(self): raise OSError('database detail')
    result = asyncio.run(LiveResearchService(Broken([])).answer('Doanh thu thuần của Hòa Phát năm 2024', 'test'))
    assert result['reason_code'] == 'NO_DATA' and 'database' not in str(result)


def test_every_hand_written_metric_code_is_a_code_the_ingestion_catalog_produces():
    """A code that no statement row carries (as TOTAL_EQUITY was) can be parsed but never answered."""
    from src.financial.mapping import INDUSTRY_SECTION_MAPS, SECTION_MAPS
    produced = {code for maps in (SECTION_MAPS, *INDUSTRY_SECTION_MAPS.values()) for section in maps.values() for code in section.values()}
    assert [code for code in (*vocab.CURATED, *vocab.COMMON_NAMES) if code not in produced] == []


def test_equity_resolves_to_the_row_that_exists_in_the_data():
    assert scope('Vốn chủ sở hữu của MBB quý 2/2026')['metric_code'] == 'OWNERS_EQUITY'
    picked = analyze_live('vốn của fpt quý 2/2026')
    assert [o.get('metric_code') for o in picked['clarification_options']] == ['OWNERS_EQUITY', 'CHARTER_CAPITAL']
    assert analyze_live('1', picked['scope'])['scope']['metric_code'] == 'OWNERS_EQUITY'
