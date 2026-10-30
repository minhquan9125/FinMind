import collections
import json
import logging
import re
from pathlib import Path

import pypdf

logging.getLogger('pypdf').setLevel(logging.ERROR)
root = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
pdf_root = Path(r'D:\finmind\data\references\vietstock\annual_reports\files_pdf')
documents = [
    'CTG/2025/CTG_2025_542401',
    'ELC/2024/ELC_2024_500811',
    'ELC/2025/ELC_2025_541948',
]


def decode_pdf_glyphs(value):
    value = re.sub(r'/uni([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), value)
    value = value.replace('/dslash', 'đ').replace('/Dslash', 'Đ')
    value = value.replace('/arrow-right', '→')
    value = re.sub(r'(?<=\d)\s+([.,])(?=\d)', r'\1', value)
    value = re.sub(r'[ \t]+\n', '\n', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


audit = {'basis': 'embedded text from original PDF; font glyph names decoded', 'documents': []}
for rel in documents:
    base = root / rel
    source = json.loads((base / 'source.json').read_text(encoding='utf-8'))
    pdf = pdf_root / source['pdf']
    reader = pypdf.PdfReader(str(pdf))
    pages_path = base / 'pages.jsonl'
    pages = [json.loads(line) for line in pages_path.read_text(encoding='utf-8').splitlines()]
    accepted = []
    skipped = []
    for page in pages:
        if page['status'] != 'REVIEW' or 'GEMINI_FAILED' not in page['flags']:
            continue
        number = page['page']
        value = decode_pdf_glyphs(reader.pages[number - 1].extract_text() or '')
        ratio = len(value) / max(1, len(page['text']))
        bad = bool(re.search(r'/uni[0-9A-Fa-f]|/dslash|[\x00-\x08\x0b-\x1f\ufffd]', value))
        if len(value) < 100 or ratio < 0.95 or bad:
            skipped.append({'page': number, 'chars': len(value), 'tesseractChars': len(page['text']), 'ratio': round(ratio, 3)})
            continue
        page['text'] = value
        page['status'] = 'OK'
        page['flags'] = ['PDF_TEXT_VERIFIED']
        page['pdfTextReview'] = {
            'source': source['pdf'],
            'method': 'embedded_pdf_text',
            'glyphNormalization': True,
            'draftLengthRatio': round(ratio, 3),
        }
        (base / 'text' / f'p-{number:03d}.txt').write_text(value + '\n', encoding='utf-8', newline='\n')
        accepted.append({'page': number, 'chars': len(value), 'draftLengthRatio': round(ratio, 3)})
    if accepted:
        pages_path.write_text(''.join(json.dumps(page, ensure_ascii=False) + '\n' for page in pages), encoding='utf-8', newline='\n')
        summary_path = base / 'summary.json'
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        summary['status'] = dict(collections.Counter(page['status'] for page in pages))
        summary['flags'] = dict(collections.Counter(flag for page in pages for flag in page['flags']))
        summary['reviewPages'] = [page['page'] for page in pages if page['status'] == 'REVIEW']
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    audit['documents'].append({'document': rel, 'pdf': source['pdf'], 'accepted': accepted, 'skipped': skipped})
    print(rel, 'accepted', len(accepted), 'skipped', [x['page'] for x in skipped], flush=True)
(root / 'pdf_text_recovery.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
