"""Ожидаемое поведение шрифта по спецификации tests/alternates-spec.json.

Независимая от собранного файла модель: какие глифы выберет набор (контекстные r/у,
затем чередование вариантов, стык e–r–a, затем tnum) и какой кернинг между ними. validate.py
сверяет с ней HarfBuzz, а тестовые таблицы пар строятся из неё же, не из сборки.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / 'tests/alternates-spec.json').read_text())
U_CONTEXT = json.loads((ROOT / 'tests/approved-spacing-v0.5.5.json').read_text())['context']
ROT = SPEC['rotation']
DIGITS = {f'uni003{d}' for d in '0123456789'}


def base_names(text, cmap, calt):
    """Контекстный lookup (как в 0.5.5): r после e, открытая у после контекстных букв."""
    out = []
    for i, c in enumerate(text):
        if calt and c == 'r' and i > 0 and text[i - 1] == 'e':
            out.append('uni0072.after_e')
        elif calt and c == 'у' and i > 0 and text[i - 1] in U_CONTEXT:
            out.append('uni0443.open')
        else:
            out.append(cmap[ord(c)])
    return out


def rotate(names, rot=None):
    """Чередование; «д» сразу после любой формы «а» не чередуется (ignore в lookup Rotate)."""
    rot = rot or ROT
    keep = rot.get('keep_after')
    lefts, target = (set(keep[0]), keep[1]) if keep else (set(), None)
    out = list(names)
    for i in range(1, len(out)):
        g = out[i]
        if g == target and out[i - 1] in lefts:
            continue
        if g in rot['shift']:
            forms = rot['forms'][g]
            k = rot['phase'][out[i - 1]]
            out[i] = forms[(k + rot['shift'][g]) % len(forms)]
    return out


def keep_after(names, rot=None):
    """После любой формы левой буквы — базовая форма целевой (отдельный lookup после Rotate)."""
    rule = (rot or ROT).get('keep_after')
    if not rule:
        return names
    lefts, target = set(rule[0]), rule[1]
    out = list(names)
    for i in range(1, len(out)):
        if out[i - 1] in lefts and out[i].split('.alt')[0] == target:
            out[i] = target
    return out


def join(names, rot=None):
    """Стык e–r–a (lookup Join после KeepAfter). Правило: глиф из «from» становится «to»,
    если предыдущий (уже обработанный) глиф входит в «after», а следующие (ещё не
    обработанные) — по порядку в классы «before»; на позиции срабатывает первое правило."""
    rules = _join_sets(rot or ROT)
    out = list(names)
    for i, g in enumerate(out):
        for src, to, after, ahead in rules:
            if g not in src:
                continue
            if after is not None and not (i > 0 and out[i - 1] in after):
                continue
            if any(i + 1 + j >= len(out) or out[i + 1 + j] not in cls for j, cls in enumerate(ahead)):
                continue
            out[i] = to
            break
    return out


_JOIN_CACHE = {}


def _join_sets(rot):
    key = id(rot)
    if key not in _JOIN_CACHE:
        _JOIN_CACHE[key] = (rot, [(set(r['from']), r['to'], set(r['after']) if 'after' in r else None,
                                   [set(c) for c in r.get('before', [])]) for r in rot.get('join', [])])
    return _JOIN_CACHE[key][1]


def expected_names(text, cmap, calt=True, tab=False, rot=None):
    names = base_names(text, cmap, calt)
    if calt:
        names = join(keep_after(rotate(names, rot), rot), rot)
    if tab:
        names = [n.split('.alt')[0] + '.tab' if n.split('.alt')[0] in DIGITS else n for n in names]
    return names


def reachable_pairs(cmap, rot=None):
    """Пары соседних глифов, которые встречаются в наборе (calt вкл., tnum вкл./выкл.):
    {(левый, правый): пример строки}. Форма глифа зависит от соседей, поэтому перебираются
    все тройки знаков (пара — второй и третий), плюс «XYer» и «Xeer» для правил Join,
    которые смотрят на два глифа вперёд."""
    chars = [chr(c) for c in sorted(cmap) if chr(c).strip()]
    out = {}
    def add(s, i, tab=False):
        n = expected_names(s, cmap, True, tab, rot)
        out.setdefault((n[i], n[i + 1]), s)
    for x in chars:
        for y in chars:
            add(x + y + 'er', 1)
            for z in chars:
                add(x + y + z, 1)
                if y.isdigit() or z.isdigit():
                    add(x + y + z, 1, tab=True)
        add(x + 'eer', 1)
    return out


class Kerning:
    def __init__(self, style):
        k = SPEC['kerning'][style]
        self.base = {(a, b): v for a, b, v in k['base_pairs']}
        self.exc = {(a, b): v for a, b, v in k['exceptions']}
        self.right = k['right_group']
        self.left = k['left_group']
        self.lift = {(a, b): dy for a, b, dy in k.get('lift', [])}

    def y_offsets(self, names):
        """Вертикальный сдвиг каждого глифа: вторая буква поднятой пары."""
        return [0] + [self.lift.get(p, 0) for p in zip(names, names[1:])]

    def __call__(self, a, b):
        if (a, b) in self.exc:
            return self.exc[(a, b)]
        return self.base.get((self.right.get(a, a), self.left.get(b, b)), 0)
