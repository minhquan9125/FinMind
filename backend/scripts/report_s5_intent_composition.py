"""Report all composition outcomes, including failures and score semantics."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/s5_intent_composition_20261112'


def main():
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    results=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    traces=json.loads((OUT/'traces.json').read_text(encoding='utf-8'))
    cases=json.loads((OUT/'cases.json').read_text(encoding='utf-8'))
    target=next(i for i,r in enumerate(cases) if r['id']=='S5-T-038')
    lines=['# Nhận diện yêu cầu kết hợp — kết quả 12/11/2026','',
           f"**Qua điều kiện đã đặt trước: {summary['passes_preregistered_gate']}.** "
           'Đây là thử nghiệm ngoài runtime, không phải kết quả E2E hoặc quyết định đã hiệu chỉnh ngưỡng.', '',
           '## Thiết kế','',
           '- Giữ nguyên hệ số/intercept classifier C=1. Không fit lại hoặc sửa gold label.',
           '- Tách yêu cầu có dấu hỏi/dấu nối, bỏ phần chỉ xin dẫn chứng hoặc giải nghĩa viết tắt '
           'khỏi việc đếm mục tiêu. Câu trích nội dung báo cáo độc lập vẫn là yêu cầu.',
           '- Một yêu cầu còn lại sau bỏ hỗ trợ: dùng classifier cho phần đó. Hai yêu cầu có nhãn '
           'đầu khác nhau: hỗ trợ MIXED = max(min(p_top_a,p_top_b)) trên cặp khác nhãn, không gồm MIXED. '
           'Chỉ tăng score MIXED nếu hỗ trợ lớn hơn score MIXED toàn câu.',
           '- Score COMPOSITION_SUPPORT_UNCALIBRATED không phải cosine hoặc probability đã '
           'hiệu chỉnh. Giữ raw score và mọi phần yêu cầu trong trace. Không áp 0,65/0,08.',
           '- 32 controls mới đóng băng trước inference; cùng tác giả, không phải test mù. '
           'Các tập 84/47/8/28 đều đã xem. Không đưa controls hoặc test vào training.', '',
           '## Kết quả','', '| Tập | Phương pháp | Top-1 | Top-3 | Top-5 | Macro-F1 |',
           '|---|---|---:|---:|---:|---:|']
    for dataset in ['development','regression','known_diagnostic','previous_check','controls']:
        for name in ['original','linear','composition']:
            m=summary['metrics'][name][dataset]
            values=[f"{m['hits'][str(k)]}/{m['labeled_cases']} ({m['hits'][str(k)]/m['labeled_cases']:.2%})" for k in [1,3,5]]
            lines.append('| '+dataset+' | '+name+' | '+' | '.join(values)+f" | {m['macro_f1']:.4f} |")
    lines += ['', '## T038 và bằng chứng thành phần','']
    for name in ['original','linear','composition']:
        row=next(r for r in results[name]['regression']['cases'] if r['id']=='S5-T-038')
        lines.append('- '+name+': '+' → '.join(f"{g['intent_label']} ({g['score']:.4f})" for g in row['ranking']['groups'][:3])+'.')
    lines.append('')
    for span,p in zip(traces[target]['parts'],traces[target]['component_probabilities']):
        labels=sorted(summary['metrics']['linear']['development']['per_label'])
        best=sorted(range(len(labels)),key=lambda j:(-p[j],labels[j]))[0]
        lines.append(f"- Vế: {span} → {labels[best]} ({p[best]:.4f}).")
    lines += ['', 'Các số ở ba phương pháp có nghĩa khác nhau; không so độ tin cậy trực tiếp giữa cosine, '
              'classifier probability và composition support.', '',
              '## Câu thay đổi so với classifier','', '| Tập | Sai → đúng | Đúng → sai | ID đúng → sai |','|---|---:|---:|---|']
    for dataset,change in summary['changes_against_linear'].items():
        lines.append(f"| {dataset} | {len(change['fixed'])} | {len(change['regressed'])} | {', '.join(change['regressed']) or '—'} |")
    lines += ['', 'So baseline cũ trên 47 câu: các ca đúng→sai còn lại: '
              +(', '.join(summary['original_regressions']['regressed']) or 'không có')+'.', '',
              '## Bộ đối chứng: kiểm tra cả câu đơn và dẫn chứng','',
              '| ID | Gold | Linear | Composition |','|---|---|---|---|']
    original={r['id']:r for r in results['linear']['controls']['cases']}
    for row in results['composition']['controls']['cases']:
        lines.append(f"| {row['id']} | {row['gold']} | {original[row['id']]['top1']} | {row['top1']} |")
    lines += ['', '## Giới hạn và bước tiếp','',
              '- Không dùng từ “và” hoặc hai công ty làm điều kiện đủ để gán MIXED. '
              'Tuy vậy heuristic tách câu và classifier từng vế vẫn có thể sai; '
              'không khẳng định đã hiểu mọi câu nhiều ý.',
              '- Việc bỏ giải nghĩa viết tắt khỏi đoạn được chấm có thể mất ngữ cảnh hữu ích; '
              'query gốc vẫn lưu, cần đọc các ca này trong controls và regression.',
              '- Giữ matcher/vector/taxonomy, ngưỡng và consumer Huyền không đổi. Chưa có '
              'source consumer 04.2 mới tại local, chưa kiểm chứng chạy WebChat.',
              '- Nếu điều kiện thất bại, không áp bản này hoặc đổi đáp án/điểm để xóa lỗi; '
              'nếu điều kiện đạt, vẫn cần kiểm tra mới, calibration riêng và hợp đồng loại điểm '
              'trước khi đề nghị tích hợp. Không tuyên bố router đạt 90% từ unit test.', '',
              '## Chạy lại bằng chứng','',
              '`python backend/scripts/audit_s5_intent_composition.py` tính lại từ vector đã lưu, '
              'không cần nạp BGE-M3. `python backend/scripts/report_s5_intent_composition.py` '
              'tạo lại báo cáo. Source: outputs/s5_intent_composition_20261112.', '']
    (ROOT/'docs/sprint5/archive/S5-WBS04.1-composition-results.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__': main()
