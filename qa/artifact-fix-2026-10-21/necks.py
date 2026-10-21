"""Поиск капель по контуру: участок длиной arc, концы которого близки (chord),
а середина уходит далеко от хорды. Знак площади отличает выступ от выемки."""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import PolyPen, render, ASC  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def resample(poly, step=2.0):
    p = np.array(poly + [poly[0]], float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1], step)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def signed_area(q):
    x, y = q[:, 0], q[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def find(glyph, step=2.0, max_arc=140, max_chord=34, ratio=0.42, min_depth=7):
    pen = PolyPen(steps=16)
    glyph.draw(pen)
    hits = []
    for ci, poly in enumerate(pen.polys):
        q = resample(poly, step)
        n = len(q)
        if n < 10:
            continue
        orient = np.sign(signed_area(q))
        cand = []
        for i in range(n):
            for L in range(int(8 / step), int(max_arc / step)):
                j = (i + L) % n
                chord = np.hypot(*(q[j] - q[i]))
                arc = L * step
                if chord > max_chord or chord > ratio * arc:
                    continue
                idx = [(i + k) % n for k in range(L + 1)]
                seg = q[idx]
                d = q[j] - q[i]
                nrm = np.hypot(*d) or 1.0
                dev = np.abs((seg[:, 0] - q[i, 0]) * d[1] - (seg[:, 1] - q[i, 1]) * d[0]) / nrm
                depth = float(dev.max())
                if depth < min_depth:
                    continue
                kind = 'bump' if np.sign(signed_area(seg)) == orient else 'notch'
                cand.append((depth * (1 - chord / arc), i, j, L, chord, depth, kind))
                break
        # подавление пересекающихся: берём лучшие непересекающиеся участки
        cand.sort(reverse=True)
        used = np.zeros(n, bool)
        for score, i, j, L, chord, depth, kind in cand:
            idx = [(i + k) % n for k in range(L + 1)]
            if used[idx].any():
                continue
            used[idx] = True
            seg = q[idx]
            hits.append({'contour': ci, 'kind': kind, 'arc': L * step, 'chord': round(chord, 1),
                         'depth': round(depth, 1), 'score': round(score, 1),
                         'x': round(float(seg[:, 0].mean())), 'y': round(float(seg[:, 1].mean())),
                         'bbox': [round(float(v)) for v in (*seg.min(0), *seg.max(0))]})
    return hits


def crops(font, items, out, cell=150, zoom=2.5):
    cols = 10
    rows = (len(items) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, max(1, rows) * (cell + 16)), (17, 17, 17))
    d = ImageDraw.Draw(img)
    cache = {}
    for k, (name, ch, h) in enumerate(items):
        if name not in cache:
            cache[name] = render(font[name], scale=1.0)
        m = cache[name]
        cx, cy = h['x'] + 40, ASC - h['y']
        r = int(cell / zoom / 2)
        sub = np.zeros((2 * r, 2 * r), bool)
        y0, x0 = cy - r, cx - r
        ys = slice(max(0, y0), min(m.shape[0], y0 + 2 * r))
        xs = slice(max(0, x0), min(m.shape[1], x0 + 2 * r))
        sub[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] = m[ys, xs]
        rgb = np.zeros(sub.shape + (3,), np.uint8)
        rgb[sub] = (240, 210, 70) if h['kind'] == 'bump' else (120, 200, 255)
        t = Image.fromarray(rgb).resize((cell - 4, cell - 4), Image.NEAREST)
        px, py = (k % cols) * cell, (k // cols) * (cell + 16)
        img.paste(t, (px + 2, py + 16))
        d.ellipse([px + cell / 2 - 4, py + 16 + cell / 2 - 4, px + cell / 2 + 4, py + 16 + cell / 2 + 4], outline=(255, 0, 0))
        d.text((px + 3, py + 2), f"{k} {ch} {name[3:]} s{h['score']}", fill=(220, 220, 220))
    img.save(out)


if __name__ == '__main__':
    style = sys.argv[1] if len(sys.argv) > 1 else 'Regular'
    font = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    items = []
    for name in sorted(font.keys()):
        g = font[name]
        ch = chr(g.unicodes[0]) if g.unicodes else name
        for h in find(g):
            items.append((name, ch, h))
    items.sort(key=lambda t: -t[2]['score'])
    (HERE / f'necks-{style}.json').write_text(json.dumps(
        [{'glyph': n, 'char': c, 'index': k, **h} for k, (n, c, h) in enumerate(items)], ensure_ascii=False, indent=1))
    crops(font, items, HERE / f'necks-{style}.png')
    print(len(items), 'hits')
    for k, (n, c, h) in enumerate(items):
        print(k, c, n, h['kind'], h['arc'], h['chord'], h['depth'], h['score'], (h['x'], h['y']))
