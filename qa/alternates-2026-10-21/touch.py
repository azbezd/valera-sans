"""Настоящее минимальное расстояние между краями двух букв при текущем кернинге
(по точкам контура, KD-дерево)."""
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from glyphraster import PolyPen  # noqa: E402
from necks import resample  # noqa: E402


def outline_points(glyph, step=3.0):
    pen = PolyPen(steps=16)
    glyph.draw(pen)
    pts = [resample(p, step) for p in pen.polys if len(p) > 2]
    return np.concatenate(pts) if pts else np.zeros((0, 2))


class Touch:
    def __init__(self, font):
        self.font = font
        self.pts, self.tree = {}, {}

    def _p(self, n):
        if n not in self.pts:
            self.pts[n] = outline_points(self.font[n])
            self.tree[n] = cKDTree(self.pts[n]) if len(self.pts[n]) else None
        return self.pts[n], self.tree[n]

    def dist(self, a, b, k, dy=0):
        pa, ta = self._p(a)
        pb, _ = self._p(b)
        if ta is None or not len(pb):
            return np.inf
        shifted = pb + np.array([self.font[a].width + k, dy])
        # быстрый отсев: правый край a и левый край b далеко
        if shifted[:, 0].min() - pa[:, 0].max() > 400:
            return np.inf
        return float(ta.query(shifted, k=1)[0].min())


def clearance_pass(font, names, chars, kern_of, dmin_of, same_script, prefilter=30, skip=None, dmax=55):
    """Пары, где настоящее расстояние между краями меньше dmin: возвращает
    {(a, b): (k_старый, k_новый, d_старый)}. Быстрый отсев по профилям строк."""
    from scipy.ndimage import minimum_filter1d, maximum_filter1d
    sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
    from glyphraster import render
    prof = {}
    for n in names:
        m = render(font[n])
        rows = m.any(1)
        L = np.where(rows, np.argmax(m, 1) - 40, 1e6).astype(float)
        R = np.where(rows, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1) - 40, -1e6).astype(float)
        prof[n] = (minimum_filter1d(L, 61), maximum_filter1d(R, 61))
    LB = np.stack([prof[n][0] for n in names])
    T = Touch(font)
    out = {}
    for a in names:
        ca = chars[a]
        k = np.array([kern_of(a, b) for b in names], float)
        rough = (font[a].width + k[:, None] + LB - prof[a][1][None, :]).min(1)   # грубый горизонтальный зазор ±30 ед.
        for j in np.nonzero(rough < dmax + prefilter + 30)[0]:
            b = names[j]
            cb = chars[b]
            if not same_script(ca, cb) or (skip and skip(a, b)):
                continue
            dmin = dmin_of(ca, cb)
            d = T.dist(a, b, k[j])
            if d >= dmin:
                continue
            kk = k[j]
            while d < dmin and kk - k[j] < 150:
                kk += 5
                d = T.dist(a, b, kk)
            out[(a, b)] = (int(k[j]), int(kk), round(T.dist(a, b, k[j])))
    return out
