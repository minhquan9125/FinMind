"""Golden set parsing and the fact-based answer scoring."""
import pytest

from src.documents.evaluation_scoring import numbers, score_answer
from src.documents.evaluation_set import golden_path, load_golden, parse_golden

VERIFIED = """# Bộ câu hỏi

### Q01
*Phân loại: tin_dự_báo_KQKD*

- **Câu hỏi**: Lợi nhuận quý 3 của MSN?
- **Đáp án chuẩn**: `3.984 tỷ đồng` (tăng 230% YoY).
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q31 (QA-FPT-BCTC-001)
*Phân loại: bctc_bảng_cân_đối*

- **Câu hỏi**: Tiền và tương đương tiền của FPT tại 30/06/2026?
- **Đáp án chuẩn**: `8.843.161.132.730 VND` (hoặc `8.843,16 tỷ VND`).
- **Trạng thái**: ✅ Đã xác thực 100%.
"""

UNAPPROVED = """### Q01 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Hai lô trái phiếu của TCB là gì?

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Mã **TCB12517** (1.740 tỷ đồng) và **TCB12518** (2.500 tỷ đồng).
**Trạng thái:** Chưa có nhãn gold được duyệt.

### Q02 — Từ chối

**Câu hỏi đã sửa:** Câu không có đáp án?
"""


# ---- parsing --------------------------------------------------------------------------------

def test_verified_layout_is_parsed_with_labels_and_the_verified_flag():
    items = parse_golden(VERIFIED)
    assert [i['id'] for i in items] == ['Q01', 'Q31']
    assert items[0]['category'] == 'tin_dự_báo_KQKD' and items[0]['verified'] is True
    assert items[0]['expected'] == '3.984 tỷ đồng (tăng 230% YoY).'
    assert items[1]['label'] == 'QA-FPT-BCTC-001' and 'hoặc' in items[1]['expected']


def test_unapproved_layout_is_parsed_but_not_marked_verified_and_incomplete_blocks_are_skipped():
    items = parse_golden(UNAPPROVED.replace('\n', '\r\n'))      # CRLF files are fine too
    assert [i['id'] for i in items] == ['Q01']
    assert items[0]['verified'] is False and 'TCB12517' in items[0]['expected']
    assert items[0]['label'] == 'Tìm đoạn bằng vector'


def test_the_real_golden_file_loads_forty_verified_questions_when_present():
    if golden_path() is None:
        pytest.skip('golden file not in this checkout')
    items = load_golden()
    assert len(items) == 40 and all(i['question'] and i['expected'] for i in items)
    assert sum(i['verified'] for i in items) >= 30


# ---- numbers --------------------------------------------------------------------------------

@pytest.mark.parametrize('text,expected', [
    ('8.843.161.132.730 VND', [[8843161132730.0]]),
    ('8.843,16 tỷ đồng', [[8843160000000.0]]),
    ('171,4 triệu cổ phiếu', [[171400000.0]]),
    ('tăng 230%', [[230.0]]),
    ('3.000 USD/mtu', [[3000.0]]),
])
def test_vietnamese_number_formats_are_read_with_their_scale(text, expected):
    assert numbers(text) == expected


def test_ambiguous_separators_keep_both_readings_and_dates_years_and_tiny_counts_are_ignored():
    assert numbers('1,740 tỷ') == [[1.74e9, 1.74e12]]
    assert numbers('50.9 nghìn đồng') == [[50900.0]]
    assert numbers('ngày 22/09/2026, quý 3 năm 2026, 2 lô') == []


# ---- scoring --------------------------------------------------------------------------------

def test_matching_unit_variants_count_as_the_same_fact():
    expected = '8.843.161.132.730 VND (hoặc 8.843,16 tỷ VND)'
    assert score_answer(expected, 'Tiền và tương đương tiền là 8.843,16 tỷ đồng.')['level'] == 'PASS'
    assert score_answer(expected, 'Khoảng 8.843.161.132.730 đồng.')['level'] == 'PASS'
    wrong = score_answer(expected, 'Con số là 7.500 tỷ đồng.')
    assert wrong['level'] == 'FAIL' and wrong['matched'] == 0


def test_every_fact_of_a_multi_fact_answer_is_checked():
    expected = 'Phân phối hơn 171,4 triệu cổ phiếu cho 181.748 cổ đông, kết thúc ngày 22/09/2026.'
    full = score_answer(expected, 'FPT phân phối 171,4 triệu cổ phiếu cho 181.748 cổ đông; đợt này kết thúc ngày 22/9/2026.')
    assert full['level'] == 'PASS' and full['matched'] == full['total'] == 3
    one_of_three = score_answer(expected, 'FPT phân phối 171,4 triệu cổ phiếu.')
    assert one_of_three['score'] == 0.333 and one_of_three['level'] == 'FAIL'
    assert [f['matched'] for f in one_of_three['facts']] == [True, False, False]
    two_of_three = score_answer(expected, 'FPT phân phối 171,4 triệu cổ phiếu cho 181.748 cổ đông.')
    assert two_of_three['level'] == 'PARTIAL' and two_of_three['matched'] == 2


def test_identifier_codes_are_matched_case_insensitively():
    result = score_answer('Mã TCB12517 (1.740 tỷ đồng) và TCB12518 (2.500 tỷ đồng).', 'Hai lô là tcb12517 và TCB12518: 1.740 tỷ, 2.500 tỷ.')
    assert result['level'] == 'PASS' and result['total'] == 4


def test_tolerance_is_a_tenth_of_a_percent():
    assert score_answer('Doanh thu 1.000 tỷ đồng', 'Khoảng 1.000,5 tỷ đồng')['level'] == 'PASS'
    assert score_answer('Doanh thu 1.000 tỷ đồng', 'Khoảng 1.010 tỷ đồng')['level'] == 'FAIL'


def test_answers_without_checkable_facts_need_a_human_and_empty_answers_fail():
    assert score_answer('Công ty hoạt động trong lĩnh vực công nghệ.', 'Công nghệ thông tin.')['level'] == 'MANUAL'
    assert score_answer('Doanh thu 5.000 tỷ đồng', '')['level'] == 'FAIL'
    assert score_answer('Doanh thu 5.000 tỷ đồng', None)['score'] == 0.0
