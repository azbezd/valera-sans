"""Слова при разных поправках для выбранных пар: kernvariants.py out.png 'ал,вл' -20 -40"""
import sys
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from glyphraster import PolyPen  # noqa: E402

LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 26)
WORDS = 'Валера сало малой вла Алла пол нл al плавал'


def draw(path, text, extra, pairs, scale=0.12):
    tt = TTFont(path); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    cm = tt.getBestCmap()
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(font, buf, {'kern': True, 'calt': True})
    infos, poss = buf.glyph_infos, buf.glyph_positions
    W = int(sum(p.x_advance for p in poss) * scale) + 60
    H = int(1650 * scale)
    acc = np.zeros((H, W), bool)
    x = 20 / scale
    for i, (info, pos) in enumerate(zip(infos, poss)):
        pen = PolyPen(gs, steps=8)
        gs[order[info.codepoint]].draw(pen)
        for poly in pen.polys:
            pts = [((px + x + pos.x_offset) * scale, (1100 - py - pos.y_offset) * scale) for px, py in poly]
            if len(pts) > 2:
                tmp = Image.new('1', (W, H), 0)
                ImageDraw.Draw(tmp).polygon(pts, fill=1)
                acc ^= np.array(tmp)
        x += pos.x_advance
        if i + 1 < len(text) and text[i:i + 2] in pairs:
            x += extra
    rgb = Image.new('RGB', (W, H), (17, 17, 17))
    rgb.paste((242, 210, 74), mask=Image.fromarray((acc * 255).astype(np.uint8)))
    return rgb


def main(out, pairs, *extras, style='Regular'):
    path = ROOT / f'fonts/ttf/ValeraSans-{style}.ttf'
    pairs = set(pairs.split(','))
    rows = []
    for e in [0] + [int(v) for v in extras]:
        lab = Image.new('RGB', (1, 40), (40, 40, 40))
        r = draw(path, WORDS, e, pairs)
        lab = Image.new('RGB', (r.width, 40), (40, 40, 40))
        ImageDraw.Draw(lab).text((10, 5), 'как сейчас' if e == 0 else f'пары {", ".join(sorted(pairs))} теснее на {-e} ед.', fill=(220, 220, 220), font=LABEL)
        rows += [lab, r]
    W = max(r.width for r in rows)
    img = Image.new('RGB', (W, sum(r.height for r in rows)), (17, 17, 17)); y = 0
    for r in rows:
        img.paste(r, (0, y)); y += r.height
    img.save(out); print(out, img.size)


if __name__ == '__main__':
    main(*sys.argv[1:])
