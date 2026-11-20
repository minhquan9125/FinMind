import json
from collections import Counter
from pathlib import Path

root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
drafts = Path(r'D:\finmind\tmp\ocr-review')
docs = {
    'ICT/2024/ICT_2024_501210': 2024,
    'ICT/2025/ICT_2025_540815': 2025,
    'ELC/2025/ELC_2025_541948': 'ELC',
}
for rel, year in docs.items():
    doc = root / rel
    rows = [json.loads(line) for line in (doc / 'pages.jsonl').read_text(encoding='utf-8').splitlines()]
    changed = 0
    for row in rows:
        if row.get('status') != 'REVIEW' or 'GEMINI_FAILED' not in row.get('flags', []):
            continue
        page = row['page']
        if year == 'ELC':
            parts = sorted(drafts.glob(f'ELC-2025-{page:03d}-part*.txt'))
            if not parts:
                continue
            content = '\n\n'.join(p.read_text(encoding='utf-8').strip() for p in parts)
        else:
            path = drafts / f'{year}-{page:03d}-combined.txt'
            if not path.exists():
                continue
            content = path.read_text(encoding='utf-8').strip()
        if len(content) < 300:
            continue
        row['text'] = content
        row['flags'] = list(dict.fromkeys(row.get('flags', []) + ['SPLIT_OCR_DRAFT']))
        row['splitOcr'] = {'engine': 'tesseract', 'languages': 'vie+eng', 'basis': 'separate page halves; rotated where needed', 'reviewed': False}
        (doc / 'text' / f'p-{page:03d}.txt').write_text(content + '\n', encoding='utf-8')
        changed += 1
    if changed:
        (doc / 'pages.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        summary_path = doc / 'summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        summary['status'] = dict(Counter(row['status'] for row in rows))
        summary['flags'] = dict(Counter(flag for row in rows for flag in row.get('flags', [])))
        summary['reviewPages'] = [row['page'] for row in rows if row['status'] == 'REVIEW']
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(rel, changed)
