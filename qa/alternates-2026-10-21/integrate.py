"""Встраивание выбранных автором вариантов в UFO-мастера.

Вход: vector/<Style>/*.json (контуры из work/alternates/vectorize.py), исходные UFO
из git HEAD (.orig/). Выход: sources/*.ufo (новые глифы, glyphOrder, features.fea)
и tests/alternates-spec.json (спецификация чередования и кернинга для validate.py).

Чередование (calt, после контекстных r/у): у каждого глифа есть «фаза» — индекс формы
для букв с вариантами, псевдослучайное число для остальных. Буква X после глифа фазы k
получает форму (k + h_X) mod m_X, где h_X ∈ [1, m_X−1] — поэтому одна и та же буква
подряд всегда меняет форму, а цепочка по тексту выглядит случайной. С 0.6.4 h_X взаимно
просто с m_X: повтор буквы перебирает все её формы, а не две-три по кругу.

Кернинг: прежние 20 718 пар «глиф-глиф» остаются как есть (база); каждая буква со
своими вариантами — класс, классовые пары повторяют значение базы. Для вариантов
используется та же формула, что строила кернинг 0.4 (refine_all_pairs.py: мягкий минимум
горизонтальных зазоров в полосе 40–680, цели по регистрам, минимум против столкновений).
Сначала поля варианта подгоняются так, чтобы по формуле он в среднем вёл себя как его
базовая буква; затем пара-исключение пишется, если формула расходится с базовой парой
на ≥ 20 ед.
"""
import json
import math
import re
import sys
import zlib
from pathlib import Path

import numpy as np
import ufoLib2
from fontTools.pens.recordingPen import RecordingPen

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'qa/artifact-fix-2026-10-21'))
sys.path.insert(0, str(ROOT / 'qa/contour-cleanup-2026-10-21'))
sys.path.insert(0, str(HERE))
from glyphraster import render, ASC  # noqa: E402
import polish as POLISH  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
import simplify as SIMPLIFY  # noqa: E402
sys.path.insert(0, str(ROOT / 'qa/digits-2026-10-22'))
import scale_digits as DIGITS  # noqa: E402
sys.path.insert(0, str(ROOT / 'qa/smooth-2026-10-22'))
import smooth as SMOOTH  # noqa: E402

STYLES = ['Light', 'Regular', 'Semibold']
BAND = 10
KERN_RANGE = (-260, 160)
NEW_ENCODED = {'uni00B0.alt1': ('uni00B0', 0xB0)}


def crc(s):
    return zlib.crc32(s.encode())


def load_vectors(style):
    out = []
    for p in sorted((HERE / 'vector' / style).glob('*.json')):
        out.append(json.loads(p.read_text()))
    return out


def add_glyphs(font, vecs):
    names = []
    for d in vecs:
        name, uni = NEW_ENCODED.get(d['name'], (d['name'], None))
        g = font.newGlyph(name)
        g.width = d['advance']
        if uni:
            g.unicodes = [uni]
        rec = RecordingPen()
        # целые координаты: TTF всё равно округлит, а CFF должен получить те же точки
        rec.value = [(op, [tuple(int(round(c)) for c in p) for p in args]) for op, args in d['value']]
        rec.replay(g.getPen())
        names.append(name)
    font.glyphOrder = list(font.glyphOrder) + names
    return names


def forms_map(font_names, vec_names):
    forms = {}
    for n in vec_names:
        if '.alt' not in n:
            continue
        base = n.split('.alt')[0]
        forms.setdefault(base, [base]).append(n)
    for base in forms:
        forms[base] = [base] + sorted(forms[base][1:], key=lambda s: int(s.split('.alt')[1]))
    return forms


def coprime_shift(b, m):
    """Шаг чередования буквы с m формами: 1 + crc mod (m − 1), а если он делит m — следующий
    взаимно простой (0.6.4; например, у «&» с шестью формами шаг 3 давал «&&&&&» из двух форм)."""
    h = 1 + crc(b) % (m - 1)
    while math.gcd(h, m) != 1:
        h = h % (m - 1) + 1
    return h


def rotation_spec(order, forms):
    n_phase = max(len(v) for v in forms.values())
    phase = {}
    for base, fs in forms.items():
        for i, n in enumerate(fs):
            phase[n] = i
    for n in order:
        phase.setdefault(n, crc(n) % n_phase)
    shift = {b: coprime_shift(b, len(fs)) for b, fs in forms.items() if len(fs) > 1}
    return {'phases': n_phase, 'phase': phase, 'forms': forms, 'shift': shift}


def rotation_fea(spec):
    forms, shift, n = spec['forms'], spec['shift'], spec['phases']
    rot = [b for b in sorted(forms) if b in shift]
    lines = []
    for k in range(n):
        pairs = [(b, forms[b][(k + shift[b]) % len(forms[b])]) for b in rot]
        pairs = [(a, z) for a, z in pairs if a != z]
        lines.append(f'lookup Rotate{k} {{')
        lines += [f' sub {a} by {z};' for a, z in pairs]
        lines.append(f'}} Rotate{k};')
    for k in range(n):
        members = sorted(g for g, p in spec['phase'].items() if p == k)
        lines.append(f'@Phase{k} = [{" ".join(members)}];')
    lines.append(f'@Rotating = [{" ".join(rot)}];')
    lines.append('lookup Rotate {')
    # «д» после любой формы «а» не чередуется (остаётся обычной), и следующая «д» отсчитывается
    # уже от обычной — иначе в «аддд» формы шли бы через одну (0.6.4)
    left, target = KEEP_AFTER
    lines.append(f" ignore sub [{' '.join(forms.get(left, [left]))}] {target}';")
    lines += [f' sub @Phase{k} @Rotating\' lookup Rotate{k};' for k in range(n)]
    lines.append('} Rotate;')
    return '\n'.join(lines)


# ---------- кернинг: формула refine_all_pairs.py (v0.4), перенесённая на варианты ----------
LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CYRILLIC = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
LETTERS = LATIN + CYRILLIC
NUMBERS = "0123456789"
OPERATORS = "+-=<>~*/\\|_^–—"
EXTRA = {'Light': -2, 'Regular': 0, 'Semibold': 5}
EXC_DIFF = 25         # меньше 2,5% кегля на рукописном шрифте не видно
LAT, CYR = set(LATIN), set(CYRILLIC)


