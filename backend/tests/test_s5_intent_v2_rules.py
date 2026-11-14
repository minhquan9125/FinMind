"""User-goal boundaries for the isolated eleven-label intent rules."""

import pytest

from src.retrieval_orchestration.intent_v2_rules import explicit_intent, requests


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        pytest.param(
            "Doanh thu FPT đã tăng từ năm 2022 đến năm 2023 bao nhiêu tỷ đồng?",
            "NUMERIC",
            id="revenue-arithmetic-is-numeric",
        ),
        pytest.param(
            "Giá cổ phiếu FPT đã tăng bao nhiêu đồng từ năm 2022 đến năm 2023?",
            "PRICE",
            id="price-arithmetic-is-price",
        ),
        ("Giá cổ phiếu FPT hiện tại là bao nhiêu?", "PRICE"),
        ("Giá đóng cửa FPT ngày 12/11/2025 là bao nhiêu?", "PRICE"),
        ("Khối lượng giao dịch cổ phiếu FPT hôm qua là bao nhiêu?", "PRICE"),
        ("Doanh thu FPT năm 2025 là bao nhiêu?", "NUMERIC"),
        ("Lợi nhuận sau thuế FPT năm 2025 là bao nhiêu?", "NUMERIC"),
        ("ROE của FPT năm 2025 bằng bao nhiêu?", "NUMERIC"),
        ("Sản lượng điện của POW năm 2025 là bao nhiêu?", "NUMERIC"),
        ("Doanh thu AI và dịch vụ cloud của FPT bao nhiêu?", "NUMERIC"),
        ("Theo bài báo đã chỉ định, doanh thu FPT năm 2025 là bao nhiêu?", "NUMERIC"),
        ("Theo báo cáo thường niên, EPS của FPT năm 2025 bằng bao nhiêu?", "NUMERIC"),
        ("Đánh giá xu hướng doanh thu FPT trong ba năm gần đây.", "ANALYSIS"),
        ("Phân tích nguyên nhân giá cổ phiếu FPT giảm.", "ANALYSIS"),
        ("Bạn đánh giá triển vọng kinh doanh của FPT như thế nào?", "ANALYSIS"),
        ("P/E là gì?", "ANALYSIS"),
        ("Giải thích ý nghĩa của chỉ số ROE.", "ANALYSIS"),
        pytest.param(
            "Bài báo đã chỉ định mô tả xu hướng giá FPT như thế nào?",
            "NEWS",
            id="article-trend-content-is-news",
        ),
        pytest.param(
            "Tóm tắt nhận định về diễn biến giá FPT trong bài báo đã chỉ định.",
            "NEWS",
            id="article-price-commentary-is-news",
        ),
        ("Tìm các bài báo mới nhất về FPT.", "NEWS"),
        ("Tóm tắt nội dung bài báo đã chỉ định về FPT.", "NEWS"),
        ("Trích nội dung bài báo có tiêu đề 'Có nên mua FPT lúc này?'.", "NEWS"),
        ("Tóm tắt khuyến nghị mua bán và giá mục tiêu FPT trong bài báo đã chỉ định.", "NEWS"),
        ("Tóm tắt nội dung báo cáo thường niên FPT năm 2025.", "REPORT_CONTENT"),
        ("Trích nguyên văn chính sách ghi nhận doanh thu trong BCTC FPT.", "REPORT_CONTENT"),
        ("Đọc nội dung phần quản trị công ty trong báo cáo thường niên FPT.", "REPORT_CONTENT"),
        ("Tóm tắt nhận định về diễn biến giá FPT trong báo cáo đã chỉ định.", "REPORT_CONTENT"),
        ("Ai là chủ tịch hội đồng quản trị của FPT?", "PERSON_ROLE"),
        ("CEO của FPT là ai?", "PERSON_ROLE"),
        ("Thành viên hội đồng quản trị độc lập của FPT là ai?", "PERSON_ROLE"),
        ("Ai là người có mức lương được công bố cao nhất trong ban điều hành FPT?", "PERSON_ROLE"),
        ("FPT có những công ty con nào?", "ENTITY_RELATION"),
        ("Ông Nguyễn Văn An sở hữu bao nhiêu phần trăm cổ phần FPT?", "ENTITY_RELATION"),
        ("Những cá nhân nào là cổ đông lớn của FPT?", "ENTITY_RELATION"),
        ("Giới thiệu tổng quan về công ty FPT.", "COMPANY_OVERVIEW"),
        ("FPT hoạt động trong những lĩnh vực kinh doanh nào?", "COMPANY_OVERVIEW"),
        ("Xin chào!", "CONVERSATION"),
        ("Cảm ơn bạn!", "CONVERSATION"),
        ("Tiếp tục câu trả lời trước.", "CONVERSATION"),
        ("Tôi chọn phương án thứ hai.", "CONVERSATION"),
        ("Tôi có 100 triệu đồng, có nên mua cổ phiếu FPT ngay không?", "OUT_OF_SCOPE"),
        ("Tôi đang giữ FPT, hãy khuyên tôi nên bán hay giữ.", "OUT_OF_SCOPE"),
        ("Dự đoán giá cổ phiếu FPT vào tháng sau.", "OUT_OF_SCOPE"),
        ("Hãy đặt giá mục tiêu cho cổ phiếu FPT năm tới.", "OUT_OF_SCOPE"),
        ("Hướng dẫn tôi nấu phở bò.", "OUT_OF_SCOPE"),
        ("Giải thích sự khác biệt giữa lợi nhuận kế toán và dòng tiền kinh doanh.", "ANALYSIS"),
        ("Đọc thuyết minh về phương pháp ghi nhận doanh thu của FPT trong báo cáo đã gửi.", "REPORT_CONTENT"),
        ("Chọn bài báo đầu tiên trong danh sách làm nguồn cho câu hỏi tiếp theo.", "CONVERSATION"),
        ("Theo bạn tuần sau cổ phiếu HPG sẽ lên mức giá nào?", "OUT_OF_SCOPE"),
        ("Tính cho tôi một mức giá bán mục tiêu mới của PNJ cho năm sau.", "OUT_OF_SCOPE"),
        ("Lấy giá mục tiêu mà bài báo đã công bố, không tự dự báo.", "NEWS"),
        ("Đọc thuyết minh về lương CEO đã công bố.", "REPORT_CONTENT"),
        ("Trong BCTC riêng của công ty mẹ ABC, số dư tiền cuối năm bao nhiêu?", "NUMERIC"),
        ("Theo bài tin đã nêu, bà Hoa được bổ nhiệm giữ chức gì?", "PERSON_ROLE"),
        ("Theo BCTN, ai là KTT? Trích câu làm bằng chứng cho câu trả lời.", "PERSON_ROLE"),
        ("Sự kiện này có những doanh nghiệp nào tham gia?", "ENTITY_RELATION"),
        ("LNST đang tăng tốc hay chậm lại? Giải thích XH đó.", "ANALYSIS"),
        ("Vui lòng: Liệt kê vốn chủ sở hữu VNM qua các năm 2021, 2022 và 2023.", "NUMERIC"),
        ("Vui lòng: Nội dung bài tin về đại hội cổ đông DGC là gì?", "NEWS"),
    ],
)
def test_explicit_intent_follows_the_requested_goal(question, expected):
    assert explicit_intent(question) == expected


