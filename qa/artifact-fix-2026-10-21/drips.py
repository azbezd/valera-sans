"""Капля = острый выпуклый носик, по обе стороны которого на расстоянии до ~50 ед.
контура есть вогнутые «шейки». Обрубленные концы штрихов шеек не имеют."""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import PolyPen, render, ASC  # noqa: E402
from necks import resample  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 13)
R = 9
DISK = (lambda y, x: x * x + y * y <= R * R)(*np.ogrid[-R:R + 1, -R:R + 1])


def fill_map(m):
    return ndi.convolve(m.astype(float), DISK / DISK.sum(), mode='constant')


def sample(fm, q):
    xs = np.clip(np.round(q[:, 0]).astype(int) + 40, 0, fm.shape[1] - 1)
    ys = np.clip(ASC - np.round(q[:, 1]).astype(int), 0, fm.shape[0] - 1)
    return fm[ys, xs]


def find(glyph, win=6, min_turn=45.0, tip_fill=0.42, neck_fill=0.58, reach=55):
    m = render(glyph)
    fm = fill_map(m)
    pen = PolyPen(steps=24)
    glyph.draw(pen)
    hits = []
    for ci, poly in enumerate(pen.polys):
        q = resample(poly, 1.0)
        n = len(q)
        if n < 4 * win:
            continue
        f = sample(fm, q)
        a, c = q[(np.arange(n) - win) % n], q[(np.arange(n) + win) % n]
        v1, v2 = q - a, c - q
        turn = np.abs(np.degrees(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1))))
        cand = np.nonzero((turn > min_turn) & (f < tip_fill))[0]
        taken = np.zeros(n, bool)
        for k in sorted(cand, key=lambda k: f[k]):
            if taken[k]:
                continue
            left = [(k - d) % n for d in range(3, reach)]
            right = [(k + d) % n for d in range(3, reach)]
            li, ri = int(np.argmax(f[left])), int(np.argmax(f[right]))
            if f[left][li] < neck_fill or f[right][ri] < neck_fill:
                continue
            lo, hi = k - (li + 3), k + (ri + 3)
            taken[[i % n for i in range(lo, hi + 1)]] = True
            hits.append({'contour': ci, 'tip': [round(float(v)) for v in q[k]],
                         'neckL': [round(float(v)) for v in q[lo % n]], 'neckR': [round(float(v)) for v in q[hi % n]],
                         'arc': int(hi - lo), 'contourIdx': [int(lo % n), int(k), int(hi % n)], 'turn': round(float(turn[k])), 'tipfill': round(float(f[k]), 2),
                         'neckfill': round(float(min(f[left][li], f[right][ri])), 2)})
    return hits


def crops(font, items, out, cell=170, cols=10):
    rows = (len(items) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, max(1, rows) * (cell + 16)), (17, 17, 17))
    d = ImageDraw.Draw(img)
    cache = {}
    for k, it in enumerate(items):
        name = it['glyph']
        m = cache.setdefault(name, render(font[name]))
        cx, cy = it['tip'][0] + 40, ASC - it['tip'][1]
        r = 60
        sub = np.zeros((2 * r, 2 * r), bool)
        y0, x0 = cy - r, cx - r
        ys = slice(max(0, y0), min(m.shape[0], y0 + 2 * r)); xs = slice(max(0, x0), min(m.shape[1], x0 + 2 * r))
        sub[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = m[ys, xs]
        rgb = np.full(sub.shape + (3,), 17, np.uint8); rgb[sub] = (240, 210, 70)
        for key, col in (('neckL', (80, 160, 255)), ('neckR', (80, 160, 255)), ('tip', (255, 40, 40))):
            px_, py_ = it[key][0] + 40 - x0, ASC - it[key][1] - y0
            if 1 <= px_ < 2 * r - 1 and 1 <= py_ < 2 * r - 1:
                rgb[py_ - 1:py_ + 2, px_ - 1:px_ + 2] = col
        t = Image.fromarray(rgb).resize((cell - 4, cell - 4), Image.NEAREST)
        px, py = (k % cols) * cell, (k // cols) * (cell + 16)
        img.paste(t, (px + 2, py + 16))
        d.text((px + 3, py + 1), f"{k} {it['char']} {it['glyph'][3:]} a{it['arc']}", fill=(220, 220, 220), font=LABEL)
    img.save(out)


if __name__ == '__main__':
    style = sys.argv[1] if len(sys.argv) > 1 else 'Regular'
    font = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    items = []
    for name in sorted(font.keys()):
        g = font[name]
        ch = chr(g.unicodes[0]) if g.unicodes else name
        for h in find(g):
            items.append({'glyph': name, 'char': ch, **h})
    for k, it in enumerate(items):
        it['index'] = k
    (HERE / f'drips-{style}.json').write_text(json.dumps(items, ensure_ascii=False, indent=1))
    crops(font, items, HERE / f'drips-{style}.png')
    print(style, len(items), 'hits in', len({i['glyph'] for i in items}), 'glyphs')
