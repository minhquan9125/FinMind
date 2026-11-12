"""Consolidated report: first support experiment, decision v2 and new check."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'outputs/s5_intent_composition_20261112'


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def main():
    parent=read(PARENT/'summary.json')
    summary=read(PARENT/'consensus-v2/summary.json')
    results=read(PARENT/'consensus-v2/results.json')
    new=read(PARENT/'new-check/summary.json')
    lines=['# Đồng thuận yêu cầu độc lập — kết quả 12/11/2026','',
           '**T038 đã được đề xuất MIXED, không tạo hồi quy trên các tập phát triển đã xem.** '
           'Đây là nhãn quyết định có bằng chứng, confidence=null; chưa nối router hoặc hiệu chỉnh ngưỡng.', '',
           '## Giữ rõ hai vòng phát triển','',
           '- Vòng support đầu: classifier từng vế nhận đúng hai ý của T038 nhưng support '
           '0,2513 không vượt raw PERSON_ROLE 0,2584; còn làm sai T003 do vế thiếu ngữ cảnh '
           'bị nhận NEWS. Vòng này không qua điều kiện, giữ nguyên toàn bộ bằng chứng.',
           '- Vòng 2: chỉ đề xuất MIXED nếu hai nhãn từ hai vế khác nhau và đúng bằng '
           'hai nhãn đầu toàn câu. Câu đơn sau bỏ hỗ trợ dùng nhãn yêu cầu chính. '
           'Không chỉnh hệ số classifier hoặc tăng score để ép MIXED lên đầu.',
           '- Output resolution.intent_label/confidence=null/reason tách khỏi base_ranking. '
           'Base scores và top-3/5 được giữ nguyên. Vì thế bảng dưới đo **accuracy nhãn cuối**, '
           'không gọi đây là top-1 của một dãy score mới hoặc độ chính xác chọn tuyến đã chạy.', '',
           '## Trên các tập đã xem','',
           '| Tập | Baseline cosine đúng nhãn đầu | Classifier đúng nhãn đầu | V2 đúng nhãn cuối | Macro-F1 V2 |',
           '|---|---:|---:|---:|---:|']
    for dataset in ['development','regression','known_diagnostic','previous_check','controls']:
        old=parent['metrics']['original'][dataset]; linear=parent['metrics']['linear'][dataset]
        m=summary['metrics'][dataset]
        lines.append(f"| {dataset} | {old['hits']['1']}/{m['labeled']} | {linear['hits']['1']}/{m['labeled']} | {m['correct']}/{m['labeled']} ({m['accuracy']:.2%}) | {m['macro_f1']:.4f} |")
    lines += ['',f"Điều kiện development đã ghi trước: **{summary['passes_gate']}**. "
              'Controls 32 câu đã được dùng ở vòng 1 nên không gọi là test mù của vòng 2.', '',
              '## Câu thay đổi so classifier','', '| Tập | Sai → đúng | Đúng → sai |', '|---|---:|---:|']
    for dataset,c in summary['changes_against_linear'].items():
        lines.append(f"| {dataset} | {len(c['fixed'])} | {len(c['regressed'])} |")
    lines += ['', 'Trên 47 câu cũ, so với baseline cosine: sửa thêm '
              f"{len(summary['changes_against_original_regression']['fixed'])} câu, "
              f"đúng→sai {len(summary['changes_against_original_regression']['regressed'])} câu.", '',
              '## T038 và câu chỉ xin dẫn chứng','']
    target=next(r for r in results['regression'] if r['id']=='S5-T-038')
    lines += ['- T038: '+target['question'],
              '- Raw classifier giữ PERSON_ROLE đầu; resolution đề xuất '+target['final_label']+
              ', reason='+target['resolution']['reason']+', confidence=null.',
              '- Các phần yêu cầu: '+' / '.join(target['parts'])+'.',
              '- Sáu CONTROL-EVIDENCE-* đều giữ PERSON_ROLE; T024/T054 được sửa về PERSON_ROLE '
              'sau khi bỏ hỗ trợ dẫn chứng/giải nghĩa khỏi việc đếm mục tiêu.', '',
              '## Một lượt kiểm tra mới sau khi đóng băng V2','',
              '42 câu mới, 21 khung × 2 công ty VHC/DBC chưa có trong training; cả bảy nhãn. '
              'Cùng tác giả soạn nên không gọi là đánh giá mù bên thứ ba. Không fit hoặc đổi quy tắc '
              'sau khi xem kết quả. Bộ này từ giờ đã được sử dụng.', '',
              '| Phương pháp | Đúng / 42 | Accuracy | Macro-F1 |','|---|---:|---:|---:|']
    for name,m in new['metrics'].items(): lines.append(f"| {name} | {m['correct']}/42 | {m['accuracy']:.2%} | {m['macro_f1']:.4f} |")
    lines += ['', 'Các câu classifier đang đúng nhưng V2 làm sai trong bộ mới: '
              +(', '.join(new['linear_correct_to_wrong']) or 'không có')+'.', '',
              '## Hợp đồng bàn giao và phần chưa hoàn tất','',
              '- Đây là giải pháp ra nhãn đề xuất, không có scalar confidence đã được kiểm chứng. '
              'Không gắn raw probability của PERSON_ROLE vào nhãn MIXED; raw_ranking giữ nguyên '
              'và có thể không chứa nhãn resolution trong top-3.',
              '- Consumer 04.2 cần biết loại quyết định này, giữ trace và dùng cơ chế xác minh '
              'hoặc fallback phù hợp khi confidence không có. Chưa có source consumer mới của Huyền '
              'tại local, nên chưa sửa hoặc khẳng định đã tích hợp consumer.',
              '- Chưa calibration: không tự biến reason hoặc nhãn đề xuất thành xác suất. '
              'Muốn có confidence cần thiết kế chỉ số/tập calibration riêng cho pipeline cuối, '
              'kiểm chứng trên tập khác rồi mới cân nhắc ngưỡng. 0,65/0,08 vẫn thuộc baseline cũ.',
              '- Taxonomy hiện có ghi MIXED không luôn đồng nghĩa BOTH. Thành phần ý định, '
              'scope công ty/kỳ và contract router phải được đối chiếu khi tích hợp; '
              'báo cáo này chỉ nghiệm tra nhãn, không mặc định quyết định tuyến.',
              '- Chưa kiểm chứng E2E hoặc đạt tiêu chí router 90%. Bộ controls còn các lỗi '
              'nhãn nội dung báo cáo và một số câu mới có thể sai; đọc đầy đủ results thay vì '
              'chỉ dùng việc sửa T038 làm bằng chứng nghiệm thu toàn hệ thống.', '',
              '## Tái tạo','',
              '`python backend/scripts/audit_s5_intent_composition.py` kiểm vòng 1; '
              '`python backend/scripts/audit_s5_intent_consensus.py` kiểm V2 và bộ mới từ vector đã lưu. '
              '`python backend/scripts/report_s5_intent_consensus.py` tạo lại báo cáo này.', '']
    (ROOT/'docs/sprint5/S5-WBS04.1-consensus-results.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__': main()
