import json
import sys
from collections import Counter
from pathlib import Path

root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
rel, page, source = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = '' if source == '--visual-blank' else Path(source).read_text(encoding='utf-8').strip()
if not text and source != '--visual-blank':
    raise ValueError('Reviewed text is empty')
doc = root / rel
rows = [json.loads(s) for s in (doc / 'pages.jsonl').read_text(encoding='utf-8').splitlines()]
row = next(r for r in rows if r['page'] == page)
if row['status'] != 'OK' or row.get('text', '').strip() or 'NEAR_EMPTY' not in row.get('flags', []):
    raise ValueError('Target is not an OK, near-empty page')
manifest = root / 'manual_visual_review.json'
data = json.loads(manifest.read_text(encoding='utf-8'))
entry = next((e for e in data['entries'] if e['document'] == rel and e['page'] == page), None)
if entry is None:
    entry = {'document': rel, 'page': page}
    data['entries'].append(entry)
entry['text'] = text
if source == '--visual-blank':
    entry['visualBlank'] = True
else:
    entry.pop('visualBlank', None)
manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
row['text'] = text
row['flags'] = ['MANUAL_REVIEWED'] + (['VISUAL_BLANK'] if source == '--visual-blank' else [])
row['manualReview'] = {'source': 'ocr_standard/manual_visual_review.json', 'basis': 'rendered_pdf_page'}
(doc / 'text' / f'p-{page:03d}.txt').write_text(text + '\n', encoding='utf-8')
(doc / 'pages.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
summary_path = doc / 'summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
summary['status'] = dict(Counter(r['status'] for r in rows))
summary['flags'] = dict(Counter(f for r in rows for f in r.get('flags', [])))
summary['reviewPages'] = [r['page'] for r in rows if r['status'] == 'REVIEW']
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(rel, page, 'VISUAL_BLANK' if source == '--visual-blank' else 'MANUAL_REVIEWED')
