"""Локальная правка квадратичного контура UFO без перетрассировки.

Контур разбирается на квадратичные/линейные сегменты (с неявными on-curve между
подряд идущими off-curve). Участок между двумя позициями по длине дуги заменяется
гладкой кривой: кубический Эрмит (или сплайн через заданные точки) с касательными
обрезанных соседей, затем cu2qu → квадратичные сегменты. Всё вне участка остаётся
теми же точками; неявные on-curve снова опускаются при записи.
"""
import math

import numpy as np
from fontTools.cu2qu import curve_to_quadratic
from ufoLib2.objects import Point

MAX_ERR = 0.35


class Seg:
    __slots__ = ('p0', 'c', 'p1', 'implied', 'smooth')

    def __init__(self, p0, c, p1, implied=False, smooth=False):
        self.p0, self.c, self.p1 = p0, c, p1
        self.implied = implied  # конечная точка была неявной (середина двух off-curve)
        self.smooth = smooth

    def at(self, t):
        if self.c is None:
            return tuple(a + (b - a) * t for a, b in zip(self.p0, self.p1))
        mt = 1 - t
        return tuple(mt * mt * a + 2 * mt * t * c + t * t * b for a, c, b in zip(self.p0, self.c, self.p1))

    def split(self, t):
        m = self.at(t)
        if self.c is None:
            return Seg(self.p0, None, m), Seg(m, None, self.p1, self.implied, self.smooth)
        c0 = tuple(a + (c - a) * t for a, c in zip(self.p0, self.c))
        c1 = tuple(c + (b - c) * t for c, b in zip(self.c, self.p1))
        return Seg(self.p0, c0, m), Seg(m, c1, self.p1, self.implied, self.smooth)

    def tan_end(self):
        a = self.c if self.c is not None else self.p0
        return unit(np.subtract(self.p1, a))

    def tan_start(self):
        b = self.c if self.c is not None else self.p1
        return unit(np.subtract(b, self.p0))


def unit(v):
    n = math.hypot(*v)
    return np.asarray(v, float) / (n or 1.0)


def to_segs(contour):
    pts = list(contour.points)
    on = [i for i, p in enumerate(pts) if p.type is not None]
    if not on:
        raise ValueError('contour without on-curve points')
    pts = pts[on[0]:] + pts[:on[0]]
    segs = []
    i, n = 0, len(pts)
    start = pts[0]
    while i < n:
        j = i + 1
        offs = []
        while pts[j % n].type is None:
            offs.append(pts[j % n])
            j += 1
        end = pts[j % n]
        p0 = (start.x, start.y)
        if not offs:
            segs.append(Seg(p0, None, (end.x, end.y), smooth=end.smooth))
        else:
            for k, c in enumerate(offs):
                if k < len(offs) - 1:
                    nx = offs[k + 1]
                    mid = ((c.x + nx.x) / 2, (c.y + nx.y) / 2)
                    segs.append(Seg(p0, (c.x, c.y), mid, implied=True, smooth=True))
                    p0 = mid
                else:
                    segs.append(Seg(p0, (c.x, c.y), (end.x, end.y), smooth=end.smooth))
        start = end
        i = j
    return segs


def flatten(segs, steps=40):
    """Возвращает массив (seg, t, x, y, s)."""
    rows = []
    s = 0.0
    prev = None
    for si, sg in enumerate(segs):
        for k in range(steps):
            t = k / steps
            p = sg.at(t)
            if prev is not None:
                s += math.hypot(p[0] - prev[0], p[1] - prev[1])
            rows.append((si, t, p[0], p[1], s))
            prev = p
    last = segs[-1].p1
    s += math.hypot(last[0] - prev[0], last[1] - prev[1])
    rows.append((len(segs) - 1, 1.0, last[0], last[1], s))
    return np.array(rows)


def locate_s(flat, xy):
    d = np.hypot(flat[:, 2] - xy[0], flat[:, 3] - xy[1])
    return float(flat[int(np.argmin(d)), 4])


def at_s(flat, s):
    total = flat[-1, 4]
    s %= total
    k = int(np.searchsorted(flat[:, 4], s))
    k = min(max(k, 1), len(flat) - 1)
    a, b = flat[k - 1], flat[k]
    if b[0] != a[0]:
        return int(b[0]), 0.0 if b[1] == 0 else float(b[1])
    f = (s - a[4]) / max(b[4] - a[4], 1e-9)
    return int(a[0]), float(a[1] + (b[1] - a[1]) * f)


