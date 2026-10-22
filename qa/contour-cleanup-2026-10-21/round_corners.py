"""Скругление острых выпуклых углов: обрубленные концы штрихов и шипы на изгибах.

Маркер круглый, поэтому острый выпуклый угол на контуре — след вырезания из скана или
трассировки. Угол находится по повороту касательной на коротком участке; выпуклость —
по доле заливки вокруг точки. Участок ±L вокруг угла заменяется гладкой кривой с
касательными соседей (contour_surgery.replace_span), остальные точки не меняются.
L = доля толщины штриха, чтобы два угла обрубка (через ширину штриха) не пересекались.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
import contour_surgery as cs  # noqa: E402
from glyphraster import render, ASC  # noqa: E402
from necks import resample  # noqa: E402
from drips import fill_map, sample  # noqa: E402

SKIP = {'.notdef', 'space', 'space.narrow'}


def corners(glyph, min_turn=58.0, win=6, tip_fill=0.42):
    """Список (номер контура, x, y, поворот) острых выпуклых углов."""
    m = render(glyph)
    fm = fill_map(m)
    out = []
    for ci, c in enumerate(glyph.contours):
        flat = cs.flatten(cs.to_segs(c))
        q = resample([tuple(p) for p in flat[:-1, 2:4]], 1.0)
        n = len(q)
        if n < 6 * win:
            continue
        a, b = q[(np.arange(n) - win) % n], q[(np.arange(n) + win) % n]
        v1, v2 = q - a, b - q
        turn = np.abs(np.degrees(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1))))
        f = sample(fm, q)
        cand = np.nonzero((turn > min_turn) & (f < tip_fill))[0]
        taken = np.zeros(n, bool)
        for k in sorted(cand, key=lambda k: -turn[k]):
            if taken[k]:
                continue
            taken[[(k + d) % n for d in range(-12, 13)]] = True
            out.append((ci, float(q[k, 0]), float(q[k, 1]), float(turn[k])))
    return out


def round_glyph(glyph, half_len, passes=2):
    """Скругляет найденные углы (два прохода: новые углы после правок тоже ловятся)."""
    done = 0
    for _ in range(passes):
        found = corners(glyph)
        if not found:
            break
        for ci, x, y, _t in found:
            c = glyph.contours[ci]
            segs = cs.to_segs(c)
            flat = cs.flatten(segs)
            total = flat[-1, 4]
            if np.min(np.hypot(flat[:, 2] - x, flat[:, 3] - y)) > 3:
                continue                    # участок уже переписан соседней правкой
            s = cs.locate_s(flat, (x, y))
            L = min(half_len, total / 6)

            def xy(sv):
                si, t = cs.at_s(flat, sv)
                return segs[si].at(t)
            try:
                pts = cs.replace_span(c, xy(s - L), xy(s + L), tension=0.42)
            except Exception:
                continue
            cs.apply(c, pts)
            done += 1
    return done
