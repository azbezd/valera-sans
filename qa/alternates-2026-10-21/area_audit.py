"""Пустота между буквами по площади: средний зазор (с ограничением глубины) в полосе
от базовой линии до x-высоты (строчные) или высоты прописных; сравнение с типичным
для группы пар. Для пар букв одной письменности; формы — базовые."""
import sys
from pathlib import Path

import numpy as np
import ufoLib2

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
sys.path.insert(0, str(ROOT / 'scripts'))
from glyphraster import render, ASC  # noqa: E402
from alternates_model import Kerning  # noqa: E402

DEPTH = 160
LAT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
CYR = set('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя')


def profiles(font, names):
    P = {}
    for n in names:
        m = render(font[n])
        rows = m.any(1)
        L = np.where(rows, np.argmax(m, 1) - 40, np.nan)
        R = np.where(rows, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1) - 40, np.nan)
        P[n] = (L.astype(float), R.astype(float), font[n].width)
    return P


def area(P, a, b, k, top):
    ys = ASC - np.arange(len(P[a][0]))
    band = (ys >= 0) & (ys <= top)
    g = P[a][2] + k + P[b][0] - P[a][1]
    g = np.where(np.isnan(g), DEPTH, np.minimum(g, DEPTH))[band]
    half = len(g) // 2
    return float(g.mean()), float(g[:half].mean()), float(g[half:].mean())   # всё, верх, низ


def main(style='Regular'):
    f = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    K = Kerning(style)
    cmap = {chr(u): g.name for g in f for u in g.unicodes}
    letters = [c for c in cmap if c in LAT or c in CYR]
    P = profiles(f, [cmap[c] for c in letters])
    rows = []
    for a in letters:
        for b in letters:
            if (a in LAT) != (b in LAT):
                continue
            case = ('U' if a.isupper() else 'l') + ('U' if b.isupper() else 'l')
            top = 700 if 'U' in case else 560
            m, up, lo = area(P, cmap[a], cmap[b], K(cmap[a], cmap[b]), top)
            rows.append((a + b, case, m, up, lo))
    import collections
    med = {c: np.median([r[2] for r in rows if r[1] == c]) for c in ['UU', 'Ul', 'lU', 'll']}
    print('типичная пустота (медиана):', {k: round(v) for k, v in med.items()})
    loose = [(p, c, m - med[c], up, lo) for p, c, m, up, lo in rows if m - med[c] > 8]
    loose.sort(key=lambda r: -r[2])
    print('пар рыхлее типичного на >8 ед.:', len(loose), 'из', len(rows))
    print(' из них «пустота сверху» (верх рыхлее низа на 30+):', sum(1 for r in loose if r[3] - r[4] > 30),
          '| «пустота снизу»:', sum(1 for r in loose if r[4] - r[3] > 30))
    print(' самые рыхлые:', [(p, round(d)) for p, c, d, up, lo in loose[:40]])
    for p in ['ал', 'ял', 'ол', 'ел', 'ад', 'ол', 'Ал', 'ла', 'лл', 'уа', 'ту', 'Та', 'Го', 'АЛ']:
        r = [x for x in rows if x[0] == p]
        if r: print(p, 'отклонение', round(r[0][2] - med[r[0][1]]), 'верх', round(r[0][3]), 'низ', round(r[0][4]))


if __name__ == '__main__':
    main(*sys.argv[1:])
