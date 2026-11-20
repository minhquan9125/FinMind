from src.b1_answering.evidence.news_extract import missing_years


def test_publication_date_does_not_require_a_reporting_year():
    evidence={'a':{'passage':'Tin cafef | 2026-08-13 | Số cổ phiếu đang lưu hành'}}
    assert missing_years('Tin ITD ngày 13/08/2026 nêu số cổ phiếu bao nhiêu?',evidence)==[]


def test_iso_event_date_does_not_require_a_reporting_year():
    assert missing_years('Thông báo có hiệu lực 2026-09-01?',{'a':{'passage':'Thông báo'}})==[]


def test_explicit_reporting_year_remains_checked_alongside_publication_date():
    evidence={'a':{'passage':'Tin đăng 2026-08-13, doanh thu năm 2024'}}
    assert missing_years('Bài ngày 13/08/2026 nói doanh thu năm 2025 bao nhiêu?',evidence)==['2025']
