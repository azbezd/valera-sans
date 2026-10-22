"""Лист «до/после» по отчёту полировки: каждое исправленное место крупно.
Базовые глифы «до» — из .orig (HEAD), варианты «до» — из векторных заготовок."""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from fontTools.pens.recordingPen import RecordingPen
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from glyphraster import render, ASC  # noqa: E402

LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 16)
R, CELL = 90, 180


class G:
    def __init__(self, value, width):
        self.value, self.width = value, width

    def draw(self, pen):
        RecordingPen.replay(self, pen)


def crop(m, x, y):
    cx, cy = int(x) + 40, ASC - int(y)
    out = np.zeros((2 * R, 2 * R), bool)
    ys = slice(max(0, cy - R), min(m.shape[0], cy + R)); xs = slice(max(0, cx - R), min(m.shape[1], cx + R))
    out[ys.start - cy + R:ys.stop - cy + R, xs.start - cx + R:xs.stop - cx + R] = m[ys, xs]
    return out


def tile(m, ref=None):
    rgb = np.full(m.shape + (3,), 17, np.uint8)
    rgb[m] = (240, 210, 70)
    if ref is not None:
        rgb[ref & ~m] = (220, 50, 50)
        rgb[m & ~ref] = (70, 190, 110)
    return Image.fromarray(rgb).resize((CELL, CELL), Image.LANCZOS)


def main(style, out, limit=400, report=None):
    rep = json.loads(Path(report or ROOT / 'qa/alternates-2026-10-21/polish-report.json').read_text())[style]
    old = ufoLib2.Font.open(ROOT / f'.orig/ValeraSans-{style}.ufo')
    new = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    vec = {}
    for p in (ROOT / 'qa/alternates-2026-10-21/vector' / style).glob('*.json'):
        d = json.loads(p.read_text())
        vec['uni00B0' if d['name'] == 'uni00B0.alt1' else d['name']] = d
    items = []
    for name, spots in sorted(rep.items()):
        for x, y, dev, kind in spots:
            items.append((name, x, y, dev, kind))
    items = items[:limit]
    cols = 6
    rows = (len(items) + cols - 1) // cols
    img = Image.new('RGB', (cols * (2 * CELL + 16), rows * (CELL + 22)), (40, 40, 40))
    d = ImageDraw.Draw(img)
    cache = {}
    for i, (name, x, y, dev, kind) in enumerate(items):
        if name not in cache:
            if name in old:
                before = render(old[name])
            else:
                v = vec[name]
                before = render(G([(op, [tuple(p) for p in a]) for op, a in v['value']], v['advance']))
            cache[name] = (before, render(new[name]))
        b, a = cache[name]
        # варианты после полировки ещё сдвигаются подгонкой полей: место ищем со сдвигом
        dx = 0 if name in old else int(np.nonzero(a.any(0))[0][0] - np.nonzero(b.any(0))[0][0])
        cb, ca = crop(b, x, y), crop(a, x + dx, y)
        px, py = (i % cols) * (2 * CELL + 16), (i // cols) * (CELL + 22)
        g = new[name]
        ch = chr(g.unicodes[0]) if g.unicodes else name
        d.text((px + 4, py + 2), f'{ch} {name} {"капля" if kind == "bump" else "вмятина"} {dev:.0f}', fill=(220, 220, 220), font=LABEL)
        img.paste(tile(cb), (px + 2, py + 20)); img.paste(tile(ca, cb), (px + CELL + 6, py + 20))
    img.save(out)
    print(style, len(items), 'мест', img.size)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], report=sys.argv[3] if len(sys.argv) > 3 else None)
