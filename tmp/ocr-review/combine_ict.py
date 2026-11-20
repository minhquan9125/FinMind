from pathlib import Path

ROOT=Path(r'D:\finmind\tmp\ocr-review')
ROTATED={
    2024: {51:{'right'},52:{'left','right'},54:{'right'},55:{'left','right'},56:{'left'}},
    2025: {55:{'right'},56:{'left'},58:{'right'},59:{'left','right'},60:{'left'}},
}
for year, pages in {
    2024:list(range(39,62)),
    2025:[43,44,45,46,47,50,51,53,54,55,56,57,58,59,60,61,62,63,64,65],
}.items():
    for page in pages:
        texts=[]
        for side in ('left','right'):
            angle=270 if side in ROTATED.get(year,{}).get(page,set()) else 0
            texts.append((ROOT/f'{year}-{page:03d}-{side}_{angle}.txt').read_text(encoding='utf-8').strip())
        (ROOT/f'{year}-{page:03d}-combined.txt').write_text('\n\n'.join(texts)+'\n',encoding='utf-8')
        print(year,page,len(texts[0]),len(texts[1]))
