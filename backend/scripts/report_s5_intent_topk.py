"""Compare top-1/3/5 intent groups from frozen run01, without model inference."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KS = (1, 3, 5)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows):
    return {str(k): dict(hits=sum(row['gold_rank'] <= k for row in rows),
                         total=len(rows),
                         hit_rate=sum(row['gold_rank'] <= k for row in rows) / len(rows)
                         if rows else None) for k in KS}


def cell(metric):
    return f"{metric['hits']}/{metric['total']} ({metric['hit_rate']:.2%})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT / 'outputs/s5_wbs041_20261110/run01')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/s5_wbs041_topk_20261111')
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/sprint5/archive/S5-WBS04.1-top1-top3-top5-report.md')
    args = parser.parse_args()
    files = ['method.json', 'test-input.jsonl', 'results.jsonl', 'summary.json']
    fingerprints = {name: digest(args.run / name) for name in files}
    method = json.loads((args.run / 'method.json').read_text(encoding='utf-8'))
    summary = json.loads((args.run / 'summary.json').read_text(encoding='utf-8'))
    cases = [json.loads(line) for line in (args.run / 'test-input.jsonl').read_text(encoding='utf-8').splitlines()]
    records = [json.loads(line) for line in (args.run / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
    labels = list(summary['per_label'])
    if fingerprints['test-input.jsonl'] != method['test_sha256'] or len(cases) != len(records):
        raise ValueError('FROZEN_INPUT_MISMATCH')
    rows, nulls = [], []
    for case, record in zip(cases, records):
        ranking = record['ranking']
        groups = ranking['groups']
        ordered = [group['intent_label'] for group in groups]
        if (record['id'] != case['id'] or ranking['question'] != case['text']
                or record['expected_label'] != case['intent_label']
                or len(ordered) != len(labels) or set(ordered) != set(labels)
                or [g['rank'] for g in groups] != list(range(1, len(labels) + 1))
                or groups != sorted(groups, key=lambda g: (-g['score'], g['intent_label']))
                or ranking['ranking_policy'] != method['ranking_policy']):
            raise ValueError('INVALID_OR_MISALIGNED_RANKING: ' + case['id'])
        row = dict(id=case['id'], question=case['text'], gold=case['intent_label'],
                   gold_rank=ordered.index(case['intent_label']) + 1 if case['intent_label'] else None,
                   ordered_labels=ordered, scope_status=case['scope_status'],
                   linguistic_form=case['linguistic_form'])
        (rows if row['gold'] else nulls).append(row)
    overall = metrics(rows)
    if (overall['1']['hit_rate'] != summary['top1_accuracy']
            or overall['3']['hit_rate'] != summary['top3_recall']
            or len(rows) != summary['labeled_cases'] or len(nulls) != summary['unlabeled_cases']):
        raise ValueError('BASELINE_METRIC_MISMATCH')
    per_label = {label: metrics([r for r in rows if r['gold'] == label]) for label in labels}
    slices = {field: {value: metrics([r for r in rows if r[field] == value])
                      for value in sorted({r[field] for r in rows})}
              for field in ['scope_status', 'linguistic_form']}
    recovered = {'rank_2_to_3': [r['id'] for r in rows if 1 < r['gold_rank'] <= 3],
                 'rank_4_to_5': [r['id'] for r in rows if 3 < r['gold_rank'] <= 5],
                 'missed_top5': [r['id'] for r in rows if r['gold_rank'] > 5]}
    report = dict(task_id='S5-WBS04.1', analysis_date='2026-11-11',
                  source='POST_HOC_ANALYSIS_OF_FROZEN_RUN01_NO_NEW_INFERENCE',
                  ranking_policy=method['ranking_policy'], model=method['model'],
                  source_hashes=fingerprints, total_cases=len(cases), excluded_null_cases=len(nulls),
                  overall=overall, per_label=per_label, slices=slices, buckets=recovered,
                  gold_rank_counts=dict(sorted(Counter(r['gold_rank'] for r in rows).items())),
                  cases=rows, null_cases=nulls)
    lines = ['# S5-WBS04.1 — So sánh top-1, top-3 và top-5', '',
             'Ngày phân tích: 11/11/2026. Người thực hiện: Hồ Phạm Đăng Nhân.', '',
             '## Kết quả chính', '',
             '| Chỉ số | Nhãn đúng nằm trong danh sách | Bỏ sót | Số nhãn trả mỗi câu |',
             '|---|---:|---:|---:|']
    for k in KS:
        m = overall[str(k)]
        lines.append(f"| Top-{k} | {cell(m)} | {m['total'] - m['hits']} | {k} |")
    lines += ['', f"Top-3 thêm **{len(recovered['rank_2_to_3'])} câu** so với top-1 "
              f"(**{(overall['3']['hit_rate'] - overall['1']['hit_rate']) * 100:.2f} điểm phần trăm**). "
              f"Top-5 thêm **{len(recovered['rank_4_to_5'])} câu** so với top-3 "
              f"(**{(overall['5']['hit_rate'] - overall['3']['hit_rate']) * 100:.2f} điểm phần trăm**).", '',
              '## Cách đo và phạm vi', '',
              '- Dùng cùng đầu ra model thật của run01 ngày 10/11, đã lưu đủ thứ hạng của **7 nhãn khác nhau**; '
              'cắt danh sách tại 1, 3 và 5. Đây là phân tích bổ sung, không phải ba lần chạy model mới.',
              '- BGE-M3 cùng full revision và artifact 03.3. Policy cosine-max-per-label-v1: '
              'điểm một nhãn là cosine cao nhất trong các câu mẫu mang nhãn đó. Không đổi mẫu, model hoặc điểm.',
              '- Top-k ở đây là **nhóm ý định**, không phải k câu mẫu trong trường examples. '
              'Mỗi câu có đúng một gold label; MIXED được tính là một nhãn. Không đánh giá component_intents.',
              '- Công thức: số câu có gold label trong k nhóm đầu / 47. '
              'Top-1 trùng accuracy; top-3/top-5 là Hit@k (cũng là Recall@k khi mỗi câu có một gold label), '
              'không phải accuracy của một quyết định cuối cùng.',
              '- Tổng 56 câu: 47 có nhãn (44 RESOLVED, 3 PARTIAL) dùng tính điểm; '
              '9 câu null bị loại khỏi mẫu số và vẫn được lưu trong JSON. '
              'PARTIAL có thể rõ ý định nhưng thiếu doanh nghiệp/ngữ cảnh để trả lời.',
              '- Top-1/top-3 đối chiếu khớp summary cũ. Run01 giữ nguyên checksum. '
              'Top-5 là chỉ số phân tích sau lượt đo, chưa phải tiêu chí nghiệm thu định trước.', '',
              '## Theo nhãn', '', '| Nhãn | Top-1 | Top-3 | Top-5 |', '|---|---:|---:|---:|']
    for label, values in per_label.items():
        lines.append('| ' + label + ' | ' + ' | '.join(cell(values[str(k)]) for k in KS) + ' |')
    lines += ['', '### Nhận xét theo nhãn', '',
              '- REPORT_CONTENT tăng từ 1/6 ở top-1 lên 6/6 ở top-3; '
              'trong bộ này nhãn đúng đã có trong ba ứng viên đầu nhưng thường chưa đứng đầu. '
              'Tăng lên top-5 không bổ sung thêm câu nào của nhóm này.',
              '- PERSON_ROLE tăng từ 3/8 lên 6/8 rồi 8/8; hai câu T021/T024 chỉ xuất hiện '
              'ở hạng 4/5. NEWS, NUMERIC và MIXED mỗi nhóm được bổ sung một câu khi tăng từ 3 lên 5.',
              '- MIXED chỉ đúng 1/6 ở top-1 dù đạt 6/6 ở top-5: '
              'chưa thể suy ra hệ thống đã tách được các ý định thành phần hoặc chọn đúng nhánh.',
              '- ENTITY_RELATION không tăng từ top-3 lên top-5 (đều 5/6). '
              'T027 hỏi quan hệ hợp tác nhưng ENTITY_RELATION ở hạng 6. '
              'Có thể câu gần mẫu theo bối cảnh báo cáo hơn thao tác hỏi quan hệ; '
              'đây là giả thuyết từ câu hỏi/thứ hạng, chưa phải nguyên nhân được kiểm chứng. '
              'Cần bộ câu development riêng để kiểm tra thay vì sửa mẫu theo riêng T027.']
    for field, title in [('scope_status', 'Theo độ đầy đủ ngữ cảnh'), ('linguistic_form', 'Theo hình thức câu hỏi')]:
        lines += ['', '## ' + title, '', '| Nhóm | Top-1 | Top-3 | Top-5 |', '|---|---:|---:|---:|']
        for value, values in slices[field].items():
            lines.append('| ' + value + ' | ' + ' | '.join(cell(values[str(k)]) for k in KS) + ' |')
    lines += ['', '## Các câu chỉ được bổ sung khi mở từ top-3 lên top-5', '',
              '| ID | Câu hỏi | Nhãn đúng | Hạng | Năm nhãn đầu |', '|---|---|---|---:|---|']
    for row in rows:
        if 3 < row['gold_rank'] <= 5:
            lines.append(f"| {row['id']} | {row['question'].replace('|', '/')} | {row['gold']} | "
                         f"{row['gold_rank']} | {' → '.join(row['ordered_labels'][:5])} |")
    lines += ['', '## Các câu vẫn bị bỏ sót ở top-5', '']
    missed = [r for r in rows if r['gold_rank'] > 5]
    if not missed:
        lines.append('Không có trong bộ test này. Điều này không bảo đảm tổng quát hóa sang câu mới.')
    for row in missed:
        lines.append(f"- **{row['id']}**, gold `{row['gold']}`, hạng {row['gold_rank']}: {row['question']} "
                     f"Năm nhãn đầu: {' → '.join(row['ordered_labels'][:5])}.")
    lines += ['', '## Ý nghĩa và đề xuất gửi reviewer', '',
              '- Top-1 đo khả năng xếp đúng nhãn đầu. Kết quả còn thấp; '
              'chưa có cơ sở mặc định dùng nhãn đầu để điều phối câu hỏi.',
              '- Top-3/top-5 đo khả năng giữ lại nhãn đúng cho bước xử lý sau. '
              'Mở rộng danh sách không làm nhãn đầu chính xác hơn và không tự giải quyết các ca sai.',
              '- Top-5 giữ 5/7 nhãn (71,43% không gian nhãn), nên tỷ lệ cao cần được đọc cùng độ rộng '
              'danh sách. Tỷ lệ 5/7 này không phải accuracy của một baseline ngẫu nhiên đã chạy.',
              '- Nếu luôn trả đủ k nhãn, top-3/top-5 sẽ luôn kèm ít nhất 2/4 nhãn không phải gold. '
              'Chưa đo chất lượng tầng chọn cuối, latency hoặc chi phí các nhánh khi tích hợp; '
              'ba top-k dùng cùng embedding và thứ hạng nên không có ba số latency độc lập.',
              '- Đề nghị Hưng review riêng: công thức/thứ hạng, khả năng giữ ứng viên và '
              'chất lượng top-1. Có thể dùng top-3 làm mốc so sánh ứng viên, xem top-5 như phân tích '
              'độ bao phủ bổ sung; chưa chốt k cho production hoặc tự thêm tầng chọn nhãn.',
              '- Nếu cần cải thiện, thống nhất tiêu chí trên tập development riêng và đánh giá bằng '
              'test mới. Bộ hiện tại nhỏ, do cùng tác giả soạn mẫu/test và đã được xem kết quả; '
              'các chênh lệch là mô tả bộ này, chưa chứng minh ý nghĩa thống kê hoặc hiệu quả Web Chat.', '',
              '## Tái tạo và truy vết', '',
              'Chạy từ repository: `python backend/scripts/report_s5_intent_topk.py` '
              '(Python chuẩn, không cần model/DB). Lệnh chỉ tạo lại báo cáo phân tích; không ghi run01.', '',
              'Dữ liệu chi tiết, thứ hạng gold của từng câu và checksum nguồn: '
              '`outputs/s5_wbs041_topk_20261111/comparison.json`. '
              'Lượt kiểm chứng model thật trước đó: '
              '`outputs/s5_wbs041_review_20261111/real-model-audit.json`.', '']
    if fingerprints != {name: digest(args.run / name) for name in files}:
        raise ValueError('SOURCE_CHANGED_DURING_ANALYSIS')
    args.output.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    (args.output / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                               encoding='utf-8', newline='\n')
    args.report.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps(dict(overall=overall, per_label=per_label, buckets=recovered), indent=2))


if __name__ == '__main__':
    main()
