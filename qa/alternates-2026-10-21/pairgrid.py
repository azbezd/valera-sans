"""Пары форм: площадь пустоты между буквами (средний зазор с ограничением глубины в
полосе x-высоты) при текущем кернинге + рисунок. pairgrid.py Style 'ал' out.png"""
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
sys.path.insert(0, str(ROOT / 'scripts'))
from glyphraster import render, ASC  # noqa: E402
from alternates_model import Kerning, ROT  # noqa: E402

LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 18)
DEPTH = 160      # глубже этого пустота не считается (открытые формы)


def profile(m, side):
    rows = m.any(1)
    if side == 'right':
        x = m.shape[1] - 1 - np.argmax(m[:, ::-1], 1) - 40
    else:
        x = np.argmax(m, 1) - 40
    return np.where(rows, x, np.nan)


def area_gap(f, a, b, k, top, bottom=0):
    ma, mb = render(f[a]), render(f[b])
    ra, lb = profile(ma, 'right'), profile(mb, 'left')
    ys = ASC - np.arange(ma.shape[0])
    band = (ys >= bottom) & (ys <= top)
    g = f[a].width + k + lb - ra
    g = np.where(np.isnan(g), DEPTH, np.minimum(g, DEPTH))
    return float(g[band].mean()), float(np.nanmin(np.where(band, f[a].width + k + lb - ra, np.nan)))


def forms(name):
    return ROT['forms'].get(name, [name])


def main(style, pair, out, top=560):
    f = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
    K = Kerning(style)
    cmap = {chr(u): g.name for g in f for u in g.unicodes}
    A, B = forms(cmap[pair[0]]), forms(cmap[pair[1]])
    rows = []
    for a in A:
        row = []
        for b in B:
            k = K(a, b)
            mean, mn = area_gap(f, a, b, k, top)
            ma, mb = render(f[a]), render(f[b])
            x = f[a].width + k
            W = max(ma.shape[1], x + mb.shape[1]) + 10
            c = np.zeros((ma.shape[0], W), bool)
            c[:, :ma.shape[1]] |= ma
            c[:, x:x + mb.shape[1]] |= mb
            im = Image.fromarray(((~c) * 255).astype(np.uint8)).crop((0, 350, W, 1250)).convert('RGB')
            im = im.resize((int(im.width * 0.2), int(im.height * 0.2)))
            d = ImageDraw.Draw(im)
            d.text((3, 2), f'{k:+d} пуст.{mean:.0f}', fill=(200, 0, 0), font=LABEL)
            row.append(im)
            print(a, b, 'кернинг', k, 'средняя пустота', round(mean), 'мин', round(mn))
        rows.append(row)
    W = max(sum(i.width + 8 for i in r) for r in rows)
    H = max(i.height for r in rows for i in r)
    img = Image.new('RGB', (W, len(rows) * (H + 8)), (200, 200, 200))
    for ri, r in enumerate(rows):
        x = 0
        for i in r:
            img.paste(i, (x, ri * (H + 8))); x += i.width + 8
    img.save(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
