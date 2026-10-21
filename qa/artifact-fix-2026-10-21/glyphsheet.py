"""Лист целых глифов: glyphsheet.py Style out.png name1 name2 ... [--h 360]"""
import sys
from pathlib import Path
import numpy as np, ufoLib2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import render
LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 16)

def sheet(font, names, out, h=360, cols=8):
    tiles = []
    for n in names:
        m = render(font[n])
        rgb = np.full(m.shape + (3,), 17, np.uint8); rgb[m] = (240, 210, 70)
        # базовая линия
        rgb[1100, :] = (70, 70, 70)
        t = Image.fromarray(rgb); s = h / t.height
        t = t.resize((max(1, int(t.width * s)), h), Image.LANCZOS)
        d = ImageDraw.Draw(t); g = font[n]
        d.text((4, 2), (chr(g.unicodes[0]) if g.unicodes else '') + ' ' + n, fill=(200, 200, 200), font=LABEL)
        tiles.append(t)
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    W = max(sum(t.width + 4 for t in r) for r in rows)
    img = Image.new('RGB', (W, len(rows) * (h + 4)), (50, 50, 50))
    for ri, r in enumerate(rows):
        x = 0
        for t in r:
            img.paste(t, (x, ri * (h + 4))); x += t.width + 4
    img.save(out)

if __name__ == '__main__':
    st, out, *names = sys.argv[1:]
    f = ufoLib2.Font.open(Path(__file__).parents[2] / f'sources/ValeraSans-{st}.ufo')
    sheet(f, names, out)
