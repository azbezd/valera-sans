"""Выравнивание бугристого края штриха без смены формы буквы.

Контур равномерно передискретизируется (шаг STEP ед.), углы (стыки, острые концы)
закрепляются, участки между ними пропускаются через фильтр низких частот: «двойной гаусс»
2·G(x) − G(G(x)), который гасит короткие волны и почти не сжимает крупные дуги.
Сила фильтра своя в каждой точке: σ = RADIUS_SHARE × местный радиус кривизны (по сильно
сглаженной копии), в пределах SIGMA_MIN…SIGMA_MAX. На длинных пологих штрихах (ножки,
чашки) волны снимаются сильно, на тугих дугах (концы штрихов, точки) форма сохраняется.
Сдвиг ограничен MAX_MOVE ед. Новый контур собирается квадратичным сплайном по сглаженным
точкам и ужимается qu2cu → cu2qu с допуском.

Мера бугристости — 90-й процентиль сдвига точек края при таком сглаживании (без зон у углов).
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d

STEP = 2.0          # ед. между точками передискретизации
SIGMA = 12.0        # ед. по длине контура (постоянная сила, для сравнения)
SIGMA_MIN = 6.0     # ед.: на самых тугих дугах
SIGMA_MAX = 40.0    # ед.: на прямых и пологих участках
RADIUS_SHARE = 0.6  # σ = доля местного радиуса кривизны
TREND_SIGMA = 40.0  # ед.: копия для оценки радиуса кривизны
CORNER_SPAN = 12.0  # ед.: окно для угла поворота
CORNER_TURN = 55.0  # градусов: острее — угол, не сглаживается
CORNER_KEEP = 10.0  # ед. вокруг угла не входят в меру бугристости
MAX_MOVE = 8.0      # ед.: дальше точку края не двигаем
SMALL = 500.0       # ед. периметра внешнего контура: точки, запятые, кавычки — не штрихи, не сглаживаем


def resample(poly, step=STEP):
    p = np.asarray(poly, float)
    if np.allclose(p[0], p[-1]):
        p = p[:-1]
    q = np.vstack([p, p[:1]])
    seg = np.hypot(*np.diff(q, axis=0).T)
    keep = seg > 1e-9
    q = np.vstack([q[:-1][keep], q[:1]])
    seg = np.hypot(*np.diff(q, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    L = s[-1]
    n = max(8, int(round(L / step)))
    t = np.linspace(0, L, n, endpoint=False)
    return np.column_stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])]), L / n


def turning(P, k):
    a = P - np.roll(P, k, 0)
    b = np.roll(P, -k, 0) - P
    ang = np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(1))
    return np.degrees(np.abs(ang))


def corners(P, h):
    k = max(2, int(round(CORNER_SPAN / h)))
    t = turning(P, k)
    idx = [i for i in range(len(P)) if t[i] >= CORNER_TURN and t[i] == max(t[(i + j) % len(P)] for j in range(-k, k + 1))]
    out = []
    for i in idx:                       # одно место — один угол
        if not out or i - out[-1] > k:
            out.append(i)
    if len(out) > 1 and out[0] + len(P) - out[-1] <= k:
        out.pop()
    return out


def lowpass(x, sig):
    g = gaussian_filter1d(x, sig, axis=0, mode='nearest')
    return 2 * g - gaussian_filter1d(g, sig, axis=0, mode='nearest')


def vgauss(x, sig):
    """Гаусс с переменной σ (в отсчётах) для каждой точки; x уже с запасом по краям."""
    n = len(x)
    out = np.empty_like(x)
    for i in range(n):
        s = sig[i]
        r = int(3 * s) + 1
        j = np.arange(max(0, i - r), min(n, i + r + 1))
        w = np.exp(-0.5 * ((j - i) / s) ** 2)
        out[i] = (w[:, None] * x[j]).sum(0) / w.sum()
    return out


def radius(P, h):
    """Местный радиус кривизны по сильно сглаженной (замкнутой) копии, ед."""
    sig = TREND_SIGMA / h
    pad = min(len(P), int(4 * sig) + 1)
    ext = np.vstack([P[-pad:], P, P[:pad]])
    T = gaussian_filter1d(ext, sig, axis=0, mode='wrap')[pad:pad + len(P)]
    d1 = (np.roll(T, -1, 0) - np.roll(T, 1, 0)) / 2
    d2 = np.roll(T, -1, 0) - 2 * T + np.roll(T, 1, 0)
    k = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.hypot(*d1.T) ** 3, 1e-9)
    return np.minimum(1e4, 1 / np.maximum(k, 1e-9))    # кривизна от параметризации не зависит


def local_sigma(P, h, sigma=None):
    if sigma is not None:
        return np.full(len(P), sigma / h)
    R = radius(P, h)
    s = np.clip(RADIUS_SHARE * R, SIGMA_MIN, SIGMA_MAX)
    return gaussian_filter1d(s, 8 / h, mode='wrap') / h


def vlowpass(x, sig):
    g = vgauss(x, sig)
    return 2 * g - vgauss(g, sig)


def smooth_closed(P, h, sigma=None):
    """Сглаживание с закреплёнными углами; sigma=None — адаптивная сила.
    Возвращает (точки, индексы углов)."""
    n = len(P)
    sg = local_sigma(P, h, sigma)
    cs = corners(P, h)
    if not cs:
        pad = min(n, int(4 * sg.max()) + 1)
        ext = np.vstack([P[-pad:], P, P[:pad]])
        se = np.concatenate([sg[-pad:], sg, sg[:pad]])
        return vlowpass(ext, se)[pad:pad + n], cs
    out = P.copy()
    for a, b in zip(cs, cs[1:] + [cs[0] + n]):
        idx = np.arange(a, b + 1) % n
        seg = P[idx]
        if len(seg) < 5:
            continue
        # нечётное отражение относительно концов: концы на месте, прямые остаются прямыми
        ss = sg[idx]
        pad = min(int(4 * ss.max()) + 1, len(seg) - 1)
        left = 2 * seg[0] - seg[1:pad + 1][::-1]
        right = 2 * seg[-1] - seg[-pad - 1:-1][::-1]
        ext = np.vstack([left, seg, right])
        se = np.concatenate([ss[1:pad + 1][::-1], ss, ss[-pad - 1:-1][::-1]])
        sm = vlowpass(ext, se)[pad:pad + len(seg)]
        sm[0], sm[-1] = seg[0], seg[-1]
        out[idx[1:-1]] = sm[1:-1]
    return out, cs


FREEZE = 30.0       # ед.: вокруг места, где менялась топология, край не двигается (до 2× — плавно)


def clamp(P, S, limit=None, frozen=()):
    limit = MAX_MOVE if limit is None else limit
    d = S - P
    L = np.hypot(*d.T)
    lim = np.full(len(P), float(limit))
    if len(frozen):
        F = np.asarray(frozen, float)
        dist = np.sqrt(((P[:, None, :] - F[None, :, :]) ** 2).sum(-1)).min(1)
        lim *= np.clip((dist - FREEZE) / FREEZE, 0, 1)
    f = np.minimum(1, lim / np.maximum(L, 1e-9))
    return P + d * f[:, None]


def bumpiness(polys, sigma=None):
    """90-й процентиль сдвига края при сглаживании, ед.; без зон у углов."""
    moves = []
    for poly in polys:
        P, h = resample(poly)
        S, cs = smooth_closed(P, h, sigma)
        d = np.hypot(*(S - P).T)
        if cs:
            near = np.zeros(len(P), bool)
            r = int(round(CORNER_KEEP / h))
            for c in cs:
                near[np.arange(c - r, c + r + 1) % len(P)] = True
            d = d[~near]
        moves.append(d)
    m = np.concatenate(moves) if moves else np.zeros(1)
    return float(np.percentile(m, 90)), float(m.max())


# --- пересборка контура ---

def signed_area(contour):
    p = np.array([q[:2] for q in contour], float)
    return 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])


TOL = 1.0           # ед.: допуск qu2cu и cu2qu
CONTROL_STEP = 8.0  # ед. между опорными точками сплайна (кривая уже гладкая, гуще не нужно)


def rebuild(P, cs, rec, h=STEP):
    """Сглаженные точки → квадратичный B-сплайн (углы — точки на кривой) в RecordingPen."""
    n = len(P)
    pts = [tuple(map(float, p)) for p in P]
    if not cs:          # без углов: одна точка на кривой там, где контур почти прямой
        cs = [int(np.argmin(turning(P, 3)))]
    order = cs + [cs[0] + n]
    rec.moveTo(pts[cs[0]])
    for a, b in zip(order, order[1:]):
        k = max(1, int(round((b - a) / max(1, round((b - a) * h / CONTROL_STEP)))))
        mid = [pts[i % n] for i in range(a + k, b - k // 2, k)]
        end = pts[b % n]
        if mid:
            rec.qCurveTo(*mid, end)
        else:
            rec.lineTo(end)
    rec.closePath()


def _to_pen(contour, pen):
    """Исходный контур TrueType без изменений."""
    from fontTools.pens.pointPen import PointToSegmentPen
    pp = PointToSegmentPen(pen)
    pp.beginPath()
    n = len(contour)
    for k, (x, y, on) in enumerate(contour):
        prev_on = contour[k - 1][2]
        pp.addPoint((x, y), ('line' if prev_on else 'qcurve') if on else None)
    pp.endPath()


def smooth_contours(contours, flatten, sigma=None, frozen=()):
    """contours: [[x, y, on], ...] TrueType. Возвращает RecordingPen (целые координаты, квадратичные)
    и наибольший сдвиг точки края, ед. Мелкие внешние контуры переносятся как есть."""
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.qu2cuPen import Qu2CuPen
    out = RecordingPen()
    moved = 0.0
    areas = [signed_area(c) for c in contours]
    outer = np.sign(max(areas, key=abs))
    for c, a in zip(contours, areas):
        P, h = resample(flatten(c, steps=24))
        if np.sign(a) == outer and len(P) * h < SMALL:
            _to_pen(c, out)
            continue
        S, cs = smooth_closed(P, h, sigma)
        S = clamp(P, S, frozen=frozen)
        moved = max(moved, float(np.hypot(*(S - P).T).max()))
        raw, part = RecordingPen(), RecordingPen()
        rebuild(S, cs, raw, h)
        raw.replay(Qu2CuPen(Cu2QuPen(part, TOL, reverse_direction=False), TOL, all_cubic=True))
        out.value += [(op, [tuple(int(round(v)) for v in q) if q is not None else None for q in args])
                      for op, args in part.value]
    return out, moved


# --- проверка топологии (растр 1 ед. = 1 px, общий сдвиг для «было» и «стало») ---

ASC, CANVAS = 1100, 1700


def mask(contours, flatten, x0, width):
    import cv2  # noqa: F401  (проверка наличия, используется в holes)
    from PIL import Image, ImageDraw
    acc = np.zeros((CANVAS, width), np.uint8)
    for c in contours:
        im = Image.new('L', (width, CANVAS), 0)
        ImageDraw.Draw(im).polygon([(x + x0, ASC - y) for x, y in flatten(c, 16)], fill=1)
        acc ^= np.array(im)
    return acc


def holes(m):
    import cv2
    n, lab, st, cen = cv2.connectedComponentsWithStats(1 - m, connectivity=4)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if x > 0 and y > 0 and x + w < m.shape[1] and y + h < m.shape[0]:
            out.append((lab == i, cen[i]))
    return out


def topology(m):
    import cv2
    return cv2.connectedComponents(m, connectivity=8)[0] - 1, len(holes(m))


def changed_spots(old, new, x0):
    """Центры полостей, которые появились, отщепились от прежней или исчезли (координаты шрифта)."""
    ho, hn = holes(old), holes(new)
    spots, groups = [], {}
    for k, (a, c) in enumerate(hn):
        ov = [(a & b).sum() for b, _ in ho]
        if not ov or max(ov) == 0:
            spots.append(c)
        else:
            groups.setdefault(int(np.argmax(ov)), []).append(k)
    for j, ks in groups.items():                  # одна прежняя полость → несколько: лишние отщепились
        ks = sorted(ks, key=lambda k: -hn[k][0].sum())
        spots += [hn[k][1] for k in ks[1:]]
    spots += [c for j, (b, c) in enumerate(ho) if j not in groups]
    return [(c[0] - x0, ASC - c[1]) for c in spots]


def smooth_glyph(contours, flatten, to_contours, tries=4):
    """Сглаживание с сохранением топологии. Если число частей или полостей изменилось,
    место изменения замораживается (FREEZE) и глиф пересчитывается. Возвращает
    (RecordingPen или None, сдвиг, замороженные места)."""
    xs = [x for c in contours for x, _ in flatten(c, 16)]
    x0 = 80 - min(0, min(xs))
    width = int(max(xs) + x0 + 80)
    old = mask(contours, flatten, x0, width)
    topo = topology(old)
    frozen = []
    for _ in range(tries):
        rec, moved = smooth_contours(contours, flatten, frozen=frozen)
        new = mask(to_contours(rec), flatten, x0, width)
        if topology(new) == topo:
            return rec, moved, frozen
        spots = changed_spots(old, new, x0)
        if not spots:
            break
        frozen += spots
    return None, 0.0, frozen


# --- UFO-мастер (integrate.py) ---

def tt_contours(rec):
    """RecordingPen → контуры TrueType [[x, y, on], ...] (для проверки топологии)."""
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    pen = TTGlyphPen(None)
    rec.replay(pen)
    g = pen.glyph()
    out, s = [], 0
    for e in g.endPtsOfContours:
        out.append([[g.coordinates[i][0], g.coordinates[i][1], g.flags[i] & 1] for i in range(s, e + 1)])
        s = e + 1
    return out


def smooth_ufo(font, flatten, ufo_contours):
    """Все глифы с контурами (составных в Valera Sans нет). Возвращает отчёт по глифам."""
    report = {}
    for g in font:
        if not g.contours or g.components:
            continue
        rec, moved, frozen = smooth_glyph(ufo_contours(g), flatten, tt_contours)
        if rec is None:
            report[g.name] = {'skipped': True}
            continue
        g.clearContours()
        rec.replay(g.getPen())
        report[g.name] = {'moved': round(moved, 1), 'frozen': [[round(float(v)) for v in p] for p in frozen]}
    return report
