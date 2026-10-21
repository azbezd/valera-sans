"""Применяет правки из fixes.json к UFO-мастерам.

Типы правок:
  drip   — капля: берём кандидат из candidates-<Style>.json (замороженный список кандидатов с исходных мастеров) по индексу, расширяем участок
           за шейки на margin единиц и заменяем гладкой кривой;
  span   — произвольный участок a→b (по направлению контура), опционально через via;
  remove — удалить контур (оторванная крошка).
Запуск: apply_fixes.py [--dry] — без --dry пишет в sources/*.ufo.
"""
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2

sys.path.insert(0, str(Path(__file__).parent))
import contour_surgery as cs  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]


def contour_near(glyph, xy):
    best = None
    for ci, c in enumerate(glyph.contours):
        flat = cs.flatten(cs.to_segs(c))
        d = float(np.min(np.hypot(flat[:, 2] - xy[0], flat[:, 3] - xy[1])))
        if best is None or d < best[0]:
            best = (d, ci)
    return best[1]


def drip_span(contour, hit, margin):
    flat = cs.flatten(cs.to_segs(contour))
    total = flat[-1, 4]
    sl, st, sr = (cs.locate_s(flat, hit[k]) for k in ('neckL', 'tip', 'neckR'))
    # neckL должен идти до носика по направлению контура
    if (st - sl) % total > (sr - sl) % total:
        sl, sr = sr, sl
    def xy(s):
        si, t = cs.at_s(flat, s)
        return cs.to_segs(contour)[si].at(t)
    return xy(sl - margin), xy(sr + margin)


def outline(g):
    return [[(p.x, p.y, p.type) for p in c.points] for c in g.contours]


def sync_tab(font, changed, log, style):
    """Табличные цифры — копии базовых со сдвигом по x. Сдвиг берём из исходника,
    где копия обязана совпадать с базой точка в точку."""
    orig = ufoLib2.Font.open(ROOT / f'.orig/ValeraSans-{style}.ufo')
    for name in sorted(changed):
        tab = name + '.tab'
        if tab not in font:
            continue
        base0, tab0 = outline(orig[name]), outline(orig[tab])
        dx = tab0[0][0][0] - base0[0][0][0]
        shifted = [[(x + dx, y, t) for x, y, t in c] for c in base0]
        if shifted != tab0:
            log.append((style, tab, '', 'tab-differs', 'проверить отдельно'))
            continue
        font[tab].clearContours()
        for c in font[name].contours:
            pen = font[tab].getPointPen()
            pen.beginPath()
            for p in c.points:
                pen.addPoint((p.x + dx, p.y), segmentType=p.type, smooth=p.smooth)
            pen.endPath()
        log.append((style, tab, '', 'sync-tab', dx))


def run(dry=False, only=None):
    spec = json.loads((HERE / 'fixes.json').read_text())
    log = []
    for style, fixes in spec.items():
        if only and style != only:
            continue
        path = ROOT / f'sources/ValeraSans-{style}.ufo'
        font = ufoLib2.Font.open(path)
        bumps = {b['index']: b for b in json.loads((HERE / f'candidates-{style}.json').read_text())}
        removals = []
        for fx in fixes:
            if fx['type'] == 'drip':
                hit = bumps[fx['index']]
                g = font[hit['glyph']]
                ci = contour_near(g, hit['tip'])
                a, b = drip_span(g.contours[ci], hit, fx.get('margin', 16))
                pts = cs.replace_span(g.contours[ci], a, b, tension=fx.get('tension', 0.38))
                cs.apply(g.contours[ci], pts)
                log.append((style, hit['glyph'], hit['char'], 'drip', hit['tip']))
            elif fx['type'] == 'span':
                g = font[fx['glyph']]
                ci = fx.get('contour', contour_near(g, fx['a']))
                pts = cs.replace_span(g.contours[ci], fx['a'], fx['b'], via=fx.get('via', ()),
                                      tension=fx.get('tension', 0.38))
                cs.apply(g.contours[ci], pts)
                log.append((style, fx['glyph'], '', 'span', fx['a']))
            elif fx['type'] == 'remove':
                removals.append((fx['glyph'], fx['contour']))
        for name, ci in sorted(removals, key=lambda r: -r[1]):
            del font[name].contours[ci]
            log.append((style, name, '', 'remove', ci))
        sync_tab(font, {r[1] for r in log if r[0] == style}, log, style)
        if not dry:
            font.save(path, overwrite=True)
    for row in log:
        print(*row)
    return log


if __name__ == '__main__':
    run(dry='--dry' in sys.argv, only=next((a for a in sys.argv[1:] if not a.startswith('-')), None))
