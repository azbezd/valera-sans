"""Слова «было | стало» двумя шрифтами: compare_words.py before.ttf after.ttf out.png"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from kernvariants import draw, LABEL  # noqa: E402

LINES = [
    'Валера сало малой вла плавал пол',
    'Алла ДА АА Гц тд вдали Жди ИЛ КЛ',
    'al all Hello lazy fox ladder',
    'цифры 1+1=2 (ц) ц! ц? «да» — ну',
]


def main(before, after, out):
    rows = []
    for text in LINES:
        for label, path in (('было', before), ('стало', after)):
            r = draw(Path(path), text, 0, set())
            lab = Image.new('RGB', (r.width, 36), (40, 40, 40))
            ImageDraw.Draw(lab).text((10, 4), label, fill=(220, 220, 220), font=LABEL)
            rows += [lab, r]
    W = max(r.width for r in rows)
    img = Image.new('RGB', (W, sum(r.height for r in rows)), (17, 17, 17))
    y = 0
    for r in rows:
        img.paste(r, (0, y)); y += r.height
    img.save(out)
    print(out, img.size)


if __name__ == '__main__':
    main(*sys.argv[1:])