def char_of(name, cmap_rev):
    base = name.split('.alt')[0]
    if base.endswith('.tab'):
        base = base[:-4]
    if base == 'uni0072.after_e':
        base = 'uni0072'
    if base == 'uni0443.open':
        base = 'uni0443'
    return cmap_rev.get(base)


def profiles(font, names):
    """По строкам в 1 ед.: left/right чернил и «безопасные» (±18 ед. по вертикали)."""
    H = 1100 + 560
    prof = {}
    for n in names:
        g = font[n]
        m = render(g)
        ys = ASC - np.arange(m.shape[0])
        rows = m.any(1)
        left = np.where(rows, np.argmax(m, 1) - 40, np.nan).astype(float)
        right = np.where(rows, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1) - 40, np.nan).astype(float)
        sel = (ys >= -560) & (ys < 1100)
        left, right, ys = left[sel], right[sel], ys[sel]
        from scipy.ndimage import minimum_filter1d, maximum_filter1d
        sl = minimum_filter1d(np.nan_to_num(left, nan=1e6), 37)
        sr = maximum_filter1d(np.nan_to_num(right, nan=-1e6), 37)
        prof[n] = {'adv': g.width, 'left': left, 'right': right,
                   'safe_left': np.where(sl < 1e5, sl, np.nan), 'safe_right': np.where(sr > -1e5, sr, np.nan), 'ys': ys}
    return prof


def formula(pa, PB, ca, cbs, extra, raw=False):
    """Вектор поправок для пары a + каждый b (как evaluate() в refine_all_pairs.py)."""
    core = (pa['ys'] >= 40) & (pa['ys'] <= 680)
    LB = np.stack([p['left'] for p in PB]); SLB = np.stack([p['safe_left'] for p in PB])
    d = pa['adv'] + LB - pa['right'][None, :]
    valid = core[None, :] & np.isfinite(d)
    fallback = ~valid.any(1)
    valid[fallback] = np.isfinite(d[fallback])
    dd = np.where(valid, d, np.inf)
    low = dd.min(1)
    with np.errstate(over='ignore', invalid='ignore'):
        e = np.where(valid, np.exp(-(dd - low[:, None]) / 70), 0)
        optical = low - 70 * np.log(e.sum(1) / np.maximum(valid.sum(1), 1))
    safe = pa['adv'] + SLB - pa['safe_right'][None, :]
    safety = np.where(np.isfinite(safe), safe, np.inf).min(1)
    out = np.zeros(len(PB))
    for j, cb in enumerate(cbs):
        if not np.isfinite(optical[j]) or not np.isfinite(safety[j]) or ca is None or cb is None:
            continue
        both_l = ca in LETTERS and cb in LETTERS
        both_d = ca in NUMBERS and cb in NUMBERS
        minimum = (62 if both_l or both_d else 50) + max(0, extra)
        if both_l:
            case = ('U' if ca.isupper() else 'l') + ('U' if cb.isupper() else 'l')
            target = {'UU': 156, 'Ul': 145, 'lU': 145, 'll': 140}[case] + extra * 2
        elif both_d:
            target = 130 + extra * 2
        elif ca in OPERATORS or cb in OPERATORS:
            target = 145 + extra * 2
        else:
            target = 112 + extra * 2
            if (ca in LETTERS and cb in NUMBERS) or (cb in LETTERS and ca in NUMBERS):
                target = 140 + extra * 2
        if raw:
            out[j] = target - optical[j]
            continue
        keep = ca not in LETTERS + NUMBERS and cb not in LETTERS + NUMBERS
        desired = 0 if keep else max(-180, min(55, 5 * round((target - optical[j]) / 5)))
        adj = max(desired, int(np.ceil((minimum - safety[j]) / 5)) * 5)
        if abs(adj) < 15:
            adj = 0
        if safety[j] + adj < minimum:
            adj = int(np.ceil((minimum - safety[j]) / 5)) * 5
        out[j] = adj
    return out


def fit_sidebearings(font, groups, all_names, style, cmap_rev):
    """Поля варианта: медианная разница «сырой» формулы вариант−база по буквенным соседям."""
    base_of = {n: b for b, fs in groups.items() for n in fs}
    prof = profiles(font, all_names)
    extra = EXTRA[style]
    partners = [n for n in all_names if base_of.get(n) == n and (char_of(n, cmap_rev) or '#') in LETTERS]
    P = [prof[n] for n in partners]
    pc = [char_of(n, cmap_rev) for n in partners]
    moves = {}
    for a in [n for n in all_names if n in base_of and base_of[n] != n]:
        ba = base_of[a]
        ca = char_of(a, cmap_rev)
        r = formula(prof[a], P, ca, pc, extra, raw=True) - formula(prof[ba], P, ca, pc, extra, raw=True)
        # левая сторона: пары партнёр + вариант
        l = np.array([formula(prof[b], [prof[a]], cb, [ca], extra, raw=True)[0]
                      - formula(prof[b], [prof[ba]], cb, [ca], extra, raw=True)[0] for b, cb in zip(partners, pc)])
        moves[a] = (float(np.median(l[np.isfinite(l)])) if np.isfinite(l).any() else 0.0,
                    float(np.median(r[np.isfinite(r)])) if np.isfinite(r).any() else 0.0)
    for a, (dl, dr) in moves.items():
        g = font[a]
        dl, dr = int(round(dl)), int(round(dr))
        if dl:
            for c in g.contours:
                for pt in c.points:
                    pt.x += dl
        g.width = g.width + dl + dr
    return moves


