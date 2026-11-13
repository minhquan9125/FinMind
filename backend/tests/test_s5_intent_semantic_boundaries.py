"""Second review: lexical evidence must respect Vietnamese spelling and goals."""
import unicodedata

import pytest

from src.retrieval_orchestration.intent_semantic_requests import explicit_intent, requests, resolve_objectives

LABELS = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']


@pytest.mark.parametrize('question', [
    'Lợi nhuận FPT có độc lập với mảng viễn thông không?',
    'Loi nhuan FPT co doc lap voi mang vien thong khong?',
    'Đọc báo cáo chất lượng dịch vụ của FPT.',
    'Đọc nội dung về sản lượng điện của GEG.',
])
def test_homographs_do_not_create_numeric_evidence(question):
    assert explicit_intent(question) != 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Đọc doanh thu FPT năm 2024.',
    'Doc doanh thu FPT nam 2024.',
    'Lương CEO FPT năm 2024 là bao nhiêu?',
    'Luong CEO FPT nam 2024 la bao nhieu?',
    'Giá cổ phiếu FPT hôm nay bao nhiêu?',
    'Doanh thu AI và cloud của FPT là bao nhiêu?',
])
def test_legitimate_value_requests_remain_numeric(question):
    assert explicit_intent(question) == 'NUMERIC'


@pytest.mark.parametrize('form', ['NFC', 'NFD'])
def test_homograph_protection_is_unicode_normalization_independent(form):
    assert explicit_intent(unicodedata.normalize(form, 'Lợi nhuận có độc lập không?')) != 'NUMERIC'
    assert explicit_intent(unicodedata.normalize(form, 'Đọc doanh thu FPT.')) == 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Ai đang làm CEO của FPT?',
    'Ai hiện đang đảm nhiệm chức Tổng giám đốc của VNM?',
    'Người đứng đầu FPT là ai?',
    'Nguoi dung dau DGC la ai?',
])
def test_role_paraphrases_have_explicit_role_evidence(question):
    assert explicit_intent(question) == 'PERSON_ROLE'


@pytest.mark.parametrize('question', ['FPT có tin gì mới?', 'VNM co tin tuc gi moi?'])
def test_indirect_news_questions_have_news_evidence(question):
    assert explicit_intent(question) == 'NEWS'


@pytest.mark.parametrize('question', [
    'Lương CEO FPT bao nhiêu?',
    'Tìm bài tin về người đứng đầu FPT.',
    'Doanh thu AI của FPT bao nhiêu?',
])
def test_role_paraphrases_do_not_override_other_goals(question):
    assert explicit_intent(question) != 'PERSON_ROLE'


def test_financial_change_explanation_is_not_every_why_question():
    assert explicit_intent('Giải thích vì sao doanh thu FPT giảm qua ba năm.') == 'TREND'
    assert explicit_intent('Giải thích vì sao ông An được bổ nhiệm.') is None
    assert explicit_intent('Giải thích vì sao doanh thu giảm theo bài tin đã chỉ định.') is None


def test_numeric_and_independent_causal_analysis_are_mixed():
    texts = requests('Cho biết doanh thu FPT năm 2024 rồi giải thích vì sao doanh thu giảm qua ba năm.')
    decision = resolve_objectives([.1, .1, .1, .4, .1, .1, .1], [], LABELS, texts)
    assert decision['intent_label'] == 'MIXED'
    assert set(decision['component_labels']) == {'NUMERIC', 'TREND'}


def test_rejected_numeric_evidence_does_not_override_classifier_head():
    base = [.1, .1, .1, .1, .1, .1, .4]
    result = resolve_objectives(base, [], LABELS, ['Lợi nhuận FPT có độc lập với mảng viễn thông không?'])
    assert result['intent_label'] == 'TREND'
    assert result['confidence'] is None and result['runtime_enabled'] is False
    assert base == [.1, .1, .1, .1, .1, .1, .4]


def test_read_report_content_is_report_instead_of_a_salary_metric():
    assert explicit_intent('Đọc báo cáo chất lượng dịch vụ của FPT.') == 'REPORT_CONTENT'


def test_indirect_news_can_be_an_independent_clause():
    text = 'FPT có tin gì mới rồi cho biết EPS FPT năm 2024.'
    assert len(requests(text)) == 2


@pytest.mark.parametrize('question', [
    'Doc lap cua loi nhuan FPT voi mang vien thong la the nao?',
    'Doc luong khach cua VJC nam 2024.',
])
def test_ambiguous_ascii_read_and_salary_need_context(question):
    assert explicit_intent(question) != 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Giải thích vì sao chất lượng dịch vụ giảm qua ba năm.',
    'Giai thich vi sao chat luong dich vu giam qua ba nam.',
])
def test_quantity_homograph_is_not_financial_trend_evidence(question):
    assert explicit_intent(question) != 'TREND'


