"""Build the review note directly from the saved regression and audit."""
import xml.etree.ElementTree as ET

from run_s5_intent_news import ROOT, OUT, PARENT
from run_s5_intent_reviewfix import read, write


def main():
    summary, results = read(OUT / 'summary.json'), read(OUT / 'results.json')
    prior = read(PARENT / 'summary.json')['metrics']
    audit = read(OUT / 'audit.json')
    suites = ET.parse(OUT.parent / 'unit-all.xml').getroot().findall('testsuite')
    count = sum(int(s.attrib['tests']) for s in suites)
    assert count == 162 and all(int(s.attrib[k]) == 0 for s in suites for k in ['failures', 'errors', 'skipped'])
    assert audit['status'] == 'PASS' and summary['passes_gate']
    lines = [
        '# S5-WBS04.1 — Sửa mục tiêu bài tin và tách nhiều ý, 12/11/2026', '',
        'Ba lỗi NV-13/NV-19/NV-20 đã được sửa ở lớp quyết định offline V6',
        '(`intent-request-objectives-v4`). Không thay BGE-M3, classifier C=1,',
        'training, nhãn chuẩn, raw ranking hoặc ngưỡng 0,65/0,08 của Huyền.', '',
        '## Nguyên nhân và thay đổi', '',
        '- NV-13: mục tiêu là tìm bài tin; thêm nhận diện thao tác trên bài tin',
        '  ở đầu yêu cầu. Câu lấy số từ bài đã chỉ định không tự thành NEWS.',
        '- NV-19: đã tách đúng nhưng điều kiện ghép xác suất không nhận hai ý.',
        '  Nhận diện rõ NUMERIC và NEWS ở hai phần để đề xuất MIXED. Không nới',
        '  điều kiện ghép xác suất chưa hiệu chỉnh cho mọi câu.',
        '- NV-20: thiếu động từ Đọc ở bước tách nên luật CEO ghi đè MIXED đúng.',
        '  Tách vế Đọc giá trị khi có hành động độc lập ở vế kế; danh sách chỉ',
        '  tiêu/mảng AI và cloud/kỳ năm vẫn là một yêu cầu.', '',
        'Không có luật theo mã câu hoặc tên doanh nghiệp. V6 nằm trong module',
        'riêng để giữ source/checksum và cách tái tạo kết quả V3–V5.', '',
        '## Hồi quy 313 hàng đã xem', '',
        '| Bộ | Có nhãn | Trước sửa | Sau sửa |', '|---|---:|---:|---:|',
    ]
    for group, metric in summary['metrics'].items():
        lines.append(f"| {group} | {metric['labeled']} | {prior[group]['correct']} | {metric['correct']} |")
    changed = ', '.join(f"{c['evaluation_set']}/{c['id']}" for c in summary['fixed'])
    lines += ['', f'Sửa đúng thêm: {changed}. Đang đúng thành sai: **0**.',
              '313 hàng gồm 9 câu không có nhãn gold, không tính chúng vào accuracy.',
              '**20 câu bổ sung nay là hồi quy đã xem; không gọi kết quả này là test mù**',
              'hoặc bằng chứng mọi câu mới đều đúng. Còn lỗi trên các tập cũ:', '',
              '| Bộ | Mã còn sai |', '|---|---|']
    for group, metric in summary['metrics'].items():
        if metric['wrong_ids']:
            lines.append(f"| {group} | {', '.join(metric['wrong_ids'])} |")
    lines += ['', '## Kiểm chứng', '',
              '- Test trước sửa: 9 fail, 9 pass; sau sửa 18 ca mới qua.',
              '- Toàn bộ **162/162 unit test ý định Sprint 5 đạt**; không phải suite toàn ứng dụng.',
              '- Lượt green riêng có cảnh báo Windows ở bước lấy thông tin máy khi xuất',
              '  JUnit. Lượt toàn bộ chạy ngoài sandbox kết thúc sạch, exit 0.',
              f"- Audit tái tạo {audit['decisions_replayed']} quyết định, tính lại softmax từ vector/head;",
              f"  sai lệch probability lớn nhất {audit['max_probability_difference']:.3g}.",
              '- Giữ nguyên raw ranking qua tham chiếu; không refit. Chỉ vector hóa hai',
              '  đoạn mới tách bằng BGE-M3 cùng revision, không đưa câu test vào training.',
              '- Unit test kiểm ca âm, hai yêu cầu cùng NEWS, raw score bất biến và',
              '  confidence=null. Replay luật không thay thế review nhãn độc lập.', '',
              '## Chạy lại và review', '',
              'Từ thư mục gốc, dùng Python trong backend/.venv. Runner cố ý từ chối',
              'ghi đè run01; kiểm lại bản đã bàn giao bằng hai lệnh:', '',
              '```powershell', "$env:PYTHONUTF8='1'", "$env:OPENBLAS_NUM_THREADS='4'",
              r'.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_news.py',
              r'.\backend\.venv\Scripts\python.exe backend/scripts/report_s5_intent_news.py', '```', '',
              'Kết quả từng câu/vector/checksum: outputs/s5_intent_news_20261112/run01.',
              'Test: backend/tests/test_s5_intent_news_requests.py và các test_s5_intent_*.py.',
              'Runner: backend/scripts/run_s5_intent_news.py (thư mục đầu ra mới trong checkout',
              'tái tạo riêng, model BGE-M3 cùng revision đã có trong cache).', '',
              'Hưng review ranh giới tìm bài/lấy số từ bài, tách câu và bảo toàn kết quả cũ.',
              'Huyền review hợp đồng đầu ra trước khi tích hợp. resolution là evidence,',
              'confidence=null; điểm classifier vẫn chưa hiệu chỉnh. Không đưa qua ngưỡng',
              'cosine và không gắn điểm nhãn cũ cho nhãn mới. MIXED không mặc định BOTH.',
              'Chưa calibration, chưa nối consumer/router/Web Chat; ranh giới kế hoạch',
              'lợi nhuận vẫn cần nhóm xác nhận. S5-WBS01.2 vẫn tạm dừng theo yêu cầu Nhân.', '']
    (ROOT / 'docs/sprint5/S5-WBS04.1-news-mixed-results.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    write(OUT / 'payload-targets.json', [row for row in results['additional_checks'] if row['id'] in {'NV-13', 'NV-19', 'NV-20'}])
    print('Report generated from audited results and 162 passing tests.')


if __name__ == '__main__':
    main()
