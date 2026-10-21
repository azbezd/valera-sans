"""Крупные кропы каждого исправленного места: до | после, все веса."""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import render, ASC  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 20)
R, CELL = 110, 300


def crop(m, x, y, ref=None):
    cx, cy = x + 40, ASC - y
    out = np.zeros((2 * R, 2 * R), bool)
    ys = slice(max(0, cy - R), min(m.shape[0], cy + R)); xs = slice(max(0, cx - R), min(m.shape[1], cx + R))
    out[ys.start - cy + R:ys.stop - cy + R, xs.start - cx + R:xs.stop - cx + R] = m[ys, xs]
    return out


def tile(m, ref=None):
    rgb = np.full(m.shape + (3,), 17, np.uint8); rgb[m] = (240, 210, 70)
    if ref is not None:
        rgb[ref & ~m] = (200, 50, 50)
    return Image.fromarray(rgb).resize((CELL, CELL), Image.LANCZOS)


spec = json.loads((HERE / 'fixes.json').read_text())
rows = []
for st in ['Light', 'Regular', 'Semibold']:
    old = ufoLib2.Font.open(ROOT / f'.orig/ValeraSans-{st}.ufo'); new = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{st}.ufo')
    cands = {c['index']: c for c in json.loads((HERE / f'candidates-{st}.json').read_text())}
    for fx in spec[st]:
        if fx['type'] == 'drip':
            c = cands[fx['index']]; g, (x, y) = c['glyph'], c['tip']
        elif fx['type'] == 'span':
            g = fx['glyph']; pts = [fx['a'], fx['b']] + fx.get('via', [])
            x, y = int(np.mean([p[0] for p in pts])), int(np.mean([p[1] for p in pts]))
        else:
            g, x, y = fx['glyph'], 180, 40
        a, b = crop(render(old[g]), x, y), crop(render(new[g]), x, y)
        ch = chr(new[g].unicodes[0]) if new[g].unicodes else g
        rows.append((f'{ch}  {st}', tile(a), tile(b, ref=a)))
cols = 4
H = CELL + 30
img = Image.new('RGB', (cols * (2 * CELL + 30), ((len(rows) + cols - 1) // cols) * H), (45, 45, 45))
d = ImageDraw.Draw(img)
for i, (lab, a, b) in enumerate(rows):
    x0, y0 = (i % cols) * (2 * CELL + 30), (i // cols) * H
    d.text((x0 + 6, y0 + 3), lab + '   до | после (красным — срезано)', fill=(230, 230, 230), font=LABEL)
    img.paste(a, (x0 + 4, y0 + 28)); img.paste(b, (x0 + CELL + 8, y0 + 28))
img.save(HERE / 'fixes-before-after.png')
print(len(rows), img.size)
