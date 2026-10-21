"""Поиск капель как острых выпуклых изломов контура.

Рукописные штрихи имеют скруглённые концы (радиус ≈ полуширины штриха), поэтому
на коротком отрезке контура поворот небольшой. Капля/шип даёт резкий поворот
наружу на нескольких единицах. Скрипт пишет spikes-<Style>.json и лист кропов.
"""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import PolyPen, render, ASC  # noqa: E402
from necks import resample, signed_area  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def material(m, p, r=9):
    cx, cy = int(round(p[0])) + 40, ASC - int(round(p[1]))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    disk = x * x + y * y <= r * r
    win = np.zeros_like(disk)
    ys, xs = slice(cy - r, cy + r + 1), slice(cx - r, cx + r + 1)
    sub = m[ys, xs]
    if sub.shape != disk.shape:
        return 1.0
    return float(sub[disk].mean())


def find(glyph, win=6, min_turn=55.0):
    m = render(glyph)
    pen = PolyPen(steps=24)
    glyph.draw(pen)
    hits = []
    for ci, poly in enumerate(pen.polys):
        q = resample(poly, 1.0)
        n = len(q)
        if n < 4 * win:
            continue
        orient = np.sign(signed_area(q))
        a = q[(np.arange(n) - win) % n]
        b = q
        c = q[(np.arange(n) + win) % n]
        v1, v2 = b - a, c - b
        cross = v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]
        dot = (v1 * v2).sum(1)
        turn = np.abs(np.degrees(np.arctan2(cross, dot)))
        mask = turn > min_turn
        # группируем подряд идущие индексы
        idx = np.nonzero(mask)[0]
        if not len(idx):
            continue
        groups, cur = [], [idx[0]]
        for k in idx[1:]:
            if k - cur[-1] <= 3:
                cur.append(k)
            else:
                groups.append(cur)
                cur = [k]
        groups.append(cur)
        if len(groups) > 1 and groups[0][0] == 0 and groups[-1][-1] == n - 1:
            groups[0] = groups.pop() + groups[0]
        for g in groups:
            k = g[int(np.argmax(turn[g]))]
            fill = material(m, q[k])
            if fill > 0.42:  # вогнутый угол или излом внутри массы — не капля
                continue
            hits.append({'contour': ci, 'turn': round(float(turn[k]), 1), 'fill': round(fill, 2),
                         'x': round(float(q[k, 0])), 'y': round(float(q[k, 1]))})
    return hits


LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 13)


def crops(font, items, out, cell=160, zoom=1.0, cols=10):
    rows = (len(items) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, max(1, rows) * (cell + 16)), (17, 17, 17))
    d = ImageDraw.Draw(img)
    cache = {}
    for k, it in enumerate(items):
        name = it['glyph']
        if name not in cache:
            cache[name] = render(font[name])
        m = cache[name]
        cx, cy = it['x'] + 40, ASC - it['y']
        r = int(cell / zoom / 2)
        sub = np.zeros((2 * r, 2 * r), bool)
        y0, x0 = cy - r, cx - r
        ys = slice(max(0, y0), min(m.shape[0], y0 + 2 * r))
        xs = slice(max(0, x0), min(m.shape[1], x0 + 2 * r))
        sub[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = m[ys, xs]
        rgb = np.full(sub.shape + (3,), 17, np.uint8)
        rgb[sub] = (240, 210, 70)
        t = Image.fromarray(rgb).resize((cell - 4, cell - 4), Image.NEAREST)
        px, py = (k % cols) * cell, (k // cols) * (cell + 16)
        img.paste(t, (px + 2, py + 16))
        c = cell / 2
        d.ellipse([px + c - 7, py + 16 + c - 7, px + c + 7, py + 16 + c + 7], outline=(255, 0, 0), width=2)
        d.text((px + 3, py + 2), f"{k} {it['char']} {it['turn']:.0f}°", fill=(220, 220, 220), font=LABEL)
    img.save(out)


if __name__ == '__main__':
    style = sys.argv[1] if len(sys.argv) > 1 else 'Regular'
    font = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    items = []
    for name in sorted(font.keys()):
        g = font[name]
        ch = chr(g.unicodes[0]) if g.unicodes else name.replace('uni', '')
        for h in find(g):
            items.append({'glyph': name, 'char': ch, **h})
    items.sort(key=lambda t: -t['turn'])
    for k, it in enumerate(items):
        it['index'] = k
    (HERE / f'spikes-{style}.json').write_text(json.dumps(items, ensure_ascii=False, indent=1))
    crops(font, items, HERE / f'spikes-{style}.png')
    print(len(items), 'hits in', len({i['glyph'] for i in items}), 'glyphs')
