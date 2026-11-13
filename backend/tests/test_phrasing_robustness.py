"""Wording around a question must not change which company, entity or evidence it resolves to.

These cover general rules (diacritic words are never tickers; an undeclared statement entity is
treated as consolidated but never as parent), not particular questions.
"""
import pytest

from src.b1_answering.evidence.live_contract import declared_reporting_entity, reporting_entity_matches
from src.retrieval_orchestration.live_research import analyze_live

STATEMENT_HEADER = 'Công ty Cổ phần FPT (FPT) | Báo cáo Kết quả hoạt động kinh doanh | năm 2024 (cả năm) | Phạm vi: INCOME_STATEMENT | Đơn vị: ...'


def test_statement_type_in_the_scope_field_does_not_declare_an_entity():
    assert declared_reporting_entity(STATEMENT_HEADER) is None
    assert declared_reporting_entity('FPT | Phạm vi: BALANCE_SHEET | x') is None
    assert declared_reporting_entity('FPT | Phạm vi: hợp nhất | x') == 'CONSOLIDATED'
    assert declared_reporting_entity('FPT | Phạm vi: Riêng | x') == 'PARENT'
    assert declared_reporting_entity('FPT | quý 2/2026 (riêng quý) | Phạm vi: INCOME_STATEMENT') is None


def test_consolidated_question_accepts_an_undeclared_chunk():
    assert reporting_entity_matches(STATEMENT_HEADER, 'CONSOLIDATED') is True
    assert reporting_entity_matches(STATEMENT_HEADER, 'UNKNOWN') is True


def test_parent_question_never_accepts_an_undeclared_chunk():
    assert reporting_entity_matches(STATEMENT_HEADER, 'PARENT') is False


def test_a_chunk_declaring_the_other_entity_is_always_rejected():
    parent = 'FPT | Phạm vi: riêng | lũy kế'
    consolidated = 'FPT | Phạm vi: hợp nhất | lũy kế'
    assert reporting_entity_matches(parent, 'CONSOLIDATED') is False
    assert reporting_entity_matches(consolidated, 'PARENT') is False
    assert reporting_entity_matches(consolidated, 'CONSOLIDATED') is True
    assert reporting_entity_matches(parent, 'PARENT') is True


def test_unknown_expected_entity_value_is_rejected():
    assert reporting_entity_matches('FPT | Phạm vi: hợp nhất', 'SOMETHING_ELSE') is False


@pytest.mark.parametrize('question', [
    'Tổng tài sản của Tập đoàn FPT năm 2024 là bao nhiêu?',
    'Tổng tài sản của tập đoàn FPT năm 2024',
    'Tổng tài sản của Nhóm công ty FPT năm 2024',
    'Tổng tài sản của Đoàn FPT năm 2024',
    'tong tai san cua tap doan fpt nam 2024',
])
def test_corporate_words_before_a_ticker_are_not_extra_companies(question):
    scope = analyze_live(question)['scope']
    assert scope['companies'] == ['FPT']


@pytest.mark.parametrize('question', [
    'Doanh thu thuần năm 2024 của FPT',
    'Tổng doanh thu thuần về bán hàng và cung cấp dịch vụ hợp nhất của FPT trong năm 2024 là bao nhiêu?',
    'Doanh thu thuần hợp nhất của FPT năm 2024',
])
def test_wordier_phrasing_keeps_the_same_company_metric_and_period(question):
    scope = analyze_live(question)['scope']
    assert (scope['companies'], scope['metric_code'], scope['periods']) == (['FPT'], 'NET_REVENUE', ['2024'])


def test_an_unlisted_ticker_typed_in_lowercase_is_still_detected():
    assert 'HPG' in analyze_live('doanh thu của hpg năm 2024')['scope']['companies']


def test_explicit_entity_words_are_still_read():
    assert analyze_live('Doanh thu thuần hợp nhất của FPT năm 2024')['scope']['reporting_entity'] == 'CONSOLIDATED'
    assert analyze_live('Doanh thu thuần riêng lẻ của FPT năm 2024')['scope']['reporting_entity'] == 'PARENT'
