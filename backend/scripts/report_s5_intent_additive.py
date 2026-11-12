"""Create the final additive experiment report from saved measurements."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def table_line(name,m):
    values=[f"{m['hits'][str(k)]}/{m['labeled']} ({m['hits'][str(k)]/m['labeled']:.2%})" for k in [1,3,5]]
    return '| '+name+' | '+' | '.join(values)+f" | {m['fallback']} | {m['accepted_correct_route']} | {m['accepted_wrong_route']} |"


def main():
    run=ROOT/'outputs/s5_intent_additive_20261112'
    results,selection=read(run/'results.json'),read(run/'selection.json')
    later=read(run/'later-check/results.json')
    later_summary=read(run/'later-check/summary.json')
    selected=selection['selected']['name']
    lines=['# S5-WBS04.1 — Giữ mẫu gốc và bổ sung: kết quả 12/11/2026','',
           '**Chưa đề nghị thay baseline chính thức.** Không ứng viên nào đạt đủ điều kiện '
           'đã đặt trước. Không sửa taxonomy, artifact gốc, ngưỡng 0,65/0,08, router hoặc payload top-3.', '',
           '## Điều đã làm','',
           '- Phân tích 9 ca hồi quy ở bản thay thế; mất mẫu tin, sự kiện, xu hướng và câu kết hợp. '
           'Chi tiết trong `S5-WBS04.1-additive-plan.md`.',
           '- add_all: 90 mẫu gốc + 112 mẫu mới = 202 hàng; add_focused: 90 gốc + 48 mẫu '
           'PERSON_ROLE/ENTITY_RELATION/MIXED = 138 hàng. Giữ nguyên từng hàng và byte vector cũ.',
           '- Không che ticker. Dùng lại embedding BGE-M3 thật đã lưu cho mẫu/query cũ, '
           'cùng revision và cosine-max-per-label-v1. Không thêm câu test vào thư viện.',
           '- Hai ứng viên được định trước. Đóng băng selection.json trước khi đọc/chấm 28 '
           'câu để dành. Chỉ ứng viên đã chọn và baseline được chạy trên bộ 28; không chọn lại theo điểm bộ này.', '']
    for subset,title in [('development','84 câu phát triển đã xem'),('regression','47 câu cũ có nhãn'),('known_diagnostic','8 câu chẩn đoán đã biết')]:
        lines += ['## '+title,'','| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for name,result in results.items(): lines.append(table_line(name,result[subset]['metrics']))
        lines += ['']
    lines += ['## Hồi quy trên bộ cũ','', '| Ứng viên | Sai → đúng | Đúng → sai | ID đúng → sai |','|---|---:|---:|---|']
    for name in ['add_all','add_focused']:
        changes=results[name]['regression_transitions']
        lines.append(f"| {name} | {len(changes['fixed'])} | {len(changes['regressed'])} | {', '.join(changes['regressed']) or '—'} |")
    lines += ['', 'add_all còn hỏng T034/T036: hai câu xu hướng bị cạnh tranh bởi mẫu đọc số mới. '
              'Giữ mẫu cũ ngăn mất độ phủ nhưng không bảo đảm nhãn cũ giữ hạng đầu khi thêm đối thủ.', '',
              '## Chọn ứng viên trước khi đo 28 câu','',
              f"Đã chọn **{selected}** theo thứ tự ưu tiên đã ghi trước: điều kiện đạt, sai tuyến "
              'vượt ngưỡng, hồi quy, điểm dev/regression, kích thước thư viện. '
              f"Cờ đủ điều kiện trước later-check: **{selection['selected']['eligible']}**. "
              'Đây là chọn để đo chẩn đoán, không phải chấp nhận thay runtime.', '',
              'add_focused có 0 hồi quy trên bộ cũ và sửa thêm 5 câu, nhưng dev top-1 giảm '
              '34→30/84; top-3 cũng giảm 67→49/84. Vì vậy chưa phải cải thiện tổng quát.', '',
              '## Một lượt kiểm tra sau — 28 câu','',
              '| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for name,result in later.items(): lines.append(table_line(name if name=='original' else selected,result['metrics']))
    lines += ['', '### Theo nhãn: baseline so với ứng viên được chọn', '',
              '| Tập / nhãn | Baseline top-1 | add_focused top-1 |', '|---|---:|---:|']
    for title,a,b in [('Dev',results['original']['development'],results[selected]['development']),
                      ('Later',later['original'],later['selected'])]:
        for label,m in a['metrics']['per_label'].items():
            other=b['metrics']['per_label'][label]
            lines.append(f"| {title} / {label} | {m['hits']['1']}/{m['total']} | {other['hits']['1']}/{other['total']} |")
    changes=later_summary['transitions']
    lines += ['',f"Trên 28 câu: sửa đúng **{len(changes['fixed'])}**, đúng→sai **{len(changes['regressed'])}**. "
              f"ID đúng→sai: {', '.join(changes['regressed']) or 'không có'}.", '',
              'Bộ này do cùng tác giả chuẩn bị từ vòng trước, không phải kiểm thử mù độc lập. '
              'Đã được dùng đúng một lượt sau khi đóng băng ứng viên; từ giờ không còn là bộ chưa xem.', '',
              '## Kết luận và giới hạn','',
              '- Hướng bổ sung giảm hồi quy rõ so với thay toàn bộ (9→0 hoặc 2 câu hỏng trên bộ cũ), '
              'nhưng chưa đồng thời đạt mục tiêu tăng chất lượng trên các tập phát triển/kiểm tra sau.',
              '- Điểm tổng tăng trên 47 câu cũ không đủ để thay baseline: phải đọc cùng dev, '
              'top-3, từng nhãn, tỷ lệ nhận và các ca sai tuyến vượt ngưỡng.',
              '- Các cột tuyến là mô phỏng theo ánh xạ đã trao đổi, chưa gọi code 04.2/WebChat. '
              'Fallback không tính là chuyển sai tuyến. Số ca sai bằng 0 khi nhận rất ít câu '
              'không đồng nghĩa chất lượng vận hành tốt.',
              '- Chưa có bằng chứng để sửa ngưỡng hoặc tự bật một thư viện mới. '
              'Lượt này kiểm chứng hướng bổ sung và chỉ ra giới hạn; không tuyên bố đã sửa xong bài toán.',
              '- Không tiếp tục chỉnh mẫu theo 28 câu rồi gọi điểm đo lại là holdout. '
              'Nếu đổi phương pháp đối chiếu tiếp, dùng tập phát triển hiện có và chuẩn bị một phép '
              'đánh giá mới; không phải chờ nhóm mới phân tích hoặc thử nghiệm được.', '',
              '## Chạy lại bằng chứng','',
              '- Không cần model: `python backend/scripts/audit_s5_intent_additive.py` (cần NumPy).',
              '- Tạo lại báo cáo: `python backend/scripts/report_s5_intent_additive.py`.',
              '- Chuẩn bị/chốt ứng viên: `python backend/scripts/run_s5_intent_additive.py --output <thư_mục_mới>` '
              '(dùng cache vector thật của vòng trước, không đọc later-check).',
              '- Script `check_s5_intent_additive_later.py` từ chối khi lượt later-check đã tồn tại. '
              'Không chạy inference lần hai để lựa chọn lại kết quả.',
              '- Nguồn: `outputs/s5_intent_additive_20261112/` gồm method, selection, '
              'thư viện DRAFT và vector, kết quả từng câu, summary later-check và audit.', '']
    (ROOT/'docs/sprint5/archive/S5-WBS04.1-additive-results.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__':
    main()