# --- Hưng review 13/11: patterns for the 25 wrong-route rows (all WHOLE_QUERY_UNCHANGED) ---
@pytest.mark.parametrize('question,label', [
    ('Trong thuyết minh báo cáo tài chính 2022 của VCB, nguyên tắc khấu hao được giải thích ra sao?', 'REPORT_CONTENT'),
    ('Báo cáo thường niên 2022 của DGC nói gì về đào tạo nhân viên?', 'REPORT_CONTENT'),
    ('Tóm tắt phần đào tạo nhân viên trong BCTN PNJ 2022', 'REPORT_CONTENT'),
    ('Nhận định đà mở rộng doanh thu VCB từ năm 2020 đến 2023.', 'TREND'),
    ('Diễn biến thị giá VCB trong tháng 08/2024 nghiêng về chiều nào?', 'TREND'),
    ('Xu hướng giá FPT 3 tháng qua thế nào?', 'TREND'),
    ('Có bài báo nào nói về việc thay kế toán trưởng TCB trong tháng 02/2024?', 'NEWS'),
    ('Nội dung bài báo DGC tổ chức đại hội ngày 20/04/2022 là gì?', 'NEWS'),
    ('danh sách bài báo phát hành cổ phiếu tháng 03/2023', 'NEWS'),
    ('Xin con số vốn chủ sở hữu TCB tại ngày cuối năm 2023.', 'NUMERIC'),
    ('Xin số vốn chủ sở hữu VCB cuối 2023', 'NUMERIC'),
    ('Sản lượng điện EVN năm 2025 là bao nhiêu?', 'NUMERIC'),
    ('BCTN REE 2022 ghi nhan ai phu trach vi tri ke toan truong tai cuoi nam?', 'PERSON_ROLE'),
    ('Ai là người đứng đầu FPT?', 'PERSON_ROLE'),
    ('Ai là Tổng giám đốc TCB', 'PERSON_ROLE'),
    ('Cho tên người điều hành TCB cuối 2022', 'PERSON_ROLE'),
    ('Theo BCTN REE 2023, REE va cong ty Song Xanh co quan he hop tac khong?', 'ENTITY_RELATION'),
    ('Những cá nhân nào là cổ đông của TCB tại cuối 2022?', 'ENTITY_RELATION'),
])
def test_review_patterns_give_explicit_evidence(question, label):
    assert explicit_intent(question) == label


@pytest.mark.parametrize('question,labels', [
    ('Xin số vốn chủ sở hữu VCB cuối 2023 kèm danh sách bài báo phát hành cổ phiếu tháng 03/2023.', {'NUMERIC', 'NEWS'}),
    ('Ai là Tổng giám đốc TCB và chiến lược kinh doanh người này nêu trong báo cáo thường niên là gì?',
     {'PERSON_ROLE', 'REPORT_CONTENT'}),
    ('Cho tên người điều hành TCB cuối 2022, đồng thời giải thích chính sách khấu hao trong BCTC 2022.',
     {'PERSON_ROLE', 'REPORT_CONTENT'}),
    ('Tóm tắt phần đào tạo nhân viên trong BCTN PNJ 2022, rồi tìm bài báo về đại hội PNJ tháng 04/2022.',
     {'REPORT_CONTENT', 'NEWS'}),
])
def test_review_compound_questions_are_mixed(question, labels):
    texts = requests(question)
    decision = resolve_objectives([.1, .1, .1, .4, .1, .1, .1], [], LABELS, texts)
    assert decision['intent_label'] == 'MIXED' and set(decision['component_labels']) == labels


@pytest.mark.parametrize('question,expected', [
    ('Thông báo bổ nhiệm Tổng giám đốc FPT ngày nào có hiệu lực?', None),
    ('Lợi nhuận trong BCTC 2022 của FPT là bao nhiêu?', 'NUMERIC'),
    ('Giá cổ phiếu FPT hôm nay bao nhiêu?', 'NUMERIC'),
    ('Theo bài báo hôm qua, lợi nhuận FPT quý 3 là bao nhiêu?', 'NUMERIC'),
    ('Doanh thu và lợi nhuận kèm theo của FPT năm 2025 là bao nhiêu?', 'NUMERIC'),
])
def test_review_patterns_keep_existing_decisions(question, expected):
    assert explicit_intent(question) == expected
    assert len(requests(question)) == 1

@pytest.mark.parametrize('question,expected', [
    ('Ai đảm trách vị trí trưởng ban kiểm soát DGC tại tháng 12/2021?', 'PERSON_ROLE'),
    ('Trong BCTC riêng của công ty mẹ HPG năm 2023, số dư tiền cuối năm là bao nhiêu?', None),
    ('HPG có kiểm soát công ty Bình Minh tại 31/12/2023 không?', 'ENTITY_RELATION'),
])
def test_relation_pattern_does_not_capture_roles_or_parent_statements(question, expected):
    # Replay of run03 found these three regressions in the first draft of the relation pattern.
    assert explicit_intent(question) == expected

