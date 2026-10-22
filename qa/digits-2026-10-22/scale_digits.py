"""Цифры крупнее при прежней толщине штриха.

Глиф масштабируется от базовой линии в s раз, затем контур сдвигается внутрь на (s − 1)·w/2,
где w — медианная толщина штриха цифр в этом начертании: рёбра управляющего многоугольника
переносятся параллельно, узлы — в точку пересечения перенесённых рёбер (ограничение MITER).
Точки и их число не меняются, поэтому характер линии сохраняется.

Проверка: растровая эрозия масштабированного глифа на ту же величину (cv2.distanceTransform)
должна совпасть с векторным результатом; число частей и полостей не меняется.
"""
import numpy as np
import cv2
from PIL import Image, ImageDraw

DIGITS = {f'uni003{d}' for d in range(10)}
MITER = 3.0          # предел сдвига узла в долях δ (острые концы штрихов)
CAPS = 'HEFIKLMNTZНПТШЕИКМ'


def digit_names(order):
    return [n for n in order if n.split('.')[0] in DIGITS]


def tab_names(order):
    return [n for n in digit_names(order) if n.endswith('.tab')]


# --- контуры TrueType: список [x, y, on] ---

def contours_of(glyph, glyf):
    coords, ends, flags = glyph.getCoordinates(glyf)
    out, s = [], 0
    for e in ends:
        out.append([[coords[i][0], coords[i][1], flags[i] & 1] for i in range(s, e + 1)])
        s = e + 1
    return out


def flatten(contour, steps=16):
    """Квадратичный B-сплайн TrueType → многоугольник."""
    pts = [(x, y, on) for x, y, on in contour]
    full = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        full.append(p)
        if not p[2] and not q[2]:
            full.append(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, 1))
    k = next((i for i, p in enumerate(full) if p[2]), None)
    full = full[k:] + full[:k]
    poly, i, n = [full[0][:2]], 0, len(full)
    while i < n:
        p0, p1 = full[i], full[(i + 1) % n]
        if p1[2]:
            poly.append(p1[:2]); i += 1
        else:
            p2 = full[(i + 2) % n]
            for t in np.linspace(0, 1, steps + 1)[1:]:
                mt = 1 - t
                poly.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                             mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))
            i += 2
    return poly


def signed_area(contour):
    p = np.array([c[:2] for c in contour], float)
    return 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])


def offset(contour, d):
    """Сдвиг на d вправо по ходу контура (в TrueType заливка справа → внутрь)."""
    P = np.array([c[:2] for c in contour], float)
    n = len(P)

    def unit(i, step):
        for k in range(1, n):
            v = (P[(i + step * k) % n] - P[i]) * step
            L = np.hypot(*v)
            if L > 1e-6:
                return v / L
        return np.array([1.0, 0.0])

    out = []
    for i in range(n):
        a, b = unit(i, -1), unit(i, 1)
        na, nb = np.array([a[1], -a[0]]), np.array([b[1], -b[0]])
        s = na + nb
        if np.hypot(*s) < 1e-6:          # разворот на 180°: конец штриха, отступаем назад
            m = -a * MITER
        else:
            m = s / (1 + na @ nb)
            L = np.hypot(*m)
            if L > MITER:
                m *= MITER / L
        x, y = P[i] + d * m
        out.append([x, y, contour[i][2]])
    return out


def transform(contours, s, d):
    """Масштаб от (0, 0) и сдвиг внутрь на d. Направление заливки — по самому большому контуру."""
    side = -np.sign(signed_area(max(contours, key=lambda c: abs(signed_area(c)))))
    return [offset([[x * s, y * s, on] for x, y, on in c], side * d) for c in contours]


def bounds(contours):
    p = np.array([q for c in contours for q in flatten(c)])
    return p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()


# --- растр: 1 px = 1 ед. ---

ASC, PAD = 1100, 60


def raster(contours, width):
    """Маска глифа; холст охватывает и ширину, и чернила за её пределами."""
    polys = [flatten(c) for c in contours]
    xs = [x for p in polys for x, _ in p] or [0]
    x0 = PAD - min(0, min(xs))
    w = int(max(width, max(xs)) + x0 + PAD)
    acc = np.zeros((1700, w), np.uint8)
    for p in polys:
        im = Image.new('L', (w, 1700), 0)
        ImageDraw.Draw(im).polygon([(x + x0, ASC - y) for x, y in p], fill=1)
        acc ^= np.array(im)
    return acc


