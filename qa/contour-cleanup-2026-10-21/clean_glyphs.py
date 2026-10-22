"""Чистка контуров: капли, шипы, рваные края — во всех глифах трёх мастеров.

Глиф растрируется (1 px = 1 ед.), затем:
  * край сглаживается гауссом по знаковому расстоянию (рваные края, мелкие заусенцы);
  * морфологическое открытие диском r = 0.5 × полуширины штриха срезает выступы уже
    ~половины штриха (капли, шипы); полости открытие не закрывает;
  * разница с исходником делится на пятна; если есть пятно больше порога — глиф
    перерисовывается (potrace → квадратичные кривые) с прежними advance и положением,
    иначе остаётся нетронутым.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import ufoLib2
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.areaPen import AreaPen
from fontTools.svgLib.path import parse_path
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from glyphraster import render, ASC  # noqa: E402

STROKE = {'Light': 55, 'Regular': 66, 'Semibold': 90}
SKIP = {'.notdef', 'space', 'space.narrow'}
SIGMA = 3.0          # ед., сглаживание края
SPOT = 60            # ед.², пятно разницы, ради которого глиф перерисовывается


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def cleaned(m, stroke):
    pad = 40
    m = np.pad(m, pad)
    sdf = ndi.distance_transform_edt(m) - ndi.distance_transform_edt(~m)
    s = ndi.gaussian_filter(sdf, SIGMA) > 0
    r = int(round(0.5 * stroke / 2))
    o = ndi.binary_opening(s, structure=disk(r))
    # мелкие самостоятельные части (точки ё/й/i/!/?) открытие не должно стирать
    lab, n = ndi.label(s)
    keep = np.zeros_like(s)
    for i in range(1, n + 1):
        part = lab == i
        if not (o & part).any():
            keep |= part
    o |= keep
    o = ndi.gaussian_filter((ndi.distance_transform_edt(o) - ndi.distance_transform_edt(~o)), SIGMA * 0.6) > 0
    return o[pad:-pad, pad:-pad]


def defects(m, c):
    d = m ^ c
    lab, n = ndi.label(d)
    if not n:
        return []
    areas = ndi.sum(d, lab, range(1, n + 1))
    out = []
    for i, a in enumerate(areas, 1):
        if a >= SPOT:
            ys, xs = np.nonzero(lab == i)
            out.append((int(a), int(xs.mean()) - 40, ASC - int(ys.mean()), bool(m[ys[0], xs[0]])))
    return out


def trace(m):
    h, w = m.shape
    with tempfile.TemporaryDirectory() as td:
        pbm = Path(td) / 'g.pbm'
        Image.fromarray(((~m) * 255).astype(np.uint8)).convert('1').save(pbm)
        out = subprocess.run(['potrace', '-b', 'svg', '-u', '4', '--flat', '-t', '4', '-a', '1.0', '-O', '0.3',
                              '-o', '-', str(pbm)], capture_output=True, text=True, check=True).stdout
    tx, ty, sx, sy = map(float, re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)', out).groups())
    rec = RecordingPen()
    tp = TransformPen(rec, (sx, 0, 0, sy, tx, ty))
    for d in re.findall(r'<path d="([^"]+)"', out):
        parse_path(d, tp)
    # пиксель (x, y_svg) → единицы: x - 40, ASC - y
    units = RecordingPen()
    rec.replay(TransformPen(units, (1, 0, 0, -1, -40, ASC)))
    q = RecordingPen()
    units.replay(Cu2QuPen(q, 0.8, reverse_direction=False))
    ap = AreaPen()
    q.replay(ap)
    if ap.value > 0:
        r = RecordingPen()
        q.replay(ReverseContourPen(r))
        q = r
    q.value = [(op, [tuple(int(round(c)) for c in p) for p in args]) for op, args in q.value]
    return q


def clean_font(font, style, names=None, dry=False):
    stroke = STROKE[style]
    changed = {}
    for g in font:
        if g.name in SKIP or not g.contours or (names and g.name not in names):
            continue
        m = render(g)
        c = cleaned(m, stroke)
        spots = defects(m, c)
        if not spots:
            continue
        changed[g.name] = spots
        if dry:
            continue
        q = trace(c)
        g.clearContours()
        q.replay(g.getPen())
    return changed


if __name__ == '__main__':
    report = {}
    for style in ['Light', 'Regular', 'Semibold']:
        path = ROOT / f'sources/ValeraSans-{style}.ufo'
        f = ufoLib2.Font.open(path)
        ch = clean_font(f, style, dry='--dry' in sys.argv)
        report[style] = ch
        if '--dry' not in sys.argv:
            f.save(path, overwrite=True)
        print(style, 'глифов с дефектами', len(ch), 'пятен', sum(len(v) for v in ch.values()))
    (HERE / 'clean-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
