"""Produce the offline scorer comparison, including its quality-gate failure."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/s5_intent_scorer_20261112'


def main():
    location=json.loads((OUT/'fit-location.json').read_text())
    fit=ROOT/location['output']
    summary=json.loads((fit/'summary.json').read_text(encoding='utf-8'))
    results=json.loads((fit/'results.json').read_text(encoding='utf-8'))
    lines=['# Tối ưu cách chấm ý định — 12/11/2026','',
           '**Có cải thiện rõ nhưng chưa thay baseline:** linear còn 1 ca cũ đúng→sai (T038), '
           'centroid còn 3 ca. Cả hai chưa đạt ràng buộc không hồi quy đã chốt.', '',
           '## Phương pháp và cách chọn','',
           '- Huấn luyện/thống kê chỉ trên 202 hàng LIBRARY (90 mẫu gốc + 112 mẫu DRAFT), '
           '58 family, cùng embedding BGE-M3 đã lưu. Không fit trên test/dev hoặc 28 câu đã xem.',
           '- Chia 4 fold theo family và nhãn; mọi biến thể cùng family ở cùng fold. '
           'Cân trọng số để các nhãn có tổng bằng nhau, các family trong một nhãn có tổng bằng nhau.',
           '- Linear: Logistic Regression L2, lbfgs; C trong {0,1; 1; 10}, chọn bằng '
           f"macro-F1 OOF rồi accuracy rồi C nhỏ hơn. C được chọn = **{summary['C_selection']['C']}**, "
           f"macro-F1 OOF = **{summary['C_selection']['macro_f1']:.4f}**. Chọn trước khi chấm các tập đánh giá.",
           '- Centroid: chuẩn hóa trung bình từng family, rồi trung bình các family của nhãn '
           'và chuẩn hóa lại; score là cosine query với đại diện nhãn.',
           '- So với baseline 90 mẫu đã duyệt. Hai phương pháp mới dùng cùng 202 hàng nên '
           'so sánh hai phương pháp mới có cùng dữ liệu; so với baseline đồng thời thay dữ liệu '
           'và cách chấm, không quy toàn bộ cải thiện cho thuật toán. Vòng additive trước đã đo '
           'max-cosine trên chính 202 hàng: dev 40/84, regression 27/47.', '',
           '## Kết quả','', '| Tập | Cấu hình | Top-1 | Top-3 | Top-5 | Macro-F1 |',
           '|---|---|---:|---:|---:|---:|']
    for dataset in ['development','regression','previous_check','known_diagnostic']:
        for name,sets in summary['metrics'].items():
            m=sets[dataset]
            vals=[f"{m['hits'][str(k)]}/{m['labeled_cases']} ({m['hits'][str(k)]/m['labeled_cases']:.2%})" for k in [1,3,5]]
            lines.append('| '+dataset+' | '+name+' | '+' | '.join(vals)+f" | {m['macro_f1']:.4f} |")
    lines += ['', 'Development = 84 câu; regression = 47 có nhãn trong 56 câu; '
              'previous_check = 28 câu đã chấm ở lượt trước; known = 8 probe đã biết. '
              'Cả bốn đều đã xem, chỉ dùng phát triển/hồi quy, không gọi là nghiệm thu độc lập.', '',
              '## Hồi quy so với baseline','', '| Cấu hình | Sai → đúng | Đúng → sai | ID đúng → sai |',
              '|---|---:|---:|---|']
    for name,changes in summary['regression_transitions'].items():
        lines.append(f"| {name} | {len(changes['fixed'])} | {len(changes['regressed'])} | {', '.join(changes['regressed']) or '—'} |")
    lines += ['', '### Ca T038','']
    for name in results:
        row=next(r for r in results[name]['regression']['cases'] if r['id']=='S5-T-038')
        groups=row['ranking']['groups'][:3]
        lines.append('- '+name+': '+' → '.join(f"{g['intent_label']} ({g['score']:.4f})" for g in groups)+'.')
    lines += ['', 'Gold MIXED: hỏi chức danh trong BCTN và hỏi chính sách kiểm soát nội bộ. '
              'Không sửa gold sang một nhãn đơn hoặc đưa nguyên câu này vào training để xóa hồi quy.', '',
              '## Hai nhóm lỗi cần xử lý trên development', '',
              '| Cấu hình | Nhóm đổi nhãn theo công ty / 21 | Nhóm cả 4 công ty đúng / 21 | Đơn → MIXED | MIXED → đơn | Sai tuyến argmax, chưa xét ngưỡng / 84 |',
              '|---|---:|---:|---:|---:|---:|']
    for name,sets in summary['metrics'].items():
        m=sets['development']
        lines.append(f"| {name} | {len(m['company_changed_top1'])}/21 | {len(m['company_all_correct'])}/21 | {len(m['single_to_mixed'])} | {len(m['mixed_to_single'])} | {len(m['argmax_route_wrong_without_threshold'])}/84 |")
    lines += ['', 'Cột cuối không phải số tuyến sai đã chạy trong hệ thống; chưa áp policy hoặc '
              'ngưỡng của Huyền lên score mới. Không dùng cột này thay cho phép đo accepted/fallback.', '',
              '## Theo nhãn — top-1','', '| Tập / nhãn | Baseline | Centroid | Linear |','|---|---:|---:|---:|']
    for dataset in ['development','regression']:
        for label in summary['labels']:
            vals=[]
            for name in ['original','centroid','linear']:
                m=summary['metrics'][name][dataset]
                correct=m['confusion_matrix'][label][label]
                vals.append(f"{correct}/{m['per_label'][label]['support']}")
            lines.append('| '+dataset+' / '+label+' | '+' | '.join(vals)+' |')
    lines += ['', '## Ảnh hưởng tới Huyền và điểm dừng','',
              '- Kết quả linear là CLASSIFIER_PROBABILITY_UNCALIBRATED, centroid là cosine '
              'đại diện nhãn, đều có policy/version riêng. Không dùng ngưỡng 0,65/0,08 của '
              'max-cosine cho hai loại điểm mới; không ghép nhãn mới với điểm cũ.',
              '- Baseline và payload top-3 không đổi. Guard thử nghiệm từ chối loại điểm '
              'không hỗ trợ trước khi áp ngưỡng; chưa xác nhận guard trong source 04.2 của Huyền.',
              '- Các sai tuyến không ngưỡng được lưu như phép đo argmax riêng. Không báo '
              'accepted/fallback cho ứng viên từ ngưỡng cũ, không tuyên bố đã chạy E2E hoặc đạt 90%.',
              '- **Không ứng viên nào qua điều kiện không hồi quy. Dừng ở checkpoint sau bước 3.** '
              'Chưa chấm bộ mới hoặc calibration; không hạ tiêu chí để chọn model. '
              'Đây là dừng đề nghị thay baseline, không phải lỗi kỹ thuật ngăn fit hay tính điểm.',
              '- Phân biệt rõ: số câu đầu bảng tăng là bằng chứng có hướng cải thiện; '
              'chưa chứng minh vận hành đủ tốt hoặc độ tin cậy của probability đã được hiệu chỉnh.', '',
              '## Tái tạo và giới hạn','',
              '- Kiểm chứng không fit lại: `python backend/scripts/audit_s5_intent_scorer.py` '
              '(cần NumPy). Tính lại grouped OOF selection, centroid, softmax và 528 thứ hạng.',
              '- Tạo lại báo cáo: `python backend/scripts/report_s5_intent_scorer.py`.',
              '- Lượt fit đầu lỗi ghi báo cáo do probe thiếu family_id; đã thêm test tái hiện và sửa. '
              'Lượt sau đã có đủ summary nhưng lỗi đường dẫn tương đối khi ghi pointer cuối. '
              'Đã sửa và khôi phục pointer sau kiểm tra; không fit lần ba. Tham số và CV của '
              'hai lượt giống nhau từng phần tử. Xem recovery-note.json, không ẩn các lượt lỗi.',
              '- Artifact giữ coefficients/intercepts/centroids dạng NPZ, không dùng pickle. '
              'Dữ liệu thư viện mới vẫn là DRAFT; dữ liệu ít, cùng tác giả và family_id '
              'không bảo đảm không có gần nghĩa giữa các family. OOF không thay cho test mới.',
              '- Phạm vi mã: module/runner thử nghiệm; không thay code matcher/router/WebChat chính thức.', '']
    (ROOT/'docs/sprint5/S5-WBS04.1-scorer-results.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__': main()
