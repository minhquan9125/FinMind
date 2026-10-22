import pytest
from src.documents.query_scope import financial_query_scope


@pytest.mark.parametrize('query,expected',[
    ('Dữ liệu clean FPT tại kỳ 2026-Q2 tiền mặt',(['FPT'],['2026-Q2'])),
    ('BCTC FPT quý 2/2026',(['FPT'],['2026-Q2'])),
    ('FPT quý 2/2026 tiền và các khoản tương đương tiền',(['FPT'],['2026-Q2'])),
    ('fpt quý 2/2026 tiền và các khoản tương đương tiền',(['FPT'],['2026-Q2'])),
    ('BCTC hợp nhất PDF FPT 2024',(['FPT'],['2024-YEAR'])),
    ('Dữ liệu clean FPT 2026-Q1 và 2026-Q2',(['FPT'],['2026-Q1','2026-Q2'])),
    ('Bài tin FPT ngày 01/10/2026',(None,None)),
    ('Theo bài CafeF doanh thu FPT năm 2026',(None,None)),
    ('Lịch sử giá FPT 2026',(None,None)),
    ('BCTC FPT và VCB 2024',(None,None)),
    ('BCTC FPT',(None,None)),
])
def test_explicit_financial_scope(query,expected):
    assert financial_query_scope(query)==expected


@pytest.mark.parametrize('query,code',[
    ('tiền chi mua sắm và xây dựng tài sản cố định','PURCHASE_FIXED_ASSETS'),
    ('doanh thu thuần gắn nhãn 2026-Q1 và 2026-Q2','NET_REVENUE'),
    ('tiền và các khoản tương đương tiền','CASH_AND_CASH_EQUIVALENTS'),
    ('lợi nhuận sau thuế chưa phân phối lũy kế','RETAINED_EARNINGS'),
])
def test_source_metric_names(query,code):
    from src.documents.query_scope import financial_metric_codes
    assert code in financial_metric_codes(query,['FPT'])


def test_excluded_concepts_and_nonfinancial_queries_are_not_constraints():
    from src.documents.query_scope import financial_metric_codes
    assert financial_metric_codes('Không dùng doanh thu thuần',['FPT']) is None
    assert financial_metric_codes('doanh thu thuần',None) is None


def test_ratio_label_alias_does_not_select_equity_or_gross_profit():
    from src.documents.query_scope import financial_metric_codes
    assert financial_metric_codes('tỷ suất sinh lời trên vốn chủ sở hữu (ROE) và biên lợi nhuận gộp',['FPT'])==['GROSS_MARGIN','ROE']
