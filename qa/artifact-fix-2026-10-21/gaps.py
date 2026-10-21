"""Минимальный зазор между соседними глифами в реальной раскладке (HarfBuzz, kern+calt),
до и после правки. Сравниваются строки, где участвует изменённый глиф."""
import json
import sys
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import PolyPen  # noqa: E402

ROOT = Path(__file__).parents[2]


class Shaper:
    def __init__(self, path):
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.hbf = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.cache = {}

    def polys(self, name):
        if name not in self.cache:
            pen = PolyPen(self.gs, steps=10)
            self.gs[name].draw(pen)
            self.cache[name] = pen.polys
        return self.cache[name]

    def masks(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbf, buf, {'kern': True, 'calt': True})
        x = 0
        out = []
        order = self.tt.getGlyphOrder()
        W = sum(p.x_advance for p in buf.glyph_positions) + 400
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = order[info.codepoint]
            im = Image.new('1', (W, 1700), 0)
            acc = np.zeros((1700, W), bool)
            for poly in self.polys(name):
                tmp = Image.new('1', (W, 1700), 0)
                ImageDraw.Draw(tmp).polygon([(px + x + pos.x_offset + 200, 1150 - py) for px, py in poly], fill=1)
                acc ^= np.array(tmp)
            out.append((name, acc))
            x += pos.x_advance
        return out


def min_gap(ms):
    gaps = []
    for (n1, a), (n2, b) in zip(ms, ms[1:]):
        if not a.any() or not b.any():
            continue
        ys, xs = np.nonzero(a | b)
        sl = (slice(max(0, ys.min() - 5), ys.max() + 6), slice(max(0, xs.min() - 5), xs.max() + 6))
        d = ndi.distance_transform_edt(~a[sl])
        gaps.append(float(d[b[sl]].min()))
    return gaps


if __name__ == '__main__':
    style = sys.argv[1]
    texts = json.loads(sys.argv[2])
    old = Shaper(ROOT / f'.orig/fonts/{style}.ttf')
    new = Shaper(ROOT / f'fonts/ttf/ValeraSans-{style}.ttf')
    worse = []
    for t in texts:
        g0, g1 = min_gap(old.masks(t)), min_gap(new.masks(t))
        for k, (a, b) in enumerate(zip(g0, g1)):
            if b < a - 0.5:
                worse.append((t, k, round(a, 1), round(b, 1)))
    worse.sort(key=lambda w: w[3])
    print(style, 'строк', len(texts), 'ухудшилось', len(worse))
    for w in worse[:25]:
        print('  ', w)