def seg_len(sg):
    pts = [sg.at(k / 16) for k in range(17)]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def snap(segs, i, t, tol=4.0):
    """Если точка разреза ближе tol к концу сегмента — режем по существующей точке."""
    L = seg_len(segs[i])
    if t * L < tol:
        return i, 0.0
    if (1 - t) * L < tol:
        return i, 1.0
    return i, t


def rotate(segs, k):
    return segs[k:] + segs[:k]


def hermite_through(a, ta, b, tb, via=(), tension=0.38):
    """Кубические кривые A→via…→B, касательные в A и B заданы; Catmull-Rom внутри."""
    knots = [np.asarray(a, float)] + [np.asarray(v, float) for v in via] + [np.asarray(b, float)]
    tans = []
    for i, p in enumerate(knots):
        if i == 0:
            tans.append(ta)
        elif i == len(knots) - 1:
            tans.append(tb)
        else:
            tans.append(unit(knots[i + 1] - knots[i - 1]))
    cubics = []
    for i in range(len(knots) - 1):
        p0, p3 = knots[i], knots[i + 1]
        h = np.hypot(*(p3 - p0)) * tension
        cubics.append([tuple(p0), tuple(p0 + tans[i] * h), tuple(p3 - tans[i + 1] * h), tuple(p3)])
    return cubics


def replace_span(contour, a_xy, b_xy, via=(), tension=0.38):
    """Заменяет участок контура от точки, ближайшей к a_xy, до ближайшей к b_xy
    (по направлению контура) гладкой кривой. Возвращает новый список Point."""
    segs = to_segs(contour)
    flat = flatten(segs)
    total = flat[-1, 4]
    sa, sb = locate_s(flat, a_xy), locate_s(flat, b_xy)
    if (sb - sa) % total > total / 2:
        raise ValueError('участок длиннее половины контура — проверь порядок a/b')
    # поворачиваем, чтобы участок не пересекал начало контура
    if sb < sa:
        mid_si, _ = at_s(flat, (sb + (sa - sb) / 2))
        segs = rotate(segs, mid_si)
        flat = flatten(segs)
        sa, sb = locate_s(flat, a_xy), locate_s(flat, b_xy)
    ia, ta = at_s(flat, sa)
    ib, tb = at_s(flat, sb)
    ia, ta = snap(segs, ia, ta)
    ib, tb = snap(segs, ib, tb)
    left, _ = segs[ia].split(ta) if ta > 1e-6 else (None, None)
    _, right = segs[ib].split(tb) if tb < 1 - 1e-6 else (None, None)
    before = segs[:ia] + ([left] if left else [])
    after = ([right] if right else []) + segs[ib + 1:]
    A = before[-1].p1 if before else segs[ia].p0
    B = after[0].p0 if after else segs[ib].p1
    tA = before[-1].tan_end() if before else segs[ia].tan_start()
    tB = after[0].tan_start() if after else segs[ib].tan_end()
    if before:
        before[-1].implied = False
        before[-1].smooth = True
    bridge = []
    for cub in hermite_through(A, tA, B, tB, via, tension):
        q = curve_to_quadratic(cub, MAX_ERR)
        p0 = q[0]
        offs = q[1:-1]
        for k, c in enumerate(offs):
            if k < len(offs) - 1:
                mid = ((c[0] + offs[k + 1][0]) / 2, (c[1] + offs[k + 1][1]) / 2)
                bridge.append(Seg(p0, c, mid, implied=True, smooth=True))
                p0 = mid
            else:
                bridge.append(Seg(p0, c, q[-1], smooth=True))
    new = before + bridge + after
    return from_segs(new)


def from_segs(segs):
    pts = []
    n = len(segs)
    for i, sg in enumerate(segs):
        nxt = segs[(i + 1) % n]
        if sg.c is not None:
            pts.append(Point(round(sg.c[0]), round(sg.c[1])))
        # неявную on-curve опускаем, только если с обеих сторон кривые
        omit = sg.implied and sg.c is not None and nxt.c is not None
        if not omit:
            typ = 'line' if sg.c is None else 'qcurve'
            pts.append(Point(round(sg.p1[0]), round(sg.p1[1]), type=typ, smooth=bool(sg.smooth and typ == 'qcurve')))
    # убрать дубли подряд
    out = []
    for p in pts:
        if out and out[-1].x == p.x and out[-1].y == p.y and (out[-1].type and p.type):
            continue
        out.append(p)
    # первая on-curve в начало, как в исходниках
    k = next(i for i, p in enumerate(out) if p.type)
    out = out[k:] + out[:k]
    if out[0].type == 'qcurve' and out[-1].type is not None:
        out[0].type = 'line'
    return out


def apply(contour, new_points):
    contour.points[:] = new_points
