"""Поиск мусорных «капель»: узких выступов, которые снимает морфологическое открытие.

Для каждого глифа: полуширина штриха по distance transform, открытие диском
радиуса k·полуширина, остаток = глиф − открытие. Компонента остатка считается
подозрительной, если торчит от тела дальше порога (углы терминалов торчат мало).
"""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import render, ASC  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def analyse(glyph, k=0.6):
    m = render(glyph)
    if not m.any():
        return m, None, []
    dt = ndi.distance_transform_edt(m)
    # медиана локальных максимумов ≈ полуширина штриха
    mx = (dt == ndi.maximum_filter(dt, size=5)) & (dt > 3)
    half = float(np.median(dt[mx])) if mx.any() else 10.0
    r = max(3, int(round(k * half)))
    opened = ndi.binary_opening(m, structure=disk(r))
    resid = m & ~opened
    lab, n = ndi.label(resid)
    dist_out = ndi.distance_transform_edt(~opened)
    found = []
    for i in range(1, n + 1):
        comp = lab == i
        area = int(comp.sum())
        stick = float(dist_out[comp].max())
        if area < 30 or stick < 0.55 * r + 4:
            continue
        ys, xs = np.nonzero(comp)
        found.append({
            'area': area, 'stick': round(stick, 1), 'half': round(half, 1),
            'x': int(xs.mean()) - 40, 'y': ASC - int(ys.mean()),
            'bbox': [int(xs.min()) - 40, ASC - int(ys.max()), int(xs.max()) - 40, ASC - int(ys.min())],
        })
    return m, resid, found


def sheet(font, names, out, cols=12, cell=180):
    rows = (len(names) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, rows * (cell + 18)), (17, 17, 17))
    d = ImageDraw.Draw(img)
    for i, (name, hits) in enumerate(names):
        g = font[name]
        m, resid, _ = analyse(g)
        rgb = np.zeros(m.shape + (3,), np.uint8)
        rgb[m] = (240, 210, 70)
        if resid is not None:
            for h in hits:
                x0, y0, x1, y1 = h['bbox']
                sl = (slice(ASC - y1 - 2, ASC - y0 + 3), slice(x0 + 38, x1 + 43))
                sub = resid[sl]
                rgb[sl][sub] = (255, 40, 40)
        t = Image.fromarray(rgb)
        t.thumbnail((cell - 6, cell - 6))
        cx, cy = (i % cols) * cell, (i // cols) * (cell + 18)
        img.paste(t, (cx + 3, cy + 18))
        d.text((cx + 4, cy + 2), f"{name} {len(hits)}", fill=(200, 200, 200))
    img.save(out)


if __name__ == '__main__':
    style = sys.argv[1] if len(sys.argv) > 1 else 'Regular'
    font = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    report = {}
    for name in sorted(font.keys()):
        _, _, hits = analyse(font[name])
        if hits:
            report[name] = hits
    (HERE / f'detect-{style}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    items = sorted(report.items(), key=lambda kv: -max(h['stick'] for h in kv[1]))
    sheet(font, items, HERE / f'detect-{style}.png')
    for name, hits in items:
        u = font[name].unicodes
        ch = chr(u[0]) if u else ''
        print(name, ch, [(h['x'], h['y'], h['area'], h['stick']) for h in hits])
