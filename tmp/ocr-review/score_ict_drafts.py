import collections
import json
import re
from pathlib import Path

root=Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
draft=Path(r'D:\finmind\tmp\ocr-review')
token=re.compile(r'[A-Za-zÀ-ỹ]{2,}')
vocab=collections.Counter()
for p in root.glob('**/pages.jsonl'):
    for line in p.read_text(encoding='utf-8').splitlines():
        r=json.loads(line)
        if r.get('status')=='OK' and ('PDF_TEXT_VERIFIED' in r.get('flags',[]) or 'MANUAL_REVIEWED' in r.get('flags',[])):
            vocab.update(x.lower() for x in token.findall(r['text']))
for year, pages in {2024:list(range(39,62)),2025:[43,44,45,46,47,50,51,53,54,55,56,57,58,59,60,61,62,63,64,65]}.items():
    for page in pages:
        text=(draft/f'{year}-{page:03d}-combined.txt').read_text(encoding='utf-8')
        words=[x.lower() for x in token.findall(text)]
        score=sum(len(x) for x in words if vocab[x]>=2)/max(1,sum(map(len,words)))
        weird=sum(ch in '§†‡□�₫⁄¡¿€|~^' for ch in text)
        print(year,page,round(score,2),len(text),weird)
