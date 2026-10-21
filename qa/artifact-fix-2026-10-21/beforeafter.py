"""Лист «до/после»: для каждого изменённого глифа три веса, слева исходник, справа правка."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import ufoLib2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from glyphraster import render  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 18)
STYLES = ['Light', 'Regular', 'Semibold']


def tile(g, h, diff_with=None):
    m = render(g)
    rgb = np.full(m.shape + (3,), 17, np.uint8)
    rgb[m] = (240, 210, 70)
    if diff_with is not None and diff_with.shape == m.shape:
        rgb[diff_with & ~m] = (230, 60, 60)    # убрано
        rgb[m & ~diff_with] = (80, 200, 120)   # добавлено
    rgb[1100, :] = (60, 60, 60)
    t = Image.fromarray(rgb)
    t = t.crop((0, 250, t.width, t.height - 100))
    s = h / t.height
    return t.resize((max(1, int(t.width * s)), h), Image.LANCZOS)


def main(out='before-after.png', h=300):
    names = subprocess.run(['git', 'diff', '--name-only', 'sources'], cwd=ROOT, capture_output=True, text=True).stdout.split()
    glyphs = sorted({Path(n).stem.replace('_', '') for n in names if n.endswith('.glif')})
    old = {s: ufoLib2.Font.open(ROOT / f'.orig/ValeraSans-{s}.ufo') for s in STYLES}
    new = {s: ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{s}.ufo') for s in STYLES}
    rows = []
    for gn in glyphs:
        if gn not in new['Regular']:
            continue
        row = []
        for s in STYLES:
            a, b = old[s][gn], new[s][gn]
            row += [tile(a, h), tile(b, h, diff_with=render(a))]
        rows.append((gn, row))
    W = max(sum(t.width + 6 for t in r) for _, r in rows) + 10
    img = Image.new('RGB', (W, len(rows) * (h + 26)), (45, 45, 45))
    d = ImageDraw.Draw(img)
    for i, (gn, row) in enumerate(rows):
        y = i * (h + 26)
        g = new['Regular'][gn]
        d.text((6, y + 2), f"{chr(g.unicodes[0]) if g.unicodes else ''} {gn}   Light: до | после   Regular: до | после   Semibold: до | после",
               fill=(230, 230, 230), font=LABEL)
        x = 4
        for k, t in enumerate(row):
            img.paste(t, (x, y + 24))
            x += t.width + (14 if k % 2 else 4)
    img.save(HERE / out)
    print(len(rows), 'glyphs ->', out)


if __name__ == '__main__':
    main()
