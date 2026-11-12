"""Generate the consolidated handoff from frozen, retained experiment outputs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/s5_intent_composition_20261112'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def main():
    original = read('results.json')
    summary = read('objectives-v3/summary.json')
    final = read('final-check-v3-utf8/summary.json')
    rows = []
    names = dict(development='Phát triển', regression='Hồi quy cũ', known_diagnostic='Chẩn đoán đã xem',
                 previous_check='28 câu từ lượt trước', controls='Kiểm soát đơn/kết hợp')
    for key, name in names.items():
        old = original['original'][key]['metrics']
        linear = original['linear'][key]['metrics']
        current = summary['metrics'][key]
        rows.append(f"| {name} | {current['labeled']} | {old['hits']['1']} | {linear['hits']['1']} | {current['correct']} |")
    rows.append('| 42 câu từng kiểm tra V2, nay đã xem | 42 | 27 | 37 | 39 |')
    new = final['metrics']
    rows.append(f"| 28 câu mới sau đóng băng V3 | 28 | {new['original']['correct']} | {new['linear']['correct']} | {new['consensus']['correct']} |")
    wrong = [r for r in read('final-check-v3-utf8/results.json') if r['gold'] != r['final_label']]
    errors = '\n'.join(f"| {r['id']} | {r['question']} | {r['gold']} | {r['final_label']} |" for r in wrong)
    text = f"""# S5-WBS04.1 — Nhận diện từng yêu cầu, 12/11/2026

Ứng viên V3 đã sửa T038, đạt **41/47 câu hồi quy** và **32/32 câu kiểm soát**.
Kiểm tra 28 câu mới sau khi đóng băng đạt **25/28 (89,29%)**, so với classifier
23/28 và baseline cosine 18/28. Không có câu classifier đang đúng bị V3 làm sai
trên các tập đã đo. Đây là kết quả offline; chưa xác nhận router hay Web Chat.

## Cách làm và những lần không đạt

Giữ nguyên model BGE-M3/revision, taxonomy đã duyệt và classifier C=1 từ bước
trước. Không thêm câu test vào training, không sửa nhãn để tăng điểm.

1. V1 tách yêu cầu rồi dùng xác suất thành phần nâng điểm MIXED: thất bại,
   T038 vẫn sai và T003 đang đúng thành sai. Giữ nguyên output để đối chiếu.
2. V2 đối chiếu nhãn của cả câu với từng yêu cầu: sửa T038 và đạt 40/47,
   nhưng chỉ đúng 22/32 câu kiểm soát, còn nhầm nội dung báo cáo và câu kết hợp.
3. V3 bổ sung quy tắc hẹp theo mục tiêu: hỏi người/chức vụ; mô tả chính sách,
   chiến lược trong báo cáo; hai yêu cầu độc lập; yêu cầu trích nguồn làm bằng
   chứng. Không có điều kiện riêng theo ticker, năm, tên người hoặc mã test.
   Yêu cầu hỗ trợ trích dẫn không tự tạo thêm ý định. Những trường hợp không có
   dấu hiệu rõ tiếp tục dùng quyết định V2, nên vẫn có lỗi.

V3 trả `resolution.intent_label` kèm lý do và bằng chứng. **Giữ nguyên
`base_ranking` và mọi điểm của classifier**, không đẩy nhãn V3 lên đầu rồi
gắn điểm cũ. Vì vậy cột V3 dưới đây là độ đúng của quyết định nhãn, không phải
top-1 của một bảng similarity mới; top-3/top-5 thô không thay đổi.

## So sánh trên cùng câu hỏi

| Tập | Số câu có nhãn | Cosine gốc đúng | Linear đúng | Quyết định V3 đúng |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

Tập hồi quy có 56 câu, chỉ 47 câu có nhãn được tính accuracy; 9 câu null không
được tự gán nhãn. V3 giữ đúng tất cả câu baseline cũ từng đúng ở tập hồi quy.
24/24 câu kiểm soát chính (vai trò, nội dung báo cáo, kết hợp, trích dẫn hỗ trợ)
đều đúng với sáu công ty. Đây là kiểm soát hữu hạn; lỗi đổi mã công ty chưa biến
mất hoàn toàn: câu số liệu DPM dưới đây sai trong khi cùng khung VRE đúng.

Các tập đã xem chỉ là phát triển/hồi quy. Bộ 42 câu từng mới ở V2 đã được xem
trước khi làm V3. Bộ 28 câu cuối có 14 khung × hai công ty DPM/VRE, được soạn
và chấm sau khi đóng băng V3; do cùng tác giả soạn, không gọi là test mù độc lập.
Nhiều câu cùng khung nên 28 hàng không phải 28 tình huống độc lập.

