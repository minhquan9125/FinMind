import json
from collections import Counter
from pathlib import Path

root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
totals = Counter()
remaining = []
errors = []
documents = 0
manual_pages = set()
document_rows = {}
for file in root.rglob('pages.jsonl'):
    documents += 1
    rows = []
    try:
        for n, line in enumerate(file.read_text(encoding='utf-8-sig').splitlines(), 1):
            if line.strip():
                rows.append(json.loads(line))
    except Exception as exc:
        errors.append(f'{file}: line {n}: {exc}')
        continue
    rel = str(file.parent.relative_to(root)).replace('/', '\\')
    document_rows[rel] = rows
    page_numbers = [r.get('page') for r in rows]
    if page_numbers != list(range(1, len(rows) + 1)):
        errors.append(f'{file}: missing, repeated or out-of-order page numbers')
    for row in rows:
        status = row.get('status') or row.get('ocr_status') or row.get('review_status')
        totals[status] += 1
        page = row.get('page')
        page_file = file.parent / 'text' / f'p-{page:03d}.txt'
        if not page_file.exists():
            errors.append(f'{page_file}: missing')
        elif page_file.read_text(encoding='utf-8-sig').strip() != row.get('text', '').strip():
            errors.append(f'{page_file}: text differs from pages.jsonl')
        if not row.get('text', '').strip() and status == 'OK' and 'VISUAL_BLANK' not in row.get('flags', []):
            errors.append(f'{file}: page {page} is OK but has empty text')
        if 'VISUAL_BLANK' in row.get('flags', []) and row.get('text', '').strip():
            errors.append(f'{file}: page {page} has VISUAL_BLANK but nonempty text')
        if 'MANUAL_REVIEWED' in row.get('flags', []):
            manual_pages.add((rel, page))
        if status in ('REVIEW', 'PENDING'):
            remaining.append((str(file.parent.relative_to(root)), row.get('page_no', row.get('page')), status))
    summary = file.parent / 'summary.json'
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding='utf-8-sig'))
            if data.get('status') != dict(Counter(r.get('status') for r in rows)):
                errors.append(f'{summary}: status counts differ from pages.jsonl')
            if data.get('reviewPages') != [r.get('page') for r in rows if r.get('status') == 'REVIEW']:
                errors.append(f'{summary}: reviewPages differs from pages.jsonl')
            if data.get('pages') != len(rows):
                errors.append(f'{summary}: pages count differs from pages.jsonl')
            if data.get('flags') != dict(Counter(f for r in rows for f in r.get('flags', []))):
                errors.append(f'{summary}: flags counts differ from pages.jsonl')
        except Exception as exc:
            errors.append(f'{summary}: {exc}')
manifest = root / 'manual_visual_review.json'
if manifest.exists():
    try:
        entries = json.loads(manifest.read_text(encoding='utf-8-sig'))['entries']
        keys = [(e['document'].replace('/', '\\'), e['page']) for e in entries]
        if len(keys) != len(set(keys)):
            errors.append(f'{manifest}: duplicate entries')
        for entry, key in zip(entries, keys):
            if key not in manual_pages:
                errors.append(f'{manifest}: {key} lacks MANUAL_REVIEWED page')
                continue
            row = document_rows[key[0]][key[1]-1]
            if entry.get('text', '').strip() != row.get('text', '').strip():
                errors.append(f'{manifest}: {key} text differs from pages.jsonl')
            if bool(entry.get('visualBlank')) != ('VISUAL_BLANK' in row.get('flags', [])):
                errors.append(f'{manifest}: {key} visualBlank differs from pages.jsonl')
    except Exception as exc:
        errors.append(f'{manifest}: {exc}')
print('documents', documents)
print('statuses', dict(totals))
print('remaining_count', len(remaining))
print('manual_reviewed_pages', len(manual_pages))
print('manifest_entries', len(entries) if manifest.exists() else 0)
for item in remaining[:100]:
    print('remaining', *item)
print('errors_count', len(errors))
for item in errors[:100]:
    print('error', item)
