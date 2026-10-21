"""Кандидаты в капли: контур минус его сглаженная копия (гаусс по длине дуги).
Узкий выступ наружу даёт пик отклонения. Список для ручного просмотра."""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import PolyPen, render, ASC  # noqa: E402
from necks import resample  # noqa: E402
from drips import crops  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def find(glyph, sigma=14.0, min_dev=4.5, max_width=60):
    m = render(glyph)
    pen = PolyPen(steps=24)
    glyph.draw(pen)
    hits = []
    for ci, poly in enumerate(pen.polys):
        q = resample(poly, 1.0)
        n = len(q)
        if n < 60:
            continue
        qs = np.stack([ndi.gaussian_filter1d(q[:, i], sigma, mode='wrap') for i in (0, 1)], 1)
        t = np.roll(qs, -1, 0) - np.roll(qs, 1, 0)
        t /= np.maximum(np.hypot(*t.T), 1e-9)[:, None]
        nrm = np.stack([t[:, 1], -t[:, 0]], 1)
        # нормаль наружу: точка чуть сдвинутая по нормали должна быть вне массы
        probe = qs + nrm * 6
        xs = np.clip(np.round(probe[:, 0]).astype(int) + 40, 0, m.shape[1] - 1)
        ys = np.clip(ASC - np.round(probe[:, 1]).astype(int), 0, m.shape[0] - 1)
        flip = np.where(m[ys, xs], -1.0, 1.0)
        flip = np.where(ndi.uniform_filter1d(flip, 31, mode='wrap') >= 0, 1.0, -1.0)
        dev = ((q - qs) * nrm).sum(1) * flip
        peaks = np.nonzero((dev > min_dev) & (dev == ndi.maximum_filter1d(dev, 41, mode='wrap')))[0]
        for k in peaks:
            # ширина выступа: где отклонение падает ниже 1
            lo = k
            while dev[lo % n] > 1 and k - lo < 200: lo -= 1
            hi = k
            while dev[hi % n] > 1 and hi - k < 200: hi += 1
            if hi - lo > max_width:
                continue
            hits.append({'contour': ci, 'tip': [round(float(v)) for v in q[k]],
                         'neckL': [round(float(v)) for v in q[lo % n]], 'neckR': [round(float(v)) for v in q[hi % n]],
                         'arc': int(hi - lo), 'dev': round(float(dev[k]), 1)})
    return hits


if __name__ == '__main__':
    style = sys.argv[1] if len(sys.argv) > 1 else 'Regular'
    font = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    items = []
    for name in sorted(font.keys()):
        if name.endswith('.tab') or name == '.notdef':
            continue
        g = font[name]
        ch = chr(g.unicodes[0]) if g.unicodes else name
        for h in find(g):
            items.append({'glyph': name, 'char': ch, **h})
    items.sort(key=lambda it: -it['dev'])
    for k, it in enumerate(items):
        it['index'] = k
    (HERE / f'bumps-{style}.json').write_text(json.dumps(items, ensure_ascii=False, indent=1))
    crops(font, items, HERE / f'bumps-{style}.png')
    print(style, len(items), 'hits in', len({i['glyph'] for i in items}), 'glyphs')
