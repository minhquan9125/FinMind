import pytest
from src.retrieval_orchestration.live_research import analyze_live
from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver
from src.retrieval_orchestration.input_normalization import company_token_text


@pytest.mark.parametrize('place',['TP.HCM','TP HCM','Thành phố HCM'])
def test_explicit_city_is_not_a_second_company(place):
    question=f'Vietcombank chi nhánh {place} nhận phần thưởng gì tại lễ kỷ niệm 50 năm?'
    assert analyze_live(question)['scope']['companies']==['VCB']
    assert ScopeResolver().resolve(question).scope.companies==['VCB']


def test_real_hcm_ticker_is_preserved_even_with_a_city_in_the_same_question():
    text='Cổ phiếu HCM, doanh nghiệp tại TP.HCM'
    assert company_token_text(text).startswith('Cổ phiếu HCM')
    assert ScopeResolver().resolve('Cổ phiếu HCM thuộc công ty nào?').scope.companies==['HCM']
