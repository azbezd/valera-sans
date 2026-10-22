"""Проба выравнивания контуров по готовому TTF: proof.py STYLE
smooth-big-STYLE.png — крупно «было | стало»; smooth-text-STYLE.png — набор (позиции из
нынешнего шрифта, контуры сглаженные); smooth-stats-STYLE.json — сдвиг, штрих, площадь, топология."""
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/digits-2026-10-22'))
sys.path.insert(0, str(HERE))
import scale_digits as SD  # noqa: E402
import smooth as SM  # noqa: E402

LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 26)
BIG = [['uni0412.alt1', 'uni0440', 'uni0440.alt1', 'uni044B.alt1', 'uni0412.alt2'],
       ['uni0431.alt3', 'uni043E.alt2', 'uni0440.alt2', 'uni0430', 'uni0072', 'uni0067']]
TEXTS = ['Съешь же ещё этих мягких французских булок, да выпей чаю.',
         'Валера рисует картины маслом и маркером. Вверху ровно.',
         'The quick brown fox jumps over the lazy dog. Hello, world!']


def tt_contours(gl):
    coords, ends, flags = gl.coordinates, gl.endPtsOfContours, gl.flags
    out, s = [], 0
    for e in ends:
        out.append([[coords[i][0], coords[i][1], flags[i] & 1] for i in range(s, e + 1)])
        s = e + 1
    return out


def smoothed(f, names):
    g = f['glyf']
    old, new, stats = {}, {}, {}
    for n in names:
        if g[n].numberOfContours <= 0:
            continue
        c = SD.contours_of(g[n], g)
        adv = f['hmtx'][n][0]
        mb = SD.raster(c, adv)
        topo = SD.topology(mb)

        def contours_of(rec):
            pen = TTGlyphPen(None)
            rec.replay(pen)
            return tt_contours(pen.glyph())
        rec, moved, frozen = SM.smooth_glyph(c, SD.flatten, contours_of)
        step = len(frozen) if rec else -1
        nc = contours_of(rec) if rec else c
        ma = SD.raster(nc, adv)
        old[n], new[n] = c, nc
        stats[n] = {'moved': round(moved, 1), 'step': step, 'points': [sum(map(len, c)), sum(map(len, nc))],
                    'stroke': [round(SD.stroke(mb), 1), round(SD.stroke(ma), 1)],
                    'area': round(float(ma.sum() / mb.sum()), 4),
                    'topology_same': SD.topology(mb) == SD.topology(ma)}
    return old, new, stats


def draw(img, contours, x, base, scale, color=(255, 255, 255)):
    acc = np.zeros((img.height, img.width), bool)
    for c in contours:
        tmp = Image.new('1', img.size, 0)
        ImageDraw.Draw(tmp).polygon([(x + px * scale, base - py * scale) for px, py in SD.flatten(c, 16)], fill=1)
        acc ^= np.array(tmp)
    img.paste(Image.new('RGB', img.size, color), mask=Image.fromarray(acc.astype(np.uint8) * 255))


def big_sheet(f, old, new):
    rows, scale = [], 0.5
    for names in BIG:
        for label, src in (('было', old), ('стало', new)):
            W = int(sum(f['hmtx'][n][0] for n in names) * scale) + 60
            img = Image.new('RGB', (W, int(1450 * scale)), (51, 51, 51))
            base = int(900 * scale)
            d = ImageDraw.Draw(img)
            for yy in (0, -250):
                d.line([(0, base - yy * scale), (W, base - yy * scale)], fill=(40, 130, 220), width=2)
            x = 30
            for n in names:
                draw(img, src[n], x, base, scale)
                x += f['hmtx'][n][0] * scale
            lab = Image.new('RGB', (W, 36), (30, 30, 30))
            ImageDraw.Draw(lab).text((10, 4), label + ': ' + ' '.join(n.replace('uni', '') for n in names), fill=(220, 220, 220), font=LABEL)
            rows += [lab, img]
    return rows


def text_sheet(path, f, old, new):
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    order = f.getGlyphOrder()
    rows, scale = [], 0.09
    for t in TEXTS:
        buf = hb.Buffer()
        buf.add_str(t)
        buf.guess_segment_properties()
        hb.shape(font, buf, {'kern': True, 'calt': True})
        W = int(sum(p.x_advance for p in buf.glyph_positions) * scale) + 40
        for label, src in (('было', old), ('стало', new)):
            img = Image.new('RGB', (W, int(1650 * scale)), (17, 17, 17))
            x = 20
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
                n = order[info.codepoint]
                if n in src:
                    draw(img, src[n], x + pos.x_offset * scale, int(1100 * scale) - pos.y_offset * scale, scale, (242, 210, 74))
                x += pos.x_advance * scale
            lab = Image.new('RGB', (W, 30), (40, 40, 40))
            ImageDraw.Draw(lab).text((10, 2), label, fill=(200, 200, 200), font=LABEL)
            rows += [lab, img]
    return rows


def stack(rows):
    W = max(r.width for r in rows)
    out = Image.new('RGB', (W, sum(r.height for r in rows)), (17, 17, 17))
    y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    return out


def main(style='Regular'):
    path = ROOT / f'fonts/ttf/ValeraSans-{style}.ttf'
    f = TTFont(path)
    names = [n for n in f.getGlyphOrder() if f['glyf'][n].numberOfContours > 0]
    old, new, stats = smoothed(f, names)
    (HERE / f'smooth-stats-{style}.json').write_text(json.dumps(stats, indent=0))
    stack(big_sheet(f, old, new)).save(HERE / f'smooth-big-{style}.png')
    stack(text_sheet(path, f, old, new)).save(HERE / f'smooth-text-{style}.png')
    r = [v['stroke'][1] / v['stroke'][0] for v in stats.values()]
    print(style, 'глифов', len(stats), '| сдвиг медиана', st.median(v['moved'] for v in stats.values()), 'макс', max(v['moved'] for v in stats.values()),
          '| штрих после/до медиана', round(st.median(r), 3), 'мин', round(min(r), 3), 'макс', round(max(r), 3),
          '| площадь мин', min(v['area'] for v in stats.values()), 'макс', max(v['area'] for v in stats.values()),
          '| топология изменилась', [n for n, v in stats.items() if not v['topology_same']],
          '| с замороженными местами', [n for n, v in stats.items() if v['step'] > 0], '| без сглаживания', [n for n, v in stats.items() if v['step'] < 0],
          '| точек', sum(v['points'][0] for v in stats.values()), '→', sum(v['points'][1] for v in stats.values()))


if __name__ == '__main__':
    main(*sys.argv[1:])