def kerning(font, base_pairs, groups, all_names, style, cmap_rev):
    """Группы по боковому профилю + исключения.

    Базовые глифы — сами себе группа (утверждённые пары воспроизводятся матрицей точно).
    Вариант справа (как первый глиф пары) приписывается к базовому r, чей ряд утверждённых
    значений меньше всего расходится с формулой для варианта; слева — к базовому l по столбцу.
    Исключение — пара, где формула расходится со значением группы на ≥ EXC_DIFF.
    """
    base_of = {n: b for b, fs in groups.items() for n in fs}
    names = [n for n in all_names if n in base_of and char_of(n, cmap_rev)]
    bases = [n for n in names if base_of[n] == n]
    alts = [n for n in names if base_of[n] != n]
    bi = {n: i for i, n in enumerate(bases)}
    A = np.array([[base_pairs.get((x, y), 0) for y in bases] for x in bases], float)
    prof = profiles(font, names)
    cs = {n: char_of(n, cmap_rev) for n in names}
    extra = EXTRA[style]
    def script(c):
        return 'L' if c in LAT else 'C' if c in CYR else '-'
    PB = [prof[n] for n in bases]
    cb_list = [cs[n] for n in bases]
    rep_r, rep_l = {}, {}
    for a in alts:
        F = formula(prof[a], PB, cs[a], cb_list, extra)
        ok = np.array([not ({script(cs[a]), script(c)} == {'L', 'C'}) for c in cb_list])
        bad = (np.abs(A - F[None, :]) >= EXC_DIFF) & ok[None, :]
        cost = bad.sum(1) + 1e-3 * np.abs(A - F[None, :]).sum(1)
        rep_r[a] = bases[int(np.argmin(cost))]
    PA = [prof[n] for n in alts]
    ca_list = [cs[n] for n in alts]
    Fl = np.stack([formula(prof[b], PA, cs[b], ca_list, extra) for b in bases])   # (bases, alts)
    for j, a in enumerate(alts):
        ok = np.array([not ({script(cs[a]), script(c)} == {'L', 'C'}) for c in cb_list])
        bad = (np.abs(A - Fl[:, j][:, None]) >= EXC_DIFF) & ok[:, None]
        cost = bad.sum(0) + 1e-3 * np.abs(A - Fl[:, j][:, None]).sum(0)
        rep_l[a] = bases[int(np.argmin(cost))]
    R = {n: rep_r.get(n, n) for n in names}
    L = {n: rep_l.get(n, n) for n in names}
    P = [prof[n] for n in names]
    cl = [cs[n] for n in names]
    exc = {}
    for a in names:
        alt_a = a in rep_r
        adj = formula(prof[a], P, cs[a], cl, extra)
        ra = bi[R[a]]
        for j, b in enumerate(names):
            if not alt_a and b not in rep_l:
                continue
            if {script(cs[a]), script(cl[j])} == {'L', 'C'}:
                continue
            cv = A[ra, bi[L[b]]]
            if abs(adj[j] - cv) >= EXC_DIFF:
                exc[(a, b)] = int(max(KERN_RANGE[0], min(KERN_RANGE[1], adj[j])))
    return exc, rep_r, rep_l


def parse_pairs(fea):
    return {(a, b): int(v) for a, b, v in re.findall(r'^\s*pos\s+(\S+)\s+(\S+)\s+(-?\d+);', fea, re.M)}


def keep_after_fea(spec):
    left, target = KEEP_AFTER
    lefts = spec['forms'].get(left, [left])
    alts = spec['forms'].get(target, [target])[1:]
    return ('# после любой формы «а» — обычная «д» (подчёркивание подныривает под хвостик)\n'
            'lookup KeepAfter {\n'
            f" sub [{' '.join(lefts)}] [{' '.join(alts)}]' by {target};\n"
            '} KeepAfter;')


def build_features(old_fea, spec, base_pairs, exc, rep_r, rep_l, lifted=None):
    head, rest = old_fea.split('feature calt {', 1)
    calt_body, rest = rest.split('} calt;', 1)
    allpairs_end = rest.index('} AllPairs;')
    tail = rest[allpairs_end + len('} AllPairs;'):]
    out = [head.rstrip(), '',
           '# Контекстные формы r после e и открытой у (как в 0.5.5)',
           'lookup Contextual {', calt_body.strip('\n'), '} Contextual;', '',
           '# Чередование вариантов: см. qa/alternates-2026-10-21/integrate.py',
           rotation_fea(spec), '',
           keep_after_fea(spec),
           join_fea(join_rules(spec)),
           'feature calt {', ' lookup Contextual;', ' lookup Rotate;', ' lookup KeepAfter;', ' lookup Join;', '} calt;', '']
    rgroups, lgroups = {}, {}
    for a, r in rep_r.items():
        rgroups.setdefault(r, [r]).append(a)
    for a, l in rep_l.items():
        lgroups.setdefault(l, [l]).append(a)
    for r, fs in sorted(rgroups.items()):
        out.append(f'@KR_{r.replace(".", "_")} = [{" ".join(fs)}];')
    for l, fs in sorted(lgroups.items()):
        out.append(f'@KL_{l.replace(".", "_")} = [{" ".join(fs)}];')
    R = lambda g: f'@KR_{g.replace(".", "_")}' if g in rgroups else g  # noqa: E731
    Lr = lambda g: f'@KL_{g.replace(".", "_")}' if g in lgroups else g  # noqa: E731
    out.append('lookup AllPairs useExtension {')
    out.append('# исключения (пары глифов) — применяются раньше групп')
    lifted = lifted or {}
    out += [f'pos {a} {b} {v};' for (a, b), v in sorted(exc.items())]
    out.append('# группы: утверждённые пары 0.5.5; вариант входит в группу базовой буквы по профилю')
    out += [f'pos {R(a)} {Lr(b)} {v};' for (a, b), v in base_pairs.items()]
    out.append('} AllPairs;')
    if lifted:
        # Подъём второй буквы — отдельным контекстным правилом: пара с ValueRecord2
        # «съела» бы вторую букву, и кернинг следующей пары не применился бы.
        out.append('# «л» после строчной и a.alt1 после r.after_e: левее (кернинг выше) и чуть выше (подъём)')
        out.append('lookup Lift {')
        by_target = {}
        for (a, b), (k, dy) in sorted(lifted.items()):
            by_target.setdefault((b, dy), []).append(a)
        for (b, dy), lefts in sorted(by_target.items()):
            out.append(f" pos [{' '.join(lefts)}] {b}' <0 {dy} 0 0>;")
        out.append('} Lift;')
        tail = tail.replace('feature kern {lookup AllPairs;} kern;', 'feature kern {lookup AllPairs; lookup Lift;} kern;')
    tail = tail.replace('} tnum;', '\n'.join(f'sub {n} by {b}.tab;' for b, fs in sorted(spec['forms'].items())
                                             if b + '.tab' in spec['phase'] for n in fs[1:]) + '\n} tnum;')
    out.append(tail.strip('\n'))
    return '\n'.join(out) + '\n'


