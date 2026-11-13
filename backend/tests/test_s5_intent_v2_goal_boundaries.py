"""Independently authored regression/development probes, not blind acceptance.

Questions and gold follow intent-labels.v2.json and were fixed before the bug
fix. They are not copied from the library or development datasets. Only the
pure rules APIs are exercised; no encoder, retrieval, network, or DB is needed.
"""

import pytest

from src.retrieval_orchestration.intent_v2_rules import explicit_intent, requests


@pytest.mark.parametrize(
    "question, expected",
    [
        pytest.param('FPT tuần sau lên bao nhiêu?', 'OUT_OF_SCOPE', id='future-price-with-implicit-price-object'),
        pytest.param('FPT mạnh hay yếu?', 'ANALYSIS', id='short-strength-analysis'),
        pytest.param('Thuyết minh nợ vay FPT', 'REPORT_CONTENT', id='report-note-request-without-number'),
        pytest.param('Doanh thu của công ty con FPT', 'NUMERIC', id='short-financial-metric-of-subsidiary'),
        pytest.param(
            "Xin chào, tôi có nên mua FPT hôm nay không?",
            "OUT_OF_SCOPE", id="greeting-does-not-hide-advice",
        ),
        pytest.param(
            "Cam on ban, toi co nen ban MWG luc nay khong?",
            "OUT_OF_SCOPE", id="ascii-thanks-does-not-hide-advice",
        ),
        pytest.param(
            "Bạn có thể giúp tôi quyết định có nên mua TCB không?",
            "OUT_OF_SCOPE", id="polite-help-does-not-hide-advice",
        ),
        pytest.param("Xin chào bạn", "CONVERSATION", id="greeting-only-control"),
        pytest.param(
            "Theo BCTN 2025 của VNM, mục tiêu doanh thu năm tới là bao nhiêu?",
            "NUMERIC", id="reported-revenue-target-is-a-value",
        ),
        pytest.param(
            "Theo BCTN 2025 cua GMD, ke hoach loi nhuan nam toi la bao nhieu?",
            "NUMERIC", id="ascii-reported-profit-plan-is-a-value",
        ),
        pytest.param(
            "Theo bản tin về HPG đã công bố, kế hoạch sản lượng năm tới là bao nhiêu?",
            "NUMERIC", id="news-sourced-operating-target-is-a-value",
        ),
        pytest.param(
            "Hãy dự báo giá cổ phiếu VNM tháng sau",
            "OUT_OF_SCOPE", id="own-price-prediction-control",
        ),
        pytest.param(
            "Tìm bài báo dự báo giá FPT trong tháng tới",
            "NEWS", id="find-forecast-article",
        ),
        pytest.param(
            "Tóm tắt bản tin dự đoán giá MWG năm sau",
            "NEWS", id="retell-forecast-article",
        ),
        pytest.param(
            'Thuật lại bài báo "Có nên mua TCB và giữ đến cuối năm?"',
            "NEWS", id="retell-quoted-source-advice",
        ),
        pytest.param(
            "Dựa trên bản tin về FPT, tôi có nên mua cổ phiếu này không?",
            "OUT_OF_SCOPE", id="news-source-does-not-authorize-own-advice",
        ),
        pytest.param(
            "Trong nội dung BCTN 2025 của VNM, ai giữ chức Chủ tịch HĐQT?",
            "PERSON_ROLE", id="title-holder-with-report-source",
        ),
        pytest.param(
            "Theo noi dung BCTN 2025 cua GMD, tong giam doc la ai?",
            "PERSON_ROLE", id="ascii-title-holder-with-report-source",
        ),
        pytest.param(
            "Trích nguyên văn phần BCTN 2025 của VNM trình bày về Chủ tịch HĐQT",
            "REPORT_CONTENT", id="quote-report-about-title-holder",
        ),
        pytest.param(
            "Tìm BCTN 2025 của TCB có phần giới thiệu ban điều hành",
            "REPORT_CONTENT", id="find-report-about-title-holders",
        ),
    ],
)
def test_explicit_intent_follows_requested_goal(question, expected):
    assert explicit_intent(question) == expected


@pytest.mark.parametrize(
    "question, expected_parts, expected_labels",
    [
        pytest.param(
            "Doanh thu VNM năm 2025 là bao nhiêu và danh sách tin tức mới nhất về VNM",
            ["Doanh thu VNM năm 2025 là bao nhiêu", "danh sách tin tức mới nhất về VNM"],
            ["NUMERIC", "NEWS"], id="numeric-then-news-list",
        ),
        pytest.param(
            "Gia GMD hom nay la bao nhieu va danh sach bai bao moi nhat ve GMD",
            ["Gia GMD hom nay la bao nhieu", "danh sach bai bao moi nhat ve GMD"],
            ["PRICE", "NEWS"], id="ascii-price-then-news-list",
        ),
        pytest.param(
            "Doanh thu HPG năm 2025 là bao nhiêu; liệt kê tin tức mới về HPG",
            ["Doanh thu HPG năm 2025 là bao nhiêu", "liệt kê tin tức mới về HPG"],
            ["NUMERIC", "NEWS"], id="semicolon-independent-goals-control",
        ),
        pytest.param(
            "Cho biết doanh thu và lợi nhuận của VNM năm 2025",
            ["Cho biết doanh thu và lợi nhuận của VNM năm 2025"],
            ["NUMERIC"], id="coordinated-two-metrics-stay-one-request",
        ),
        pytest.param(
            "Cho biet doanh thu, loi nhuan va tong tai san cua GMD nam 2025",
            ["Cho biet doanh thu, loi nhuan va tong tai san cua GMD nam 2025"],
            ["NUMERIC"], id="ascii-three-metrics-stay-one-request",
        ),
        pytest.param(
            'Tóm tắt bài báo "Doanh thu tăng và có nên mua FPT?"',
            ['Tóm tắt bài báo "Doanh thu tăng và có nên mua FPT?"'],
            ["NEWS"], id="quoted-news-advice-conjunction-is-preserved",
        ),
        pytest.param(
            'Trích phần BCTN VNM có tiêu đề "Doanh thu và lợi nhuận; dự báo năm sau"',
            ['Trích phần BCTN VNM có tiêu đề "Doanh thu và lợi nhuận; dự báo năm sau"'],
            ["REPORT_CONTENT"], id="quoted-report-separators-are-preserved",
        ),
    ],
)
def test_requests_preserves_goal_and_quote_boundaries(
    question, expected_parts, expected_labels
):
    parts = requests(question)
    assert parts == expected_parts
    assert [explicit_intent(part) for part in parts] == expected_labels
