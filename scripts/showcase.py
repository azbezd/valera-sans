"""Render the README cover using the actual released font files."""
from pathlib import Path
import os
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
def label(size):
    for name in [os.environ.get('LABEL_FONT',''),'/System/Library/Fonts/Supplemental/Arial.ttf','DejaVuSans.ttf','LiberationSans-Regular.ttf']:
        if not name:continue
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default(size=size)
def hand(style,size):return ImageFont.truetype(str(ROOT/f'fonts/ttf/ValeraSans-{style}.ttf'),size)
im=Image.new('RGB',(1920,1080),'#191c18');d=ImageDraw.Draw(im)
ink,muted,gold='#efeee5','#aaaF9e','#c5ad5e'
d.text((96,66),'VALERASKETCH / TYPEFACE',font=label(28),fill=muted)
d.line((96,128,1824,128),fill='#3d4438',width=2)
d.text((83,420),'Valera Sans',font=hand('Regular',258),fill=ink,anchor='ls',features=['calt','kern'])
d.text((96,598),'Буквы, как от руки.',font=hand('Regular',104),fill=ink,anchor='ls')
d.text((96,680),'Handwritten Latin & Cyrillic',font=label(34),fill=muted)
for i,(style,weight)in enumerate([('Light',300),('Regular',400),('Semibold',600)]):
    x=96+i*585
    d.line((x,786,x+470,786),fill=gold,width=2)
    d.text((x,820),style.upper(),font=label(25),fill=muted)
    d.text((x,994),'Аа / er re',font=hand(style,84),fill=ink,anchor='ls')
out=ROOT/'docs/assets/banner.webp';out.parent.mkdir(exist_ok=True)
im.save(out,'WEBP',lossless=True)
print(out.relative_to(ROOT),out.stat().st_size,'bytes')