LAMBDA_FAMILY = 'лЛдДАA'     # левая сторона наклонная: пустота пары уходит вверх (замечание автора к «ал»)
LAMBDA_MAX = 30
LAMBDA_FLOOR = 40            # нижние концы не ближе (обычный минимум без касания — 62)
LAMBDA_IMBALANCE = 60


def lambda_pairs(font, base_pairs, exc, rep_r, rep_l, forms, style, cmap_rev):
    """Пары «буква + Λ-буква»: если пустота сверху больше нижней на LAMBDA_IMBALANCE,
    сближаем до LAMBDA_MAX ед., внизу не ближе LAMBDA_FLOOR. Базовые пары правятся в
    базе, сочетания с вариантами — исключениями."""
    import area_refine as AR
    letters = [g.name for g in font if g.unicodes and (chr(g.unicodes[0]) in AR.LAT or chr(g.unicodes[0]) in AR.CYR)]
    all_forms = lambda n: forms.get(n, [n])  # noqa: E731
    lefts = [x for n in letters for x in all_forms(n)]
    targets = [x for n in letters if chr(font[n].unicodes[0]) in LAMBDA_FAMILY for x in all_forms(n)]
    P = AR.profiles(font, sorted(set(lefts + targets)), render, ASC)
    ch = lambda n: char_of(n, cmap_rev)  # noqa: E731
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    def adjust(a, b, k):
        ca, cb = ch(a), ch(b)
        if (ca in AR.LAT) != (cb in AR.LAT):
            return k
        top = 700 if (ca.isupper() or cb.isupper()) else 560
        ys = P[a]['ys']; band = (ys >= 0) & (ys <= top)
        x = (P[a]['w'] + k + P[b]['L'] - P[a]['R'])[band]
        x = np.where(np.isnan(x), 300, np.minimum(x, 300))
        h = len(x) // 2
        if x[:h].mean() - x[h:].mean() <= LAMBDA_IMBALANCE:
            return k
        sa = P[a]['w'] + k + P[b]['sL'] - P[a]['sR']
        safety = float(np.nanmin(np.where(np.isnan(sa), np.inf, sa)))
        d = min(LAMBDA_MAX, max(0.0, safety - LAMBDA_FLOOR))
        return int(k - 5 * int(d // 5))
    changed = 0
    bases_t = [n for n in targets if '.alt' not in n]
    for a in [n for n in lefts if '.alt' not in n]:
        for b in bases_t:
            k0 = base_pairs.get((a, b), 0)
            k1 = adjust(a, b, k0)
            if k1 != k0:
                base_pairs[(a, b)] = k1
                changed += 1
    for a in lefts:
        for b in targets:
            if '.alt' not in a and '.alt' not in b:
                continue
            k0 = eff(a, b)
            k1 = adjust(a, b, k0)
            group = base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
            if k1 != group:
                exc[(a, b)] = k1
                changed += 1
            elif (a, b) in exc:
                del exc[(a, b)]
    return changed


CLEAR_LETTERS = 50    # ед.: настоящее расстояние между краями букв/цифр не меньше
CLEAR_OTHER = 40      # для пар со знаками


def clearance(font, base_pairs, exc, rep_r, rep_l, order, cmap_rev):
    """Буквы не должны слипаться: если край ближе порога — раздвигаем ровно до порога
    (шаг 5 ед.). Сначала базовые пары (меняется база), затем все сочетания вариантов."""
    import touch
    import area_refine as AR
    names = [n for n in order if char_of(n, cmap_rev) and char_of(n, cmap_rev).strip() and '.tab' not in n]
    chars = {n: char_of(n, cmap_rev) for n in names}
    alnum = lambda c: c in AR.LAT or c in AR.CYR or c.isdigit()  # noqa: E731
    dmin = lambda a, b: CLEAR_LETTERS if alnum(a) and alnum(b) else CLEAR_OTHER  # noqa: E731
    same = lambda a, b: not ((a in AR.LAT and b in AR.CYR) or (a in AR.CYR and b in AR.LAT))  # noqa: E731
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    bases = [n for n in names if '.alt' not in n]
    fixed_base = touch.clearance_pass(font, bases, chars, eff, dmin, same, dmax=CLEAR_LETTERS)
    for (a, b), (k0, k1, d) in fixed_base.items():
        base_pairs[(a, b)] = k1
    fixed_alt = touch.clearance_pass(font, names, chars, eff, dmin, same, dmax=CLEAR_LETTERS,
                                     skip=lambda a, b: '.alt' not in a and '.alt' not in b)
    for (a, b), (k0, k1, d) in fixed_alt.items():
        group = base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
        if k1 != group:
            exc[(a, b)] = k1
        else:
            exc.pop((a, b), None)
    return fixed_base, fixed_alt


LIFT_TARGETS = 'л'      # замечание автора к «ал»: «л» левее, но чуть выше
LIFT = 25               # ед. подъёма второй буквы (2,5% кегля)
LIFT_MIN_GAIN = 15      # поднимаем, только если это даёт сдвиг влево хотя бы на столько


def lift_pairs(font, base_pairs, exc, rep_r, rep_l, forms, cmap_rev):
    """Строчная кириллица + «л»: если поднятая на LIFT «л» может встать левее хотя бы на
    LIFT_MIN_GAIN при прежнем зазоре между краями (CLEAR_LETTERS), пара получает подъём."""
    import touch
    import area_refine as AR
    T = touch.Touch(font)
    lefts = [x for g in font if g.unicodes and chr(g.unicodes[0]) in AR.CYR and chr(g.unicodes[0]).islower()
             for x in forms.get(g.name, [g.name])]
    targets = [x for g in font if g.unicodes and chr(g.unicodes[0]) in LIFT_TARGETS for x in forms.get(g.name, [g.name])]
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    def best(a, b, dy, k0):
        k = k0 + 60
        while k > k0 - 200 and T.dist(a, b, k - 5, dy) >= CLEAR_LETTERS:
            k -= 5
        return k
    lifted = {}
    for a in lefts:
        for b in targets:
            k0 = eff(a, b)
            k_flat = best(a, b, 0, k0)
            k_up = best(a, b, LIFT, k0)
            if min(k0, k_flat) - k_up >= LIFT_MIN_GAIN:
                lifted[(a, b)] = (int(k_up), LIFT)
    return lifted


DENSE_CAP = 300       # ед.: глубже пустота не считается
DENSE_PCT = 40        # цель — пустота плотных пар своей группы (процентиль)
DENSE_MAX = 80        # не сближать больше чем на столько


def densify(font, base_pairs, exc, rep_r, rep_l, forms, lifted):
    """Рыхлые пары букв одной письменности (по площади пустоты) подтягиваются к
    DENSE_PCT-процентилю своей группы, но край не ближе CLEAR_LETTERS. Только сближение."""
    import touch
    import area_refine as AR
    T = touch.Touch(font)
    letters = [g.name for g in font if g.unicodes and (chr(g.unicodes[0]) in AR.LAT or chr(g.unicodes[0]) in AR.CYR)]
    ch = {x: chr(font[n].unicodes[0]) for n in letters for x in forms.get(n, [n])}
    allf = list(ch)
    P = AR.profiles(font, allf, render, ASC)
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    def gaps(a, b, k):
        case = AR.case_of(ch[a]) + AR.case_of(ch[b])
        top = 700 if 'U' in case else 560
        ys = P[a]['ys']; band = (ys >= 0) & (ys <= top)
        return case, (P[a]['w'] + k + P[b]['L'] - P[a]['R'])[band]
    def area(g, s=0):
        x = g - s
        return float(np.where(np.isnan(x), DENSE_CAP, np.clip(x, None, DENSE_CAP)).mean())
    same = lambda x, y: (ch[x] in AR.LAT) == (ch[y] in AR.LAT)  # noqa: E731
    vals = {}
    for a in letters:
        for b in letters:
            if same(a, b):
                case, g = gaps(a, b, eff(a, b))
                vals.setdefault(case, []).append(area(g))
    target = {c: float(np.percentile(v, DENSE_PCT)) for c, v in vals.items()}
    def tighten(a, b):
        k = eff(a, b)
        case, g = gaps(a, b, k)
        if area(g) <= target[case] + 2.5:
            return None
        s = 0
        while s < DENSE_MAX and area(g, s) > target[case]:
            s += 5
        while s > 0 and T.dist(a, b, k - s) < CLEAR_LETTERS:
            s -= 5
        return (k, k - s) if s else None
    changed_base = {}
    for a in letters:
        for b in letters:
            if same(a, b) and (a, b) not in lifted:
                r = tighten(a, b)
                if r:
                    base_pairs[(a, b)] = r[1]
                    changed_base[(a, b)] = r
    changed_alt = 0
    for a in allf:
        for b in allf:
            if ('.alt' not in a and '.alt' not in b) or not same(a, b) or (a, b) in lifted:
                continue
            r = tighten(a, b)
            if r:
                group = base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
                if r[1] != group:
                    exc[(a, b)] = r[1]
                else:
                    exc.pop((a, b), None)
                changed_alt += 1
    return changed_base, changed_alt, target


TUCK = 'uni0434'          # «д» с подчёркиванием: оно подныривает под предыдущую букву
TUCK_FLOOR = 25           # ближе не подпускаем (только если налезает)
KEEP_AFTER = ('uni0430', 'uni0434')   # после любой формы «а» — обычная «д» (выбор автора)


def restore_tuck(font, base_pairs, exc, rep_r, rep_l, forms, orig_pairs):
    """Пары «буква + д»: значения 0.5.5 (подчёркивание «д» подныривает), общие проходы
    сближения/зазора их не меняют. Вариант левой буквы, у которого край ближе TUCK_FLOOR,
    раздвигается ровно до него."""
    import touch
    T = touch.Touch(font)
    names = [n for n in font.keys() if n not in ('.notdef', 'space', 'space.narrow')]
    base_of = {x: b for b, fs in forms.items() for x in fs}
    restored = 0
    for a in names:
        ba = base_of.get(a, a)
        if (ba, TUCK) not in orig_pairs:
            continue
        k = orig_pairs[(ba, TUCK)]
        while T.dist(a, TUCK, k) < TUCK_FLOOR and k < orig_pairs[(ba, TUCK)] + 150:
            k += 5
        if '.alt' not in a:
            base_pairs[(a, TUCK)] = k
            exc.pop((a, TUCK), None)
        else:
            exc[(a, TUCK)] = k
        restored += 1
    return restored


R_AFTER_E = 'uni0072.after_e'
JOIN_E = 'uni0065'          # перед r.after_e — только обычная «e»: остальные стыкуются плохо (решение автора, 0.6.3)
JOIN_E_FIRST = ('uni0065.alt2', 'uni0065.alt3')   # «eer»: первая e — вариант (alt2 оставляет меньше всего пустоты перед e; alt3 — если перед ней уже alt2), 0.6.4
JOIN_A = 'uni0061.alt1'     # после r.after_e — a.alt1: меньше всего пустоты под плечом r во всех весах
JOIN_LIFT = LIFT            # и чуть выше, чтобы встать левее (как «л» после хвостика)
LOOPED_U = 'uni0443'        # петлевая у: все её варианты со сканов без петли
OPEN_U = 'uni0443.open'     # открытая у в контекстах чередует себя и четыре варианта без петли, 0.6.4


def join_rules(rot):
    """Замены после Rotate и KeepAfter (отдельный lookup Join): стык e–r–a, петлевая у вне
    контекстов, чередование открытой у. «after» — класс предыдущего (уже обработанного)
    глифа, «before» — классы следующих по порядку. rot — forms, phase, shift, phases."""
    forms = rot['forms']
    e_forms, a_forms = forms[JOIN_E], forms[JOIN_A.split('.alt')[0]]
    first, second = JOIN_E_FIRST
    rules = [{'from': e_forms[1:], 'to': JOIN_E, 'before': [[R_AFTER_E]]},
             # повтор e подряд всегда меняет форму: если перед основной e (перед r) тоже основная — она становится вариантом
             {'from': [JOIN_E], 'to': second, 'after': [first], 'before': [e_forms, [R_AFTER_E]]},
             {'from': [JOIN_E], 'to': first, 'before': [e_forms, [R_AFTER_E]]},
             {'from': [n for n in a_forms if n != JOIN_A], 'to': JOIN_A, 'after': [R_AFTER_E]},
             # вне контекстов открытой у — петлевая у (обещано в README и CONTEXTS); варианты у — без петли, 0.6.4
             {'from': forms[LOOPED_U][1:], 'to': LOOPED_U}]
    # открытая у (после букв из CONTEXTS и после у) чередует пять форм без петли, как остальные буквы:
    # форма — по фазе предыдущего глифа; у формы i фаза i, поэтому соседние у всегда разные
    open_forms = [OPEN_U] + forms[LOOPED_U][1:]
    assert all(rot['phase'][g] == i for i, g in enumerate(open_forms))
    step = rot['shift'][LOOPED_U]
    for k in range(rot['phases']):
        to = open_forms[(k + step) % len(open_forms)]
        if to != OPEN_U:
            rules.append({'from': [OPEN_U], 'to': to, 'after': sorted(g for g, q in rot['phase'].items() if q == k)})
    return rules


def join_fea(rules):
    lines = ['# после чередования: стык e–r–a (перед r.after_e — обычная «e», в «eer» первая — вариант, после — a.alt1; 0.6.3–0.6.4)',
             '# петлевая у вне контекстов открытой, открытая у чередует пять форм (0.6.4)',
             'lookup Join {']
    for r in rules:
        back = f"[{' '.join(r['after'])}] " if 'after' in r else ''
        ahead = ''.join(f" [{' '.join(c)}]" for c in r.get('before', []))
        lines.append(f" sub {back}[{' '.join(r['from'])}]'{ahead} by {r['to']};")
    lines.append('} Join;')
    return '\n'.join(lines)


def rot_spec(spec):
    """Правила выбора форм для tests/alternates-spec.json и модели."""
    return {'phases': spec['phases'], 'phase': spec['phase'], 'forms': spec['forms'], 'shift': spec['shift'],
            'keep_after': [spec['forms'].get(KEEP_AFTER[0], [KEEP_AFTER[0]]), KEEP_AFTER[1]],
            'join': join_rules(spec)}


def join_fit(font, exc, lifted):
    """a.alt1 после r.after_e: подъём JOIN_LIFT и кернинг вплотную до CLEAR_LETTERS —
    пустота под плечом r закрывается. После всех общих проходов, чтобы они пару не меняли."""
    import touch
    T = touch.Touch(font)
    k = 100
    while k > -300 and T.dist(R_AFTER_E, JOIN_A, k - 5, JOIN_LIFT) >= CLEAR_LETTERS:
        k -= 5
    lifted[(R_AFTER_E, JOIN_A)] = (k, JOIN_LIFT)
    exc[(R_AFTER_E, JOIN_A)] = k
    return k


N_TO_M = ('uni006E', 'uni006D')    # все формы n — до высоты m (решение автора 23.10.2026, 0.6.4)


def scale_n(font, forms):
    """Все формы n — до высоты m при прежнем штрихе: масштаб от базовой линии и сдвиг контура
    наружу на (1 − s)·штрих/2, как цифры в 0.6.1; поля сохраняются, кернинг не меняется.
    Форма, уже стоящая на высоте m (±2 ед.), не трогается — повторный запуск ничего не меняет."""
    D = DIGITS
    n, m = N_TO_M
    target = D.bounds(D.ufo_contours(font[m]))[3]
    report = {'target': round(target), 'glyphs': {}}
    for name in forms.get(n, [n]):
        g = font[name]
        c = D.ufo_contours(g)
        x0, _, x1, top = D.bounds(c)
        if abs(top - target) < 2:
            continue
        mask = D.raster(c, g.width)
        w, topo = D.stroke(mask), D.topology(mask)
        s = (target - w / 2) / (top - w / 2)        # s·top + (1 − s)·w/2 = высота m
        t = D.transform(c, s, (s - 1) * w / 2)
        nx0, _, nx1, _ = D.bounds(t)
        adv = g.width
        g.width = int(round(nx1 - nx0 + x0 + (g.width - x1)))
        D.set_ufo_contours(g, t, x0 - nx0)
        after = D.raster(D.ufo_contours(g), g.width)
        assert D.topology(after) == topo, name
        report['glyphs'][name] = {'s': round(s, 4), 'top': [round(top), round(D.bounds(D.ufo_contours(g))[3])],
                                  'stroke': [round(w, 1), round(D.stroke(after), 1)], 'advance': [adv, g.width]}
    return report


LIFT_ALWAYS = 'акцщ'    # обещано в README и CONTEXTS: «л» после любой формы этих букв всегда выше (0.6.4)


def lift_always(font, base_pairs, exc, rep_r, rep_l, forms, lifted):
    """«л» после любой формы а, к, ц, щ: подъём LIFT всегда; кернинг — левее, насколько
    позволяет зазор CLEAR_LETTERS с подъёмом, но не правее прежнего."""
    import touch
    T = touch.Touch(font)
    lefts = [x for g in font if g.unicodes and chr(g.unicodes[0]) in LIFT_ALWAYS for x in forms.get(g.name, [g.name])]
    targets = [x for g in font if g.unicodes and chr(g.unicodes[0]) in LIFT_TARGETS for x in forms.get(g.name, [g.name])]
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    added = 0
    for a in lefts:
        for b in targets:
            if (a, b) in lifted:
                continue
            k0 = eff(a, b)
            k = k0 + 60
            while k > k0 - 200 and T.dist(a, b, k - 5, LIFT) >= CLEAR_LETTERS:
                k -= 5
            lifted[(a, b)] = (int(min(k0, k)), LIFT)
            exc[(a, b)] = int(min(k0, k))
            added += 1
    return added


def final_clearance(font, base_pairs, exc, rep_r, rep_l, lifted, rot, cmap_rev):
    """Последний проход зазора по парам, которые реально встречаются в наборе (модель
    scripts/alternates_model.py), с подъёмом: край не ближе CLEAR_LETTERS (буквы и цифры),
    CLEAR_OTHER (знаки), LAMBDA_FLOOR перед Λ-буквами, TUCK_FLOOR перед «д». Раздвигается
    без ограничения шага — проход 0.6.0 останавливался на +150 ед. Латиница↔кириллица и
    пары табличных цифр между собой не трогаются."""
    import touch
    sys.path.insert(0, str(ROOT / 'scripts'))
    import alternates_model as M
    T = touch.Touch(font)
    cmap = {ord(c): n for n, c in cmap_rev.items()}
    def eff(a, b):
        if (a, b) in exc:
            return exc[(a, b)]
        return base_pairs.get((rep_r.get(a, a), rep_l.get(b, b)), 0)
    def floor(b, ca, cb):
        if b == TUCK:
            return TUCK_FLOOR
        if cb in LAMBDA_FAMILY:
            return LAMBDA_FLOOR
        return CLEAR_LETTERS if ca.isalnum() and cb.isalnum() else CLEAR_OTHER
    fixed = {}
    for a, b in sorted(M.reachable_pairs(cmap, rot)):
        ca, cb = char_of(a, cmap_rev), char_of(b, cmap_rev)
        if not ca or not cb or not ca.strip() or not cb.strip():
            continue
        if ('.tab' in a and '.tab' in b) or (ca in LAT and cb in CYR) or (ca in CYR and cb in LAT):
            continue
        dy = lifted[(a, b)][1] if (a, b) in lifted else 0
        k0 = k = eff(a, b)
        lim = floor(b, ca, cb)
        while T.dist(a, b, k, dy) < lim:
            k += 5
        if k != k0:
            exc[(a, b)] = k
            if (a, b) in lifted:
                lifted[(a, b)] = (k, dy)
            fixed[(a, b)] = (k0, k)
    return fixed


def fix_stray_j_dot(font):
    """У базовой j лишняя точка слева — точка соседней i со скана («ij»). Удаляем контур,
    который целиком левее основной точки и ниже её (в Light/Regular/Semibold он один)."""
    from fontTools.pens.boundsPen import BoundsPen
    g = font['uni006A']
    bb = []
    for c in g.contours:
        p = BoundsPen(None)
        c.draw(p)
        bb.append(p.bounds)
    stray = [i for i, b in enumerate(bb) if b[2] < 200 and b[1] > 500]
    assert len(stray) == 1, bb
    del g.contours[stray[0]]


MANUAL_SPANS = {
    # j: наплыв снизу на изгибе крючка (шире порога полировки)
    'Light': [('uni006A', 1, (329, -418), (230, -428), ())],
    'Regular': [('uni006A', 1, (339, -423), (236, -433), ()),
                # j: «клювик» с загибом на конце крючка → круглый конец, как в Light
                ('uni006A', 1, (31, -316), (108, -303), ((17, -285), (38, -254), (70, -247), (86, -270)))],
    'Semibold': [('uni006A', 1, (368, -430), (254, -445), ())],
}


def manual_spans(font, style):
    import contour_surgery as cs
    for name, ci, a, b, via in MANUAL_SPANS.get(style, []):
        c = font[name].contours[ci]
        cs.apply(c, cs.replace_span(c, a, b, via=via))
    return [m[0] for m in MANUAL_SPANS.get(style, [])]


def refit_j_column(font, base_pairs, names, style, cmap_rev):
    """Пары «X + j» считались по лишней точке — пересчитываем той же формулой v0.4."""
    prof = profiles(font, names + ['uni006A'])
    changed = 0
    for x in names:
        cx = char_of(x, cmap_rev)
        if cx is None:
            continue
        v = int(formula(prof[x], [prof['uni006A']], cx, ['j'], EXTRA[style])[0])
        old = base_pairs.get((x, 'uni006A'), 0)
        if v != old:
            changed += 1
            if v:
                base_pairs[(x, 'uni006A')] = v
            else:
                base_pairs.pop((x, 'uni006A'), None)
    return changed


def refit_digit_pairs(font, base_pairs, names, digits, style, cmap_rev):
    """Пары с цифрами после их увеличения (qa/digits-2026-10-22) — той же формулой v0.4.
    Табличные цифры получают только прежние пары (с открытой «у»), между собой не кернятся."""
    tabs = [d for d in digits if d.endswith('.tab')]
    plain = [d for d in digits if '.alt' not in d and not d.endswith('.tab')]
    others = [n for n in names if not n.endswith('.tab') and char_of(n, cmap_rev)]
    prof = profiles(font, sorted(set(others + tabs)))
    extra = EXTRA[style]
    oc = [char_of(n, cmap_rev) for n in others]
    new = {}
    for d in plain:
        cd = char_of(d, cmap_rev)
        for x, v in zip(others, formula(prof[d], [prof[x] for x in others], cd, oc, extra)):
            new[(d, x)] = int(v)
        for x, cx in zip(others, oc):
            new[(x, d)] = int(formula(prof[x], [prof[d]], cx, [cd], extra)[0])
    for a, b in [p for p in base_pairs if p[0] in tabs or p[1] in tabs]:
        new[(a, b)] = int(formula(prof[a], [prof[b]], char_of(a, cmap_rev), [char_of(b, cmap_rev)], extra)[0])
    changed = 0
    for p, v in new.items():
        changed += base_pairs.get(p, 0) != v
        if v:
            base_pairs[p] = v
        else:
            base_pairs.pop(p, None)
    return changed


def main():
    specs = {}
    digits_report = {}
    smooth_report = {}
    all_polished = {}
    clear_report = {}
    for style in STYLES:
        font = ufoLib2.Font.open(ROOT / f'.orig/ValeraSans-{style}.ufo')
        polished = {}
        vecs = load_vectors(style)
        names = add_glyphs(font, vecs)
        for n in names:
            fx = POLISH.polish(font[n])
            if fx:
                polished[n] = fx
        # упрощение трассированных контуров вариантов (меньше точек, отклонение ≤ 2,5 ед.)
        SIMPLIFY.TOL, SIMPLIFY.MAX_DEV = 1.5, 2.5
        simp = [SIMPLIFY.simplify(font[n], POLISH.topology) for n in names]
        simplified = (sum(s[0] for s in simp), sum(s[1] for s in simp))
        forms = forms_map(font.keys(), names)
        order = list(font.glyphOrder)
        spec = rotation_spec(order, forms)
        groups = {n: [n] for n in order}
        for b, fs in forms.items():
            groups[b] = fs
            for n in fs[1:]:
                groups.pop(n, None)
        old_fea = font.features.text
        base_pairs = parse_pairs(old_fea)
        fix_stray_j_dot(font)
        for g in font:
            if g.name in names:
                continue
            fx = POLISH.polish(g)
            if fx:
                polished[g.name] = fx
        for n in manual_spans(font, style):
            polished.setdefault(n, []).append([0.0, 0.0, 0.0, 'manual'])
        # цифры ≈95% высоты прописных при прежнем штрихе (выбор автора, 0.6.1)
        digit_glyphs, digits_report[style] = DIGITS.scale_ufo(font, style)
        # ровный край штриха: адаптивное сглаживание, углы и топология сохраняются (0.6.2)
        smooth_report[style] = SMOOTH.smooth_ufo(font, DIGITS.flatten, DIGITS.ufo_contours)
        cmap_rev0 = {g.name: chr(g.unicodes[0]) for g in font if g.unicodes}
        base_names = [n for n in order if '.alt' not in n and char_of(n, cmap_rev0)]
        j_changed = refit_j_column(font, base_pairs, base_names, style, cmap_rev0)
        digit_pairs = refit_digit_pairs(font, base_pairs, base_names, digit_glyphs, style, cmap_rev0)
        cmap_rev = {g.name: chr(g.unicodes[0]) for g in font if g.unicodes}
        moves = fit_sidebearings(font, groups, order, style, cmap_rev)
        exc, rep_r, rep_l = kerning(font, base_pairs, groups, order, style, cmap_rev)
        lam = lambda_pairs(font, base_pairs, exc, rep_r, rep_l, spec['forms'], style, cmap_rev)
        clear_base, clear_alt = clearance(font, base_pairs, exc, rep_r, rep_l, order, cmap_rev)
        lifted = lift_pairs(font, base_pairs, exc, rep_r, rep_l, spec['forms'], cmap_rev)
        for (a, b), (k, dy) in lifted.items():
            exc[(a, b)] = k
        dense_base, dense_alt, dense_target = densify(font, base_pairs, exc, rep_r, rep_l, spec['forms'], lifted)
        tuck = restore_tuck(font, base_pairs, exc, rep_r, rep_l, spec['forms'], parse_pairs(old_fea))
        n_lifted = len(lifted)
        n_report = scale_n(font, spec['forms'])
        join_k = join_fit(font, exc, lifted)
        lift_n = lift_always(font, base_pairs, exc, rep_r, rep_l, spec['forms'], lifted)
        cleared = final_clearance(font, base_pairs, exc, rep_r, rep_l, lifted, rot_spec(spec), cmap_rev)
        clear_report[style] = {'base': {f'{a} {b}': v for (a, b), v in clear_base.items()},
                               'alternates': len(clear_alt)}
        font.features.text = build_features(old_fea, spec, base_pairs, exc, rep_r, rep_l, lifted)
        major, minor = json.loads((ROOT / 'font-project.json').read_text())['font_version'].split('.')
        font.info.versionMajor, font.info.versionMinor = int(major), int(minor)
        font.save(ROOT / f'sources/ValeraSans-{style}.ufo', overwrite=True)
        all_polished[style] = {k: [list(map(float, v[:3])) + [v[3]] for v in vals] for k, vals in polished.items()}
        specs[style] = {'lift': [[a, b, dy] for (a, b), (k, dy) in sorted(lifted.items())],
                        'base_pairs': [[a, b, v] for (a, b), v in sorted(base_pairs.items())],
                        'exceptions': [[a, b, v] for (a, b), v in sorted(exc.items())],
                        'right_group': rep_r, 'left_group': rep_l}
        mv = np.array(list(moves.values()))
        print(style, f'точек вариантов {simplified[0]}→{simplified[1]}', '| пар «буква + д» возвращено к 0.5.5:', tuck, '| сближено рыхлых: базовых', len(dense_base), 'с вариантами', dense_alt,
              'цели', {c: round(v) for c, v in dense_target.items()}, '| «л» поднято в парах', n_lifted, '| n до высоты m:', {k: v['top'] for k, v in n_report['glyphs'].items()}, '| a.alt1 после r.after_e: кернинг', join_k, '| «л» после а/к/ц/щ поднято дополнительно', lift_n, '| раздвинуто последним проходом', len(cleared),'| раздвинуто (слипались): базовых', len(clear_base), 'с вариантами', len(clear_alt), '| Λ-пар уплотнено', lam, '| пар «X+j» пересчитано', j_changed, '| цифры: масштаб', digits_report[style]['s'], 'пар пересчитано', digit_pairs,
              '| выровнено глифов', sum(1 for v in smooth_report[style].values() if 'moved' in v), '| глифов', len(order), 'новых', len(names), 'исключений кернинга', len(exc),
              '| сдвиг полей, медиана |лев| |прав|:', round(float(np.median(abs(mv[:, 0])))), round(float(np.median(abs(mv[:, 1])))))
    (HERE / 'clearance-report.json').write_text(json.dumps(clear_report, ensure_ascii=False, indent=0))
    (HERE / 'polish-report.json').write_text(json.dumps(all_polished, ensure_ascii=False, indent=0))
    (ROOT / 'qa/digits-2026-10-22/digits-report.json').write_text(json.dumps(digits_report, ensure_ascii=False, indent=1))
    (ROOT / 'qa/smooth-2026-10-22/smooth-report.json').write_text(json.dumps(smooth_report, ensure_ascii=False, indent=0))
    (ROOT / 'tests/alternates-spec.json').write_text(json.dumps({'rotation': rot_spec(spec), 'kerning': specs},
                                                               ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
