"""Упрощение трассированных контуров: квадратичный сплайн → кубики (qu2cu) → квадратичный
(cu2qu) с допуском. Принимается, только если отклонение по плотной выборке ≤ MAX_DEV ед.
и число частей/полостей глифа не изменилось."""
import math
import sys
from pathlib import Path

import numpy as np
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.basePen import BasePen
from scipy.spatial import cKDTree

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/contour-cleanup-2026-10-21'))

MAX_DEV = 1.5
TOL = 0.7


class Sampler(BasePen):
    def __init__(self):
        super().__init__(None)
        self.pts = []

    def _moveTo(self, p):
        self.pts.append(p)

    def _lineTo(self, p):
        a = np.array(self._getCurrentPoint()); b = np.array(p)
        n = max(2, int(np.linalg.norm(b - a) / 0.5))
        self.pts.extend(a + (b - a) * t for t in np.linspace(0, 1, n))

    def _qCurveToOne(self, c, p):
        a = np.array(self._getCurrentPoint()); c = np.array(c); b = np.array(p)
        n = max(3, int((np.linalg.norm(c - a) + np.linalg.norm(b - c)) / 0.5))
        for t in np.linspace(0, 1, n):
            self.pts.append((1 - t) ** 2 * a + 2 * t * (1 - t) * c + t * t * b)

    def _curveToOne(self, c1, c2, p):
        a = np.array(self._getCurrentPoint()); c1 = np.array(c1); c2 = np.array(c2); b = np.array(p)
        n = max(4, int((np.linalg.norm(c1 - a) + np.linalg.norm(c2 - c1) + np.linalg.norm(b - c2)) / 0.5))
        for t in np.linspace(0, 1, n):
            mt = 1 - t
            self.pts.append(mt ** 3 * a + 3 * mt * mt * t * c1 + 3 * mt * t * t * c2 + t ** 3 * b)


def sample(drawable):
    s = Sampler()
    drawable.draw(s) if hasattr(drawable, 'draw') else drawable.replay(s)
    return np.array(s.pts, float)


def deviation(a, b):
    x, y = sample(a), sample(b)
    return max(cKDTree(y).query(x)[0].max(), cKDTree(x).query(y)[0].max())


def npoints(glyph):
    return sum(len(c.points) for c in glyph.contours)


def simplify(glyph, topology):
    before = npoints(glyph)
    topo = topology(glyph)
    rec = RecordingPen()
    glyph.draw(Qu2CuPen(Cu2QuPen(rec, TOL, reverse_direction=False), TOL, all_cubic=True))
    rec.value = [(op, [tuple(int(round(c)) for c in p) for p in args]) for op, args in rec.value]
    dev = deviation(glyph, rec)
    saved = [[(p.x, p.y, p.type, p.smooth) for p in c.points] for c in glyph.contours]
    if dev > MAX_DEV:
        return before, before, dev, False
    glyph.clearContours()
    rec.replay(glyph.getPen())
    if npoints(glyph) >= before or topology(glyph) != topo:
        from ufoLib2.objects import Contour, Point
        glyph.clearContours()
        for pts in saved:
            glyph.contours.append(Contour(points=[Point(x, y, type=t, smooth=s) for x, y, t, s in pts]))
        return before, before, dev, False
    return before, npoints(glyph), dev, True