## Ba câu mới còn sai — giữ nguyên sau phép đo

| Mã | Câu hỏi | Kỳ vọng | Quyết định V3 |
|---|---|---|---|
{errors}

Câu số liệu bị classifier nghiêng về ENTITY_RELATION. Hai câu MIXED bị NEWS lấn
át; V3 chưa đủ bằng chứng để sửa. Bộ chẩn đoán cũ cũng còn KNOWN-07/08 sai.
Chưa kết luận đã xử lý hết nhầm đơn/kết hợp hay mọi ảnh hưởng của tên công ty.

## Hợp đồng bàn giao cho Hưng/Huyền

- `resolution.confidence = null`, `score_type = DECISION_EVIDENCE_NO_CONFIDENCE`,
  `runtime_enabled = false`. Không tự bịa confidence từ số quy tắc khớp.
- Probability classifier chưa calibration; khác cosine. Không áp 0,65/0,08
  cho V3 hoặc probability rồi gọi đó là cùng policy đã duyệt.
- Ngưỡng và payload top-3 hiện tại của Huyền không đổi. Source consumer 04.2
  mới chưa có trong checkout; chưa cài guard hoặc adapter vào consumer đó.
- MIXED không mặc định là BOTH: cần xét thành phần và chính sách router.
  Quy tắc V3 mới nhận rõ ROLE/REPORT, chưa phải bộ phân rã hoàn chỉnh bảy nhãn.
- Bàn giao để review logic/contract; muốn nối thật cần chốt cách tiêu thụ
  evidence, calibration/fallback phù hợp và kiểm thử consumer. Chưa đạt bằng
  chứng E2E hoặc mốc 90% của WBS04.3.

## Bằng chứng và cách chạy lại

`outputs/s5_intent_composition_20261112/` giữ cả V1, V2, V3, vector, từng câu,
manifest và checksum nguồn. Audit V3 tái hiện 278 quyết định; tái tính điểm
28 câu cuối từ vector bằng công thức riêng (sai lệch tối đa dưới 1e-10).
Replay quy tắc chỉ chứng minh tái tạo được, không thay review nhãn độc lập.
Có 101 unit test cho các module Sprint 5 liên quan; không phải test toàn app.

Lượt `final-check-v3/` không hợp lệ vì PowerShell làm mất dấu thành `?` bên
trong từ. Giữ producer lỗi, output và `invalid-input.json`; không tính lượt
đó vào chất lượng. `final-check-v3-utf8/` sửa cách ghi UTF-8 và thêm guard trước
embedding, giữ nguyên câu dự kiến, model và quy tắc. Audit đối chiếu hash cả
hai lượt để kiểm việc sửa mã hóa không thay head/rules.

Giải nén gói ở thư mục riêng, dùng môi trường backend hoặc dependency trong
`docs/sprint5/requirements-s5-objectives-check.txt` (có thêm dependency config
cho test guard mã hóa). Các audit/report dùng vector đã
lưu, không tải model, không gọi API/DB và không huấn luyện lại:

```powershell
$env:PYTHONPATH=(Join-Path $PWD.Path 'backend')
$env:PYTHONUTF8='1'
python backend/scripts/audit_s5_intent_composition.py
python backend/scripts/audit_s5_intent_consensus.py
python backend/scripts/audit_s5_intent_objectives.py
python backend/scripts/report_s5_intent_objectives.py
$intentTests=(Get-ChildItem backend/tests/test_s5_intent_*.py).FullName
python -m pytest $intentTests -q -p no:cacheprovider
```

Kế hoạch đã đóng băng: [V1](S5-WBS04.1-composition-plan.md),
[V2](S5-WBS04.1-consensus-plan.md), [V3](S5-WBS04.1-objective-plan.md).
Các kết quả chưa đạt: [V1](S5-WBS04.1-composition-results.md),
[V2](S5-WBS04.1-consensus-results.md).
"""
    target = ROOT / 'docs/sprint5/S5-WBS04.1-objective-results.md'
    target.write_text(text, encoding='utf-8', newline='\n')
    sample = next(r for r in read('objectives-v3/results.json')['regression'] if r['id'] == 'S5-T-038')
    payload = dict(case_id=sample['id'], question=sample['question'], resolution=sample['resolution'],
                   base_ranking=sample['base_ranking'], advisory_only=True,
                   legacy_threshold_compatible=False, route=None)
    (OUT / 'objectives-v3/payload-T038.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(target.relative_to(ROOT))


if __name__ == '__main__':
    main()
