"""Поздние шаги integrate.py (13–15) на готовых мастерах, без полного прогона.

Кернинг общих проходов не пересчитывается, поэтому к sources/*.ufo и tests/alternates-spec.json
дописывается ровно то, что дали бы эти шаги integrate.py, теми же функциями:
12б. шаг чередования взаимно прост с числом форм (coprime_shift, блок Rotate заново), с 0.6.4;
13. стык e–r–a (lookup Join: join_rules, join_fea) и a.alt1 после r.after_e (join_fit), с 0.6.3;
    петлевая у вне контекстов открытой и чередование открытой у (тот же lookup), с 0.6.4;
13б. все формы n до высоты m при прежнем штрихе и полях (scale_n), с 0.6.4 — единственный шаг, меняющий контуры;
14. «л» после любой формы а, к, ц, щ всегда выше (lift_always), с 0.6.4;
15. последний проход зазора по парам, которые встречаются в наборе (final_clearance), с 0.6.4.
Блоки исключений и подъёма пересобираются; перед правкой проверяется, что пересборка
без изменений даёт исходный текст байт в байт. Повторный запуск ничего не меняет.
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


def split(fea):
    """Позиции блоков исключений и подъёма; разбор с проверкой обратной сборки."""
    i0 = fea.index(EXC_HEAD) + len(EXC_HEAD)
    i1 = fea.index(GROUP_HEAD)
    exc = {(a, b): int(v) for a, b, v in re.findall(r'^pos (\S+) (\S+) (-?\d+);$', fea[i0:i1], re.M)}
    assert exc_block(exc) == fea[i0:i1]
    head = LIFT_NEW if LIFT_NEW in fea else LIFT_OLD
    j0 = fea.index(head)
    j1 = fea.index('} Lift;\n') + len('} Lift;\n')
    lifted = {}
    for lefts, b, dy in re.findall(r"^ pos \[([^\]]+)\] (\S+)' <0 (-?\d+) 0 0>;$", fea[j0:j1], re.M):
        for a in lefts.split():
            lifted[(a, b)] = int(dy)
    assert head + lift_block(lifted) == fea[j0:j1]
    return (i0, i1, exc), (j0, j1, lifted)


ROT_HEAD = '# Чередование вариантов: см. qa/alternates-2026-10-21/integrate.py\n'
KEEP_HEAD = '\n\n# после любой формы «а» — обычная «д»'


def set_rotation(fea, rot):
    a = fea.index(ROT_HEAD) + len(ROT_HEAD)
    b = fea.index(KEEP_HEAD)
    return fea[:a] + I.rotation_fea(rot) + fea[b:]


def set_join(fea, rules):
    block = I.join_fea(rules) + '\n'
    if 'lookup Join {' in fea:
        a = fea.index('# после чередования') if '# после чередования' in fea else fea.index('# стык e–r–a')
        b = fea.index('} Join;\n') + len('} Join;\n')
        return fea[:a] + block + fea[b:]
    fea = fea.replace('} KeepAfter;\nfeature calt {', '} KeepAfter;\n' + block + 'feature calt {', 1)
    return fea.replace(' lookup KeepAfter;\n} calt;', ' lookup KeepAfter;\n lookup Join;\n} calt;', 1)


def patch_style(style, spec):
    """Одно начертание: правит features.fea и fontinfo.plist, возвращает данные для спецификации."""
    rot = spec['rotation']
    major, minor = json.loads((ROOT / 'font-project.json').read_text())['font_version'].split('.')
    path = ROOT / f'sources/ValeraSans-{style}.ufo'
    font = ufoLib2.Font.open(path)
    n_report = I.scale_n(font, rot['forms'])
    if n_report['glyphs']:
        font.save(path, overwrite=True)          # меняются только глифы n (features.fea и fontinfo — те же)
    ks = spec['kerning'][style]
    base_pairs = {(a, b): v for a, b, v in ks['base_pairs']}
    rep_r, rep_l = ks['right_group'], ks['left_group']
    fea_path = path / 'features.fea'
    fea = set_rotation(fea_path.read_text(), rot)
    fea = set_join(fea, rot['join'])
    (i0, i1, exc), (j0, j1, lift_dy) = split(fea)
    assert exc == {(a, b): v for a, b, v in ks['exceptions']}, 'fea и спецификация расходятся'
    lifted = {p: (exc[p], dy) for p, dy in lift_dy.items()}
    cmap_rev = {g.name: chr(g.unicodes[0]) for g in font if g.unicodes}
    join_k = I.join_fit(font, exc, lifted)
    lift_n = I.lift_always(font, base_pairs, exc, rep_r, rep_l, rot['forms'], lifted)
    cleared = I.final_clearance(font, base_pairs, exc, rep_r, rep_l, lifted, rot, cmap_rev)
    fea = fea[:i0] + exc_block(exc) + fea[i1:j0] + LIFT_NEW + lift_block({p: dy for p, (k, dy) in lifted.items()}) + fea[j1:]
    fea_path.write_text(fea)
    info = path / 'fontinfo.plist'
    text = re.sub(r'(<key>versionMajor</key>\s*<integer>)\d+', rf'\g<1>{int(major)}', info.read_text())
    info.write_text(re.sub(r'(<key>versionMinor</key>\s*<integer>)\d+', rf'\g<1>{int(minor)}', text))
    report = (f'{style} | n до высоты m: {n_report} | a.alt1 после r.after_e: кернинг {join_k} | «л» поднято дополнительно {lift_n} '
              f'| раздвинуто последним проходом {len(cleared)} | исключений {len(exc)}')
    return (style, [[a, b, v] for (a, b), v in sorted(exc.items())],
            [[a, b, dy] for (a, b), (k, dy) in sorted(lifted.items())], report)


def main():
    import multiprocessing
    spec_path = ROOT / 'tests/alternates-spec.json'
    spec = json.loads(spec_path.read_text())
    rot = spec['rotation']
    rot['shift'] = {b: I.coprime_shift(b, len(fs)) for b, fs in rot['forms'].items() if len(fs) > 1}
    rot['join'] = I.join_rules(rot)
    # начертания независимы — считаются параллельно (fork: модули уже загружены)
    with multiprocessing.get_context('fork').Pool(len(I.STYLES)) as pool:
        results = pool.starmap(patch_style, [(style, spec) for style in I.STYLES])
    for style, exceptions, lift, report in results:
        spec['kerning'][style]['exceptions'] = exceptions
        spec['kerning'][style]['lift'] = lift
        print(report)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
