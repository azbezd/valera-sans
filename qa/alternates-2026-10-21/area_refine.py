"""Уплотнение рыхлых пар по площади пустоты.

Пустота пары — средняя ширина просвета между буквами в полосе от базовой линии до
x-высоты (строчная справа и слева) или высоты прописных, с потолком глубины DEPTH.
Если пара рыхлее типичной для своей группы (медиана по регистрам), буквы сдвигаются
ближе до типичной пустоты, но не ближе минимума без касания из формулы 0.4
(62 ед. по контуру, расширенному на ±18 ед. по вертикали). Ничего не раздвигается.
Только пары букв одной письменности.
"""
import numpy as np
from scipy.ndimage import minimum_filter1d, maximum_filter1d

DEPTH = 220
STEP = 5
MAX_TIGHTEN = 90
MINIMUM = 62
LAT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
CYR = set('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя')


def profiles(font, names, render, ASC):
    P = {}
    for n in names:
        m = render(font[n])
        rows = m.any(1)
        L = np.where(rows, np.argmax(m, 1) - 40, np.nan).astype(float)
        R = np.where(rows, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1) - 40, np.nan).astype(float)
        sl = minimum_filter1d(np.nan_to_num(L, nan=1e6), 37)
        sr = maximum_filter1d(np.nan_to_num(R, nan=-1e6), 37)
        ys = ASC - np.arange(m.shape[0])
        P[n] = {'L': L, 'R': R, 'sL': np.where(sl < 1e5, sl, np.nan), 'sR': np.where(sr > -1e5, sr, np.nan),
                'w': font[n].width, 'ys': ys}
    return P


def case_of(c):
    return 'U' if c.isupper() else 'l'


def tighten(P, a, bs, ca, cbs, k, medians):
    """Новые значения кернинга для пар a + каждый из bs (только уплотнение)."""
    ys = P[a]['ys']
    LB = np.stack([P[b]['L'] for b in bs]); SLB = np.stack([P[b]['sL'] for b in bs])
    g0 = P[a]['w'] + LB - P[a]['R'][None, :]              # зазор без кернинга по строкам
    s0 = np.nanmin(np.where(np.isnan(P[a]['w'] + SLB - P[a]['sR'][None, :]), np.inf,
                            P[a]['w'] + SLB - P[a]['sR'][None, :]), axis=1)
    out = k.astype(float).copy()
    for j, (b, cb) in enumerate(zip(bs, cbs)):
        if ca is None or cb is None or not (((ca in LAT) and (cb in LAT)) or ((ca in CYR) and (cb in CYR))):
            continue
        case = case_of(ca) + case_of(cb)
        top = 700 if 'U' in case else 560
        band = (ys >= 0) & (ys <= top)
        g = g0[j][band]
        def mean_at(kk):
            x = g + kk
            return float(np.where(np.isnan(x), DEPTH, np.minimum(x, DEPTH)).mean())
        T = medians[case]
        if mean_at(k[j]) <= T + STEP:
            continue
        floor = MINIMUM - s0[j]                            # ближе нельзя: касание
        best = k[j]
        kk = k[j]
        while kk - STEP >= max(floor, k[j] - MAX_TIGHTEN):
            kk -= STEP
            best = kk
            if mean_at(kk) <= T:
                break
        out[j] = best
    return out


def medians_of(P, pairs_k, cmap_rev):
    vals = {'UU': [], 'Ul': [], 'lU': [], 'll': []}
    for (a, b), k in pairs_k.items():
        ca, cb = cmap_rev.get(a), cmap_rev.get(b)
        if ca is None or cb is None or not (((ca in LAT) and (cb in LAT)) or ((ca in CYR) and (cb in CYR))):
            continue
        case = case_of(ca) + case_of(cb)
        top = 700 if 'U' in case else 560
        band = (P[a]['ys'] >= 0) & (P[a]['ys'] <= top)
        x = (P[a]['w'] + k + P[b]['L'] - P[a]['R'])[band]
        vals[case].append(float(np.where(np.isnan(x), DEPTH, np.minimum(x, DEPTH)).mean()))
    return {c: float(np.median(v)) for c, v in vals.items()}


# ---- «треугольник сверху»: пустота собрана наверху, внизу буквы почти касаются ----
TRI_START = 60        # перекос (верх − низ) в ед., с которого начинаем уплотнять
TRI_GAIN = 0.3
TRI_BASE = 10
TRI_MAX = 35
TRI_FLOOR = 40        # нижние концы не ближе этого (вместо 62 для обычных пар)


def triangle(P, a, bs, ca, cbs, k):
    """Дополнительное уплотнение пар a + bs с перекосом пустоты вверх."""
    ys = P[a]['ys']
    out = k.astype(float).copy()
    for j, (b, cb) in enumerate(zip(bs, cbs)):
        if ca is None or cb is None or not (((ca in LAT) and (cb in LAT)) or ((ca in CYR) and (cb in CYR))):
            continue
        case = case_of(ca) + case_of(cb)
        top = 700 if 'U' in case else 560
        band = (ys >= 0) & (ys <= top)
        x = (P[a]['w'] + k[j] + P[b]['L'] - P[a]['R'])[band]
        x = np.where(np.isnan(x), 300, np.minimum(x, 300))
        h = len(x) // 2
        imb = x[:h].mean() - x[h:].mean()
        if imb <= TRI_START:
            continue
        want = min(TRI_MAX, (imb - TRI_START) * TRI_GAIN + TRI_BASE)
        s = P[a]['w'] + k[j] + P[b]['sL'] - P[a]['sR']
        safety = float(np.nanmin(np.where(np.isnan(s), np.inf, s)))
        d = min(want, max(0.0, safety - TRI_FLOOR))
        d = STEP * int(d // STEP)
        out[j] = k[j] - d
    return out
