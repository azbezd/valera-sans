"""Растеризация глифов UFO в numpy-маски (even-odd по контурам) для поиска артефактов."""
import numpy as np
from PIL import Image, ImageDraw
from fontTools.pens.basePen import BasePen

ASC, DESC = 1100, -550


class PolyPen(BasePen):
    def __init__(self, glyphset=None, steps=12):
        super().__init__(glyphset)
        self.polys, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                             mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                             mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if self.cur:
            self.polys.append(self.cur)
        self.cur = []

    _endPath = _closePath


def render(glyph, scale=1.0, pad=40):
    """Возвращает (маска bool, x0) где маска в координатах (y вниз), 1 px = 1/scale единиц."""
    pen = PolyPen()
    glyph.draw(pen)
    w = int((glyph.width + 2 * pad) * scale)
    h = int((ASC - DESC) * scale)
    acc = np.zeros((h, w), bool)
    for poly in pen.polys:
        im = Image.new('1', (w, h), 0)
        pts = [((x + pad) * scale, (ASC - y) * scale) for x, y in poly]
        if len(pts) > 2:
            ImageDraw.Draw(im).polygon(pts, fill=1)
        acc ^= np.array(im)
    return acc