@pytest.mark.parametrize(
    ("question", "clause_phrases"),
    [
        (
            "Cho biết doanh thu FPT năm 2025 và tìm bài báo mới nhất về FPT.",
            ["doanh thu FPT", "bài báo mới nhất"],
        ),
        (
            "Cho biết giá cổ phiếu FPT rồi phân tích xu hướng doanh thu FPT.",
            ["giá cổ phiếu FPT", "xu hướng doanh thu FPT"],
        ),
        (
            "Tóm tắt báo cáo thường niên FPT kèm cho biết CEO của FPT là ai.",
            ["báo cáo thường niên FPT", "CEO của FPT"],
        ),
        (
            "Giá đóng cửa FPT hôm qua là bao nhiêu; ai là chủ tịch FPT?",
            ["Giá đóng cửa FPT", "chủ tịch FPT"],
        ),
        (
            "Cho biết doanh thu FPT rồi tìm bài báo về FPT; giới thiệu tổng quan FPT.",
            ["doanh thu FPT", "bài báo về FPT", "tổng quan FPT"],
        ),
        (
            "BCTN ghi bà Mai đảm nhiệm chức danh nào? Báo cáo mô tả chính sách kiểm soát nội bộ ra sao?",
            ["chức danh", "chính sách"],
        ),
        ("Tóm tắt tin ACB; kèm bảng EPS theo BCTC.", ["tin ACB", "bảng EPS"]),
        ("Công ty A kiểm soát công ty B không, và XH giá cổ phiếu ra sao?", ["kiểm soát", "XH giá"]),
    ],
)
def test_requests_separates_independent_actions(question, clause_phrases):
    clauses = requests(question)

    assert len(clauses) == len(clause_phrases)
    for clause, phrase in zip(clauses, clause_phrases):
        assert phrase.casefold() in clause.casefold()


@pytest.mark.parametrize(
    "question",
    [
        "Doanh thu và lợi nhuận FPT 2025 bao nhiêu?",
        "Doanh thu AI và dịch vụ cloud của FPT bao nhiêu?",
        "Giá mở cửa và giá đóng cửa FPT hôm qua là bao nhiêu?",
        "Tóm tắt khuyến nghị mua và bán trong bài báo đã chỉ định.",
        "Cho biết các công ty con và công ty liên kết của FPT.",
        "Theo BCTN FPT, ai là KTT? Trích câu làm bằng chứng cho câu trả lời.",
        "Đọc và tóm lược phần cam kết trong BCTN FPT.",
        "Bài tin FPT trình bày việc trả cổ tức thế nào? Hãy tóm lược bài.",
    ],
)
def test_requests_preserves_coordinated_subjects_with_one_goal(question):
    clauses = requests(question)

    assert len(clauses) == 1
    assert "FPT" in clauses[0] or "bài báo" in clauses[0]