def stroke(mask):
    """Медианная толщина штриха: 2 × расстояние до края на гребне карты расстояний
    (локальные максимумы ≈ средняя линия штриха), без кончиков (меньше 40% максимума)."""
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    ridge = (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8)) - 0.25) & (dt > 1)
    v = dt[ridge]
    v = v[v >= 0.4 * v.max()]
    return float(np.median(v) * 2)


def topology(mask):
    parts = cv2.connectedComponents(mask, connectivity=8)[0] - 1
    holes = cv2.connectedComponents(1 - mask, connectivity=4)[0] - 2
    return parts, holes


def erode_check(contours, s, d, width):
    """Доля несовпадения векторного результата с растровой эрозией масштабированного глифа."""
    scaled = [[[x * s, y * s, on] for x, y, on in c] for c in contours]
    ref = raster(scaled, width * s)
    dt = cv2.distanceTransform(ref, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    ref_er = (dt > d).astype(np.uint8)
    vec = raster(transform(contours, s, d), width * s)
    return float((ref_er ^ vec).sum() / max(ref_er.sum(), 1))


# --- UFO-мастер (integrate.py) ---

RATIO = 0.95         # высота цифр — доля медианной высоты прописных (выбор автора 22.10.2026)


def ufo_contours(glyph):
    return [[[p.x, p.y, int(p.type is not None)] for p in c.points] for c in glyph.contours]


def set_ufo_contours(glyph, contours, dx=0):
    for c, new in zip(glyph.contours, contours):
        for p, (x, y, _) in zip(c.points, new):
            p.x, p.y = int(round(x + dx)), int(round(y))


def own_offset(name, s, widths, style):
    """Сдвиг внутрь, сохраняющий толщину штриха самого глифа. Основной «0» в Semibold
    (с 0.5.1 штрих как в Regular, ~62 ед. против ~88) доводится до медианы остальных нулей."""
    w = widths[name]
    if style == 'Semibold' and name in ('uni0030', 'uni0030.tab'):
        target = float(np.median([v for k, v in widths.items() if k.startswith('uni0030.alt')]))
        return (s * w - target) / 2
    return (s - 1) * w / 2


def scale_ufo(font, style, ratio=RATIO):
    """Все формы цифр (основные, .tab, .altN) → ratio высоты прописных при прежнем штрихе.
    Пропорциональные сохраняют поля; табличные получают общую новую ширину, знак по центру."""
    names = digit_names(list(font.glyphOrder))
    tabs = [n for n in names if n.endswith('.tab')]
    cmap = {chr(g.unicodes[0]): g.name for g in font if g.unicodes}
    caps = float(np.median([bounds(ufo_contours(font[cmap[c]]))[3] for c in CAPS]))
    top = float(np.median([bounds(ufo_contours(font[n]))[3] for n in names]))
    widths = {n: stroke(raster(ufo_contours(font[n]), font[n].width)) for n in names}
    w = float(np.median(list(widths.values())))
    s = (ratio * caps - w / 2) / (top - w / 2)        # s·top − (s − 1)·w/2 = ratio·caps
    new = {}
    for n in names:
        c = ufo_contours(font[n])
        x0, _, x1, _ = bounds(c)
        d = own_offset(n, s, widths, style)
        t = transform(c, s, d)
        nx0, _, nx1, _ = bounds(t)
        new[n] = (c, t, x0, x1, nx0, nx1, d)
    grow = max((v[5] - v[4]) - (v[3] - v[2]) for k, v in new.items() if k in tabs)
    tab_adv = font[tabs[0]].width + int(round(grow))
    report = {'s': round(s, 4), 'caps': round(caps), 'top_before': round(top), 'stroke': round(w, 1),
              'tab_advance': [font[tabs[0]].width, tab_adv], 'glyphs': {}}
    for n, (c, t, x0, x1, nx0, nx1, d) in new.items():
        g = font[n]
        before = (g.width, topology(raster(c, g.width)), widths[n])
        if n in tabs:
            dx = (tab_adv - (nx1 - nx0)) / 2 - nx0
            g.width = tab_adv
        else:
            dx = x0 - nx0
            g.width = int(round(nx1 - nx0 + x0 + (g.width - x1)))
        set_ufo_contours(g, t, dx)
        after = ufo_contours(g)
        mask = raster(after, g.width)
        report['glyphs'][n] = {'offset': round(d, 2), 'advance': [before[0], g.width],
                               'stroke': [round(before[2], 1), round(stroke(mask), 1)],
                               'topology_same': before[1] == topology(mask)}
        assert report['glyphs'][n]['topology_same'], (style, n)
    report['top_after'] = round(float(np.median([bounds(ufo_contours(font[n]))[3] for n in names])))
    return names, report
