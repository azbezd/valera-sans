"""Полировка контуров: каждый узкий выступ (капля, шип, острый носик, обрубленный угол)
заменяется гладкой кривой с касательными соседей; остальные точки не меняются.

Вмятины детектор тоже находит, но они не правятся: при просмотре это оказались
внутренние углы изгибов и стыков штриха — так рисует круглый маркер (см. README). Вмятина правится, только если она «прокусывает» штрих: толщина под ней
меньше обычной. Во внутренних углах на стыках штрихов под дном — масса стыка, толщина
больше, такие места остаются: так рисует круглый маркер.

Выступ ищется как отклонение контура от его сглаженной копии (bumps.find): пик
наружу ≥ MIN_DEV ед., шириной по контуру ≤ MAX_WIDTH ед. Круглые концы штрихов
(радиус ≈ полуширина пера, дуга ~100 ед.) шире порога и не трогаются.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
import contour_surgery as cs  # noqa: E402
from glyphraster import PolyPen, render, ASC  # noqa: E402
from necks import resample  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

SKIP = {'.notdef', 'space', 'space.narrow'}
MIN_DEV = 3.5          # выступ наружу, ед.
MAX_WIDTH = 55         # уже конца штриха даже в Light (55): концы не укорачиваются
DENT = (3.5, 8.0)      # вмятина внутрь: мелкие да, глубокие стыки штрихов — нет
ARM_TURN = 60.0        # град.: плечи вокруг вмятины расходятся сильнее — точно стык штрихов
THIN = 1.1             # вмятина «прокусывает» штрих: толщина под ней < THIN × обычной
DENT_WIDTH = 45
MARGIN = 10


def find(glyph, sigma=14.0):
    """Выступы (dev > MIN_DEV) и неглубокие вмятины относительно сглаженного контура."""
    m = render(glyph)
    dtm = ndi.distance_transform_edt(m)
    ridge = (dtm == ndi.maximum_filter(dtm, size=5)) & (dtm > 1)
    stroke = 2 * float(np.median(dtm[ridge])) if ridge.any() else 60.0
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
        probe = qs + nrm * 6
        xs = np.clip(np.round(probe[:, 0]).astype(int) + 40, 0, m.shape[1] - 1)
        ys = np.clip(ASC - np.round(probe[:, 1]).astype(int), 0, m.shape[0] - 1)
        flip = np.where(m[ys, xs], -1.0, 1.0)
        flip = np.where(ndi.uniform_filter1d(flip, 31, mode='wrap') >= 0, 1.0, -1.0)
        dev = ((q - qs) * nrm).sum(1) * flip
        for sign, lo_dev, hi_dev, width in ((1, MIN_DEV, 1e9, MAX_WIDTH), (-1, DENT[0], DENT[1], DENT_WIDTH)):
            d = dev * sign
            peaks = np.nonzero((d > lo_dev) & (d < hi_dev) & (d == ndi.maximum_filter1d(d, 41, mode='wrap')))[0]
            for k in peaks:
                lo = k
                while d[lo % n] > 1 and k - lo < 200:
                    lo -= 1
                hi = k
                while d[hi % n] > 1 and hi - k < 200:
                    hi += 1
                if hi - lo > width:
                    continue
                if sign < 0:
                    # направление сглаженного контура до и после ямки (плечи по 25 ед.)
                    a0, a1 = qs[(lo - 25) % n], qs[lo % n]
                    b0, b1 = qs[hi % n], qs[(hi + 25) % n]
                    va, vb = a1 - a0, b1 - b0
                    ang = abs(np.degrees(np.arctan2(va[0] * vb[1] - va[1] * vb[0], (va * vb).sum())))
                    if ang > ARM_TURN:
                        continue
                    # толщина под ямкой: от дна внутрь по нормали до выхода из чернил;
                    # в развилке уходим в массу стыка и толщина больше обычного штриха
                    inward = -nrm[k] * flip[k]
                    depth_in = 0
                    while depth_in < 400:
                        px_, py_ = q[k] + inward * (depth_in + 2)
                        xi, yi = int(round(px_)) + 40, ASC - int(round(py_))
                        if not (0 <= yi < m.shape[0] and 0 <= xi < m.shape[1]) or not m[yi, xi]:
                            break
                        depth_in += 1
                    if depth_in > THIN * stroke:
                        continue
                hits.append({'contour': ci, 'kind': 'bump' if sign > 0 else 'dent',
                             'tip': [round(float(v)) for v in q[k]],
                             'neckL': [round(float(v)) for v in q[lo % n]], 'neckR': [round(float(v)) for v in q[hi % n]],
                             'arc': int(hi - lo), 'dev': round(float(d[k]), 1)})
    return hits


def contour_near(glyph, xy):
    best = None
    for ci, c in enumerate(glyph.contours):
        flat = cs.flatten(cs.to_segs(c))
        d = float(np.min(np.hypot(flat[:, 2] - xy[0], flat[:, 3] - xy[1])))
        if best is None or d < best[0]:
            best = (d, ci)
    return best


def fix_bump(glyph, hit):
    d, ci = contour_near(glyph, hit['tip'])
    if d > 3:
        return False
    c = glyph.contours[ci]
    segs = cs.to_segs(c)
    flat = cs.flatten(segs)
    total = flat[-1, 4]
    sl, st, sr = (cs.locate_s(flat, hit[k]) for k in ('neckL', 'tip', 'neckR'))
    if (st - sl) % total > (sr - sl) % total:
        sl, sr = sr, sl
    span = (sr - sl) % total + 2 * MARGIN
    if span > total / 3:
        return False

    def xy(s):
        si, t = cs.at_s(flat, s)
        return segs[si].at(t)
    try:
        pts = cs.replace_span(c, xy(sl - MARGIN), xy(sr + MARGIN), tension=0.38)
    except Exception:
        return False
    cs.apply(c, pts)
    return True


def topology(glyph):
    m = render(glyph)
    parts = ndi.label(m, structure=np.ones((3, 3)))[1]
    holes = ndi.label(ndi.binary_fill_holes(m) & ~m)[1]
    return parts, holes


def polish(glyph, passes=3):
    """Возвращает список исправленных мест (x, y, отклонение, вид). Если правка изменила
    число кусков или полостей глифа, все правки этого глифа откатываются."""
    if glyph.name in SKIP or not glyph.contours:
        return []
    before = topology(glyph)
    saved = [[(p.x, p.y, p.type, p.smooth) for p in c.points] for c in glyph.contours]
    fixed = []
    for _ in range(passes):
        # только выступы: вмятины на поверку оказались внутренними углами изгибов штриха
        hits = [h for h in find(glyph) if h['kind'] == 'bump']
        if not hits:
            break
        n0 = len(fixed)
        for h in sorted(hits, key=lambda h: -h['dev']):
            if fix_bump(glyph, h):
                fixed.append((h['tip'][0], h['tip'][1], h['dev'], h['kind']))
        if len(fixed) == n0:
            break
    if fixed and topology(glyph) != before:
        from ufoLib2.objects import Point
        for c, pts in zip(glyph.contours, saved):
            c.points[:] = [Point(x, y, type=t, smooth=sm) for x, y, t, sm in pts]
        return []
    return fixed
