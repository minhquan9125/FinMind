"""Generate the single current review report from verified artifacts."""
import xml.etree.ElementTree as ET

from run_s5_intent_review2 import ROOT, BASE, OUT
from run_s5_intent_reviewfix import read


def main():
    results, summary = read(OUT / 'results.json'), read(OUT / 'summary.json')
    audit, integration = read(OUT / 'audit.json'), read(BASE / 'integration-final-checks.json')
    cases = ET.parse(BASE / 'unit-complete.xml').getroot().findall('testsuite')
    assert sum(int(s.attrib['tests']) for s in cases) == 276
    assert all(int(s.attrib[k]) == 0 for s in cases for k in ['failures', 'errors', 'skipped'])
    assert audit['status'] == integration['status'] == 'PASS' and summary['passes_gate']
    prior = read(ROOT / 'outputs/s5_intent_news_20261112/run01/summary.json')['metrics']
    probe = summary['metrics']['review2_probes']
    lines = [
        '# S5-WBS04.1 — Review vòng 2: chính tả và hợp đồng bàn giao', '',
        'Cập nhật 12/11/2026. Phụ trách Hồ Phạm Đăng Nhân; nhánh nhan-sprint-501.',
        'Đã sửa và kiểm chứng phần kỹ thuật dưới đây, đang chờ review. Chưa nối',
        'consumer vào router/Web Chat, chưa calibration hoặc hoàn thành toàn luồng.', '',
        '## Đã sửa', '',
        '1. Đọc/độc và lương/lượng: kiểm chính tả Unicode NFC và ngữ cảnh trước',
        '   khi dùng bản bỏ dấu. Hỗ trợ câu không dấu khi có ngữ cảnh phù hợp.',
        '   Dùng chung kiểm chỉ tiêu cho NUMERIC và giải thích diễn biến TREND.',
        '2. Bổ sung “Ai đang làm CEO/CFO”, “người đứng đầu”, “có tin gì mới”.',
        '   Vế giải thích thay đổi tài chính có thể tạo TREND và ghép với NUMERIC.',
        '   Không tự gán mọi câu “vì sao” hoặc câu thuật lại nguồn thành TREND.',
        '3. Đọc consumer thật của Huyền tại 8e854d47748189ad0fbf617d949657bf3c79ac40.',
        '   Chuẩn bị bản sửa local: metadata thiếu/sai trả REJECT_CLASSIFICATION,',
        '   reason INVALID_SCORE_CONTRACT, không SEARCH và không yêu cầu AI fallback.',
        '4. MIXED chưa có thành phần query được xác minh không tự BOTH: consumer',
        '   trả NEED_FALLBACK / MIXED_COMPONENTS_UNVERIFIED với top-3 cosine hợp lệ.',
        '   Đây là thay đổi có chủ đích so với mapping cũ, cần Huyền review trước áp dụng.',
        '5. Thêm prepare_intent_review: phân biệt nhãn đề xuất với nhãn được chấp nhận.',
        '   Thiếu mục tiêu rõ, lệch nhãn hoặc xác suất chưa hiệu chỉnh đều dừng ở',
        '   NEED_VALIDATION, accepted_intent=null, route=null; không mượn điểm nhãn khác.', '',
        '## Điểm phải đọc kỹ: câu “độc lập”', '',
        'Với “Lợi nhuận FPT có độc lập với mảng viễn thông không?”, quy tắc đã ngừng',
        'ép NUMERIC và không còn ghi đè classifier bằng bằng chứng đọc sai.',
        '**Classifier gốc vẫn đề xuất NUMERIC cho bản có dấu**; bản không dấu đề',
        'xuất PERSON_ROLE. Không báo đã phân loại đúng hoặc đã sửa tính bất biến',
        'của model. Câu được ghi unresolved_requests và handoff trả NEED_VALIDATION,',
        'accepted_intent=null. Cần xác minh mục tiêu/phạm vi hoặc xử lý 07.2 sau tích hợp.', '',
        '## Kết quả đã đo', '',
        '| Bộ đã xem | Có nhãn | V6 đúng | Bản mới đúng |', '|---|---:|---:|---:|',
    ]
    for group, metric in summary['metrics'].items():
        if group != 'review2_probes':
            lines.append(f"| {group} | {metric['labeled']} | {prior[group]['correct']} | {metric['correct']} |")
    lines += ['', '313 hàng cũ giữ nguyên nhãn; không phát sinh đúng→sai. Chín hàng cũ',
              'không có gold không được tính accuracy. Các lỗi cũ vẫn còn, không tự sửa gold.',
              f"32 probe bổ sung: **{probe['correct']}/{probe['labeled']} câu có gold đúng** và",
              '**5/5 kiểm tra không ép nhãn đạt**. Năm câu này chưa có gold, không tính',
              'là phân loại đúng. Các probe cùng tác giả và dựa trên review, không phải test mù.',
              'Giữ training/model/head/điểm gốc. Vector hóa 50 văn bản bằng BGE-M3 cùng',
              'revision ở run01; run02 dùng lại đúng cache sau sửa chung guard TREND.', '',
              '| Probe chưa chốt gold | Nhãn đề xuất của classifier/quyết định | Handoff |',
              '|---|---|---|']
    for row in results['review2_probes']:
        if row['gold'] is None:
            lines.append(f"| {row['id']}: {row['question']} | {row['final_label']} | NEED_VALIDATION; không chấp nhận nhãn |")
    lines += ['', 'Các tập cũ còn sai:', '', '| Bộ | Mã |', '|---|---|']
    for group, metric in summary['metrics'].items():
        if metric['wrong_ids']:
            lines.append(f"| {group} | {', '.join(metric['wrong_ids'])} |")
    lines += ['', '## Consumer và luồng giá', '',
              '- Tái hiện ba trường hợp thiếu khóa với score=0,71: bản Huyền SEARCH,',
              '  bản local REJECT_CLASSIFICATION. Không suy loại điểm từ số 0–1.',
              f"- {integration['unchanged_valid_cosine']}/35 ca cosine hợp lệ giống hệt bản gốc;",
              f"  {integration['intentional_mixed_deferrals']} ca MIXED đổi từ SEARCH/BOTH sang chờ xác minh thành phần.",
              '  Ngưỡng 0,65/0,08 và top-3 giữ nguyên. Đây không phải accuracy router.',
              '- Cả 32 payload classifier/advisory đều NEED_VALIDATION ở chốt bàn giao.',
              '  Không tính việc chặn chúng là đã chọn tuyến đúng; chưa có coverage nhận tự động.',
              '- Schema đã duyệt bao gồm giá trong NUMERIC. Kiểm analyze_live thực tế',
              '  trả MARKET_LOOKUP, source_type=PRICE, LAST_PRICE, QUOTE cho giá FPT hôm nay.',
              '  Đây là kiểm phân giải nguồn offline, chưa lấy giá thật hoặc chạy UI.',
              '  Khi tích hợp phải giữ luồng giá hiện có trước consumer ý định tổng quát.',
              '- Nhánh Huyền chưa bị thay đổi. Bản sửa và patch nằm ở nhánh Nhân để review.',
              '  Caller cần xử lý kết quả mới REJECT_CLASSIFICATION; không đưa vào AI fallback.', '',
              '## Bằng chứng và chạy lại', '',
              '- **276/276 test qua**: 255 test Sprint 5 và 21 test giá/hội thoại có sẵn.',
              '  Không phải bộ test toàn ứng dụng hoặc E2E Web Chat. Có một cảnh báo',
              '  deprecation sẵn có từ Starlette/AnyIO; không skip hoặc tắt test.',
              f"- Audit tái tạo {audit['decisions_replayed']} quyết định; sai lệch probability lớn nhất",
              f"  {audit['max_probability_difference']:.3g}; nguồn, raw ranking và head không đổi.",
              '- Audit V6 vẫn qua. run01 là ứng viên trước hai test âm bổ sung về chất lượng;',
              '  run02 giữ logic cuối nhưng manifest còn xuống dòng Windows. Bản bàn giao',
              '  run03 chuẩn hóa manifest LF, giữ dữ liệu/logic/điểm, có snapshot metadata cũ.',
              '- Artifact: outputs/s5_intent_review2_20261112/run03/results.json và audit.json.',
              '- Handoff/consumer/price: outputs/s5_intent_review2_20261112/integration-final-checks.json.',
              '  Checksum mã nguồn Python ở manifest này chuẩn hóa LF để clone Windows/Linux nhất quán.',
              '- Patch cho Huyền: outputs/s5_intent_review2_20261112/consumer-fix.patch;',
              '  provenance gốc ở consumer-source.json và consumer-original.py.', '',
              'Patch không có dòng context; chỉ áp lên đúng bản gốc đã đối chiếu. Huyền',
              'chạy git apply --unidiff-zero --check trước khi áp bằng --unidiff-zero.', '',
              'Tại thư mục gốc (không cần DB, provider hay model weights cho audit):', '',
              '```powershell', "$env:PYTHONUTF8='1'", "$env:OPENBLAS_NUM_THREADS='4'",
              r'.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_review2.py',
              r'.\backend\.venv\Scripts\python.exe backend/scripts/check_s5_intent_handoff.py --verify',
              r'.\backend\.venv\Scripts\python.exe backend/scripts/report_s5_intent_review2.py', '```', '',
              '## Cần review/chốt', '',
              '- Hưng: ngữ cảnh chính tả, role/news/giải thích, bảo toàn ca cũ và giới hạn',
              '  của câu chưa có gold. Không xem các câu dừng xác minh là phân loại thành công.',
              '- Huyền: nhận patch, kiểm kết quả REJECT_CLASSIFICATION và MIXED_COMPONENTS_UNVERIFIED;',
              '  kiểm chốt bàn giao khi nhãn lệch/thiếu mục tiêu/probability chưa hiệu chỉnh.',
              '- Nhóm: chốt ranh giới kế hoạch lợi nhuận và cách tiêu thụ evidence, giữ phân',
              '  giải PRICE. Sau đó mới tích hợp 07.2/router, đo coverage/sai tuyến và E2E.',
              'Task 01.2 tiếp tục tạm dừng theo yêu cầu Nhân.', '']
    (ROOT / 'docs/sprint5/S5-WBS04.1-news-mixed-results.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print('Current review report generated from final audited artifacts and 276 passing tests.')


if __name__ == '__main__':
    main()
