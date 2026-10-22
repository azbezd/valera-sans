"""Обещания README, CONTEXTS и образца — прямо по набору HarfBuzz, без модели форм.

validate.py сверяет шрифт с моделью (scripts/alternates_model.py); если ошибка попала в
модель, такая сверка её подтверждает. Здесь каждое обещание проверяется по тому, что
HarfBuzz реально поставил, и по настоящим контурам из файла. Модель нужна только чтобы
перечислить строки, в которых встречаются все пары соседних форм (для зазора).
"""
import json
from pathlib import Path

import numpy as np
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
U_CONTEXT = set(json.loads((ROOT / 'tests/approved-spacing-v0.5.5.json').read_text())['context'])
LAMBDA = 'лЛдДАA'           # Λ-буквы: нижние концы не ближе 40 (CHANGELOG 0.6.0)
TUCK = 'uni0434'            # подчёркивание «д» подныривает: не ближе 25
LIFT_AFTER = 'акцщ'         # «л» после любой формы этих букв выше
LIFT = 25
LAT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
CYR = set('АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя')


class Points(BasePen):
    """Точки контура через каждые ~3 ед. (кривые разбиваются)."""
    def __init__(self, gs):
        super().__init__(gs)
        self.pts, self.cur = [], None

    def _add(self, p):
        if self.cur is not None:
            (x0, y0), (x1, y1) = self.cur, p
            n = max(1, int(np.hypot(x1 - x0, y1 - y0) / 3))
            self.pts += [(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n) for t in range(1, n + 1)]
        self.cur = p

    def _moveTo(self, p):
        self.cur = p
        self.pts.append(p)

    def _lineTo(self, p):
        self._add(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur
        for i in range(1, 17):
            t = i / 16
            m = 1 - t
            self._add((m**3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t**3 * p3[0],
                       m**3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t**3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur
        for i in range(1, 17):
            t = i / 16
            m = 1 - t
            self._add((m * m * p0[0] + 2 * m * t * p1[0] + t * t * p2[0], m * m * p0[1] + 2 * m * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        self.cur = None


class Font:
    def __init__(self, path):
        tt = TTFont(path)
        self.order, self.cmap = tt.getGlyphOrder(), tt.getBestCmap()
        self.char = {}
        for cp, n in self.cmap.items():
            self.char.setdefault(n, chr(cp))
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        self.gs = tt.getGlyphSet()
        self.adv = {n: tt['hmtx'][n][0] for n in self.order}
        self._pts = {}

    def char_of(self, name):
        return self.char.get(name.split('.')[0], '')

    def shape(self, text, tab=False):
        b = hb.Buffer()
        b.add_str(text)
        b.guess_segment_properties()
        hb.shape(self.hb, b, {'calt': True, 'kern': True, 'tnum': tab})
        return [self.order[i.codepoint] for i in b.glyph_infos], b.glyph_positions

    def points(self, name):
        if name not in self._pts:
            pen = Points(self.gs)
            self.gs[name].draw(pen)
            p = np.array(pen.pts) if pen.pts else np.zeros((0, 2))
            self._pts[name] = (p, cKDTree(p) if len(p) else None)
        return self._pts[name]


def floor(f, a, b):
    ca, cb = f.char_of(a), f.char_of(b)
    if b == TUCK:
        return 25
    if cb in LAMBDA:
        return 40
    return 50 if ca.isalnum() and cb.isalnum() else 40


def check(path, witnesses):
    """witnesses: {(левый, правый): строка} — пары, которые встречаются в наборе."""
    f = Font(path)
    chars = [chr(c) for c in sorted(f.cmap) if chr(c).strip()]
    looped_u = f.cmap[ord('у')]
    open_u = {looped_u + '.open'} | {o for o in f.order if o.startswith(looped_u + '.alt')}
    bad = {}

    def fail(key, example):
        bad.setdefault(key, []).append(example)

    for x in chars:
        # плавная r после e; перед ней основная e, после — a.alt1 на 25 выше
        n, pos = f.shape(x + 'era')
        if n[1:3] != ['uni0065', 'uni0072.after_e'] or n[3] != 'uni0061.alt1' or pos[3].y_offset != LIFT:
            fail('e–r–a', x + 'era → ' + ' '.join(n))
        # повтор подряд меняет форму, и в «eer» тоже
        n, _ = f.shape(x + 'eer')
        if n[1] == n[2]:
            fail('eer', x + 'eer → ' + ' '.join(n))
        # после любой формы «а» — обычная «д»
        n, _ = f.shape(x + 'ад')
        if n[2] != 'uni0434':
            fail('ад', x + 'ад → ' + ' '.join(n))
        # «л» после любой формы а, к, ц, щ — выше
        for c in LIFT_AFTER:
            n, pos = f.shape(x + c + 'л')
            if pos[2].y_offset != LIFT:
                fail('л', f'{x}{c}л → ' + ' '.join(n))
        # открытая у (любая из форм без петли) — ровно после букв из CONTEXTS и после у, в остальных сочетаниях — петлевая
        for c in chars + [' ']:
            if c == 'У':
                continue
            n, _ = f.shape(x + c + 'у')
            if (c in U_CONTEXT or c == 'у') != (n[2] in open_u) or (n[2] not in open_u and n[2] != looped_u):
                fail('у', f'{x}{c}у → ' + ' '.join(n))
        # один и тот же знак подряд меняет форму и перебирает все свои формы (если у него есть варианты)
        for c in chars:
            m = 1 + sum(o.startswith(f.cmap[ord(c)] + '.alt') for o in f.order)
            if m == 1:
                continue
            for pre in (x, x + 'er'):     # после «er» a ставится правилом стыка
                run = f.shape(pre + c * m)[0][len(pre):]
                if any(a == b for a, b in zip(run, run[1:])) or len(set(run)) < m:
                    fail('повтор', pre + c * m + ' → ' + ' '.join(run))
    # зазор между краями во всех встречающихся парах
    checked = 0
    for (a, b), text in witnesses.items():
        ca, cb = f.char_of(a), f.char_of(b)
        if not ca.strip() or not cb.strip() or ('.tab' in a and '.tab' in b):
            continue
        if (ca in LAT and cb in CYR) or (ca in CYR and cb in LAT):
            continue
        n, pos = f.shape(text, tab='.tab' in a + b)
        i = next(j for j in range(len(n) - 1) if n[j] == a and n[j + 1] == b)
        pa, ta = f.points(a)
        pb, _ = f.points(b)
        if ta is None or not len(pb):
            continue
        dx = pos[i].x_advance + pos[i + 1].x_offset - pos[i].x_offset
        shifted = pb + np.array([dx, pos[i + 1].y_offset - pos[i].y_offset])
        if shifted[:, 0].min() - pa[:, 0].max() > 60:
            continue
        checked += 1
        d = float(ta.query(shifted, k=1)[0].min())
        if d < floor(f, a, b) - 0.5:
            fail('зазор', f'{text}: {a} {b} {d:.0f}')
    return {k: (len(v), sorted(v)[:5]) for k, v in bad.items()}, checked
