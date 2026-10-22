"""Пробные TTF с увеличенными цифрами (без пересчёта кернинга): proof_fonts.py OUT_DIR

Для каждого начертания и доли R от высоты прописных подбирает масштаб s и сдвиг d,
переписывает 56 глифов цифр в копии fonts/ttf и печатает проверку: толщина штриха до/после,
расхождение с растровой эрозией, части и полости.
"""
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

sys.path.insert(0, str(Path(__file__).parent))
import scale_digits as SD  # noqa: E402

ROOT = Path(__file__).parents[2]
RATIOS = {'95': 0.95, '100': 1.0}


def top(gs, name):
    p = BoundsPen(gs)
    gs[name].draw(p)
    return p.bounds[3]


def stats(f):
    gs, cm, glyf = f.getGlyphSet(), f.getBestCmap(), f['glyf']
    order = f.getGlyphOrder()
    digits = SD.digit_names(order)
    caps = st.median(top(gs, cm[ord(c)]) for c in SD.CAPS)
    dtop = st.median(top(gs, n) for n in digits)
    widths = {}
    for n in digits:
        c = SD.contours_of(glyf[n], glyf)
        widths[n] = SD.stroke(SD.raster(c, f['hmtx'][n][0]))
    letters = [SD.stroke(SD.raster(SD.contours_of(glyf[cm[ord(c)]], glyf), f['hmtx'][cm[ord(c)]][0])) for c in 'нпиНПИHnu']
    return digits, caps, dtop, widths, st.median(letters)


def rewrite(f, names, s, widths, style, report):
    glyf, hmtx = f['glyf'], f['hmtx']
    tabs = [n for n in names if n.endswith('.tab')]
    new = {}
    for n in names:
        c = SD.contours_of(glyf[n], glyf)
        adv, _ = hmtx[n]
        x0, _, x1, _ = SD.bounds(c)
        d = SD.own_offset(n, s, widths, style)
        t = SD.transform(c, s, d)
        nx0, _, nx1, _ = SD.bounds(t)
        new[n] = (c, t, adv, x0, x1, nx0, nx1, d)
    grow = max((v[6] - v[5]) - (v[4] - v[3]) for k, v in new.items() if k in tabs)
    tab_adv = hmtx[tabs[0]][0] + round(grow)
    for n, (c, t, adv, x0, x1, nx0, nx1, d) in new.items():
        if n in tabs:                        # табличные: общая ширина, знак по центру
            adv2 = tab_adv
            dx = (adv2 - (nx1 - nx0)) / 2 - nx0
        else:                                # пропорциональные: прежние поля
            adv2 = round(nx1 - nx0 + x0 + (adv - x1))
            dx = x0 - nx0
        pts = [(round(x + dx), round(y)) for cc in t for x, y, _ in cc]
        g = glyf[n]
        g.coordinates = GlyphCoordinates(pts)
        g.recalcBounds(glyf)
        hmtx[n] = (adv2, g.xMin)
        mask_after = SD.raster(SD.contours_of(g, glyf), adv2)
        mask_before = SD.raster(c, adv)
        report[n] = {
            'stroke_before': round(SD.stroke(mask_before), 1),
            'stroke_after': round(SD.stroke(mask_after), 1),
            'topology_same': SD.topology(mask_before) == SD.topology(mask_after),
            'erosion_mismatch': round(SD.erode_check(c, s, d, adv), 4) if d > 0 else None,
            'advance': [adv, adv2],
        }


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for style in ('Light', 'Regular', 'Semibold'):
        src = ROOT / f'fonts/ttf/ValeraSans-{style}.ttf'
        digits, caps, dtop, widths, letters = stats(TTFont(src))
        w = st.median(widths.values())
        summary[style] = {'caps': round(caps), 'digits_top': round(dtop), 'digit_stroke': round(w, 1), 'letter_stroke': round(letters, 1)}
        for tag, R in RATIOS.items():
            # s·top − (s − 1)·w/2 = R·caps
            s = (R * caps - w / 2) / (dtop - w / 2)
            d = (s - 1) * w / 2
            f = TTFont(src)
            report = {}
            rewrite(f, digits, s, widths, style, report)
            f.save(out / f'ValeraSans-{style}-{tag}.ttf')
            gs = f.getGlyphSet()
            after_top = st.median(top(gs, n) for n in digits)
            summary[style][tag] = {
                's': round(s, 4), 'd': round(d, 2), 'digits_top_after': round(after_top),
                'zero_fixed': {n: [r['stroke_before'], r['stroke_after']] for n, r in report.items() if r['erosion_mismatch'] is None},
                'stroke_ratio_median': round(st.median(r['stroke_after'] / r['stroke_before'] for r in report.values()), 3),
                'stroke_ratio_range': [round(min(r['stroke_after'] / r['stroke_before'] for r in report.values()), 3),
                                       round(max(r['stroke_after'] / r['stroke_before'] for r in report.values()), 3)],
                'topology_changed': [n for n, r in report.items() if not r['topology_same']],
                'erosion_mismatch_max': max(r['erosion_mismatch'] or 0 for r in report.values()),
                'tab_advance': report[[n for n in digits if n.endswith('.tab')][0]]['advance'],
            }
            (out / f'report-{style}-{tag}.json').write_text(json.dumps(report, indent=1))
        print(style, json.dumps(summary[style], ensure_ascii=False))
    (Path(__file__).parent / 'proof-summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
