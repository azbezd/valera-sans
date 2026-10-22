"""Листы пробы увеличенных цифр: proof_sheets.py PROOF_DIR
proof-text.png — набор (HarfBuzz, calt и kern включены): 0.6.0 / 95% / 100% высоты прописных;
proof-site.png — карточка сайта: название 34px, цена 26px;
proof-forms.png — все формы цифр в трёх начертаниях, линии строчных и прописных;
proof-zero.png — основной «0» в Semibold до и после выравнивания штриха."""
import statistics as st
import sys
from pathlib import Path

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/alternates-2026-10-21'))
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
from textproof import line  # noqa: E402
from glyphraster import PolyPen  # noqa: E402
import scale_digits as SD  # noqa: E402

LABEL = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 24)
BG, INK, GREY = (17, 17, 17), (242, 210, 74), (200, 200, 200)
TEXTS = [
    'Раки с лимонами — 3 500 ₽, Форель — 12 800 ₽',
    '№ 12, 2025 год, 35 000 ₽ — 100% & 1 + 1 = 2.',
    'ДОМ 1987, кв. 45, 30 x 20 см, тел. +7 (999) 123-45-67',
    'Hello 2026! The 4th of July, 10:30. АБВ 0123456789 абв',
]


def label(text, width, h=32):
    im = Image.new('RGB', (width, h), (40, 40, 40))
    ImageDraw.Draw(im).text((10, 3), text, fill=GREY, font=LABEL)
    return im


def stack(rows, gap=0):
    W = max(r.width for r in rows)
    img = Image.new('RGB', (W, sum(r.height + gap for r in rows)), BG)
    y = 0
    for r in rows:
        img.paste(r, (0, y)); y += r.height + gap
    return img


def fonts(proof, style):
    return [('0.6.0 (сейчас)', ROOT / f'fonts/ttf/ValeraSans-{style}.ttf'),
            ('цифры ≈ 95% прописных', proof / f'ValeraSans-{style}-95.ttf'),
            ('цифры = прописные', proof / f'ValeraSans-{style}-100.ttf')]


def text_sheet(proof):
    rows = []
    for t in TEXTS:
        for name, path in fonts(proof, 'Regular'):
            r = line(path, t, True, scale=0.08)
            rows += [label(f'Regular · {name}', r.width), r]
        rows.append(Image.new('RGB', (10, 16), BG))
    for style in ('Light', 'Semibold'):
        for name, path in fonts(proof, style)[:2]:
            r = line(path, TEXTS[1], True, scale=0.08)
            rows += [label(f'{style} · {name}', r.width), r]
    return stack(rows)


def site_sheet(proof):
    rows = []
    for name, path in fonts(proof, 'Regular')[:2]:
        title = line(path, 'Раки с лимонами', True, scale=34 / 1000 * 2)
        price = line(path, '3 500 ₽', True, scale=26 / 1000 * 2)
        card = Image.new('RGB', (max(title.width, 820), title.height + price.height), BG)
        card.paste(title, (0, 0)); card.paste(price, (0, title.height - 14))
        rows += [label(f'сайт (×2): название 34px, цена 26px · {name}', card.width), card]
    return stack(rows)


def draw_glyph(img, gs, name, x, base, scale, color):
    pen = PolyPen(gs, steps=10)
    gs[name].draw(pen)
    acc = np.zeros((img.height, img.width), bool)
    for poly in pen.polys:
        tmp = Image.new('1', img.size, 0)
        ImageDraw.Draw(tmp).polygon([(x + px * scale, base - py * scale) for px, py in poly], fill=1)
        acc ^= np.array(tmp)
    layer = Image.new('RGB', img.size, color)
    img.paste(layer, mask=Image.fromarray(acc.astype(np.uint8) * 255))


def forms_row(path, names, scale, refs=('uni0048', 'uni043D')):
    f = TTFont(path)
    gs, cm, hmtx = f.getGlyphSet(), f.getBestCmap(), f['hmtx']
    caps = st.median(BoundsPen_top(gs, cm[ord(c)]) for c in SD.CAPS)
    xh = st.median(BoundsPen_top(gs, cm[ord(c)]) for c in 'xzvwuнпткши')
    W = int(sum(hmtx[n][0] for n in list(refs) + names) * scale) + 80
    img = Image.new('RGB', (W, int(1000 * scale)), BG)
    d = ImageDraw.Draw(img)
    base = int(820 * scale)
    for val, col in ((0, (110, 110, 110)), (xh, (90, 170, 255)), (caps, (120, 220, 120))):
        d.line([(10, base - val * scale), (W - 10, base - val * scale)], fill=col, width=2)
    x = 20
    for ref in refs:                                  # H и н для сравнения
        draw_glyph(img, gs, ref, x, base, scale, GREY); x += hmtx[ref][0] * scale
    x += 40
    for n in names:
        draw_glyph(img, gs, n, x, base, scale, INK); x += hmtx[n][0] * scale
    return img


def forms_sheet(proof):
    rows = []
    order = TTFont(ROOT / 'fonts/ttf/ValeraSans-Regular.ttf').getGlyphOrder()
    names = sorted((n for n in SD.digit_names(order) if not n.endswith('.tab')), key=lambda n: (n.split('.')[0], n))
    halves = [[n for n in names if n[6] in '01234'], [n for n in names if n[6] in '56789']]
    for style in ('Light', 'Regular', 'Semibold'):
        for part in halves:
            for name, path in fonts(proof, style)[:2]:
                img = forms_row(path, part, 0.16)
                rows += [label(f'{style} · {name} · зелёная линия — прописные, синяя — строчные', img.width), img]
        rows.append(Image.new('RGB', (10, 24), BG))
    return stack(rows)


def zero_sheet(proof):
    """Semibold: основной «0» был тоньше остальных нулей (штрих как в Regular)."""
    rows = []
    zeros = ['uni0030', 'uni0030.alt1', 'uni0030.alt2', 'uni0030.alt3']
    for name, path in fonts(proof, 'Semibold')[:2]:
        img = forms_row(path, zeros, 0.3, refs=('uni043E', 'uni041E'))
        rows += [label(f'Semibold · {name} · первый ноль — основной, серые — о и О', img.width), img]
    return stack(rows)


def BoundsPen_top(gs, n):
    p = BoundsPen(gs); gs[n].draw(p); return p.bounds[3]


def main(proof):
    proof = Path(proof)
    for fn, out in ((text_sheet, 'proof-text.png'), (site_sheet, 'proof-site.png'), (forms_sheet, 'proof-forms.png'), (zero_sheet, 'proof-zero.png')):
        img = fn(proof)
        img.save(HERE / out)
        print(out, img.size)


if __name__ == '__main__':
    main(sys.argv[1])
