"""Freeze experimental samples, development controls and unscored later-check cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs/sprint5/intent-experiment-v2'
# Separate template families for the library, development and later check.
LIBRARY = {
 'NUMERIC': ['Doanh thu thuần của {c} năm 2024 là bao nhiêu?', 'Cho biết ROE của {c} năm 2023.', 'Tổng nợ của {c} cuối năm 2024 bằng bao nhiêu đồng?', 'Lợi nhuận sau thuế {c} năm 2024 chênh năm 2023 bao nhiêu?'],
 'REPORT_CONTENT': ['Tóm tắt chiến lược kinh doanh trong BCTN {c} năm 2024.', 'Giải thích chính sách kế toán doanh thu trong BCTC {c} năm 2023.', 'Trích đoạn mô tả rủi ro trong BCTN {c} năm 2024.', 'BCTN {c} năm 2023 trình bày định hướng phát triển thế nào?'],
 'NEWS': ['Tìm bài tin về bổ nhiệm Tổng giám đốc {c} năm 2024.', 'Liệt kê tin chia cổ tức {c} trong tháng 05/2024.', 'Tóm tắt các bài báo về dự án mới của {c} tháng 06/2024.', 'Trích nguyên văn thông báo miễn nhiệm Chủ tịch {c} tháng 07/2024.'],
 'PERSON_ROLE': ['Ai là Chủ tịch HĐQT {c} cuối năm 2024?', 'Ai giữ chức Tổng giám đốc {c} tại 31/12/2023?', 'Theo BCTN {c} năm 2024, bà Lan giữ chức vụ nào?', 'Ông Minh được bổ nhiệm làm Giám đốc tài chính {c} ngày nào năm 2023?'],
 'ENTITY_RELATION': ['{c} có những công ty con nào cuối năm 2024?', 'Đối tác hợp tác của {c} trong dự án năm 2023 là doanh nghiệp nào?', 'Ông Nam sở hữu bao nhiêu phần trăm cổ phần {c} cuối năm 2024?', 'Doanh nghiệp nào là công ty mẹ của {c} tại 31/12/2023?'],
 'TREND': ['Nhận xét xu hướng doanh thu {c} giai đoạn 2021–2024.', 'Giá cổ phiếu {c} tăng hay giảm trong quý II/2024?', 'Biên lợi nhuận {c} đang cải thiện hay suy giảm từ 2022 đến 2024?', 'Đánh giá mức ổn định tăng trưởng lợi nhuận {c} qua ba năm 2022–2024.'],
 'MIXED': ['Ai là Tổng giám đốc {c} cuối 2024 và tóm tắt chiến lược trong BCTN 2024?', 'Cho biết doanh thu {c} năm 2024 và tìm bài tin chia cổ tức tháng 05/2024.', 'Liệt kê công ty con {c} cuối 2024 và đánh giá xu hướng giá {c} quý I/2025.', 'Tóm tắt rủi ro trong BCTN {c} năm 2024 và liệt kê bài báo liên quan tháng 01/2025.']}
DEV = {
 'NUMERIC': ['EPS của {c} trong kỳ tài chính 2022 bằng mấy đồng?', 'Xin con số vốn chủ sở hữu {c} tại ngày cuối năm 2023.', 'Giá đóng cửa {c} phiên 12/08/2024 là bao nhiêu?'],
 'REPORT_CONTENT': ['Ban điều hành {c} mô tả kế hoạch mở rộng thế nào trong báo cáo thường niên 2022?', 'Trong thuyết minh báo cáo tài chính 2022 của {c}, nguyên tắc khấu hao được giải thích ra sao?', 'Hãy rút gọn phần cam kết môi trường của {c} ở báo cáo thường niên 2023.'],
 'NEWS': ['Có bài báo nào nói về việc thay kế toán trưởng {c} trong tháng 02/2024?', 'Tôi muốn đọc tin về {c} phát hành cổ phiếu tháng 03/2023.', 'Tóm lược bài tin {c} mở nhà máy đăng ngày 10/04/2024.'],
 'PERSON_ROLE': ['Tên người đảm nhiệm ghế Chủ tịch Hội đồng quản trị {c} tại cuối 2022 là gì?', 'Chức danh của ông Hải tại {c} được ghi trong BCTN 2022 là gì?', 'Ngày bắt đầu nhiệm kỳ Tổng giám đốc {c} theo báo cáo thường niên 2023 là ngày nào?'],
 'ENTITY_RELATION': ['{c} và Sao Việt có quan hệ liên kết tại cuối 2022 không?', 'Tìm doanh nghiệp mà {c} nắm quyền kiểm soát tại 30/06/2023.', 'Những cá nhân nào là cổ đông của {c} tại cuối 2022?'],
 'TREND': ['Khả năng sinh lời {c} có tốt dần trong các năm 2020–2023 không?', 'Diễn biến thị giá {c} trong tháng 08/2024 nghiêng về chiều nào?', 'Nhận định đà mở rộng doanh thu {c} từ năm 2020 đến 2023.'],
 'MIXED': ['Cho tên người điều hành {c} cuối 2022, đồng thời giải thích chính sách khấu hao trong BCTC 2022.', 'Xin số vốn chủ sở hữu {c} cuối 2023 kèm danh sách bài báo phát hành cổ phiếu tháng 03/2023.', 'Xác định công ty liên kết {c} cuối 2022, rồi nhận định đà doanh thu {c} từ 2020 đến 2023.']}
LATER = {
 'NUMERIC': ['Tỷ lệ chi trả cổ tức của {c} trong năm 2021 đạt mức nào?', 'Mức tiền và tương đương tiền {c} tại 30/06/2022 là bao nhiêu?'],
 'REPORT_CONTENT': ['Diễn giải mục quản trị rủi ro thanh khoản trong báo cáo tài chính {c} năm 2021.', 'Báo cáo thường niên 2022 của {c} nói gì về đào tạo nhân viên?'],
 'NEWS': ['Tìm các bản tin về {c} ký hợp đồng xuất khẩu tháng 09/2022.', 'Nội dung bài báo {c} tổ chức đại hội ngày 20/04/2022 là gì?'],
 'PERSON_ROLE': ['Ai đảm trách vị trí trưởng ban kiểm soát {c} tại tháng 12/2021?', 'Bà Mai thôi chức thành viên HĐQT {c} vào thời điểm nào năm 2022?'],
 'ENTITY_RELATION': ['Nhà đầu tư nào nắm cổ phần chi phối {c} tại cuối 2021?', 'Tại cuối 2022, {c} là đối tác của doanh nghiệp nào?'],
 'TREND': ['Đà tăng chi phí hoạt động {c} giai đoạn 2019–2022 đang nhanh lên hay chậm lại?', 'Đánh giá diễn biến ROA {c} qua các năm 2019–2022.'],
 'MIXED': ['Xem ai là trưởng ban kiểm soát {c} cuối 2021 và lấy tỷ lệ chi trả cổ tức {c} năm đó.', 'Tóm tắt phần đào tạo nhân viên trong BCTN {c} 2022, rồi tìm bài báo về đại hội {c} tháng 04/2022.']}


def make_rows(templates, companies, split):
    rows = []
    for label, phrases in templates.items():
        for i, phrase in enumerate(phrases, 1):
            for company in companies:
                rows.append(dict(id=f'{split}-{label}-{i}-{company}', text=phrase.format(c=company),
                                 intent_label=label, company=company, family_id=f'{split}-{label}-{i}', split=split))
    return rows


def main():
    if DEST.exists():
        raise FileExistsError(DEST)
    DEST.mkdir()
    files = {}
    for name, rows in [('library-draft.jsonl', make_rows(LIBRARY, ['VCB','TCB','MBB','FPT'], 'LIBRARY')),
                       ('development.jsonl', make_rows(DEV, ['VCB','TCB','MBB','FPT'], 'DEV')),
                       ('later-check-UNSCORED.jsonl', make_rows(LATER, ['DGC','PNJ'], 'LATER'))]:
        raw = ''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows).encode('utf-8')
        (DEST/name).write_bytes(raw)
        files[name] = dict(rows=len(rows), sha256=hashlib.sha256(raw).hexdigest())
    manifest = dict(version='intent-experiment-v2-draft1', approval='DRAFT_NOT_RUNTIME',
                    authored_by_same_agent=True, blind_test=False,
                    later_check_policy='NOT_SCORED_BY_RUNNER_REQUIRES_TEAM_REVIEW', files=files)
    (DEST/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
