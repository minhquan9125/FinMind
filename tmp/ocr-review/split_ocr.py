import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard')
OUT = Path(r'D:\finmind\tmp\ocr-review')
TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
DOCS = ['ICT/2024/ICT_2024_501210', 'ICT/2025/ICT_2025_540815']


def ocr(image):
    result = subprocess.run(
        [TESS, 'stdin', 'stdout', '-l', 'vie+eng', '--oem', '1', '--psm', '3',
         '-c', 'preserve_interword_spaces=1', '-c', 'tessedit_do_invert=0'],
        input=image, capture_output=True, check=True,
    )
    return result.stdout.decode('utf-8', errors='replace').strip()


def process(item):
    doc, page = item
    image = Image.open(ROOT / doc / 'work' / f'p-{page:03d}.png').convert('RGB')
    w, h = image.size
    halves = [image.crop((0, 0, w // 2, h)), image.crop((w // 2, 0, w, h))]
    texts = {}
    for side, half in zip(('left', 'right'), halves):
        for angle in (0, 270):
            rotated = half.rotate(angle, expand=True)
            from io import BytesIO
            buffer = BytesIO()
            rotated.save(buffer, format='PNG')
            text = ocr(buffer.getvalue())
            texts[f'{side}_{angle}'] = text
    year = doc.split('/')[1]
    for key, text in texts.items():
        (OUT / f'{year}-{page:03d}-{key}.txt').write_text(text, encoding='utf-8')
    scores = {k: len(re.findall(r'[A-Za-zÀ-ỹ0-9]', v)) for k, v in texts.items()}
    return year, page, scores


def main():
    items = []
    for doc in DOCS:
        for line in (ROOT / doc / 'pages.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row.get('status') == 'REVIEW' and 'GEMINI_FAILED' in row.get('flags', []):
                items.append((doc, row['page']))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for year, page, scores in pool.map(process, items):
            print(year, page, scores, flush=True)


if __name__ == '__main__':
    main()
