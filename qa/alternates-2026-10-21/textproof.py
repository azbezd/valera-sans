"""Проба набора через HarfBuzz (kern + calt вкл/выкл): textproof.py out.png [style]"""
import sys
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from glyphraster import PolyPen  # noqa: E402

TEXTS = [
    'Съешь же ещё этих мягких французских булок, да выпей чаю.',
    'Аааа оооо нннн ееее — разные формы подряд: шшш, ддд, ккк.',
    'Привет! Как дела? Валера рисует картины маслом и маркером.',
    'The quick brown fox jumps over the lazy dog. Hello, world!',
    '№ 12, 2025 год, 35 000 ₽ — 100% & 1 + 1 = 2.',
]
LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 22)


def line(path, text, calt, scale=0.09):
    tt = TTFont(path)
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {'kern': True, 'calt': calt})
    W = int(sum(p.x_advance for p in buf.glyph_positions) * scale) + 40
    H = int(1650 * scale)
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    x = 20 / scale
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = PolyPen(gs, steps=8)
        gs[order[info.codepoint]].draw(pen)
        for poly in pen.polys:
            pts = [((px + x + pos.x_offset) * scale, (1100 - py - pos.y_offset) * scale) for px, py in poly]
            if len(pts) > 2:
                tmp = Image.new('L', im.size, 0)
                ImageDraw.Draw(tmp).polygon(pts, fill=255)
                im = Image.fromarray(np.asarray(im) ^ np.asarray(tmp))
        x += pos.x_advance
    rgb = Image.new('RGB', im.size, (17, 17, 17))
    rgb.paste((242, 210, 74), mask=im)
    return rgb


def main(out, style='Regular'):
    path = ROOT / f'fonts/ttf/ValeraSans-{style}.ttf'
    rows = []
    for t in TEXTS:
        for calt in (False, True):
            r = line(path, t, calt)
            lab = Image.new('RGB', (r.width, 30), (40, 40, 40))
            ImageDraw.Draw(lab).text((10, 3), 'без чередования' if not calt else 'с чередованием (по умолчанию)', fill=(200, 200, 200), font=LABEL)
            rows += [lab, r]
    W = max(r.width for r in rows)
    img = Image.new('RGB', (W, sum(r.height for r in rows)), (17, 17, 17))
    y = 0
    for r in rows:
        img.paste(r, (0, y)); y += r.height
    img.save(out)
    print(out, img.size)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'Regular')
