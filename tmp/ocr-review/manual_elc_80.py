import json
from collections import Counter
from pathlib import Path

root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
rel = 'ELC/2025/ELC_2025_541948'
text = '''CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM
Tòa nhà Elcom, phố Duy Tân, phường Cầu Giấy, Thành phố Hà Nội
Mẫu số B 09 - DN/HN
Ban hành theo Thông tư số 202/2014/TT-BTC ngày 22/12/2014 của Bộ Tài chính

BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH HỢP NHẤT (TIẾP THEO)
Cho năm tài chính kết thúc ngày 31/12/2025

5.8 Hàng tồn kho (Đơn vị tính: VND)
Khoản mục | 31/12/2025 Giá gốc | 31/12/2025 Dự phòng | 01/01/2025 Giá gốc | 01/01/2025 Dự phòng
Hàng đang đi trên đường | - | - | 83.237.779 | -
Công cụ, dụng cụ | 2.532.000 | - | 2.532.000 | -
Chi phí sản xuất kinh doanh dở dang | 180.818.954.287 | - | 50.082.816.293 | -
Thành phẩm | 6.600.531.309 | - | 9.194.864.671 | -
Hàng hóa (không bao gồm hàng hóa bất động sản) | 31.583.425.588 | - | 18.177.991.603 | -
Tổng | 219.005.443.184 | - | 77.541.442.346 | -

5.9 Chi phí trả trước (Đơn vị tính: VND)
Khoản mục | 31/12/2025 | 01/01/2025
Ngắn hạn | 501.566.033 | 308.592.841
  Công cụ dụng cụ | 27.697.242 | 9.249.162
  Chi phí chờ phân bổ khác | 473.868.791 | 299.343.679
Dài hạn | 298.887.071.775 | 309.032.571.278
  Công cụ dụng cụ | 950.235.421 | 2.635.528.116
  Giá trị lợi thế đầu tư vào công ty con (i) | 294.492.736.837 | 305.073.314.208
  Chi phí trả trước dài hạn khác | 3.444.099.517 | 1.323.728.954
Tổng | 299.388.637.808 | 309.341.164.119
(i) Giá trị lợi thế đầu tư vào Công ty Cổ phần Truyền thông và Máy tính Việt Nam.'''
manifest = root / 'manual_visual_review.json'
data = json.loads(manifest.read_text(encoding='utf-8'))
if not any(e['document'] == rel and e['page'] == 80 for e in data['entries']):
    data['entries'].append({'document': rel, 'page': 80, 'text': text})
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
doc = root / rel
lines = [json.loads(s) for s in (doc / 'pages.jsonl').read_text(encoding='utf-8').splitlines()]
for row in lines:
    if row['page'] == 80 and row['status'] == 'REVIEW' and 'GEMINI_FAILED' in row.get('flags', []):
        row['text'] = text
        row['status'] = 'OK'
        row['flags'] = ['MANUAL_REVIEWED']
        row['manualReview'] = {'source': 'ocr_standard/manual_visual_review.json', 'basis': 'rendered_pdf_page'}
        (doc / 'text' / 'p-080.txt').write_text(text + '\n', encoding='utf-8')
(doc / 'pages.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in lines), encoding='utf-8')
summary_path = doc / 'summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
summary['status'] = dict(Counter(row['status'] for row in lines))
summary['flags'] = dict(Counter(flag for row in lines for flag in row.get('flags', [])))
summary['reviewPages'] = [row['page'] for row in lines if row['status'] == 'REVIEW']
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
