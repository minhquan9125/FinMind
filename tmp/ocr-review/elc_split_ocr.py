from io import BytesIO
from pathlib import Path
import subprocess
from PIL import Image

ROOT=Path(r'D:\finmind\data\references\vietstock\annual_reports\ocr_standard\ELC\2025\ELC_2025_541948\work')
OUT=Path(r'D:\finmind\tmp\ocr-review')
TESS=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
PAGES=[69,70,75,76,80,93,185,189]
for page in PAGES:
    im=Image.open(ROOT/f'p-{page:03d}.png').convert('RGB')
    w,h=im.size
    if page==80:
        crops=[im.crop((int(w*.43),0,int(w*.80),h))]
    elif page==185:
        crops=[im.crop((int(w*.31),0,int(w*.88),h))]
    else:
        crops=[im.crop((int(w*.25),0,int(w*.63),h)),im.crop((int(w*.63),0,w,h))]
    texts=[]
    for i,crop in enumerate(crops,1):
        buf=BytesIO();crop.save(buf,format='PNG')
        result=subprocess.run([TESS,'stdin','stdout','-l','vie+eng','--oem','1','--psm','3','-c','preserve_interword_spaces=1'],input=buf.getvalue(),capture_output=True,check=True)
        text=result.stdout.decode('utf-8',errors='replace').strip()
        texts.append(text)
        (OUT/f'ELC-2025-{page:03d}-part{i}.txt').write_text(text,encoding='utf-8')
    print(page,[len(t) for t in texts],flush=True)
