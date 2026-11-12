"""Generate experiment review tables from actual saved results."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'outputs/s5_intent_experiment_20261111/run01'
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    results=json.loads((out/'results.json').read_text(encoding='utf-8'))
    lines=['# S5-WBS04.1 — Thử nghiệm cải thiện mẫu và ảnh hưởng ticker', '',
           'Ngày: 11/11/2026. Trạng thái: **DRAFT, chưa thay bản đã review hoặc đưa vào runtime.**', '',
           '## Thiết kế trước lượt đo', '',
           'Theo `S5-WBS04.1-improvement-plan.md`: bốn cấu hình, cùng BGE-M3/revision và '
           'cosine-max-per-label-v1; không thay ngưỡng 0,65/0,08 hoặc payload top-3. '
           'Chấm top-1/3/5 bằng đủ bảy nhóm được lưu, không tăng payload production.', '',
           '- original: thư viện 90 dòng đã duyệt, văn bản nguyên gốc.',
           '- original_masked: thư viện gốc nhưng che ticker trong cả mẫu và query.',
           '- balanced: thư viện mới 112 dòng (7 nhãn × 4 khung × 4 công ty), không che ticker.',
           '- balanced_masked: thư viện mới và che ticker cả hai phía.', '',
           'Thư viện mới là ứng viên DRAFT. 84 câu development thuộc các khung riêng; '
           '56 câu regression cũ đã xem, trong đó 47 có nhãn; 8 known probes được tính riêng. '
           '28 câu later-check chưa được runner đọc/chấm và cần nhóm review. '
           'Cùng tác giả soạn các phần nên không coi test là mù/độc lập.', '']
    for dataset,title in [('development','Development — 84 câu'),('regression','Regression cũ — 47 câu có nhãn'),('known_diagnostic','Known probes — 8 câu đã biết lỗi')]:
        lines += ['## '+title,'', '| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name,sets in summary['metrics'].items():
            m=sets[dataset]
            vals=[f"{m['hits'][str(k)]}/{m['labeled']} ({m['hits'][str(k)]/m['labeled']:.2%})" for k in [1,3,5]]
            lines.append('| '+name+' | '+' | '.join(vals)+f" | {m['fallback']} | {m['accepted_correct_route']} | {m['accepted_wrong_route']} |")
        lines += ['','Đúng/sai tuyến ở đây là **mô phỏng policy trên các câu có nhãn**, '
                  'không phải E2E WebChat hay xác nhận code 04.2 đã chạy. '
                  'Fallback không bị tính là đã chuyển sai tuyến. Cosine không phải xác suất.', '']
    lines += ['## Đổi công ty và ranh giới đơn/kết hợp trên development','',
              '| Cấu hình | Nhóm đổi nhãn đầu khi đổi công ty / 21 | Nhóm cả 4 công ty đúng / 21 | Câu đơn → MIXED | MIXED → câu đơn |',
              '|---|---:|---:|---:|---:|']
    for name,sets in summary['metrics'].items():
        m=sets['development']
        lines.append(f"| {name} | {len(m['company_changed_top1'])}/21 | {len(m['company_all_correct'])}/21 | {len(m['single_misread_as_mixed'])} | {len(m['mixed_misread_as_single'])} |")
    lines += ['', 'Che toàn bộ ticker tạo đầu vào giống nhau trong một khung nên giảm biến động '
              'nhãn theo công ty là hệ quả trực tiếp của phép biến đổi; cần đọc cùng tỷ lệ đúng, '
              'không dùng riêng chỉ số bất biến này để tuyên bố model tốt.', '',
              '## Hồi quy: sửa được gì, làm hỏng gì trên 47 câu cũ','',
              '| Cấu hình | Sai → đúng | Đúng → sai | ID đúng → sai |','|---|---:|---:|---|']
    for name,t in summary['regression_transitions'].items():
        lines.append(f"| {name} | {len(t['fixed'])} | {len(t['regressed'])} | {', '.join(t['regressed']) or '—'} |")
    lines += ['', 'ID tất cả ca sửa đúng và regression, thứ hạng/điểm từng câu: `run01/results.json` '
              'và `run01/summary.json`. Không đổi gold label hoặc âm thầm loại ca giảm chất lượng.', '',
              '## Theo nhãn — top-1','', '| Tập / nhãn | original | original_masked | balanced | balanced_masked |',
              '|---|---:|---:|---:|---:|']
    for dataset in ['development','regression']:
        for label in summary['metrics']['original'][dataset]['per_label']:
            vals=[sets[dataset]['per_label'][label] for sets in summary['metrics'].values()]
            lines.append('| '+dataset+' / '+label+' | '+' | '.join(f"{m['hits']['1']}/{m['total']}" for m in vals)+' |')
    lines += ['', '## Ứng viên theo điều kiện đã đặt trước', '',
              'Điều kiện: top-1 dev tăng, số sai tuyến vượt ngưỡng không tăng trên dev và regression. '
              'Các cấu hình qua bộ lọc này: **'+(', '.join(summary['candidates_for_review']) or 'không có')+'**. '
              'Đây chỉ là lọc ứng viên gửi review, không phải nghiệm thu hoặc tự triển khai.', '',
              '## Giới hạn và cách chạy lại', '',
              '- **Chưa có cấu hình nào được đề nghị thay baseline chính thức.** Balanced qua '
              'bộ lọc ứng viên nhưng làm hỏng 9 câu cũ và chỉ nhận 4/84 câu dev, còn 80/84 fallback. '
              'Không coi số sai tuyến bằng 0 là đã có hệ thống phân loại tốt.',
              '- Balanced sửa cả 8 known probes nhưng chỉ đúng 40/84 câu dev (47,62%). '
              'Đây là minh họa vì sao không nghiệm thu chỉ bằng các câu lỗi đã biết. '
              'Original_masked có dev top-1 cao nhất nhưng tăng sai tuyến vượt ngưỡng trên regression từ 0 lên 2; '
              'balanced_masked tăng lên 1. Chưa chọn các cấu hình này để tích hợp.',
              '- Bước tiếp theo cần Huyền/Hưng review bộ mẫu ứng viên và tiêu chí chấp nhận hồi quy; '
              'bổ sung bộ riêng rồi đánh giá lại. 28 câu later-check vẫn để nguyên chưa chấm. '
              'Không chỉnh tiếp dữ liệu sau lượt này rồi gọi cùng các tập vừa xem là kiểm thử độc lập.',
              '- Số ca sai tuyến phụ thuộc cả độ bao phủ: phải đọc accepted_coverage và '
              'wrong_route_rate_among_accepted trong summary, không chỉ đếm lỗi tuyệt đối.',
              '- Bản cân bằng thay nội dung/số lượng/cách phân bố ticker cùng lúc; '
              'chưa quy được cải thiện cho riêng một thay đổi trong đó.',
              '- Che ticker chỉ dùng registry hữu hạn, không giải quyết đầy đủ tên doanh nghiệp/alias. '
              'Chưa kiểm tra câu hỏi so sánh nhiều công ty mà masking có thể mất phân biệt.',
              '- File library-draft là định dạng tối thiểu của thí nghiệm, chưa là artifact 03.2 '
              'được duyệt. Runner gắn component_intents cho bốn family MIXED để mô tả mẫu; '
              'chưa trích thành phần query và chưa dùng loader artifact chính thức cho bản DRAFT.',
              '- Chưa hiệu chỉnh ngưỡng, chưa gọi LLM/fallback, chưa tích hợp WebChat.', '',
              'Kiểm chứng không cần model: `python backend/scripts/audit_s5_intent_experiment.py` '
              '(cần NumPy). Tạo lại báo cáo: `python backend/scripts/report_s5_intent_experiment.py`.', '',
              'Muốn chạy lại inference: `python backend/scripts/run_s5_intent_experiment.py '
              '--output outputs/s5_intent_experiment_20261111/run02` (từ chối ghi đè); '
              'cần cache BGE-M3 đúng revision và thiết lập offline/CPU như tài liệu 04.1. '
              'Bản gốc, run01 cũ và ngưỡng không thay đổi.', '']
    (ROOT/'docs/sprint5/archive/S5-WBS04.1-improvement-results.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__':
    main()
