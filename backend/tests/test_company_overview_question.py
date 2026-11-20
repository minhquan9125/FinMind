import pytest
from src.retrieval_orchestration.live_research import analyze_live
from src.retrieval_orchestration.source_intent import company_overview_question


@pytest.mark.parametrize('symbol',['FPT','CTG','MBB','TCB','BID','VCB','CMG','ELC','ITD','ICT'])
def test_general_company_question_is_not_a_financial_metric_menu(symbol):
    text=f'bạn cho tôi xem công ty {symbol.lower()} bây giờ ra sao'
    decision=analyze_live(text)
    assert decision['decision']=='SEARCH'
    assert decision['scope']['source_type']=='COMPANY_PROFILE'
    assert decision['scope']['companies']==[symbol]


@pytest.mark.parametrize('text',[
    'Tổng tài sản FPT bây giờ ra sao?',
    'Nhân sự FPT hiện tại như thế nào?',
    'Chi nhánh MBB bây giờ ra sao?',
    'Báo cáo FPT như thế nào?',
    'Giá FPT bây giờ ra sao?',
])
def test_specific_subject_does_not_become_company_profile(text):
    assert not company_overview_question(text)
