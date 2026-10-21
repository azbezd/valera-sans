"""Крупный вид участка глифа с точками контура: zoomview.py Style glyph x0 y0 x1 y1 out.png"""
import sys
from pathlib import Path
import numpy as np, ufoLib2
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import render, ASC

def view(glyph, box, out, scale=4):
    x0, y0, x1, y1 = box
    m = render(glyph, scale=scale)
    pad = 40
    sub = m[int((ASC - y1) * scale):int((ASC - y0) * scale), int((x0 + pad) * scale):int((x1 + pad) * scale)]
    rgb = np.full(sub.shape + (3,), 17, np.uint8); rgb[sub] = (240, 210, 70)
    im = Image.fromarray(rgb); d = ImageDraw.Draw(im)
    def P(x, y): return ((x - x0) * scale, (y1 - y) * scale)
    for ci, c in enumerate(glyph.contours):
        pts = list(c.points)
        for pi, p in enumerate(pts):
            if not (x0 - 5 <= p.x <= x1 + 5 and y0 - 5 <= p.y <= y1 + 5): continue
            X, Y = P(p.x, p.y)
            if p.type: d.rectangle([X-4,Y-4,X+4,Y+4], outline=(255,40,40), width=2)
            else: d.ellipse([X-3,Y-3,X+3,Y+3], outline=(60,160,255), width=2)
            d.text((X+5,Y-12), f"{ci}.{pi}", fill=(255,255,255))
    im.save(out)

if __name__ == '__main__':
    st, gn = sys.argv[1], sys.argv[2]
    f = ufoLib2.Font.open(Path(__file__).parents[2] / f'sources/ValeraSans-{st}.ufo')
    view(f[gn], tuple(map(int, sys.argv[3:7])), sys.argv[7], scale=float(sys.argv[8]) if len(sys.argv) > 8 else 4)
