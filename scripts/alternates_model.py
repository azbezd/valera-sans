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


def rotate(names):
    out = list(names)
    for i in range(1, len(out)):
        g = out[i]
        if g in ROT['shift']:
            forms = ROT['forms'][g]
            k = ROT['phase'][out[i - 1]]
            out[i] = forms[(k + ROT['shift'][g]) % len(forms)]
    return out


def keep_after(names):
    """После любой формы левой буквы — базовая форма целевой (отдельный lookup после Rotate)."""
    rule = ROT.get('keep_after')
    if not rule:
        return names
    lefts, target = set(rule[0]), rule[1]
    out = list(names)
    for i in range(1, len(out)):
        if out[i - 1] in lefts and out[i].split('.alt')[0] == target:
            out[i] = target
    return out


def join(names):
    """Стык e–r–a (lookup Join после KeepAfter): форма по соседнему глифу — «before»
    смотрит на следующий, «after» на предыдущий; на позиции срабатывает первое правило."""
    rules = ROT.get('join', [])
    out = list(names)
    for i, g in enumerate(out):
        for r in rules:
            if g not in r['from']:
                continue
            if ('before' in r and i + 1 < len(out) and out[i + 1] == r['before']) or \
                    ('after' in r and i > 0 and out[i - 1] == r['after']):
                out[i] = r['to']
                break
    return out


def expected_names(text, cmap, calt=True, tab=False):
    names = base_names(text, cmap, calt)
    if calt:
        names = join(keep_after(rotate(names)))
    if tab:
        names = [n.split('.alt')[0] + '.tab' if n.split('.alt')[0] in DIGITS else n for n in names]
    return names


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
