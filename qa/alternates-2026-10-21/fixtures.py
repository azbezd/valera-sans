"""Тестовые таблицы после встраивания вариантов.

Значения пар и ширины строк берутся из модели (scripts/alternates_model.py по
tests/alternates-spec.json), а не из собранного шрифта. Из сборки берётся только
геометрия новых и изменённых глифов для эталона контуров — её утверждает автор
по пробным листам.
"""
import json
import sys
from pathlib import Path

import ufoLib2
from fontTools.ttLib import TTFont

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from alternates_model import expected_names, Kerning, SPEC  # noqa: E402

STYLES = ['Light', 'Regular', 'Semibold']
BASE_TAG = 'df51644'   # эталон после правки капель — с него стартует integrate (.orig)
CHANGED_BASE = {'uni006A'}          # убрана лишняя точка (i со скана)
POLISHED = json.loads((Path(__file__).parent / 'polish-report.json').read_text())  # отполированные глифы
NEW_ENCODED = {'uni00B0': 0xB0}


def main():
    # основа — эталон коммита с правкой капель: повторный запуск даёт тот же результат
    import subprocess
    approved = json.loads(subprocess.run(['git', 'show', f'{BASE_TAG}:tests/approved-v0.5.3.json'], cwd=ROOT,
                                         capture_output=True, text=True, check=True).stdout)
    browser = json.loads((ROOT / 'tests/browser-expected.json').read_text())
    new_names = set()
    for fs in SPEC['rotation']['forms'].values():
        new_names.update(fs[1:])
    new_names.update(NEW_ENCODED)
    for style in STYLES:
        tt = TTFont(ROOT / f'fonts/ttf/ValeraSans-{style}.ttf')
        glyf, hmtx = tt['glyf'], tt['hmtx']
        ufo = ufoLib2.Font.open(ROOT / f'sources/ValeraSans-{style}.ufo')
        adv = {g.name: g.width for g in ufo}
        rec = approved[style]
        for name in tt.getGlyphOrder():
            coords, ends, flags = glyf[name].getCoordinates(glyf)
            entry = {'coords': [list(p) for p in coords], 'ends': list(ends), 'flags': list(flags), 'metrics': list(hmtx[name])}
            changed = CHANGED_BASE | set(POLISHED.get(style, {}))
            if name in rec['glyphs'] and name not in changed:
                old = rec['glyphs'][name]
                assert old['coords'] == entry['coords'] and old['metrics'] == entry['metrics'], (style, name, 'неожиданное изменение')
                continue
            assert name in new_names or name in changed, (style, name)
            rec['glyphs'][name] = {k: entry[k] for k in old_keys(rec)}
        for name, cp in NEW_ENCODED.items():
            rec['cmap'][str(cp)] = name
        rec['source'] += ('; alternates-2026-10-21: 348 scan alternates, degree sign, stray dot removed from j, '
                          'drips/spikes/dents polished (qa/contour-cleanup-2026-10-21)')
        cmap = {int(k): v for k, v in rec['cmap'].items()}
        chars = ''.join(chr(c) for c in sorted(cmap))
        kern = Kerning(style)

        def adjustment(text, calt, tab=False):
            n = expected_names(text, cmap, calt, tab)
            return sum(kern(a, b) for a, b in zip(n, n[1:]))

        rows = json.loads((ROOT / f'tests/glyph-pairs-{style}.json').read_text())
        for r in rows:
            r['adjustment'] = kern(r['left'], r['right'])
        (ROOT / f'tests/glyph-pairs-{style}.json').write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
        for fname, calt in [('pairs', True), ('base-pairs', False)]:
            out = {a + b: {'adjustment': adjustment(a + b, calt)} for a in chars for b in chars}
            (ROOT / f'tests/{fname}-{style}.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
        digits = '0123456789'
        tab = {a + b: {'adjustment': adjustment(a + b, True, True)} for a in chars for b in chars if a in digits or b in digits}
        (ROOT / f'tests/tabular-pairs-{style}.json').write_text(json.dumps(tab, ensure_ascii=False, separators=(',', ':')))
        for case in browser[style]:
            n = expected_names(case['text'], cmap, case['calt'])
            w = sum(adv[x] for x in n) + (sum(kern(a, b) for a, b in zip(n, n[1:])) if case['kern'] else 0)
            case['width_units'] = w
        print(style, 'глифов в эталоне', len(rec['glyphs']), 'знаков', len(chars), 'пар', len(chars) ** 2, 'табличных', len(tab))
    (ROOT / 'tests/approved-v0.5.3.json').write_text(json.dumps(approved, separators=(',', ':')) + '\n')
    (ROOT / 'tests/browser-expected.json').write_text(json.dumps(browser, ensure_ascii=False, separators=(',', ':')) + '\n')


def old_keys(rec):
    return list(next(iter(rec['glyphs'].values())).keys())


if __name__ == '__main__':
    main()
