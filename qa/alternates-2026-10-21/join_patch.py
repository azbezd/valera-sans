"""Стык e–r–a (0.6.3) без полного прогона integrate.py.

Контуры и прочий кернинг не меняются, поэтому к готовым sources/*.ufo и
tests/alternates-spec.json дописывается ровно то, что добавил бы integrate.py:
lookup Join, пара-исключение r.after_e + a.alt1 и её подъём в lookup Lift.
Значения считаются теми же функциями integrate.py (join_rules, join_fea, join_fit).
Блоки исключений и подъёма пересобираются; перед правкой проверяется, что
пересборка без изменений даёт исходный текст байт в байт.
"""
import json
import re
import sys
from pathlib import Path

import ufoLib2

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import integrate as I  # noqa: E402

EXC_HEAD = '# исключения (пары глифов) — применяются раньше групп\n'
GROUP_HEAD = '# группы: утверждённые пары 0.5.5; вариант входит в группу базовой буквы по профилю\n'
LIFT_OLD = '# «л» после строчной: левее (кернинг выше) и чуть выше (подъём)\n'
LIFT_NEW = '# «л» после строчной и a.alt1 после r.after_e: левее (кернинг выше) и чуть выше (подъём)\n'


def exc_block(exc):
    return ''.join(f'pos {a} {b} {v};\n' for (a, b), v in sorted(exc.items()))


def lift_block(lifted):
    by_target = {}
    for (a, b), dy in sorted(lifted.items()):
        by_target.setdefault((b, dy), []).append(a)
    return 'lookup Lift {\n' + ''.join(f" pos [{' '.join(lefts)}] {b}' <0 {dy} 0 0>;\n"
                                       for (b, dy), lefts in sorted(by_target.items())) + '} Lift;\n'


def patch_fea(fea, rules, k):
    assert 'lookup Join' not in fea, 'уже есть'
    # calt: Join после KeepAfter
    fea = fea.replace('} KeepAfter;\nfeature calt {', '} KeepAfter;\n' + I.join_fea(rules) + '\nfeature calt {', 1)
    fea = fea.replace(' lookup KeepAfter;\n} calt;', ' lookup KeepAfter;\n lookup Join;\n} calt;', 1)
    # исключения кернинга
    i0 = fea.index(EXC_HEAD) + len(EXC_HEAD)
    i1 = fea.index(GROUP_HEAD)
    exc = {(a, b): int(v) for a, b, v in re.findall(r'^pos (\S+) (\S+) (-?\d+);$', fea[i0:i1], re.M)}
    assert exc_block(exc) == fea[i0:i1]
    exc[(I.R_AFTER_E, I.JOIN_A)] = k
    fea = fea[:i0] + exc_block(exc) + fea[i1:]
    # подъём
    j0 = fea.index(LIFT_OLD)
    j1 = fea.index('} Lift;\n') + len('} Lift;\n')
    lifted = {}
    for lefts, b, dy in re.findall(r"^ pos \[([^\]]+)\] (\S+)' <0 (-?\d+) 0 0>;$", fea[j0:j1], re.M):
        for a in lefts.split():
            lifted[(a, b)] = int(dy)
    assert LIFT_OLD + lift_block(lifted) == fea[j0:j1]
    lifted[(I.R_AFTER_E, I.JOIN_A)] = I.JOIN_LIFT
    return fea[:j0] + LIFT_NEW + lift_block(lifted) + fea[j1:]


def main():
    spec_path = ROOT / 'tests/alternates-spec.json'
    spec = json.loads(spec_path.read_text())
    rules = I.join_rules(spec['rotation']['forms'])
    spec['rotation']['join'] = rules
    major, minor = json.loads((ROOT / 'font-project.json').read_text())['font_version'].split('.')
    for style in I.STYLES:
        path = ROOT / f'sources/ValeraSans-{style}.ufo'
        font = ufoLib2.Font.open(path)
        exc, lifted = {}, {}
        k = I.join_fit(font, exc, lifted)
        fea_path = path / 'features.fea'
        fea_path.write_text(patch_fea(fea_path.read_text(), rules, k))
        info = path / 'fontinfo.plist'
        text = re.sub(r'(<key>versionMajor</key>\s*<integer>)\d+', rf'\g<1>{int(major)}', info.read_text())
        info.write_text(re.sub(r'(<key>versionMinor</key>\s*<integer>)\d+', rf'\g<1>{int(minor)}', text))
        ks = spec['kerning'][style]
        e = {(a, b): v for a, b, v in ks['exceptions']}
        e[(I.R_AFTER_E, I.JOIN_A)] = k
        ks['exceptions'] = [[a, b, v] for (a, b), v in sorted(e.items())]
        lf = {(a, b): dy for a, b, dy in ks['lift']}
        lf[(I.R_AFTER_E, I.JOIN_A)] = I.JOIN_LIFT
        ks['lift'] = [[a, b, dy] for (a, b), dy in sorted(lf.items())]
        print(style, 'a.alt1 после r.after_e: кернинг', k, 'подъём', I.JOIN_LIFT)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
