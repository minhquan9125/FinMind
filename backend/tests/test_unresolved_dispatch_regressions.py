from datetime import date
import pytest
from src.retrieval_orchestration.price_analytics import parse,_period
from src.retrieval_orchestration.conversation_actions import conversation_action


@pytest.mark.parametrize('ticker',['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
def test_annual_shareholder_question_is_not_price_history(ticker):
    assert parse(f'Cơ cấu cổ đông của {ticker} trong BCTN 2025 như thế nào?',[ticker],date(2026,11,20))is None


@pytest.mark.parametrize('question',[
    'Giá trị hợp đồng ký mới của ELC trong 8 tháng 2026 tăng mấy phần trăm?',
    'Hợp đồng ký mới của ELC chỉ tăng 26% trong 8 tháng 2026 đúng không?',
    'Các lô trái phiếu BIDV được niêm yết có tổng giá trị theo mệnh giá bao nhiêu?',
])
def test_corporate_values_and_contract_growth_are_not_share_price(question):
    assert parse(question,['ELC','BID'],date(2026,11,20))is None


def test_year_cannot_be_read_as_a_month_prefix():
    assert _period('8 thang 2026',date(2026,11,20))[0]==date(2026,1,1)


@pytest.mark.parametrize('question',[
    'BIDV mua lại bao nhiêu trái phiếu, gồm những mã nào?',
    'Mạng lưới BIDV gồm bao nhiêu chi nhánh?',
    'Giá trị cốt lõi của BIDV gồm những gì?',
])
def test_in_sentence_gom_does_not_request_a_chat_summary(question):
    assert conversation_action(question)is None


def test_explicit_chat_summary_remains_a_command():
    assert conversation_action('Tổng hợp nội dung chat nãy giờ')=='SUMMARY'


def test_foundation_syllable_is_not_a_stock_price_increase():
    assert parse('Thông điệp Chủ tịch trong báo cáo CTG 2024 nêu hành trình X01 hoàn thành bao nhiêu sáng kiến nền tảng?',
        ['CTG'],date(2026,11,20))is None


def test_chairman_message_names_an_annual_report_topic():
    from src.retrieval_orchestration.live_research import analyze_live
    r=analyze_live('Thông điệp Chủ tịch trong báo cáo CTG 2024 nêu hành trình X01 hoàn thành bao nhiêu sáng kiến nền tảng?')
    assert r['scope']['source_type']=='BCTN'
    assert r['scope']['periods']==['2024']


@pytest.mark.parametrize('symbol',['CTG','MBB','TCB','FPT','BID','VCB','ITD','ICT','CMG','ELC'])
def test_annual_topic_noun_is_not_a_news_summary_command(symbol):
    from src.retrieval_orchestration.market_dialogue import article_query
    assert article_query(f'Các nội dung phát triển bền vững mà {symbol} đề cập năm 2025 là gì?')is None


@pytest.mark.parametrize('question',[
    'Tin ITD ngày 13/08/2026 nêu số cổ phiếu có quyền biểu quyết đang lưu hành là bao nhiêu?',
    'Tin 13/8/2026 của ITD ghi bao nhiêu cp có quyền vote đang lưu hành?',
])
def test_dated_article_uses_the_shared_news_reader(question):
    from src.retrieval_orchestration.live_research import analyze_live
    decision=analyze_live(question,today=date(2026,11,20))
    assert decision['decision']=='MARKET_LOOKUP'
    assert decision['scope']['companies']==['ITD']
    assert decision['scope']['_market_request']['day']=='2026-08-13'


def test_a_dated_news_question_does_not_become_financial_period_lookup():
    from src.retrieval_orchestration.market_dialogue import article_content_request
    request=article_content_request('Tin 06/10/2026 cho biết Agtex sở hữu bao nhiêu MBB?',date(2026,11,20))
    assert request['action']=='DETAIL'
